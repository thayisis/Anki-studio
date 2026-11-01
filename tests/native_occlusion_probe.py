"""Native backend round-trip study. Input image/masks are explicitly synthetic."""

import hashlib
import json
from pathlib import Path
import sys

from anki.collection import Collection
from anki.import_export_pb2 import (
    ExportAnkiPackageOptions,
    ImportAnkiPackageRequest,
    ImportAnkiPackageOptions,
)

folder = Path(sys.argv[1])
spec = json.loads((folder / "spec.json").read_text())
image = folder / "synthetic.png"
source = Collection(str(folder / "source.anki2"))
try:
    source.add_image_occlusion_notetype()
    model = next(m for m in source.models.all() if m.get("originalStockKind") == 6)
    assert model["type"] == 1
    assert [f.get("tag") for f in model["flds"][:4]] == [0, 1, 2, 3]
    source.add_image_occlusion_note(
        model["id"], str(image), spec["occlusions"], "Synthetic study only", "", []
    )
    assert source.note_count() == 1 and source.card_count() == 2
    result = source.get_image_occlusion_note(source.db.scalar("select id from notes"))
    assert not result.error
    assert len(result.note.occlusions) == 2
    assert result.note.image_data == image.read_bytes()
    source.export_anki_package(
        out_path=str(folder / "native.apkg"),
        options=ExportAnkiPackageOptions(with_media=True),
        limit=None,
    )
finally:
    source.close()
restored = Collection(str(folder / "restored.anki2"))
try:
    restored.import_anki_package(
        ImportAnkiPackageRequest(
            package_path=str(folder / "native.apkg"), options=ImportAnkiPackageOptions()
        )
    )
    assert restored.note_count() == 1 and restored.card_count() == 2
    note_id = restored.db.scalar("select id from notes")
    note = restored.get_note(note_id)
    model = note.note_type()
    assert model["originalStockKind"] == 6
    assert model["type"] == 1 and len(model["flds"]) >= 4
    parsed = restored.get_image_occlusion_note(note_id)
    assert not parsed.error
    assert {o.ordinal for o in parsed.note.occlusions} == {1, 2}
    expected = spec["masks"]
    for occlusion in parsed.note.occlusions:
        shape = occlusion.shapes[0]
        assert shape.shape == "rect"
        props = {p.name: p.value for p in shape.properties}
        rectangle = next(m for m in expected if m["number"] == occlusion.ordinal)
        for key in ("left", "top", "width", "height"):
            assert abs(float(props[key]) - rectangle[key]) < 1e-7
    assert (
        hashlib.sha256(parsed.note.image_data).digest()
        == hashlib.sha256(image.read_bytes()).digest()
    )
    for cid in restored.find_cards(""):
        card = restored.get_card(cid)
        question = card.question()
        answer = card.answer()
        assert "anki.imageOcclusion.setup()" in question
        assert "image-occlusion-canvas" in question
        assert 'class="cloze"' in question and 'class="cloze-inactive"' in question
        assert question.count('data-shape="rect"') == 2
        assert 'data-occludeInactive="1"' in question
        assert "image-occlusion-canvas" in answer
    print(
        json.dumps(
            {
                "native_notes": 1,
                "native_cards": 2,
                "native_masks": 2,
                "stock_kind": 6,
                "roundtrip": True,
            }
        )
    )
finally:
    restored.close()
