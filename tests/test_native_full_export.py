"""All eight original IO notes with TEST-ONLY masks; no course masks are prefilled."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import zipfile
import io

import pytest
from engine import parse_pdf
from exporter import build_apkg, export_plan
from test_occlusion_state import reviewed


@pytest.mark.parametrize(
    "filename,expected_notes,expected_io",
    [
        ("Anki 2 HISTO.pdf", 16, 0),
        ("Anki 1 BIO.pdf", 58, 7),
        ("Anki 2 ANTHROPO .pdf", 11, 1),
    ],
)
def test_all_original_notes_export_without_losing_basic_or_cloze(
    filename, expected_notes, expected_io, tmp_path
):
    path = Path(os.environ.get("ANKI_REFERENCE_DIR", "tests/private-pdfs")) / filename
    if not path.exists():
        pytest.skip("Private PDF unavailable")
    cards = parse_pdf(path.read_bytes())
    io_indices = [i for i, c in enumerate(cards) if c["type"] == "CARTE OCCLUSION"]
    assert len(io_indices) == expected_io
    for i in io_indices:
        assert cards[i]["io"]["masks"] == []  # Production never invents course masks.
        cards[i] = reviewed(cards[i])  # Explicit test-only gesture/review simulation.
    payload, plan = build_apkg(
        cards,
        set(range(len(cards))),
        filename,
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    assert plan["notes"] == expected_notes and plan["cards"] == expected_notes
    assert plan["excluded"] == []
    if expected_io:
        package = tmp_path / "native.apkg"
        package.write_bytes(payload)
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("verify_editable_io.py")),
                str(package),
                str(expected_io),
                str(tmp_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    else:
        assert "collection.anki2" in zipfile.ZipFile(io.BytesIO(payload)).namelist()


def test_native_grouped_rectangles_produce_distinct_cards_and_unreviewed_notes_are_excluded():
    from test_occlusion_state import card

    c = reviewed(
        card(),
        [
            dict(id="a", number=1, left=0.1, top=0.1, width=0.2, height=0.1),
            dict(id="b", number=1, left=0.5, top=0.1, width=0.2, height=0.1),
            dict(id="c", number=3, left=0.1, top=0.6, width=0.2, height=0.1),
        ],
    )
    payload, plan = build_apkg([c], {0}, "Synthetic grouped IO", "synthetic-io")
    assert plan["notes"] == 1 and plan["cards"] == 2 and payload[:2] == b"PK"
    c["io"]["reviewed"] = []
    assert not export_plan([c], {0})["included"]
