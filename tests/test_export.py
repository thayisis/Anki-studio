import io
import json
import sqlite3
import zipfile

import pytest

from engine import parse_pdf
from exporter import (
    build_apkg,
    export_plan,
    source_bundle,
    cloze_numbers,
    export_reason,
)
from test_regressions import pdf


def sample():
    return parse_pdf(
        pdf(
            [
                (40, 40, "CARTE"),
                (40, 70, "Basic title"),
                (70, 100, "Exact answer."),
                (40, 300, "CARTE CLOZE"),
                (40, 330, "Cloze title"),
                (70, 360, "{{c1::One}} {{c2::Two::hint}}"),
                (40, 400, "CARTE OCCLUSION"),
            ],
            image=True,
        )
    )


def db_for(payload, tmp_path):
    z = zipfile.ZipFile(io.BytesIO(payload))
    path = tmp_path / "collection.anki2"
    path.write_bytes(z.read("collection.anki2"))
    return sqlite3.connect(path), z


def test_partial_export_basic_and_native_cloze_with_media(tmp_path):
    cards = sample()
    payload, report = build_apkg(cards, {0, 1, 2}, "Test", "document-A")
    assert report["notes"] == 2 and report["cards"] == 3
    assert report["included"] == [0, 1]
    assert (
        len(report["excluded"]) == 1 and "Occlusion" in report["excluded"][0]["reason"]
    )
    db, z = db_for(payload, tmp_path)
    models = json.loads(db.execute("select models from col").fetchone()[0])
    assert {m["type"] for m in models.values()} == {0, 1}
    assert db.execute("select count(*) from notes").fetchone()[0] == 2
    assert db.execute("select count(*) from cards").fetchone()[0] == 3
    assert (
        db.execute("select flds from notes order by id")
        .fetchone()[0]
        .split("\x1f")[1]
        .count("<img")
        == 1
    )
    assert len(json.loads(z.read("media"))) == 1


def test_export_is_immediate_and_counts_are_exact():
    plan = export_plan(sample(), set())
    assert plan["included"] == [0, 1]
    assert plan["awaiting"] == 0 and len(plan["excluded"]) == 1
    payload, report = build_apkg(sample(), set(), "Test", "x")
    assert payload.startswith(b"PK") and report["notes"] == 2


@pytest.mark.parametrize(
    "text",
    [
        "no deletions",
        "{{c0::invalid}}",
        "{{c1::}}",
        "{{c1::x}",
        "{{c1::outer {{c2::nested}}}}",
        "{{c1:: ::hint}}",
    ],
)
def test_malformed_or_missing_clozes_are_not_exported(text):
    cards = sample()
    cards[1]["blocks"][0]["text"] = text
    assert export_reason(cards[1])
    assert export_plan(cards, {0, 1})["included"] == [0]


def test_multiple_deletions_same_number_make_one_card():
    assert cloze_numbers("{{c1::a}} {{c1::b}} {{c3::c}}") == {1, 3}


def test_empty_front_excluded_even_when_validated():
    c = sample()
    c[0]["front"] = " "
    assert 0 not in export_plan(c, {0})["included"]


def test_missing_media_blocks_export():
    c = sample()
    c[0]["media"] = []
    assert "Média" in export_reason(c[0])


def test_decks_distinct_and_note_guids_stable(tmp_path):
    cards = sample()
    a, _ = build_apkg(cards, {0}, "A", "document-A")
    db, _ = db_for(a, tmp_path)
    guid = db.execute("select guid from notes").fetchone()[0]
    did = db.execute("select did from cards").fetchone()[0]
    db.close()
    cards[0]["blocks"][0]["text"] = "Edited answer"
    b, _ = build_apkg(cards, {0}, "Renamed", "document-A")
    db, _ = db_for(b, tmp_path)
    assert guid == db.execute("select guid from notes").fetchone()[0]
    assert did == db.execute("select did from cards").fetchone()[0]
    db.close()
    c, _ = build_apkg(cards, {0}, "B", "document-B")
    db, _ = db_for(c, tmp_path)
    assert did != db.execute("select did from cards").fetchone()[0]


def test_source_bundle_keeps_every_card_and_original_pdf():
    data = pdf(
        [(40, 40, "CARTE"), (40, 70, "Title"), (40, 300, "CARTE OCCLUSION")], image=True
    )
    cards = parse_pdf(data)
    z = zipfile.ZipFile(io.BytesIO(source_bundle(data, cards, {0})))
    assert z.read("source.pdf") == data
    assert len(json.loads(z.read("cards.json"))) == 2
    assert "cards/002/source-1.png" in z.namelist()
    assert len([n for n in z.namelist() if n.startswith("media/")]) == 1
    assert "pas un paquet Anki" in z.read("LIRE-MOI.txt").decode()
