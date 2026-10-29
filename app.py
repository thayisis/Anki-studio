
import hashlib
import html
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from engine import parse_pdf, preview_html, crop

st.set_page_config(
    page_title="Anki Studio V6",
    page_icon="📚",
    layout="wide"
)

st.title("📚 Anki Studio V6")
st.caption(
    "Titres contextualisés · puces hiérarchisées · "
    "images · comparaison PDF / Anki"
)

uploaded = st.file_uploader(
    "Importer un PDF balisé CARTE",
    type=["pdf"]
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
            st.error(
                f"Erreur pendant l'analyse : {error}"
            )
            st.stop()

    st.session_state.update(
        digest=digest,
        cards=cards,
        edits={},
        apkg=None
    )

cards = st.session_state.cards

if not cards:
    st.warning(
        "Aucune carte détectée. Vérifie les marqueurs CARTE."
    )
    st.stop()

classic = sum(
    c["type"] == "CARTE"
    for c in cards
)

cloze = sum(
    c["type"] == "CARTE CLOZE"
    for c in cards
)

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
        f"{html.unescape(cards[i]['front'])[:65]}"
    )
)

card = cards[index]

front, back = st.session_state.edits.get(
    index,
    (card["front"], card["back"])
)

suggested = card.get(
    "suggested_front",
    card["front"]
)

if suggested != card["front"]:
    with st.expander(
        "✨ Proposition de titre contextualisé",
        expanded=False
    ):
        st.write(
            html.unescape(suggested)
        )

        st.caption(
            "Cette proposition est automatique. "
            "Vérifie qu'elle reprend bien les titres "
            "parents de cette section."
        )

        if st.button(
            "Utiliser ce titre",
            key=f"title_{index}"
        ):
            st.session_state.edits[index] = (
                suggested,
                back
            )
            st.session_state.apkg = None
            st.rerun()

side = st.radio(
    "Aperçu",
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

left, right = st.columns(
    2,
    gap="medium"
)

with left:
    st.subheader("PDF original")

    try:
        image = crop(
            data,
            card,
            zoom
        )

        import base64

        encoded = base64.b64encode(
            image
        ).decode("ascii")

        document = f"""
        <html>
        <head>
        <meta name="viewport"
              content="width=device-width, initial-scale=1">
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                background: white;
            }}
            .viewport {{
                width: 100%;
                height: 760px;
                overflow: auto;
                border: 1px solid #aaa;
                border-radius: 10px;
                background: white;
            }}
            img {{
                display: block;
                width: auto;
                max-width: none;
                height: auto;
            }}
        </style>
        </head>
        <body>
            <div class="viewport">
                <img src="data:image/png;base64,{encoded}">
            </div>
        </body>
        </html>
        """

        components.html(
            document,
            height=775,
            scrolling=False
        )

        st.caption(
            "Fais défiler la zone du PDF pour "
            "examiner les détails. Le curseur "
            "modifie la taille réelle de l'image."
        )

    except Exception as error:
        st.error(
            f"Erreur d'affichage du PDF : {error}"
        )

with right:
    st.subheader("Carte Anki")

    content = (
        front
        if side == "Recto"
        else preview_html(
            back,
            card["media"]
        )
    )

    preview_document = f"""
    <html>
    <head>
    <meta name="viewport"
          content="width=device-width, initial-scale=1">
    <style>
        body {{
            margin: 0;
            padding: 16px;
            font-family: -apple-system,
                         BlinkMacSystemFont,
                         "Segoe UI",
                         sans-serif;
            font-size: 16px;
            line-height: 1.5;
            color: #202124;
            overflow-wrap: anywhere;
        }}
        img {{
            max-width: 100%;
            height: auto;
        }}
        .card {{
            box-sizing: border-box;
            border: 1px solid #aaa;
            border-radius: 10px;
            min-height: 120px;
            padding: 16px;
        }}
    </style>
    </head>
    <body>
        <div class="card">
            {content}
        </div>
    </body>
    </html>
    """

    components.html(
        preview_document,
        height=775,
        scrolling=True
    )

    for warning in card["warnings"]:
        st.warning(warning)

with st.expander(
    "✏️ Modifier la carte",
    expanded=False
):
    with st.form(
        key=f"editor_{index}"
    ):
        edited_front = st.text_area(
            "Recto (HTML)",
            value=front,
            height=110
        )

        edited_back = st.text_area(
            "Verso (HTML)",
            value=back,
            height=340
        )

        if st.form_submit_button(
            "Enregistrer les modifications"
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
        f"Export désactivé : {unsupported} cartes "
        "Cloze ou Occlusion ne sont pas encore "
        "prises en charge. Aucun paquet incomplet "
        "ne sera généré."
    )

else:
    st.warning(
        "V6 expérimentale : vérifie le texte, "
        "les images et tous les niveaux de "
        "hiérarchie avant d'exporter."
    )

    verified = st.checkbox(
        "J'ai vérifié les cartes et j'accepte "
        "cet export expérimental."
    )

    if verified and st.button(
        "Préparer le paquet .apkg"
    ):
        try:
            import genanki

            model = genanki.Model(
                1904830217,
                "Anki Studio V6 Basic",
                fields=[
                    {"name": "Front"},
                    {"name": "Back"}
                ],
                templates=[
                    {
                        "name": "Card 1",
                        "qfmt": "{{Front}}",
                        "afmt": (
                            "{{FrontSide}}"
                            "<hr id='answer'>"
                            "{{Back}}"
                        )
                    }
                ]
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
                        (
                            item["front"],
                            item["back"]
                        )
                    )

                    for filename, raw in item["media"]:
                        path = Path(tmp) / filename

                        if not path.exists():
                            path.write_bytes(raw)

                        paths.append(str(path))

                    note = genanki.Note(
                        model=model,
                        fields=[f, b],
                        guid=genanki.guid_for(
                            digest,
                            i
                        )
                    )

                    deck.add_note(note)

                package = genanki.Package(deck)

                package.media_files = list(
                    dict.fromkeys(paths)
                )

                output = Path(tmp) / "cards.apkg"

                package.write_to_file(
                    str(output)
                )

                st.session_state.apkg = (
                    output.read_bytes()
                )

        except Exception as error:
            st.error(
                f"Erreur d'export : {error}"
            )

    if st.session_state.get("apkg"):
        st.download_button(
            "📥 Télécharger le paquet Anki",
            data=st.session_state.apkg,
            file_name="anki_studio_v6.apkg",
            mime="application/octet-stream"
        )

st.caption(
    "Anki Studio V6 — prototype expérimental. "
    "Les titres contextualisés sont des propositions "
    "à valider. Les alinéas et les images nécessitent "
    "encore un contrôle visuel."
)
