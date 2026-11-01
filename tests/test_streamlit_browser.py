"""Actual Streamlit component bridge and native download, with local synthetic PDF."""

from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import zipfile
from urllib.request import urlopen

import pymupdf as fitz
import pytest


@pytest.fixture
def local_app(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    log = (tmp_path / "streamlit.log").open("w")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.headless=true",
            "--server.address=127.0.0.1",
            f"--server.port={port}",
            "--browser.gatherUsageStats=false",
        ],
        cwd=Path(__file__).resolve().parents[1],
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(150):
            if process.poll() is not None:
                raise RuntimeError((tmp_path / "streamlit.log").read_text())
            try:
                with urlopen(url + "/_stcore/health", timeout=0.3) as response:
                    if response.read() == b"ok":
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Streamlit startup timeout")
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        log.close()


def test_draw_review_download_and_invalidate_in_actual_streamlit(local_app, tmp_path):
    from playwright.sync_api import sync_playwright, expect

    executable = shutil.which("chromium")
    with sync_playwright() as pw:
        executable = executable or pw.chromium.executable_path
        if not Path(executable).exists():
            pytest.skip("Chromium unavailable")
        browser = pw.chromium.launch(
            executable_path=executable,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            page = browser.new_page(viewport={"width": 1100, "height": 1000})
            doc = fitz.open()
            source = doc.new_page()
            source.insert_text((40, 40), "CARTE OCCLUSION")
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 600, 400), False)
            pix.clear_with(200)
            source.insert_image(fitz.Rect(50, 80, 350, 280), pixmap=pix)
            source.insert_text((40, 310), "CARTE OCCLUSION")
            source.insert_image(fitz.Rect(50, 350, 350, 550), pixmap=pix)
            path = tmp_path / "synthetic.pdf"
            path.write_bytes(doc.tobytes())
            page.goto(local_app)
            page.locator("input[type=file]").set_input_files(path)
            frame = page.frame_locator('iframe[title*="anki_occlusion_editor"]')
            frame.locator("body[data-ready=true]").wait_for(timeout=20000)
            assert frame.locator("svg rect").count() == 0
            button = page.get_by_role(
                "button", name="Préparer le paquet .apkg", exact=True
            )
            expect(button).to_be_disabled()
            frame.locator("#overlay").scroll_into_view_if_needed()
            box = frame.locator("#overlay").bounding_box()
            page.mouse.move(
                box["x"] + 0.1 * box["width"], box["y"] + 0.1 * box["height"]
            )
            page.mouse.down()
            page.mouse.move(
                box["x"] + 0.4 * box["width"], box["y"] + 0.4 * box["height"], steps=8
            )
            page.mouse.up()
            group_label = (
                "Carte Anki 1 : j’ai vérifié les zones masquées et la réponse."
            )
            group = page.get_by_label(group_label, exact=True)
            expect(group).to_be_disabled()
            frame.locator("#question").click()
            expect(group).to_be_enabled(timeout=15000)
            page.get_by_text(group_label, exact=True).click()
            expect(group).to_be_checked()
            overall = "J’ai comparé le titre, chaque ligne, les retraits, les images et leur ordre avec le PDF."
            page.get_by_text(overall, exact=True).click()
            expect(button).to_be_enabled(timeout=15000)
            button.click()
            page.get_by_text(
                "Archive vérifiée : 1 notes, 1 cartes et médias contrôlés.", exact=True
            ).wait_for(timeout=30000)
            link = page.get_by_role(
                "button", name="Télécharger le paquet Anki", exact=True
            )
            expect(link).to_be_visible()
            with page.expect_download() as downloaded:
                link.click()
            downloaded.value.save_as(tmp_path / "download.apkg")
            assert (tmp_path / "download.apkg").read_bytes()[:2] == b"PK"
            with zipfile.ZipFile(tmp_path / "download.apkg") as archive:
                assert archive.testzip() is None

            # Switching notes recreates the frame but must preserve saved masks
            # and reviews; an unedited second note must still start completely blank.
            page.get_by_role("combobox").first.click()
            page.get_by_role("combobox").first.press("ArrowDown")
            page.get_by_role("combobox").first.press("Enter")
            frame.locator("body[data-ready=true]").wait_for()
            expect(frame.locator("svg rect")).to_have_count(0)
            page.get_by_role("combobox").first.click()
            page.get_by_role("combobox").first.press("ArrowUp")
            page.get_by_role("combobox").first.press("Enter")
            frame.locator("body[data-ready=true]").wait_for()
            expect(frame.locator("svg rect[data-mask]").first).to_be_attached()
            expect(page.get_by_label(overall, exact=True)).to_be_checked()
            # Any new geometry must disable export and remove the old download.
            frame.locator("#draw").click()
            frame.locator("#overlay").scroll_into_view_if_needed()
            box = frame.locator("#overlay").bounding_box()
            page.mouse.move(
                box["x"] + 0.55 * box["width"], box["y"] + 0.1 * box["height"]
            )
            page.mouse.down()
            page.mouse.move(
                box["x"] + 0.8 * box["width"], box["y"] + 0.35 * box["height"], steps=8
            )
            page.mouse.up()
            expect(button).to_be_disabled(timeout=15000)
            expect(link).to_have_count(0)
            # The component must not grow on every height/resize acknowledgement.
            height = page.locator(
                'iframe[title*="anki_occlusion_editor"]'
            ).bounding_box()["height"]
            assert 440 < height < 1100
            page.on("dialog", lambda dialog: dialog.accept())
            frame.locator("#clear").click()
            expect(frame.locator("svg rect")).to_have_count(0)
            expect(button).to_be_disabled()
        finally:
            browser.close()
