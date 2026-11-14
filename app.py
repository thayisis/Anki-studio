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
    update_edited_levels,
)
from exporter import build_apkg, export_plan, export_reason, source_bundle, fields_for
from exporter import cloze_numbers
from cloze_preview import preview_cloze
from manual_workflow import (
    make_request,
    chatgpt_prompt,
    apply_corrections,
    canonical,
    move_source_title,
)
from project import save_project, load_project
from occlusion import (
    apply_editor_event,
    groups,
    fingerprint,
    review_group,
    ready_to_confirm,
    confirm_note,
    invalidate,
)
from occlusion_component import editor as occlusion_editor

st.set_page_config(page_title="Anki Studio", page_icon="📚", layout="wide")
st.title("📚 Anki Studio")
st.caption(
    "PDF → ChatGPT manuel (facultatif et gratuit) → Anki. Le document source reste la référence."
)
uploaded = st.file_uploader(
    "Importer un PDF balisé CARTE ou un projet Anki Studio (.zip)", type=["pdf", "zip"]
)
if uploaded is None:
    st.stop()
input_data = uploaded.getvalue()
input_id = hashlib.sha256(input_data).hexdigest()
if st.session_state.get("input_id") != input_id:
    try:
        with st.spinner(
            "Lecture du projet ou extraction des textes, positions et images…"
        ):
            if uploaded.name.lower().endswith(".zip"):
                loaded = load_project(input_data)
                data, cards, digest = loaded["data"], loaded["cards"], loaded["digest"]
                document_name, exchange = loaded["name"], loaded["exchange"]
                validated_input = loaded["validated"]
            else:
                data = input_data
                digest = input_id
                cards = parse_pdf(data)
                document_name, exchange, validated_input = (
                    Path(uploaded.name).stem,
                    None,
                    set(),
                )
    except Exception as error:
        st.error(f"Lecture impossible : {error}")
        st.stop()
    st.session_state.update(
        input_id=input_id,
        pdf_data=data,
        document_name=document_name,
        digest=digest,
        cards=cards,
        edits={},
        validated=validated_input,
        revisions={},
        apkg=None,
        bundle=None,
        project_payload=None,
        exchange=exchange,
        correction_notice=None,
        export_selection=None,
    )
data = st.session_state.pdf_data
digest = st.session_state.digest
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
    "Basic et Cloze : export immédiat après les contrôles automatiques. La revue individuelle est facultative. "
    "Les titres incertains sont signalés. Une image ou une zone ambiguë n’est pas une carte perdue."
)
mode = st.radio("Méthode", ["Sans IA", "ChatGPT manuel (gratuit)"], horizontal=True)
if mode == "ChatGPT manuel (gratuit)":
    st.subheader("1. Préparer un lot pour ChatGPT")
    st.caption(
        "Aucune API ni connexion automatique. Le JSON contient les textes et les retraits, sans PDF ni images. "
        "Copiez le prompt dans ChatGPT, puis collez sa réponse ici. Choisissez de petits lots si nécessaire. "
        "Les textes copiés seront partagés avec ChatGPT selon votre utilisation de ce service."
    )
    first = st.number_input(
        "Première carte du lot", min_value=1, max_value=len(cards), value=1, step=1
    )
    batch_size = st.number_input(
        "Nombre de cartes du lot",
        min_value=1,
        max_value=len(cards),
        value=min(20, len(cards)),
        step=1,
    )
    if st.button("Générer le JSON et le prompt"):
        request, states = make_request(
            cards, digest, range(first - 1, min(len(cards), first - 1 + batch_size))
        )
        st.session_state.exchange = dict(request=request, states=states)
        st.session_state.project_payload = None
        st.session_state.correction_notice = None
    exchange = st.session_state.exchange
    if exchange:
        request = exchange["request"]
        st.caption(
            f"Lot actif : {len(request['cards'])} cartes · référence {request['request_id'][:12]}"
        )
        st.code(chatgpt_prompt(request), language="text")
        st.download_button(
            "Télécharger le JSON léger",
            canonical(request),
            file_name="cartes_chatgpt.json",
            mime="application/json",
        )
        st.subheader("2. Réimporter les rectos corrigés")
        answer = st.text_area(
            "Réponse JSON de ChatGPT", key="answer_" + request["request_id"], height=180
        )
        answer_file = st.file_uploader(
            "Ou importer la réponse JSON",
            type=["json"],
            key="answer_file_" + request["request_id"],
        )
        if st.button("Appliquer les corrections JSON"):
            try:
                corrected, changed = apply_corrections(
                    cards,
                    digest,
                    request,
                    exchange["states"],
                    answer_file.getvalue() if answer_file else answer,
                )
                for i in changed:
                    st.session_state.edits[i] = corrected[i]
                    st.session_state.revisions[i] = (
                        st.session_state.revisions.get(i, 0) + 1
                    )
                    validated.discard(i)
                st.session_state.apkg = None
                st.session_state.bundle = None
                st.session_state.project_payload = None
                st.session_state.correction_notice = f"{len(changed)} carte(s) corrigée(s). Versos existants et images conservés."
                st.rerun()
            except (ValueError, TypeError, KeyError, UnicodeError) as error:
                st.error(f"Corrections refusées, aucune carte modifiée : {error}")
    if st.session_state.correction_notice:
        st.success(st.session_state.correction_notice)

io_indices = [i for i, c in enumerate(cards) if c["type"] == "CARTE OCCLUSION" and c.get("io", {}).get("canvas")]
io_mode = st.toggle("Gérer les occlusions", disabled=not io_indices, key="io_mode")
if io_mode and io_indices:
    selected = st.session_state.get(f"select_{digest}", io_indices[0])
    if selected not in io_indices:
        st.session_state[f"select_{digest}"] = io_indices[0]
    position = io_indices.index(st.session_state[f"select_{digest}"])
    a, b, c = st.columns([1, 2, 1])
    with a:
        if st.button("← Précédente", disabled=position == 0):
            st.session_state[f"select_{digest}"] = io_indices[position - 1]
            st.rerun()
    with b:
        st.caption(f"Occlusion {position + 1} / {len(io_indices)}")
    with c:
        if st.button("Suivante →", disabled=position == len(io_indices) - 1):
            st.session_state[f"select_{digest}"] = io_indices[position + 1]
            st.rerun()

index = st.selectbox(
    "Choisir une carte",
    io_indices if io_mode and io_indices else range(len(cards)),
    format_func=lambda i, reviewed=frozenset(validated): (
        f"{'✓ ' if i in reviewed else ''}{i + 1} · "
        f"{' — '.join(cards[i]['context'] + [cards[i]['title']])[:90] or ('[Occlusion sans titre]' if cards[i]['type'] == 'CARTE OCCLUSION' else '[Titre à renseigner]')}"
    ),
    key=f"select_{digest}",
)
card = cards[index]
revision = st.session_state.revisions.get(index, 0)
prefix = f"{digest}_{index}_{revision}"
if uploaded.name.lower().endswith(".zip"):
    prefix += "_" + input_id[:12]
zoom = st.slider("Zoom du PDF original", 1.0, 4.0, 2.0, 0.25)
left, right = st.columns(2)
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
    front_content = card["front"]
    back_content = preview_html(render_blocks(card["blocks"]), card["media"])
    if card["type"] == "CARTE CLOZE":
        numbers = sorted(cloze_numbers(fields_for(card)[0]))
        active = (
            st.selectbox("Suppression Cloze", numbers, key="cloze_" + prefix)
            if len(numbers) > 1 else numbers[0] if numbers else 1
        )
        source = preview_html(fields_for(card)[0], card["media"])
        front_content = preview_cloze(source, answer=False, active_number=active)
        back_content = preview_cloze(source, answer=True, active_number=active)
    components.html(
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<div style="font:18px/1.5 sans-serif;overflow-wrap:anywhere">'
        '<div style="font-size:13px;color:#666">RECTO</div>'
        '<div style="padding:14px;border:1px solid #bbb;border-radius:9px">'
        + front_content +
        '</div><hr style="margin:20px 0">'
        '<div style="font-size:13px;color:#666">VERSO</div>'
        '<div style="padding:14px;border:1px solid #bbb;border-radius:9px">'
        + back_content + '</div></div>',
        height=620,
        scrolling=True,
    )
if card["type"] == "CARTE OCCLUSION" and card.get("io", {}).get("canvas"):
    st.subheader("Dessiner et vérifier les zones d’occlusion")
    st.caption(
        "Aucun masque automatique. Dessiner, déplacer ou redimensionner ; utiliser Défiler pour naviguer dans l’image. Chaque modification annule la validation."
    )
    editor_id = f"{input_id}:{index}:{card['io']['canvas']['sha256']}"
    event = occlusion_editor(card, editor_id, key=f"io_{input_id}_{index}")
    try:
        before_editor = fingerprint(card)
        updated, accepted = apply_editor_event(card, event, editor_id)
        if accepted:
            card = updated
            cards[index] = card
            st.session_state.edits[index] = card
            if event["kind"] in ("editing", "commit") or before_editor != fingerprint(
                card
            ):
                validated.discard(index)
                st.session_state.apkg = None
                st.session_state.bundle = None
                st.session_state.project_payload = None
    except (ValueError, KeyError, TypeError) as error:
        validated.discard(index)
        st.session_state.apkg = None
        st.session_state.bundle = None
        st.session_state.project_payload = None
        invalidate(card)
        card["io"]["draft"] = True
        st.session_state.edits[index] = card
        cards[index] = card
        st.error(f"Zones refusées : {error}")
    state = card["io"]
    fp = fingerprint(card)
    for number in groups(card):
        group_checked = st.checkbox(
            f"Carte Anki {number} : j’ai vérifié les zones masquées et la réponse.",
            value=number in state["reviewed"],
            disabled=state["draft"] or number not in state["previewed"],
            key=f"io_review_{prefix}_{fp}_{state['epoch']}_{number}",
        )
        review_group(card, number, group_checked)
    if groups(card) and not ready_to_confirm(card):
        st.info(
            "Revue facultative : afficher l’aperçu masqué de chaque numéro, puis cocher sa vérification ci-dessus. L’export des masques terminés reste possible sans ces cases."
        )
    if state["draft"]:
        st.warning("Modification en cours : l’export de cette note est désactivé.")

with st.expander("Afficher les problèmes potentiels", expanded=False):
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
            if not title.strip() and card["type"] != "CARTE OCCLUSION":
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
                move_source_title(updated)
            updated["levels"] = update_edited_levels(updated["blocks"])
            updated["back"] = render_blocks(updated["blocks"])
            if updated.get("io"):
                invalidate(updated)
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
            st.session_state.project_payload = None
            st.rerun()
        except (ValueError, TypeError) as error:
            st.error(str(error))

st.caption("Vérification facultative")
is_io = card["type"] == "CARTE OCCLUSION"
can_confirm = not is_io or ready_to_confirm(card)
verify_key = "verified_" + prefix
if is_io:
    verify_key += (
        "_"
        + fingerprint(card)
        + str(card["io"]["epoch"])
        + str(card["io"]["reviewed"])
        + str(card["io"]["draft"])
    )
checked = st.checkbox(
    "J’ai comparé le titre, chaque ligne, les retraits, les images et leur ordre avec le PDF.",
    value=index in validated and can_confirm,
    key=verify_key,
    disabled=not can_confirm,
)
if checked and can_confirm:
    if is_io:
        confirm_note(card)
    validated.add(index)
else:
    validated.discard(index)
    if is_io:
        card["io"]["verified"] = None
current_issue = export_reason(card)
if current_issue:
    st.info(current_issue)
# Rebuild on each validation change so old downloads cannot expose stale selections.
plan = export_plan(cards, validated)
selection = (tuple(plan["included"]), tuple(sorted(validated)))
if st.session_state.get("export_selection") != selection:
    st.session_state.apkg = None
    st.session_state.bundle = None
    st.session_state.project_payload = None
    st.session_state.export_selection = selection
st.write(f"{len(validated)} / {len(cards)} notes vérifiées.")
st.subheader("Exporter vers Anki")
st.write(
    f"**{plan['notes']} notes incluses → {plan['cards']} cartes Anki** · "
    f"{len(plan['excluded'])} exclues — consultez le tableau de correction"
)
if plan["warnings"]:
    st.warning(
        "Export avec avertissements : les contrôles automatiques ne garantissent pas la fidélité sémantique. Consultez le tableau de correction."
    )
if plan["excluded"] or plan["warnings"]:
    with st.expander("Afficher le tableau des problèmes potentiels", expanded=False):
        st.dataframe(
        [
            {
                "Carte": e["index"] + 1,
                "Type": e["type"],
                "Statut": e["status"],
                "Motif": e["reason"],
            }
            for e in [
                dict(e, status="Exclue : correction nécessaire")
                for e in plan["excluded"]
            ]
            + [
                dict(
                    w,
                    type=cards[w["index"]]["type"],
                    status="Exportée avec avertissement"
                    if w["index"] in plan["included"]
                    else "Avertissement sur carte exclue",
                )
                for w in plan["warnings"]
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )
st.caption(
    "Les Basic et Cloze compatibles sont exportables immédiatement, sans validation individuelle. Les anomalies bloquantes sont exclues et signalées ; les autres sont exportées avec avertissements. "
    "Une note Cloze ou Occlusion peut produire plusieurs cartes. Les zones dessinées et terminées sont exportées au format natif ; leur revue reste facultative. Les sources restent inchangées."
)
if st.button(
    "Exporter toutes les cartes en .apkg"
    if not plan["excluded"]
    else "Exporter les cartes valides en .apkg",
    disabled=not plan["included"],
):
    try:
        payload, report = build_apkg(
            cards, validated, st.session_state.document_name, digest
        )
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
    "Les zones dessinées sont exportées en notes Image Occlusion natives, éditables dans un client Anki compatible."
)

st.subheader("Conserver et reprendre le projet")
st.caption(
    "Le projet ZIP réimportable conserve le PDF, toutes les cartes, les corrections, les images, les masques et le lot ChatGPT actif. Importez-le en haut de cette page pour reprendre, même sans IA."
)
if st.button("Préparer le projet réimportable (.zip)"):
    try:
        st.session_state.project_payload = save_project(
            data,
            cards,
            validated,
            st.session_state.document_name,
            st.session_state.exchange,
        )
    except (ValueError, TypeError) as error:
        st.error(f"Sauvegarde impossible : {error}")
if st.session_state.project_payload:
    st.download_button(
        "Télécharger le projet réimportable",
        st.session_state.project_payload,
        file_name="anki_studio_projet.zip",
        mime="application/zip",
    )
