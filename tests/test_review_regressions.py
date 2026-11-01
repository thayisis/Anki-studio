"""Defects found by critical review, beyond source-element bookkeeping."""

from html.parser import HTMLParser
from engine import parse_pdf, restore_source_title, update_edited_levels, render_blocks
from exporter import export_plan, export_reason
from test_regressions import pdf


class BodyText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fragments = []
        self.in_bullet = False

    def handle_starttag(self, tag, attrs):
        if tag == "span" and "position:absolute" in dict(attrs).get("style", ""):
            self.in_bullet = True

    def handle_endtag(self, tag):
        if tag == "span":
            self.in_bullet = False

    def handle_data(self, value):
        if not self.in_bullet:
            self.fragments.append(value)


def test_basic_with_no_answer_is_explicitly_excluded_until_recovered():
    c = parse_pdf(pdf([(40, 40, "CARTE"), (60, 70, "Full source sentence.")]))[0]
    assert "Verso vide" in export_reason(c)
    assert export_plan([c], {0})["included"] == []
    original = c["title"]
    restore_source_title(c, original)
    c["title"] = "Subject"
    c["front"] = "Subject"
    assert export_reason(c) is None
    assert c["blocks"][0]["text"] == original


def test_source_title_recovery_is_idempotent_and_keeps_user_corrections():
    c = {"blocks": []}
    restore_source_title(c, "Original text")
    c["blocks"][0]["text"] = "Corrected text"
    restore_source_title(c, "Original text")
    assert len(c["blocks"]) == 1 and c["blocks"][0]["text"] == "Corrected text"


def test_levels_follow_edited_indent_and_do_not_rewrite_text():
    blocks = [
        dict(kind="text", text="A", indent=0, level=0),
        dict(kind="text", text="B", indent=42, level=0),
        dict(kind="text", text="C", indent=0, level=1),
    ]
    assert update_edited_levels(blocks) == [0, 42]
    assert [b["level"] for b in blocks] == [0, 1, 0]
    assert [b["text"] for b in blocks] == ["A", "B", "C"]


def test_wingdings_normalization_does_not_alter_literal_symbols():
    blocks = [
        dict(kind="text", text="Real ® symbol", indent=0, bullet=True, bullet_text="®"),
        dict(kind="text", text="Numbered", indent=20, bullet=True, bullet_text="2."),
    ]
    value = render_blocks(blocks)
    assert ">•</span>Real ® symbol" in value
    assert ">2.</span>Numbered" in value
    parser = BodyText()
    parser.feed(value)
    assert "".join(parser.fragments).splitlines() == ["Real ® symbol", "Numbered"]


def test_wrapped_previous_paragraph_is_not_reused_as_a_section_label():
    import pymupdf as fitz

    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((40, 40), "CARTE")
    p.insert_text((40, 70), "Author", fontname="hebo")
    p.insert_text((70, 110), "- Introductory point")
    for x, y, text in [
        (40, 150, "CARTE"),
        (60, 180, "- This paragraph begins"),
        (66.7, 195, "and continues as a sentence."),
        (90, 230, "- A deeper point"),
        (40, 270, "CARTE"),
        (80, 300, "- Next concept"),
        (110, 340, "- Its answer"),
    ]:
        p.insert_text((x, y), text)
    cards = parse_pdf(doc.tobytes())
    assert cards[2]["context"] == ["Author"]
    assert "This paragraph" not in cards[2]["front"]


def test_scientific_small_digits_keep_their_sizing_and_edits_do_not_reuse_stale_runs():
    import pymupdf as fitz
    from engine import render_text

    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((40, 40), "CARTE")
    p.insert_text((40, 70), "Transport")
    p.insert_text((70, 110), "O", fontsize=12)
    x = 70 + fitz.get_text_length("O", fontsize=12)
    p.insert_text((x, 110), "2", fontsize=8)
    c = parse_pdf(doc.tobytes())[0]
    line = next(b for b in c["blocks"] if b.get("text") == "O2")
    assert "font-size:66.6667%" in c["back"]
    assert ">2</span>" in c["back"]
    line["text"] = "CO2"
    assert render_text(line) == "CO2"
