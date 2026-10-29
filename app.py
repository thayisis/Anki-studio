
import hashlib
import tempfile
from pathlib import Path

import streamlit as st
from engine import parse_pdf, preview_html, crop

st.set_page_config(
    page_title="Anki Studio V5",
    page_icon="📚",
    layout="wide"
)

st.title("📚 Anki Studio V5")
st.caption(
    "Puces hiérarchisées · images intégrées · "
    "comparaison PDF / Anki"
)

uploaded = st.file_uploader(
    "Importer un PDF balisé CARTE",
    type="pdf"
)

if uploaded is None:
    st.stop()

data = uploaded.getvalue()
digest = hashlib.sha256(data).hexdigest()

if st.session_state.get("digest") != digest:
    with st.spinner("Analyse du PDF…"):
        try:
            cards = parse_pdf(data)
        except Exception as error:
            st.error(f"Erreur de lecture : {error}")
            st.stop()

    st.session_state.update(
        digest=digest,
        cards=cards,
        edits={},
        apkg=None
    )

cards = st.session_state.cards

if not cards:
    st.warning("Aucune carte détectée.")
    st.stop()

classic = sum(c["type"] == "CARTE" for c in cards)
cloze = sum(c["type"] == "CARTE CLOZE" for c in cards)
occlusion = sum(
    c["type"] == "CARTE OCCLUSION"
    for c in cards
)

st.write(
    f"**{len(cards)} cartes** · "
    f"{classic} classiques · "
    f"{cloze} Cloze · "
    f"{occlusion} Occlusion"
)

index = st.selectbox(
    "Choisir une carte",
    options=list(range(len(cards))),
    format_func=lambda i: (
        f"{i + 1}. "
        f"{cards[i]['front'][:65]}"
    )
)

card = cards[index]

front, back = st.session_state.edits.get(
    index,
    (card["front"], card["back"])
)

side = st.radio(
    "Afficher",
    ["Verso", "Recto"],
    horizontal=True
)

zoom = st.slider(
    "Zoom du PDF original",
    min_value=1.0,
    max_value=3.0,
    value=2.0,
    step=0.25
)

left, right = st.columns(2, gap="medium")

with left:
    st.subheader("PDF original")

    try:
        image = crop(data, card, zoom)

        st.image(
            image,
            use_container_width=True
        )

        st.caption(
            "Tu peux aussi zoomer avec les "
            "gestes habituels de ton iPad."
        )

    except Exception as error:
        st.error(
            f"Impossible d'afficher le PDF : {error}"
        )

with right:
    st.subheader("Carte Anki")

    content = (
        front
        if side == "Recto"
        else preview_html(back, card["media"])
    )

    st.markdown(
        '<div style="'
        'border:1px solid #999;'
        'border-radius:12px;'
        'padding:18px;'
        'line-height:1.5;'
        'overflow-wrap:anywhere;'
        'max-height:900px;'
        'overflow:auto;'
        '">'
        + content +
        '</div>',
        unsafe_allow_html=True
    )

    for warning in card["warnings"]:
        st.warning(warning)

with st.expander(
    "✏️ Modifier le recto ou le verso",
    expanded=False
):
    with st.form("editor"):
        edited_front = st.text_area(
            "Recto (HTML)",
            value=front,
            height=100
        )

        edited_back = st.text_area(
            "Verso (HTML)",
            value=back,
            height=320
        )

        if st.form_submit_button(
            "Enregistrer cette carte"
        ):
            st.session_state.edits[index] = (
                edited_front,
                edited_back
            )
            st.session_state.apkg = None
            st.rerun()

st.divider()
st.subheader("Exporter vers Anki")

unsupported = cloze + occlusion

if unsupported:
    st.error(
        f"Export bloqué : {unsupported} cartes "
        "Cloze/Occlusion nécessitent encore "
        "un moteur d'export compatible."
    )

else:
    st.warning(
        "Vérifie chaque carte avant l'export : "
        "les alinéas et les images peuvent "
        "encore nécessiter des corrections."
    )

    checked = st.checkbox(
        "J'ai vérifié les cartes et j'accepte "
        "cet export expérimental."
    )

    if checked and st.button(
        "Préparer le fichier Anki"
    ):
        try:
            import genanki

            model = genanki.Model(
                1904830217,
                "Anki Studio V5 Basic",
                fields=[
                    {"name": "Front"},
                    {"name": "Back"}
                ],
                templates=[{
                    "name": "Card 1",
                    "qfmt": "{{Front}}",
                    "afmt": (
                        "{{FrontSide}}"
                        "<hr id='answer'>"
                        "{{Back}}"
                    )
                }]
            )

            deck = genanki.Deck(
                1904830218,
                Path(uploaded.name).stem
            )

            with tempfile.TemporaryDirectory() as tmp:
                paths = []

                for i, item in enumerate(cards):
                    f, b = st.session_state.edits.get(
                        i,
                        (item["front"], item["back"])
                    )

                    for filename, raw in item["media"]:
                        path = Path(tmp) / filename

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

                output = Path(tmp) / "cards.apkg"
                package.write_to_file(str(output))

                st.session_state.apkg = (
                    output.read_bytes()
                )

        except Exception as error:
            st.error(f"Erreur d'export : {error}")

    if st.session_state.get("apkg"):
        st.download_button(
            "📥 Télécharger le paquet .apkg",
            data=st.session_state.apkg,
            file_name="anki_studio_v5.apkg",
            mime="application/octet-stream"
        )

st.caption(
    "Anki Studio V5 — prototype expérimental. "
    "La hiérarchie est déduite des coordonnées "
    "du texte dans le PDF."
)
