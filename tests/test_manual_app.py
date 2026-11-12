"""Actual Streamlit reruns for JSON imports, failed transactions and project reopen."""

import io
import json
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from test_app import button
from test_manual_workflow import histology_pdf, response
from exporter import fields_for

APP = Path(__file__).resolve().parents[1] / "app.py"


def uploaded(data, name):
    file = io.BytesIO(data)
    file.name = name
    return file


def test_json_corrections_export_invalidate_and_project_reopen():
    source = uploaded(histology_pdf(), "histologie-test.pdf")

    def uploader(label, **kwargs):
        return source if label.startswith("Importer un PDF") else None

    with patch("streamlit.file_uploader", side_effect=uploader):
        at = AppTest.from_file(APP).run()
        assert not at.exception
        next(r for r in at.radio if r.label == "Méthode").set_value(
            "ChatGPT manuel (gratuit)"
        ).run()
        button(at, "Générer le JSON et le prompt").click().run()
        req = at.session_state["exchange"]["request"]
        answer = response(
            req,
            {0: "Quels criteres de reconnaissance ?", 1: "Que secrete cette cellule ?"},
        )
        textarea = next(t for t in at.text_area if t.label == "Réponse JSON de ChatGPT")
        textarea.set_value(json.dumps(answer))
        button(at, "Appliquer les corrections JSON").click().run()
        assert not at.exception and not at.error
        assert (
            at.session_state["edits"][0]["title"]
            == "Quels criteres de reconnaissance ?"
        )
        assert at.session_state["edits"][1]["blocks"]
        button(at, "Exporter les cartes valides en .apkg").click().run()
        assert not at.exception and at.session_state["apkg"][:2] == b"PK"
        assert at.session_state["validated"] == set()
        button(at, "Préparer le projet réimportable (.zip)").click().run()
        payload = at.session_state["project_payload"]
        assert payload[:2] == b"PK"
        before = fields_for(at.session_state["edits"][0])
        # Replaying an obsolete batch fails atomically and leaves an existing export alone.
        button(at, "Appliquer les corrections JSON").click().run()
        assert at.error and "aucune carte modifiée" in at.error[0].value
        assert at.session_state["apkg"][:2] == b"PK"
    project = uploaded(payload, "projet.zip")
    with patch(
        "streamlit.file_uploader",
        side_effect=lambda label, **kwargs: (
            project if label.startswith("Importer un PDF") else None
        ),
    ):
        restarted = AppTest.from_file(APP).run()
        assert not restarted.exception and not restarted.error
        assert fields_for(restarted.session_state["cards"][0]) == before
        assert restarted.session_state["cards"][1]["blocks"]
        assert restarted.session_state["exchange"]["request"] == req
        button(restarted, "Exporter les cartes valides en .apkg").click().run()
        assert restarted.session_state["apkg"][:2] == b"PK"


def test_new_prompt_after_manual_edit_discards_previous_export():
    source = uploaded(histology_pdf(), "histologie.pdf")
    with patch(
        "streamlit.file_uploader",
        side_effect=lambda label, **kwargs: (
            source if label.startswith("Importer un PDF") else None
        ),
    ):
        at = AppTest.from_file(APP).run()
        button(at, "Exporter les cartes valides en .apkg").click().run()
        assert at.session_state["apkg"]
        next(r for r in at.radio if r.label == "Méthode").set_value(
            "ChatGPT manuel (gratuit)"
        ).run()
        button(at, "Générer le JSON et le prompt").click().run()
        req = at.session_state["exchange"]["request"]
        next(t for t in at.text_area if t.label == "Titre exact").set_value(
            "Correction manuelle"
        )
        button(at, "Enregistrer les corrections").click().run()
        assert at.session_state["apkg"] is None
        next(t for t in at.text_area if t.label == "Réponse JSON de ChatGPT").set_value(
            json.dumps(response(req))
        )
        button(at, "Appliquer les corrections JSON").click().run()
        assert at.error and "modifiée depuis" in at.error[0].value
        assert at.session_state["edits"][0]["title"] == "Correction manuelle"
