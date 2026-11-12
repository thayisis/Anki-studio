"""Free workflow in real Chromium with iPad-sized viewport and touch support."""

import json
import shutil
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, expect

from test_streamlit_browser import local_app as local_app
from test_manual_workflow import histology_pdf, response
from project import load_project
from exporter import fields_for


def test_pdf_manual_chatgpt_download_and_project_reopen(local_app, tmp_path):
    with sync_playwright() as pw:
        executable = shutil.which("chromium") or pw.chromium.executable_path
        if not Path(executable).exists():
            pytest.skip("Chromium unavailable")
        browser = pw.chromium.launch(
            executable_path=executable,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport={"width": 820, "height": 1180},
            is_mobile=True,
            has_touch=True,
            device_scale_factor=2,
            accept_downloads=True,
        )
        try:
            page = context.new_page()
            page.goto(local_app)
            page.locator("input[type=file]").first.set_input_files(
                {
                    "name": "histo-synthetic.pdf",
                    "mimeType": "application/pdf",
                    "buffer": histology_pdf(),
                }
            )
            page.get_by_text("ChatGPT manuel (gratuit)", exact=True).click()
            page.get_by_role(
                "button", name="Générer le JSON et le prompt", exact=True
            ).click()
            with page.expect_download() as download:
                page.get_by_role(
                    "button", name="Télécharger le JSON léger", exact=True
                ).click()
            path = tmp_path / "request.json"
            download.value.save_as(path)
            req = json.loads(path.read_text())
            answer = response(
                req,
                {
                    0: "Quels criteres de reconnaissance ?",
                    1: "Que secrete la cellule ?",
                },
            )
            page.get_by_label("Réponse JSON de ChatGPT", exact=True).fill(
                json.dumps(answer)
            )
            page.get_by_role(
                "button", name="Appliquer les corrections JSON", exact=True
            ).click()
            expect(
                page.get_by_text(
                    "2 carte(s) corrigée(s). Versos existants et images conservés.",
                    exact=True,
                )
            ).to_be_visible()
            export = page.get_by_role(
                "button", name="Exporter les cartes valides en .apkg", exact=True
            )
            export.click()
            expect(
                page.get_by_text(
                    "Archive vérifiée : 3 notes, 4 cartes et médias contrôlés.",
                    exact=True,
                )
            ).to_be_visible()
            with page.expect_download() as download:
                page.get_by_role(
                    "button", name="Télécharger le paquet Anki", exact=True
                ).click()
            path = tmp_path / "cards.apkg"
            download.value.save_as(path)
            assert path.read_bytes()[:2] == b"PK"
            page.get_by_role(
                "button", name="Préparer le projet réimportable (.zip)", exact=True
            ).click()
            with page.expect_download() as download:
                page.get_by_role(
                    "button", name="Télécharger le projet réimportable", exact=True
                ).click()
            project = tmp_path / "project.zip"
            download.value.save_as(project)
            loaded = load_project(project.read_bytes())
            assert loaded["cards"][0]["title"] == "Quels criteres de reconnaissance ?"
            expected_back = fields_for(loaded["cards"][0])[1]
            # Reopen in a new browser session; no prior Streamlit state survives.
            fresh = context.new_page()
            fresh.goto(local_app)
            fresh.locator("input[type=file]").first.set_input_files(project)
            expect(fresh.get_by_label("Titre exact", exact=True)).to_have_value(
                "Quels criteres de reconnaissance ?"
            )
            fresh.get_by_role(
                "button", name="Exporter les cartes valides en .apkg", exact=True
            ).click()
            expect(
                fresh.get_by_text(
                    "Archive vérifiée : 3 notes, 4 cartes et médias contrôlés.",
                    exact=True,
                )
            ).to_be_visible()
            assert expected_back.count("<img") == 2
            assert fresh.get_by_test_id("stException").count() == 0
        finally:
            context.close()
            browser.close()
