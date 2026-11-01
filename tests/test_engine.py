"""Synthetic geometry regressions; never stand in for lecture-PDF validation."""

import html
from collections import Counter

import pymupdf as fitz

from engine import parse_pdf, crop, preview_html
from test_regressions import pdf


def test_single_line_card_preserves_the_whole_sentence():
    cards = parse_pdf(
        pdf([(40, 40, "CARTE"), (60, 70, "An entire sentence, not a summary.")])
    )
    assert cards[0]["title"] == "An entire sentence, not a summary."
    assert cards[0]["back"] == ""
    assert cards[0]["warnings"]


def test_wrapped_body_and_new_bullets_remain_separate():
    c = parse_pdf(
        pdf(
            [
                (40, 40, "CARTE"),
                (40, 70, "Title"),
                (70, 110, "- A long sentence"),
                (80, 125, "continued here; exactly."),
                (70, 140, "- Another point."),
            ]
        )
    )[0]
    texts = [b["text"] for b in c["blocks"]]
    assert texts == ["A long sentence", "continued here; exactly.", "Another point."]
    assert [b["bullet"] for b in c["blocks"]] == [True, False, True]
    assert c["back"].count("<div ") == 3


def test_nested_levels_from_text_position_not_glyph():
    c = parse_pdf(
        pdf(
            [(40, 40, "CARTE"), (40, 70, "Title")]
            + [(60 + i * 25, 110 + i * 25, "- Level " + str(i)) for i in range(7)]
        )
    )[0]
    assert [b["level"] for b in c["blocks"]] == list(range(7))
    assert [b["indent"] for b in c["blocks"]] == [i * 25 for i in range(7)]


def test_orphan_bullet_retained_and_associated_with_image():
    c = parse_pdf(
        pdf([(40, 40, "CARTE"), (40, 70, "Title"), (50, 170, "-")], image=True)
    )[0]
    orphan = next(b for b in c["blocks"] if b["kind"] == "text")
    assert orphan["image_association"] == c["media"][0][0]
    assert "-" in c["back"]


def test_isolated_bullet_without_image_is_reported():
    c = parse_pdf(pdf([(40, 40, "CARTE"), (40, 70, "Title"), (50, 170, "-")]))[0]
    assert any("Puce isolée" in w for w in c["warnings"])
    assert "-" in c["back"]


def test_mixed_images_keep_their_position_and_readable_resolution():
    c = parse_pdf(
        pdf(
            [
                (40, 40, "CARTE"),
                (40, 70, "Title"),
                (60, 110, "Before image."),
                (60, 290, "After image."),
            ],
            image=True,
        )
    )[0]
    assert (
        c["back"].index("Before image.")
        < c["back"].index("<img")
        < c["back"].index("After image.")
    )
    image = fitz.Pixmap(c["media"][0][1])
    assert image.width >= 400
    assert "data:image/png;base64," in preview_html(c["back"], c["media"])


def test_long_single_page_card_and_all_markers():
    data = pdf(
        [
            (40, 40, "CARTE"),
            (40, 70, "Title"),
            (80, 9500, "Last sentence."),
            (40, 9600, "CARTE CLOZE"),
            (40, 9640, "{{c1::Text}}"),
            (40, 9800, "CARTE OCCLUSION"),
        ],
        height=10000,
    )
    cards = parse_pdf(data)
    assert Counter(c["type"] for c in cards) == {
        "CARTE": 1,
        "CARTE CLOZE": 1,
        "CARTE OCCLUSION": 1,
    }
    assert "Last sentence." in cards[0]["back"]
    pix = fitz.Pixmap(crop(data, cards[0]))
    assert pix.width * pix.height <= 16_100_000
    assert cards[2]["front"] == "" and cards[2]["warnings"]


def test_cross_page_card_continues_until_next_marker():
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((40, 40), "CARTE")
    p.insert_text((40, 70), "Title")
    p.insert_text((70, 110), "First page content.")
    p = doc.new_page()
    p.insert_text((70, 40), "Second page continuation.")
    p.insert_text((40, 100), "CARTE")
    p.insert_text((40, 130), "Other title")
    cards = parse_pdf(doc.tobytes())
    assert len(cards) == 2
    assert "Second page continuation." in cards[0]["back"]
    assert len(cards[0]["regions"]) == 2
    assert crop(doc.tobytes(), cards[0], region_index=1).startswith(b"\x89PNG")


def test_heading_context_only_from_styled_shallower_headings():
    doc = fitz.open()
    p = doc.new_page()
    for x, y, text, bold in [
        (40, 40, "CARTE", False),
        (40, 70, "Glandes exocrines", True),
        (70, 100, "Do not prepend this sentence.", False),
        (60, 140, "CARTE", False),
        (80, 170, "Mérocrine", True),
        (100, 210, "Exact secretion wording.", False),
        (60, 250, "CARTE", False),
        (80, 280, "Apocrine", True),
        (100, 320, "Other wording.", False),
    ]:
        p.insert_text((x, y), text, fontname="hebo" if bold else "helv")
    cards = parse_pdf(doc.tobytes())
    assert html.unescape(cards[1]["front"]) == "Glandes exocrines — Mérocrine"
    assert html.unescape(cards[2]["front"]) == "Glandes exocrines — Apocrine"
    assert "Do not prepend" not in cards[1]["front"]
    assert "Mérocrine" not in cards[2]["front"]
    assert "Mérocrine" not in cards[1]["back"]


def test_image_before_text_is_not_removed_or_mislabeled_as_title():
    c = parse_pdf(
        pdf([(40, 40, "CARTE"), (60, 290, "Caption after image")], image=True)
    )[0]
    assert c["front"] == ""
    assert c["back"].index("<img") < c["back"].index("Caption after image")


def test_vector_diagram_preserved():
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((40, 40), "CARTE")
    p.insert_text((40, 70), "Diagram")
    p.draw_rect(fitz.Rect(70, 110, 200, 220), color=(1, 0, 0))
    cards = parse_pdf(doc.tobytes())
    assert len(cards[0]["media"]) == 1
    assert any("vectoriel" in w for w in cards[0]["warnings"])


def test_separate_bullet_and_text_baselines_preserve_all_text():
    c = parse_pdf(
        pdf(
            [
                (40, 40, "CARTE"),
                (40, 70, "Title"),
                (60, 110, "-"),
                (80, 108, "Actual point"),
                (80, 124, "continuation"),
            ]
        )
    )[0]
    assert len(c["blocks"]) == 2
    assert c["blocks"][0]["bullet"]
    assert c["blocks"][0]["text"] == "Actual point"
    assert c["blocks"][1]["continuation"]


def test_bold_heading_does_not_consume_plain_body_at_same_indent():
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((40, 40), "CARTE")
    p.insert_text((40, 70), "Heading", fontname="hebo")
    p.insert_text((40, 85), "Actual answer.", fontname="helv")
    c = parse_pdf(doc.tobytes())[0]
    assert c["title"] == "Heading"
    assert "Actual answer." in c["back"]


def test_full_page_background_does_not_hide_vector_diagram():
    doc = fitz.open()
    p = doc.new_page()
    p.draw_rect(p.rect, fill=(1, 1, 1))
    p.insert_text((40, 40), "CARTE")
    p.insert_text((40, 70), "Diagram")
    p.draw_rect(fitz.Rect(70, 110, 200, 220), color=(1, 0, 0))
    assert len(parse_pdf(doc.tobytes())[0]["media"]) == 1


def test_same_baseline_columns_are_reported():
    c = parse_pdf(
        pdf(
            [
                (40, 40, "CARTE"),
                (40, 70, "Title"),
                (60, 110, "Left fragment"),
                (350, 110, "Right fragment"),
            ]
        )
    )[0]
    assert "Left fragment" in c["back"] and "Right fragment" in c["back"]
    assert any("Colonnes" in w for w in c["warnings"])


def test_synthetic_reference_concepts_keep_exact_text_and_image_order():
    # These names are from the brief; all content below is synthetic, not
    # a transcription or claimed validation of the inaccessible Histo PDF.
    doc = fitz.open()
    p = doc.new_page()
    for x, y, t, b in [
        (40, 40, "CARTE", False),
        (40, 70, "Glandes exocrines", True),
        (60, 100, "Synthetic parent text.", False),
        (60, 150, "CARTE", False),
        (80, 180, "Mérocrine", True),
        (100, 210, "- Exact wording; symbols: ®.", False),
        (130, 240, "- Nested point.", False),
        (107, 350, "After first image.", False),
        (60, 450, "CARTE", False),
        (80, 480, "Apocrine", True),
        (100, 520, "Second synthetic explanation.", False),
    ]:
        p.insert_text((x, y), t, fontname="hebo" if b else "helv")
    for rect, color in [
        (fitz.Rect(100, 270, 160, 330), 60),
        (fitz.Rect(100, 370, 160, 430), 180),
    ]:
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 60), False)
        pix.clear_with(color)
        p.insert_image(rect, pixmap=pix)
    cards = parse_pdf(doc.tobytes())
    c = cards[1]
    assert html.unescape(c["front"]) == "Glandes exocrines — Mérocrine"
    assert [b["text"] for b in c["blocks"] if b["kind"] == "text"] == [
        "Exact wording; symbols: ®.",
        "Nested point.",
        "After first image.",
    ]
    assert [b["level"] for b in c["blocks"] if b["kind"] == "text"] == [0, 1, 0]
    assert len(c["media"]) == 2
    assert (
        c["back"].index(c["media"][0][0])
        < c["back"].index("After first image.")
        < c["back"].index(c["media"][1][0])
    )
    assert html.unescape(cards[2]["front"]) == "Glandes exocrines — Apocrine"


def test_hanging_bullet_does_not_shift_content_relative_to_continuation():
    from engine import render_blocks

    back = render_blocks(
        [
            dict(
                kind="text",
                text="First line",
                indent=0,
                level=0,
                bullet=True,
                bullet_text="-",
            ),
            dict(kind="text", text="Continuation", indent=0, level=0, bullet=False),
        ]
    )
    assert back.count("margin-left:24px") == 2
    assert "position:absolute;right:100%" in back


def test_image_left_of_text_preserves_relative_horizontal_position():
    c = parse_pdf(
        pdf(
            [
                (40, 40, "CARTE"),
                (40, 70, "Title"),
                (110, 110, "Before image."),
                (110, 290, "After image."),
            ],
            image=True,
        )
    )[0]
    blocks = c["blocks"]
    assert blocks[0]["indent"] == 40
    assert blocks[1]["indent"] == 0
    assert blocks[2]["indent"] == 40


def test_plain_indentation_outline_provides_parents_across_card_markers():
    doc = fitz.open()
    p = doc.new_page()
    for x, y, t in [
        (40, 40, "CARTE"),
        (40, 70, "Parent concept"),
        (60, 100, "-"),
        (85, 100, "Classification"),
        (85, 120, "-"),
        (105, 120, "Mode of secretion"),
        (40, 150, "CARTE"),
        (120, 180, "-"),
        (140, 180, "First subtype"),
        (160, 210, "-"),
        (177, 210, "Explanation one."),
        (40, 250, "CARTE"),
        (120, 280, "-"),
        (140, 280, "Second subtype"),
        (160, 310, "-"),
        (177, 310, "Explanation two."),
    ]:
        p.insert_text((x, y), t)
    cards = parse_pdf(doc.tobytes())
    assert cards[1]["context"] == [
        "Parent concept",
        "Classification",
        "Mode of secretion",
    ]
    assert cards[2]["context"] == cards[1]["context"]
    assert "Explanation one." not in cards[2]["front"]
