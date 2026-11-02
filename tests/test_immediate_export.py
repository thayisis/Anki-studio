"""V9 contract: literal content, paragraphs and independent export readiness."""

import os
from pathlib import Path

import pytest

from engine import definition_split, parse_pdf, render_blocks
from exporter import export_plan, export_reason, content_warnings
from test_export import sample
from test_pdf_audit import Rendered, tokens
from reviewed_notes import without_cloze
from test_regressions import pdf


def test_definitions_move_once_but_categories_and_trailing_colons_do_not():
    assert definition_split("Catégorie : Sous-catégorie") is None
    assert definition_split("Classification :") is None
    c = parse_pdf(
        pdf(
            [
                (40, 40, "CARTE"),
                (40, 70, "Concept : est une explication exacte."),
                (60, 110, "- Suite."),
            ]
        )
    )[0]
    assert c["title"] == "Concept"
    assert c["blocks"][0]["text"] == ": est une explication exacte."
    assert c["back"].count("explication exacte.") == 1
    assert "explication" not in c["front"]
    assert not any("Texte modifié" in w for w in content_warnings(c))


def test_bad_hierarchy_and_missing_images_only_exclude_affected_card():
    cards = sample()
    cards[0]["blocks"][0]["indent"] = float("nan")
    plan = export_plan(cards, set())
    assert plan["included"] == [1]
    assert "Hiérarchie" in plan["excluded"][0]["reason"]
    cards = sample()
    cards[0]["blocks"] = [b for b in cards[0]["blocks"] if b["kind"] != "image"]
    assert "Images" in export_reason(cards[0])


def test_modified_text_is_never_silently_called_faithful():
    cards = sample()
    cards[0]["blocks"][0]["text"] = "Truncated."
    report = export_plan(cards, set())
    assert 0 in report["included"]
    assert any(
        w["index"] == 0 and "incomplet" in w["reason"] for w in report["warnings"]
    )


@pytest.mark.parametrize(
    "filename,count",
    [("Anki 2 HISTO.pdf", 16), ("Anki 1 BIO.pdf", 51), ("Anki 2 ANTHROPO .pdf", 10)],
)
def test_real_pdfs_export_without_any_manual_validation(filename, count):
    path = Path(os.environ.get("ANKI_REFERENCE_DIR", "tests/private-pdfs")) / filename
    if not path.exists():
        pytest.skip("Private PDF unavailable")
    cards = parse_pdf(path.read_bytes())
    report = export_plan(cards, set())
    assert report["notes"] == count
    assert all(
        cards[e["index"]]["type"] == "CARTE OCCLUSION" for e in report["excluded"]
    )
    assert not any("Texte modifié" in w["reason"] for w in report["warnings"])
    for c in cards:
        assert len(c["context"]) <= 1
        parser = Rendered()
        parser.feed(c["back"])
        body = without_cloze("".join(parser.fragments))
        own = "" if c.get("source_partitioned") else c["title"]
        source = " ".join(
            e["text"] for e in c["source_elements"] if e["kind"] == "text"
        )
        assert tokens(own + " " + body) == tokens(source)
        if c.get("definition_moved"):
            assert ":" not in c["title"]
            assert c["blocks"][0]["moved_definition"]
    if "HISTO" in filename:
        c = cards[2]
        assert (
            c["title"]
            == "Apocrine (perte de la partie apicale) —> muqueuse (ou mucigène, protéine glycosylée)"
        )
        assert "Classification et diagnostic" not in c["front"]
        assert "Glandes exocrines" not in c["front"]
        parser = Rendered()
        parser.feed(c["back"])
        assert len(parser.rows) == 5
        assert c["back"].count("<img") == 2
        assert "(pont S-S) aux extrémités" in c["back"]
        assert "PAS et mucicarmin positifs)" in c["back"]
        assert parser.images == [
            e["media_name"] for e in c["source_elements"] if e["kind"] == "image"
        ]


def test_altered_source_image_is_blocking():
    cards = sample()
    name, raw = cards[0]["media"][0]
    cards[0]["media"][0] = (name, raw + b"alteration")
    assert "Média altéré" in export_reason(cards[0])
    assert export_plan(cards, set())["included"] == [1]


def test_multiline_definition_wraps_are_display_whitespace_only():
    c = dict(
        kind="text",
        text=": exact first line\nexact continuation",
        moved_definition=True,
    )
    rendered = render_blocks([c])
    assert ": exact first line exact continuation" in rendered
    assert c["text"] == ": exact first line\nexact continuation"
    assert rendered.count("data-level=") == 1
