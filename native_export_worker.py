"""Separate process per export: no Anki Collection is shared between users/threads."""

import hashlib
import json
from pathlib import Path
import sys

from anki.collection import Collection
from anki.import_export_pb2 import (
    ExportAnkiPackageOptions,
    ImportAnkiPackageOptions,
    ImportAnkiPackageRequest,
)


def import_package(col, path):
    col.import_anki_package(
        ImportAnkiPackageRequest(
            package_path=str(path),
            options=ImportAnkiPackageOptions(merge_notetypes=True),
        )
    )


def verify(col, manifest):
    if (
        col.note_count() != len(manifest["notes"])
        or col.card_count() != manifest["cards"]
    ):
        raise ValueError("Nombre de notes/cartes incorrect après réimport.")
    for e in manifest["notes"]:
        nid = col.db.scalar("select id from notes where guid=?", e["guid"])
        if not nid:
            raise ValueError("Identifiant de note perdu.")
        note = col.get_note(nid)
        actual_ords = {
            row[0] for row in col.db.all("select ord from cards where nid=?", nid)
        }
        if e["kind"] == "CARTE OCCLUSION":
            model = note.note_type()
            assert model["originalStockKind"] == 6 and model["type"] == 1
            assert [f.get("tag") for f in model["flds"][:4]] == [0, 1, 2, 3]
            parsed = col.get_image_occlusion_note(nid)
            assert not parsed.error
            assert (
                parsed.note.header == e["header"]
                and parsed.note.back_extra == e["extra"]
            )
            assert (
                hashlib.sha256(parsed.note.image_data).hexdigest()
                == manifest["media"][e["image"]]
            )
            assert actual_ords == {m["number"] - 1 for m in e["masks"]}
            grouped = {}
            for mask in e["masks"]:
                grouped.setdefault(mask["number"], []).append(mask)
            assert {o.ordinal for o in parsed.note.occlusions} == set(grouped)
            for oc in parsed.note.occlusions:
                assert len(oc.shapes) == len(grouped[oc.ordinal])
                for shape, mask in zip(oc.shapes, grouped[oc.ordinal]):
                    assert shape.shape == "rect"
                    props = {p.name: p.value for p in shape.properties}
                    assert props["oi"] == "1"
                    for key in ("left", "top", "width", "height"):
                        assert abs(float(props[key]) - mask[key]) < 1e-7
            for (cid,) in col.db.all("select id from cards where nid=?", nid):
                question = col.get_card(cid).question()
                assert (
                    "anki.imageOcclusion.setup()" in question
                    and "image-occlusion-canvas" in question
                )
                assert 'class="cloze"' in question
        else:
            assert note.fields == e["fields"] and actual_ords == set(e["ords"])
            model = note.note_type()
            assert model["type"] == (1 if e["kind"] == "CARTE CLOZE" else 0)
    for name, digest in manifest["media"].items():
        assert (
            hashlib.sha256((Path(col.media.dir()) / name).read_bytes()).hexdigest()
            == digest
        ), (name, "media changed")


def run(root):
    manifest = json.loads((root / "manifest.json").read_text())
    col = Collection(str(root / "build.anki2"))
    try:
        if (root / "base.apkg").exists():
            import_package(col, root / "base.apkg")
        col.add_image_occlusion_notetype()
        model = next(m for m in col.models.all() if m.get("originalStockKind") == 6)
        model["name"] = "Anki Studio Image Occlusion"
        col.models.update_dict(model)
        did = col.decks.id(manifest["deck_name"])
        for e in manifest["notes"]:
            if e["kind"] != "CARTE OCCLUSION":
                continue
            # Native backend supplies tagged fields and the genuine stock model.
            before = set(col.find_notes(""))
            col.add_image_occlusion_note(
                model["id"],
                str(root / "input-media" / e["image"]),
                e["occlusions"],
                e["header"],
                e["extra"],
                [],
            )
            added = set(col.find_notes("")) - before
            assert len(added) == 1
            nid = added.pop()
            note = col.get_note(nid)
            note.guid = e["guid"]
            col.update_note(note)
            cids = col.find_cards("nid:" + str(nid))
            col.set_deck(cids, did)
        # References in Back Extra keep original component images in multi-image notes.
        for name, digest in manifest["media"].items():
            target = Path(col.media.dir()) / name
            if not target.exists():
                target.write_bytes((root / "input-media" / name).read_bytes())
        verify(col, manifest)
        col.export_anki_package(
            out_path=str(root / "native.apkg"),
            options=ExportAnkiPackageOptions(with_media=True),
            limit=None,
        )
    finally:
        col.close()
    restored = Collection(str(root / "verify.anki2"))
    try:
        import_package(restored, root / "native.apkg")
        verify(restored, manifest)
        # A repeated import must not duplicate notes or masks.
        import_package(restored, root / "native.apkg")
        verify(restored, manifest)
    finally:
        restored.close()
    (root / "verified.json").write_text(
        json.dumps({"notes": len(manifest["notes"]), "cards": manifest["cards"]})
    )


if __name__ == "__main__":
    run(Path(sys.argv[1]))
