"""Regression cases explicitly reviewed on the user's actual lecture passages."""

import os
from pathlib import Path

import pytest

from engine import parse_pdf, render_blocks
from exporter import export_reason, fields_for, cloze_numbers
from reviewed_notes import RECIPES, recipe_for, without_cloze, normalized
from cloze_preview import preview_cloze
from test_review_regressions import BodyText
from test_regressions import pdf

CASES = [
    ("Anki 1 BIO.pdf", 15, "bio-polymer"),
    ("Anki 1 BIO.pdf", 16, "bio-dehydration"),
    ("Anki 1 BIO.pdf", 17, "bio-hydrolysis"),
    ("Anki 1 BIO.pdf", 53, "bio-symbiosis"),
    ("Anki 2 ANTHROPO .pdf", 6, "anthro-domestic-nature"),
    ("Anki 2 ANTHROPO .pdf", 7, "anthro-beyond-nature-culture"),
    ("Anki 1 BIO.pdf", 4, "bio-energy-cloze"),
    ("Anki 1 BIO.pdf", 5, "bio-evolution-cloze"),
    ("Anki 1 BIO.pdf", 54, "bio-endosymbiosis-cloze"),
    ("Anki 2 ANTHROPO .pdf", 1, "anthro-subcultures-cloze"),
]


@pytest.mark.parametrize("filename,index,recipe_id", CASES)
def test_exact_reviewed_partition_on_original_pdf(filename, index, recipe_id):
    path = Path(os.environ.get("ANKI_REFERENCE_DIR", "tests/private-pdfs")) / filename
    if not path.exists():
        pytest.skip("Private PDF unavailable")
    card = parse_pdf(path.read_bytes())[index]
    recipe = next(r for r in RECIPES if r["id"] == recipe_id)
    assert card["reviewed_recipe"] == recipe_id
    assert card["title"] == recipe["title"]
    assert card["title"] in card["source_title"]
    assert export_reason(card) is None
    parser = BodyText()
    parser.feed(render_blocks(card["blocks"]))
    actual = without_cloze("".join(parser.fragments))
    source = "\n".join(
        e["text"] for e in card["source_elements"] if e["kind"] == "text" and e["text"]
    )
    assert actual == source  # Exact original physical lines, spaces and punctuation.
    assert normalized(actual) == normalized(recipe["source"])
    assert card["source_title_restored"]
    assert card["title_source_ids"] == []
    if "deletion" in recipe:
        value = fields_for(card)[0]
        assert cloze_numbers(value) == {1}
        assert value.count("{{c1::" + recipe["deletion"] + "}}") == 1
        question = BodyText()
        question.feed(preview_cloze(value))
        answer = BodyText()
        answer.feed(preview_cloze(value, answer=True))
        assert recipe["deletion"] not in "".join(question.fragments)
        assert normalized("".join(answer.fragments)) == normalized(source)
        assert value == render_blocks(
            card["blocks"]
        )  # No separate title or hint leaks the answer.
    else:
        assert "{{c" not in card["back"]
    if "ANTHROPO" in filename and index in (6, 7):
        assert card["context"] == ["Descola"]


@pytest.mark.parametrize("recipe", RECIPES, ids=lambda r: r["id"])
def test_recipe_matching_fails_closed_for_modified_source_or_wrong_note_type(recipe):
    assert recipe_for(recipe["type"], recipe["source"]) == recipe
    assert recipe_for(recipe["type"], recipe["source"] + " Added word.") is None
    assert recipe_for("UNKNOWN", recipe["source"]) is None


def test_small_unrelated_definition_is_not_rewritten():
    c = parse_pdf(pdf([(40, 40, "CARTE"), (40, 70, "Unreviewed = other content")]))[0]
    assert not c.get("source_partitioned")
    assert export_reason(c).startswith("Verso vide")


def test_preview_hides_only_the_active_cloze_like_native_anki():
    value = "{{c1::First}} and {{c2::Second}}"
    question = BodyText()
    question.feed(preview_cloze(value, active_number=1))
    assert "First" not in "".join(question.fragments) and "Second" in "".join(
        question.fragments
    )
    answer = BodyText()
    answer.feed(preview_cloze(value, answer=True, active_number=1))
    assert "".join(answer.fragments) == "First and Second"


@pytest.mark.parametrize("recipe", RECIPES, ids=lambda r: r["id"])
def test_reviewed_transformation_in_synthetic_unicode_pdf_without_private_files(recipe):
    """CI exercises the transform; real-PDF cases separately verify the transcription."""
    import copy
    import pymupdf as fitz
    from engine import apply_reviewed_partition

    doc = fitz.open()
    p = doc.new_page(width=3000, height=200)
    font = fitz.Font("cjk")
    p.insert_font(fontname="source", fontbuffer=font.buffer)
    p.insert_text((40, 40), recipe["type"], fontname="source")
    p.insert_text((40, 70), recipe["source"], fontname="source")
    c = parse_pdf(doc.tobytes())[0]
    assert c["reviewed_recipe"] == recipe["id"]
    assert export_reason(c) is None
    parser = BodyText()
    parser.feed(c["back"])
    assert without_cloze("".join(parser.fragments)) == recipe["source"]
    prior = copy.deepcopy(c)
    apply_reviewed_partition(c)
    assert c == prior
