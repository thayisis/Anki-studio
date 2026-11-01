"""iPad-friendly review of coordinate-preserving conversion and explicit partial export."""

import base64
import copy
import hashlib
import html
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from engine import (
    crop,
    parse_pdf,
    preview_html,
    render_blocks,
    restore_source_title,
    update_edited_levels,
)
from exporter import build_apkg, export_plan, export_reason, source_bundle, fields_for
from exporter import cloze_numbers
from cloze_preview import preview_cloze

st.set_page_config(page_title="Anki Studio", page_icon="📚", layout="wide")
st.title("📚 Anki Studio")
st.caption("PDF → cartes vérifiées → Anki. Le document source reste la référence.")
uploaded = st.file_uploader("Importer un PDF balisé CARTE", type=["pdf"])
if uploaded is None:
    st.stop()
data = uploaded.getvalue()
digest = hashlib.sha256(data).hexdigest()
if st.session_state.get("digest") != digest:
    try:
        with st.spinner("Extraction des textes, positions et images…"):
            cards = parse_pdf(data)
    except Exception as error:
        st.error(f"Lecture du PDF impossible : {error}")
        st.stop()
    st.session_state.update(
        digest=digest,
        cards=cards,
        edits={},
        validated=set(),
        revisions={},
        apkg=None,
        bundle=None,
    )
cards = [st.session_state.edits.get(i, c) for i, c in enumerate(st.session_state.cards)]
validated = st.session_state.validated
if not cards:
    st.warning(
        "Aucun marqueur textuel détecté. Un PDF scanné nécessite une reconnaissance de texte "
        "(OCR), non disponible ici. Aucun contenu n’a été converti."
    )
    st.download_button(
        "Conserver le PDF source", data, file_name="source.pdf", mime="application/pdf"
    )
    st.stop()
counts = {
    k: sum(c["type"] == k for c in cards)
    for k in ("CARTE", "CARTE CLOZE", "CARTE OCCLUSION")
}
st.write(
    f"**{len(cards)} marqueurs / notes détectés** · {counts['CARTE']} Basic · "
    f"{counts['CARTE CLOZE']} Cloze · {counts['CARTE OCCLUSION']} Occlusion"
)
st.info(
    "Comparez chaque carte au PDF avant validation. Les lignes et retraits sont conservés ; "
    "les titres incertains sont signalés. Une image ou une zone ambiguë n’est pas une carte perdue."
)
index = st.selectbox(
    "Choisir une carte",
    range(len(cards)),
    format_func=lambda i, reviewed=frozenset(validated): (
        f"{'✓ ' if i in reviewed else ''}{i + 1}. "
        f"{' — '.join(cards[i]['context'] + [cards[i]['title']])[:90] or '[Titre à renseigner]'}"
    ),
    key=f"select_{digest}",
)
card = cards[index]
revision = st.session_state.revisions.get(index, 0)
prefix = f"{digest}_{index}_{revision}"
zoom = st.slider("Zoom du PDF original", 1.0, 4.0, 2.0, 0.25)
side = st.radio("Aperçu", ["Verso", "Recto"], horizontal=True)
layout = st.radio("Disposition", ["Côte à côte", "Verticale"], horizontal=True)
left, right = (
    st.columns(2) if layout == "Côte à côte" else (st.container(), st.container())
)
with left:
    st.subheader("PDF original")
    region = st.selectbox(
        "Page de cette carte",
        range(len(card["regions"])),
        format_func=lambda r: f"Page {card['regions'][r]['page'] + 1}",
        key="region_" + prefix,
    )
    try:
        image = crop(data, card, zoom, region)
        encoded = base64.b64encode(image).decode()
        components.html(
            '<div style="height:600px;overflow:auto"><img alt="Zone du PDF" '
            f'src="data:image/png;base64,{encoded}" style="max-width:none"></div>',
            height=620,
            scrolling=True,
        )
    except Exception as error:
        st.error(f"Aperçu du PDF impossible : {error}")
with right:
    st.subheader("Carte Anki")
    content = (
        card["front"]
        if side == "Recto"
        else preview_html(render_blocks(card["blocks"]), card["media"])
    )
    if card["type"] == "CARTE CLOZE":
        numbers = sorted(cloze_numbers(fields_for(card)[0]))
        active = (
            st.selectbox("Suppression Cloze", numbers, key="cloze_" + prefix)
            if len(numbers) > 1
            else numbers[0]
            if numbers
            else 1
        )
        content = preview_cloze(
            preview_html(fields_for(card)[0], card["media"]),
            answer=side == "Verso",
            active_number=active,
        )
    components.html(
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<div style="font:18px/1.5 sans-serif;white-space:pre-wrap;overflow-wrap:anywhere">'
        + content
        + "</div>",
        height=620,
        scrolling=True,
    )
for warning in card["warnings"]:
    st.warning(warning)

with st.expander("Corriger le titre, le texte et les retraits", expanded=False):
    st.caption(
        "Pas de HTML : chaque ligne reste à sa place. Un retrait est mesuré en points PDF. "
        "Les images restent dans l’ordre des lignes. Les changements annulent la validation."
    )
    with st.form("editor_" + prefix):
        title = st.text_area("Titre exact", value=card["title"], key="title_" + prefix)
        context = st.text_area(
            "Sections parentes confirmées (une par ligne)",
            value="\n".join(card["context"]),
            key="context_" + prefix,
        )
        restore_title = st.checkbox(
            "Replacer aussi le titre source au début du verso",
            key="restore_" + prefix,
            disabled=card.get("source_title_restored", False),
        )
        rows = [
            {
                "Élément": "Image" if b["kind"] == "image" else "Texte",
                "Texte": b.get("text", ""),
                "Retrait": float(b.get("indent", 0)),
                "Puce": bool(b.get("bullet", False)),
                "Média": b.get("media_name", ""),
            }
            for b in card["blocks"]
        ]
        edited = (
            st.data_editor(
                rows,
                num_rows="fixed",
                hide_index=True,
                disabled=["Élément", "Média"],
                use_container_width=True,
                key="rows_" + prefix,
                column_config={
                    "Retrait": st.column_config.NumberColumn(
                        min_value=0, max_value=10000, step=1
                    )
                },
            )
            if rows
            else []
        )
        st.caption(
            "Cloze : écrire {{c1::mot à masquer}}, {{c2::autre mot}} dans le titre ou le texte. "
            "Aucune suppression n’est inventée depuis le simple marqueur CARTE CLOZE."
        )
        saved = st.form_submit_button("Enregistrer les corrections")
    if saved:
        try:
            if not title.strip():
                raise ValueError("Renseignez un titre.")
            updated = copy.deepcopy(card)
            updated.update(
                title=title,
                context=[line for line in context.splitlines() if line.strip()],
            )
            updated["title_html"] = (
                card.get("title_html", html.escape(title))
                if title == card["title"]
                else html.escape(title)
            )
            updated["front"] = (
                html.escape(" — ".join(updated["context"])) + " — "
                if updated["context"]
                else ""
            ) + updated["title_html"]
            for block, row in zip(updated["blocks"], edited):
                block["indent"] = float(row["Retrait"])
                if block["kind"] == "text":
                    block["text"] = row["Texte"] or ""
                    block["bullet"] = bool(row["Puce"])
                    if block["bullet"] and not block.get("bullet_text"):
                        block["bullet_text"] = "•"
            if restore_title:
                restore_source_title(updated, st.session_state.cards[index]["title"])
            updated["levels"] = update_edited_levels(updated["blocks"])
            updated["back"] = render_blocks(updated["blocks"])
            if (
                updated.get("proposed_deletion")
                and "{{c1::" + updated["proposed_deletion"] + "}}"
                not in updated["back"]
            ):
                updated["warnings"] = [
                    w
                    for w in updated["warnings"]
                    if not w.startswith("Cible Cloze proposée")
                ]
                updated.pop("proposed_deletion", None)
            st.session_state.edits[index] = updated
            st.session_state.revisions[index] = revision + 1
            validated.discard(index)
            st.session_state.apkg = None
            st.session_state.bundle = None
            st.rerun()
        except (ValueError, TypeError) as error:
            st.error(str(error))

current_issue = export_reason(card)
if current_issue:
    st.info(current_issue)
st.subheader("Contrôle de fidélité")
checked = st.checkbox(
    "J’ai comparé le titre, chaque ligne, les retraits, les images et leur ordre avec le PDF.",
    value=index in validated,
    key="verified_" + prefix,
)
if checked:
    validated.add(index)
else:
    validated.discard(index)
# Rebuild on each validation change so old downloads cannot expose stale selections.
plan = export_plan(cards, validated)
selection = (tuple(plan["included"]), tuple(sorted(validated)))
if st.session_state.get("export_selection") != selection:
    st.session_state.apkg = None
    st.session_state.bundle = None
    st.session_state.export_selection = selection
st.write(f"{len(validated)} / {len(cards)} notes vérifiées.")
st.subheader("Exporter vers Anki")
st.write(
    f"**{plan['notes']} notes incluses → {plan['cards']} cartes Anki** · "
    f"{len(plan['excluded'])} exclues · {plan['awaiting']} en attente de validation (parmi les exclues)"
)
if plan["excluded"]:
    st.dataframe(
        [
            {"Carte": e["index"] + 1, "Type": e["type"], "Motif": e["reason"]}
            for e in plan["excluded"]
        ],
        hide_index=True,
        use_container_width=True,
    )
st.caption(
    "Export partiel : seules les notes validées et compatibles sont incluses. "
    "Une note Cloze peut produire plusieurs cartes. Les cartes Occlusion restent dans le dossier source ; "
    "leur export natif et l’éditeur de masques ne sont pas encore intégrés."
)
if st.button("Préparer le paquet .apkg", disabled=not plan["included"]):
    try:
        payload, report = build_apkg(cards, validated, Path(uploaded.name).stem, digest)
        st.session_state.apkg = payload
        st.success(
            f"Archive vérifiée : {report['notes']} notes, {report['cards']} cartes et médias contrôlés."
        )
    except Exception as error:
        st.error(f"Export impossible : {error}")
if st.session_state.apkg:
    st.download_button(
        "Télécharger le paquet Anki",
        st.session_state.apkg,
        file_name="anki_studio.apkg",
        mime="application/octet-stream",
    )
if st.button("Préparer le dossier source complet (.zip)"):
    try:
        with st.spinner("Conservation du PDF, des cartes et des médias…"):
            st.session_state.bundle = source_bundle(data, cards, validated)
    except Exception as error:
        st.error(f"Dossier source impossible : {error}")
if st.session_state.bundle:
    st.download_button(
        "Télécharger toutes les sources (ZIP, pas un paquet Anki)",
        st.session_state.bundle,
        file_name="anki_studio_sources.zip",
        mime="application/zip",
    )
st.caption(
    "Le dossier source contient le PDF original, toutes les notes, les images et les zones PDF. "
    "Pour une Occlusion native, créer les masques dans un client Anki compatible ; "
    "cette étape dépend du client et n’est pas automatisée dans Safari."
)
