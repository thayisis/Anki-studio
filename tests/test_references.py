"""Optional private lecture PDFs. Real checks skip explicitly when files unavailable.

Set ANKI_REFERENCE_DIR to a directory holding the original filenames below.
PDFs are never committed. Counts below are hypotheses checked independently
against raw PyMuPDF lines before checking the converter.
"""

import os
from pathlib import Path
from collections import Counter
import hashlib

import pymupdf as fitz
import pytest

from engine import MARKER, extract_elements, parse_pdf
from exporter import build_apkg
from reviewed_notes import without_cloze

REFERENCE_DIR = Path(os.environ.get("ANKI_REFERENCE_DIR", "tests/private-pdfs"))


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("Anki 2 ANTHROPO .pdf", {"CARTE": 9, "CARTE CLOZE": 1, "CARTE OCCLUSION": 1}),
        ("Anki 2 HISTO.pdf", {"CARTE": 16}),
        ("Anki 1 BIO.pdf", {"CARTE": 48, "CARTE CLOZE": 3, "CARTE OCCLUSION": 7}),
    ],
)
def test_reference_marker_counts_and_no_text_loss(filename, expected):
    path = REFERENCE_DIR / filename
    if not path.exists():
        pytest.skip(f"Original unavailable: {filename}")
    data = path.read_bytes()
    with fitz.open(stream=data, filetype="pdf") as doc:
        # Independent raw-line count, no converter boundary logic.
        raw_markers = Counter(
            " ".join(line.upper().split())
            for page in doc
            for line in page.get_text().splitlines()
            if MARKER.fullmatch(line.strip())
        )
        extracted = extract_elements(doc)
    assert raw_markers == expected, (
        "Previously reported marker counts differ from the actual PDF"
    )
    # Independent dictionary extraction verifies original physical lines and
    # image placements, not just the converter's own provenance bookkeeping.
    with fitz.open(stream=data, filetype="pdf") as doc:
        lines = [
            (
                pi,
                line["bbox"][1],
                "".join(span["text"] for span in line["spans"]).strip(),
            )
            for pi, page in enumerate(doc)
            for block in page.get_text("dict")["blocks"]
            if block["type"] == 0
            for line in block["lines"]
        ]
        first_position = min(
            (pi, y) for pi, y, value in lines if MARKER.fullmatch(value)
        )
        direct_text = Counter(
            value
            for pi, y, value in lines
            if value and (pi, y) >= first_position and not MARKER.fullmatch(value)
        )
        direct_images = [
            (pi, tuple(block["bbox"]))
            for pi, page in enumerate(doc)
            for block in page.get_text("dict")["blocks"]
            if block["type"] == 1
        ]
    cards = parse_pdf(data)
    assert (
        Counter(
            e["original_text"]
            for c in cards
            for e in c["source_elements"]
            if e["kind"] == "text"
        )
        == direct_text
    )
    parsed_images = [
        (e["page"], e["bbox"])
        for c in cards
        for e in c["source_elements"]
        if e["kind"] == "image"
    ]
    assert sorted(parsed_images) == sorted(direct_images)
    assert (
        len(parsed_images)
        == {"Anki 2 HISTO.pdf": 49, "Anki 1 BIO.pdf": 43, "Anki 2 ANTHROPO .pdf": 1}[
            filename
        ]
    )
    assert Counter(c["type"] for c in cards) == raw_markers
    first = next(
        i
        for i, e in enumerate(extracted)
        if e["kind"] == "text" and MARKER.fullmatch(e["original_text"])
    )
    expected_ids = {
        e["source_id"]
        for e in extracted[first:]
        if not (e["kind"] == "text" and MARKER.fullmatch(e["original_text"]))
    }
    actual_ids = {e["source_id"] for c in cards for e in c["source_elements"]}
    assert actual_ids == expected_ids
    for c in cards:
        represented = set(c["title_source_ids"]) | {b["source_id"] for b in c["blocks"]}
        represented |= {b["bullet_source"] for b in c["blocks"] if "bullet_source" in b}
        assert represented == {e["source_id"] for e in c["source_elements"]}
        assert c["back"].count("<img") == sum(
            e["kind"] == "image" for e in c["source_elements"]
        )
        # Every physical source text survives either in the title, a body line,
        # or the preserved bullet attached to that line (no word normalization).
        for e in c["source_elements"]:
            if e["kind"] != "text" or not e["text"]:
                continue
            assert e["text"] in c["title"] or any(
                e["text"] == without_cloze(b.get("text", "")) for b in c["blocks"]
            )
    payload, plan = build_apkg(
        cards, set(range(len(cards))), path.stem, hashlib.sha256(data).hexdigest()
    )
    assert (
        plan["notes"]
        == {"Anki 2 HISTO.pdf": 16, "Anki 1 BIO.pdf": 51, "Anki 2 ANTHROPO .pdf": 10}[
            filename
        ]
    )
    empty_answers = {
        i + 1
        for i, c in enumerate(cards)
        if c["type"] == "CARTE"
        and not any(
            b["kind"] == "image" or b.get("text", "").strip() for b in c["blocks"]
        )
    }
    assert (
        empty_answers
        == {
            "Anki 2 HISTO.pdf": set(),
            "Anki 1 BIO.pdf": set(),
            "Anki 2 ANTHROPO .pdf": set(),
        }[filename]
    )
    if "ANTHROPO" in filename:
        assert plan["notes"] == 10 and plan["cards"] == 10
        assert cards[8]["type"] == "CARTE OCCLUSION" and len(cards[8]["media"]) == 1
        assert all(cards[i]["context"] == ["Descola"] for i in (3, 4, 5, 6, 7, 9, 10))
        assert (
            "Un organisme domestique est somewhat dependent de l’humain"
            in cards[3]["back"]
        )
        assert max(b["level"] for b in cards[3]["blocks"]) >= 3


@pytest.mark.parametrize(
    "index,title,expected_text,image_count",
    [
        (
            0,
            "Glandes exocrines : sécrétion déversée dans le milieu extérieur",
            [
                "Critères de reconnaissance:",
                "Cellules étroitement associées",
                "Cellules reposent sur une lame basale",
                "Cellules différenciées",
                "Cellules en contact avec une cavité",
                "Cellules généralement polarisées (noyau basal, sécrétion apicale)",
                "Classification et diagnostic :",
                "Mode et nature de la sécrétion (*mode —> nature)",
            ],
            0,
        ),
        (
            1,
            "Mérocrine (exocytose de vésicules) —> séreuse (ou protéique)",
            [
                "*meros = une partie",
                "Sécrétion protéique (= enzymes)",
                "Sécrétion de sueur (= eau, sels, urée, …)",
                "Exocytose du contenu des grains de sécrétion un par un",
                "Rôle: production d’enzymes digestives ou élimination",
                "Où: pancréas, glandes salivaires, glandes sudoripares de la peau",
            ],
            4,
        ),
        (
            2,
            "Apocrine (perte de la partie apicale) —> muqueuse (ou mucigène, protéine glycosylée)",
            [
                "*apocrino = séparer",
                "Sécrétion de mucine ou mucigène (gel visqueux, très hydraté, formé de protéines sucrées ou mucopolysaccharides) mucine = protéine avec cystéines (pont",
                "S-S) aux extrémités; sérine et thréonine au centre (enrobage sucré + groupements sulfate et carboxyl —> pouvoir hygroscopique et en coloration: PAS et",
                "mucicarmin positifs)",
                "Expulsion en bloc du mucigène",
                "Rôle: protection d’épithelium de revêtements (acidité gastrique, bouche pâteuse: hydrater le mucus)",
                "Où: intestin, estomac, trachée",
            ],
            2,
        ),
    ],
)
def test_real_histology_key_cards(index, title, expected_text, image_count):
    """Transcribed from the supplied compressed Histo PDF, checked against its source crop."""
    path = REFERENCE_DIR / "Anki 2 HISTO.pdf"
    if not path.exists():
        pytest.skip("Histology reference unavailable")
    cards = parse_pdf(path.read_bytes())
    c = cards[index]
    assert c["title"] == title
    text = [b for b in c["blocks"] if b["kind"] == "text" and b["text"]]
    assert [b["text"] for b in text] == expected_text
    assert len(c["media"]) == image_count
    images = [b for b in c["blocks"] if b["kind"] == "image"]
    assert [b["media_name"] for b in images] == [name for name, _ in c["media"]]
    assert [b["bbox"][1] for b in images] == sorted(b["bbox"][1] for b in images)
    assert [c["back"].index(b["media_name"]) for b in images] == sorted(
        c["back"].index(b["media_name"]) for b in images
    )
    assert title not in c["back"]
    if index == 0:
        assert c["context"] == []
        assert [b["level"] for b in text] == [0, 1, 1, 1, 1, 1, 0, 1]
        assert [b["indent"] for b in text] == [
            0,
            20.02,
            20.02,
            20.02,
            20.02,
            20.02,
            0,
            20.02,
        ]
    else:
        assert c["context"] == [
            cards[0]["title"],
            "Classification et diagnostic :",
            "Mode et nature de la sécrétion (*mode —> nature)",
        ]
        assert all(b["level"] == 0 and b["indent"] == 0 for b in text)
        linked = [b for b in c["blocks"] if b.get("image_association")]
        assert len(linked) == image_count
        # Orphan glyphs are displayed beside images, never as empty extra points.
        assert c["back"].count("data-level=") == len(text)
    if index == 2:
        assert [b["continuation"] for b in text] == [
            False,
            False,
            True,
            True,
            False,
            False,
            False,
        ]
    assert cards[4]["context"][-1] == "Morphologie"
    assert "Mode et nature" not in " ".join(cards[4]["context"])


def test_real_biology_scientific_digit_preserved_in_html():
    path = REFERENCE_DIR / "Anki 1 BIO.pdf"
    if not path.exists():
        pytest.skip("Biology reference unavailable")
    card = parse_pdf(path.read_bytes())[29]
    assert (
        'O<span style="font-size:66.6666%;vertical-align:0em">2 </span>)'
        in card["back"]
    )
