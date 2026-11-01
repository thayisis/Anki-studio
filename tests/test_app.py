"""Streamlit AppTest exercises reruns; uploaded PDF bytes replace unsupported upload widget."""

import io
from unittest.mock import patch
from pathlib import Path

from streamlit.testing.v1 import AppTest

from test_regressions import pdf


def button(at, label):
    return next(b for b in at.button if b.label == label)


def upload():
    f = io.BytesIO(
        pdf(
            [
                (40, 40, "CARTE"),
                (40, 70, "Title"),
                (70, 110, "Answer."),
                (40, 300, "CARTE CLOZE"),
                (40, 330, "Cloze"),
                (70, 370, "No deletion yet."),
                (40, 450, "CARTE OCCLUSION"),
            ]
        )
    )
    f.name = "synthetic.pdf"
    return f


def test_ui_validation_partial_export_edit_invalidates_download_and_review():
    with patch("streamlit.file_uploader", return_value=upload()):
        at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
        assert not at.exception
        assert button(at, "Préparer le paquet .apkg").disabled
        at.checkbox[-1].check().run()
        assert not at.exception
        assert at.session_state["validated"] == {0}
        button(at, "Préparer le paquet .apkg").click().run()
        assert not at.exception
        assert at.session_state["apkg"][:2] == b"PK"
        at.text_area[0].set_value("Corrected title")
        button(at, "Enregistrer les corrections").click().run()
        assert not at.exception
        assert at.session_state["validated"] == set()
        assert at.session_state["apkg"] is None
        assert at.session_state["edits"][0]["title"] == "Corrected title"
        assert not at.checkbox[-1].value
        assert button(at, "Préparer le paquet .apkg").disabled


def test_ui_switch_cards_keeps_reviews_independent_and_retains_empty_occlusion():
    with patch("streamlit.file_uploader", return_value=upload()):
        at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
        at.checkbox[-1].check().run()
        at.selectbox[0].select(1).run()
        assert not at.exception
        assert not at.checkbox[-1].value
        at.checkbox[-1].check().run()
        assert at.session_state["validated"] == {0, 1}
        # A validated Cloze without deletions is still excluded.
        assert any("sans suppression" in str(df.value) for df in at.dataframe)
        at.selectbox[0].select(2).run()
        assert not at.exception
        assert any("Titre absent" in w.value for w in at.warning)
        at.selectbox[0].select(0).run()
        assert at.checkbox[-1].value
        at.checkbox[-1].uncheck().run()
        assert at.session_state["validated"] == {1}
        assert button(at, "Préparer le paquet .apkg").disabled


def test_ui_editor_changes_text_indentation_and_restores_source_title():
    with patch("streamlit.file_uploader", return_value=upload()):
        at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
        row_key = "rows_" + at.session_state["digest"] + "_0_0"
        at.session_state[row_key] = {
            "edited_rows": {0: {"Texte": "Corrected answer.", "Retrait": 42}},
            "added_rows": [],
            "deleted_rows": [],
        }
        at.checkbox[0].check()
        button(at, "Enregistrer les corrections").click().run()
        assert not at.exception
        blocks = at.session_state["edits"][0]["blocks"]
        assert blocks[0]["text"] == "Title"
        assert blocks[1]["text"] == "Corrected answer."
        assert blocks[1]["indent"] == 42


def test_ui_title_recovery_is_once_only_after_repeated_saves():
    with patch("streamlit.file_uploader", return_value=upload()):
        at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
        at.checkbox[0].check()
        button(at, "Enregistrer les corrections").click().run()
        assert not at.exception and at.checkbox[0].disabled
        before = at.session_state["edits"][0]["blocks"]
        at.text_area[0].set_value("New title")
        button(at, "Enregistrer les corrections").click().run()
        assert not at.exception
        assert at.session_state["edits"][0]["blocks"] == before
