"""Synthetic PDFs: these are not the user's lecture documents."""

import pymupdf as fitz
from engine import parse_pdf


def pdf(lines=(), image=False, height=842):
    doc = fitz.open()
    page = doc.new_page(width=600, height=height)
    for x, y, text in lines:
        page.insert_text((x, y), text)
    if image:
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 60), False)
        pix.clear_with(120)
        page.insert_image(fitz.Rect(70, 130, 270, 250), pixmap=pix)
    return doc.tobytes()


def test_image_only_card_is_not_discarded():
    cards = parse_pdf(pdf([(40, 40, "CARTE OCCLUSION")], image=True))
    assert len(cards) == 1
    assert len(cards[0]["media"]) == 1


def test_empty_marker_is_reported():
    assert len(parse_pdf(pdf([(40, 40, "CARTE"), (40, 80, "CARTE")]))) == 2


def test_wrapped_front_does_not_swallow_indented_body():
    cards = parse_pdf(
        pdf(
            [
                (40, 40, "CARTE"),
                (60, 70, "First title line"),
                (60, 85, "second title line"),
                (90, 110, "Body sentence."),
            ]
        )
    )
    assert "second title line" in cards[0]["front"]
    assert "Body sentence." in cards[0]["back"]


def test_symbols_are_not_discarded():
    cards = parse_pdf(pdf([(40, 40, "CARTE"), (60, 70, "Title"), (90, 100, "®")]))
    assert "®" in cards[0]["back"]
