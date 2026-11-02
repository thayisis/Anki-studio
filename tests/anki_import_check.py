"""Run with a separate interpreter containing the official Anki Python package."""

import json
import hashlib
from pathlib import Path
import sys
import re
from html.parser import HTMLParser

from anki.collection import Collection
from anki.import_export_pb2 import ImportAnkiPackageRequest, ImportAnkiPackageOptions


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.hidden -= 1

    def handle_data(self, text):
        if not self.hidden:
            self.parts.append(text)


def visible(value):
    p = VisibleText()
    p.feed(value)
    return " ".join(" ".join(p.parts).split())


package, expectation, collection_path = sys.argv[1:]
expected = json.loads(Path(expectation).read_text())
col = Collection(collection_path)
try:
    col.import_anki_package(
        ImportAnkiPackageRequest(
            package_path=package, options=ImportAnkiPackageOptions()
        )
    )
    assert col.note_count() == len(expected["notes"])
    assert col.card_count() == expected["cards"]
    for note in expected["notes"]:
        fields = col.db.scalar("select flds from notes where guid=?", note["guid"])
        assert fields == "\x1f".join(note["fields"]), (note, fields)
        ords = [
            r[0]
            for r in col.db.all(
                "select ord from cards join notes on notes.id=cards.nid where notes.guid=? order by ord",
                note["guid"],
            )
        ]
        assert ords == note["ords"]
        for cid, ordinal in col.db.all(
            "select cards.id,cards.ord from cards join notes on notes.id=cards.nid where notes.guid=?",
            note["guid"],
        ):
            card = col.get_card(cid)
            question, answer = card.question(), card.answer()
            assert question.strip() and answer.strip()
            if note["kind"] == "CARTE":
                assert visible(note["fields"][0]) in visible(question)
                assert visible(note["fields"][1]) in visible(answer)
            else:
                assert not re.search(r"{{c[1-9]\d*::", question)
                for number, word in note.get("cloze_words", []):
                    if number == ordinal + 1:
                        assert word not in visible(question)
                    else:
                        assert word in visible(question)
                    assert word in visible(answer)

    for name, digest in expected["media"].items():
        assert (
            hashlib.sha256((Path(col.media.dir()) / name).read_bytes()).hexdigest()
            == digest
        )
    print(
        json.dumps(
            {
                "notes": col.note_count(),
                "cards": col.card_count(),
                "media": len(expected["media"]),
            }
        )
    )
finally:
    col.close()
