"""Second-reader audits against private PDFs: Poppler words, exported HTML and geometry.

Unlike test_references, decoding here uses an independent PDF implementation.
Image labels embedded in pixels are not OCRed and require visual review.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

from engine import MARKER, parse_pdf
from reviewed_notes import without_cloze
from test_review_regressions import BodyText

PDF_NAMES = ["Anki 2 HISTO.pdf", "Anki 1 BIO.pdf", "Anki 2 ANTHROPO .pdf"]


def positioned_line(words):
    # Poppler splits the lowered digit in O₂/O2 into a separate word even
    # though the glyphs touch (measured gap -0.002 pt in the biology PDF).
    # Join only touching glyph boxes; real word spaces remain significant.
    parts = []
    previous = None
    for word in words:
        if previous is not None and word[0] - previous[2] > 0.1:
            parts.append(" ")
        parts.append(word[4])
        previous = word
    return "".join(parts)


def tokens(value):
    return re.findall(r"\w+|[^\w\s]", value)


class Rendered(BodyText):
    def __init__(self):
        super().__init__()
        self.images = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        attrs = dict(attrs)
        if tag == "img":
            self.images.append(attrs["src"])
        if tag == "div" and "data-level" in attrs:
            self.rows.append(attrs)


@pytest.mark.parametrize("filename", PDF_NAMES)
def test_poppler_word_order_punctuation_indentation_and_rendered_images(filename):
    path = Path(os.environ.get("ANKI_REFERENCE_DIR", "tests/private-pdfs")) / filename
    if not path.exists():
        pytest.skip(f"Private PDF unavailable: {filename}")
    if not shutil.which("pdftotext"):
        pytest.skip("Poppler pdftotext unavailable")
    xml = subprocess.check_output(["pdftotext", "-bbox-layout", str(path), "-"])
    root = ET.fromstring(xml)
    ns = {"p": "http://www.w3.org/1999/xhtml"}
    pages = root.findall(".//p:page", ns)
    words = [
        [
            (
                float(w.attrib["xMin"]),
                float(w.attrib["yMin"]),
                float(w.attrib["xMax"]),
                float(w.attrib["yMax"]),
                w.text or "",
            )
            for w in page.findall(".//p:word", ns)
        ]
        for page in pages
    ]
    # Independently locate markers and track every Poppler word, including
    # words on lines the main extractor might otherwise omit altogether.
    marker_words = set()
    marker_positions = []
    for pi, page in enumerate(pages):
        for line in page.findall(".//p:line", ns):
            nodes = line.findall("p:word", ns)
            if MARKER.fullmatch(" ".join(w.text or "" for w in nodes)):
                marker_positions.append((pi, float(line.attrib["yMin"])))
                for w in nodes:
                    marker_words.add(
                        (
                            pi,
                            (
                                float(w.attrib["xMin"]),
                                float(w.attrib["yMin"]),
                                float(w.attrib["xMax"]),
                                float(w.attrib["yMax"]),
                                w.text or "",
                            ),
                        )
                    )
    covered = set()
    cards = parse_pdf(path.read_bytes())
    assert len(marker_positions) == len(cards)
    for card in cards:
        expected = []
        first_x = {}
        for e in card["source_elements"]:
            if e["kind"] != "text":
                continue
            if not e["text"]:
                x0, y0, x1, y1 = e["bbox"]
                covered.update(
                    (e["page"], w)
                    for w in words[e["page"]]
                    if x0 - 0.2 <= w[0]
                    and w[2] <= x1 + 0.2
                    and y0 - 0.2 <= (w[1] + w[3]) / 2 <= y1 + 0.2
                )
                continue
            x0, y0, x1, y1 = e["bbox"]
            line = sorted(
                [
                    w
                    for w in words[e["page"]]
                    if e["text_x"] - 0.2 <= w[0]
                    and w[2] <= x1 + 0.2
                    and y0 - 0.2 <= (w[1] + w[3]) / 2 <= y1 + 0.2
                ],
                key=lambda w: w[0],
            )
            assert line, (filename, card["id"], e["original_text"])
            covered.update((e["page"], w) for w in line)
            expected.extend(tokens(positioned_line(line)))
            first_x[e["source_id"]] = line[0][0]
        rendered = Rendered()
        rendered.feed(card["back"])
        # Context repeats source ancestors intentionally; audit only this card's
        # own heading and back to avoid hiding lost content behind duplicates.
        own_title = "" if card.get("source_partitioned") else card["title"] + "\n"
        actual = tokens(without_cloze(own_title + "".join(rendered.fragments)))
        assert actual == expected, (filename, card["id"], actual, expected)
        image_blocks = [b for b in card["blocks"] if b["kind"] == "image"]
        assert rendered.images == [b["media_name"] for b in image_blocks]
        assert [
            (b["page"], b["bbox"][1], b["bbox"][0]) for b in image_blocks
        ] == sorted((b["page"], b["bbox"][1], b["bbox"][0]) for b in image_blocks)
        body_text = [b for b in card["blocks"] if b["kind"] == "text" and b["text"]]
        anchors = [first_x[b["source_id"]] for b in body_text] + [
            b["bbox"][0] for b in image_blocks
        ]
        if anchors:
            origin = min(anchors)
            for b in body_text:
                assert b["text_x"] == pytest.approx(first_x[b["source_id"]], abs=0.02)
                assert b["indent"] == pytest.approx(
                    first_x[b["source_id"]] - origin, abs=0.02
                )
        # Read back CSS actually emitted, not merely level metadata in JSON.
        text_blocks = [
            b
            for b in card["blocks"]
            if b["kind"] == "text"
            and not (b.get("image_association") and not b.get("text"))
        ]
        assert len(rendered.rows) == len(text_blocks)
        for row, block in zip(rendered.rows, text_blocks):
            margin = float(re.search(r"margin-left:([0-9.]+)px", row["style"])[1])
            assert margin == pytest.approx(block["indent"] + 24, abs=0.02)
            assert int(row["data-level"]) == block["level"]

    first = min(marker_positions)
    all_course_words = {
        (pi, w)
        for pi, page_words in enumerate(words)
        for w in page_words
        if (pi, w[1]) >= first and (pi, w) not in marker_words
    }
    assert not (all_course_words - covered), (
        filename,
        sorted(all_course_words - covered),
    )
