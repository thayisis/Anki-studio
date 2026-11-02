"""After import, change a structured native mask using Anki's actual editing API."""

from pathlib import Path
import sys
from anki.collection import Collection
from anki.import_export_pb2 import ImportAnkiPackageRequest, ImportAnkiPackageOptions

package, count, root = sys.argv[1:]
col = Collection(str(Path(root) / "editable.anki2"))
try:
    col.import_anki_package(
        ImportAnkiPackageRequest(
            package_path=package, options=ImportAnkiPackageOptions(merge_notetypes=True)
        )
    )
    io_notes = []
    for nid in col.find_notes(""):
        note = col.get_note(nid)
        if note.note_type().get("originalStockKind") == 6:
            io_notes.append(note)
    assert len(io_notes) == int(count)
    for note in io_notes:
        before = col.get_image_occlusion_note(note.id)
        assert not before.error and before.note.occlusions
        image = before.note.image_data
        # These are geometric test masks, not suggested pedagogical masks.
        masks = note.fields[0].replace("left=0.1:", "left=0.12:")
        assert masks != note.fields[0]
        col.update_image_occlusion_note(
            note.id, masks, note.fields[2], note.fields[3], note.tags
        )
        after = col.get_image_occlusion_note(note.id)
        assert not after.error and after.note.image_data == image
        props = {p.name: p.value for p in after.note.occlusions[0].shapes[0].properties}
        assert abs(float(props["left"]) - 0.12) < 1e-8
    print("Editable native notes:", len(io_notes))
finally:
    col.close()
