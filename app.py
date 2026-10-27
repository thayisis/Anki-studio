
import hashlib
import tempfile
from pathlib import Path

import streamlit as st
from engine import parse_pdf, preview_html, crop

st.set_page_config(
    page_title="Anki Studio V4",
    page_icon="📚",
    layout="wide"
)

st.title("📚 Anki Studio V4 — laboratoire")
st.caption(
    "Comparaison côte à côte · texte et images "
    "dans leur ordre vertical · contrôle avant export"
)

st.info(
    "Prototype expérimental. Les PDF sont traités "
    "sur le serveur Streamlit. Évite les documents "
    "confidentiels sur un hébergement public."
)

up = st.file_uploader(
    "Importer un PDF balisé CARTE",
    type="pdf"
)

if not up:
    st.stop()

data = up.getvalue()
digest = hashlib.sha256(data).hexdigest()

if st.session_state.get("digest") != digest:
    with st.spinner("Lecture de la structure du PDF…"):
        try:
            cards = parse_pdf(data)
        except Exception as e:
            st.error(f"Erreur de lecture : {e}")
            st.stop()

    st.session_state.update(
        digest=digest,
        cards=cards,
        edit={},
        apkg=None
    )

cards = st.session_state.cards

if not cards:
    st.warning("Aucun marqueur CARTE détecté.")
    st.stop()

count = {
    t: sum(c["type"] == t for c in cards)
    for t in (
        "CARTE",
        "CARTE CLOZE",
        "CARTE OCCLUSION"
    )
}

st.write(
    f"**{len(cards)} sections** · "
    f"{count['CARTE']} classiques · "
    f"{count['CARTE CLOZE']} Cloze · "
    f"{count['CARTE OCCLUSION']} occlusions"
)

index = st.number_input(
    "Carte",
    min_value=1,
    max_value=len(cards),
    value=1,
    step=1
) - 1

card = cards[index]

front, back = st.session_state.edit.get(
    index,
    (card["front"], card["back"])
)

side = st.radio(
    "Aperçu",
    ["Verso", "Recto"],
    horizontal=True
)

zoom = st.slider(
    "Zoom PDF",
    min_value=0.8,
    max_value=3.0,
    value=1.8,
    step=0.2
)

left, right = st.columns(
    2,
    gap="medium"
)

with left:
    st.subheader("PDF original")

    try:
        st.image(
            crop(data, card, zoom),
            use_container_width=True
        )
    except Exception as e:
        st.error(
            f"Impossible de rendre cet extrait : {e}"
        )

    st.caption(
        f"Page {card['page'] + 1} · "
        f"{card['type']} · "
        f"{len(card['media'])} images"
    )

with right:
    st.subheader("Aperçu de la carte")

    body = (
        front
        if side == "Recto"
        else preview_html(back, card["media"])
    )

    st.markdown(
        '<div style="'
        'border:1px solid #aaa;'
        'border-radius:10px;'
        'padding:16px;'
        'max-height:780px;'
        'overflow:auto;'
        'overflow-wrap:anywhere'
        '">'
        + body +
        '</div>',
        unsafe_allow_html=True
    )

    for issue in card["warnings"]:
        st.warning(issue)

with st.expander(
    "✏️ Modifier la carte (HTML)",
    expanded=False
):
    with st.form("edit"):
        f = st.text_area(
            "Recto",
            value=front,
            height=90
        )

        b = st.text_area(
            "Verso",
            value=back,
            height=260
        )

        if st.form_submit_button(
            "Enregistrer les modifications"
        ):
            st.session_state.edit[index] = (f, b)
            st.session_state.apkg = None
            st.rerun()

st.divider()
st.subheader("Export Anki (expérimental)")

unsupported = sum(
    c["type"] != "CARTE"
    for c in cards
)

if unsupported:
    st.error(
        f"Export désactivé : {unsupported} sections "
        "Cloze/Occlusion non prises en charge. "
        "Aucun export incomplet."
    )

else:
    st.warning(
        "Avant export, vérifie chaque carte et "
        "chaque image. Des anomalies restent possibles."
    )

    verified = st.checkbox(
        "J'ai vérifié les cartes et accepte "
        "un export expérimental"
    )

    if verified:
        if st.button("Préparer le .apkg"):
            try:
                import genanki

                model = genanki.Model(
                    1904830217,
                    "Anki Studio V4 Basic",
                    fields=[
                        {"name": "Front"},
                        {"name": "Back"}
                    ],
                    templates=[{
                        "name": "Card 1",
                        "qfmt": "{{Front}}",
                        "afmt": (
                            '{{FrontSide}}'
                            '<hr id="answer">'
                            '{{Back}}'
                        )
                    }]
                )

                deck = genanki.Deck(
                    1904830218,
                    Path(up.name).stem
                )

                with tempfile.TemporaryDirectory() as tmp:
                    paths = []

                    for i, c in enumerate(cards):
                        f, b = st.session_state.edit.get(
                            i,
                            (c["front"], c["back"])
                        )

                        for name, raw in c["media"]:
                            path = Path(tmp) / name

                            if not path.exists():
                                path.write_bytes(raw)

                            paths.append(str(path))

                        note = genanki.Note(
                            model=model,
                            fields=[f, b],
                            guid=genanki.guid_for(digest, i)
                        )

                        deck.add_note(note)

                    package = genanki.Package(deck)

                    package.media_files = list(
                        dict.fromkeys(paths)
                    )

                    path = Path(tmp) / "cards.apkg"

                    package.write_to_file(str(path))

                    st.session_state.apkg = (
                        path.read_bytes()
                    )

            except Exception as e:
                st.error(f"Erreur export : {e}")

        if st.session_state.get("apkg"):
            st.download_button(
                "Télécharger le .apkg",
                st.session_state.apkg,
                file_name="anki_studio_v4.apkg",
                mime="application/octet-stream"
            )

st.caption(
    "V4 expérimentale : les retraits sont déduits "
    "de la géométrie du texte. La fidélité à 100 % "
    "n'est pas encore garantie. Les cartes Cloze "
    "et Occlusion ne sont pas exportables."
)
