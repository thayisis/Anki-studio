"""Optional genuine Anki import, in an isolated interpreter (not a GUI/iPad test)."""

import hashlib
import json
import os
import re
from pathlib import Path
import subprocess

import genanki
import pytest

from engine import parse_pdf
from exporter import build_apkg, fields_for, cloze_numbers
from test_regressions import pdf


@pytest.mark.parametrize(
    "filename",
    ["Anki 2 HISTO.pdf", "Anki 1 BIO.pdf", "Anki 2 ANTHROPO .pdf", "synthetic-cloze"],
)
def test_official_anki_import(filename, tmp_path):
    interpreter = os.environ.get("ANKI_TEST_PYTHON")
    if not interpreter:
        pytest.skip(
            "Set ANKI_TEST_PYTHON to an interpreter with official anki installed"
        )
    if filename == "synthetic-cloze":
        data = pdf(
            [
                (40, 40, "CARTE CLOZE"),
                (40, 70, "Cloze title"),
                (70, 110, "{{c1::One}} {{c2::Two}}"),
            ]
        )
    else:
        path = (
            Path(os.environ.get("ANKI_REFERENCE_DIR", "tests/private-pdfs")) / filename
        )
        if not path.exists():
            pytest.skip("Private PDF unavailable")
        data = path.read_bytes()
    cards = parse_pdf(data)
    digest = hashlib.sha256(data).hexdigest()
    payload, plan = build_apkg(cards, set(range(len(cards))), filename, digest)
    package = tmp_path / "test.apkg"
    package.write_bytes(payload)
    expected = {
        "notes": [
            {
                "guid": genanki.guid_for("anki-studio-v8", digest, i, cards[i]["type"]),
                "fields": fields_for(cards[i]),
                "kind": cards[i]["type"],
                "cloze_words": [
                    (int(n), value)
                    for n, value in re.findall(
                        r"{{c(\d+)::([^{}]+?)}}", fields_for(cards[i])[0]
                    )
                ],
                "ords": sorted(n - 1 for n in cloze_numbers(fields_for(cards[i])[0]))
                if cards[i]["type"] == "CARTE CLOZE"
                else [0],
            }
            for i in plan["included"]
        ],
        "cards": plan["cards"],
        "media": {
            n: hashlib.sha256(raw).hexdigest()
            for i in plan["included"]
            for n, raw in cards[i]["media"]
        },
    }
    manifest = tmp_path / "expected.json"
    manifest.write_text(json.dumps(expected))
    result = subprocess.run(
        [
            interpreter,
            str(Path(__file__).with_name("anki_import_check.py")),
            str(package),
            str(manifest),
            str(tmp_path / "collection.anki2"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert f'"notes": {plan["notes"]}' in result.stdout
