"""Isolated official-Anki export of mixed Basic/Cloze/native Image Occlusion."""

import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import genanki
from engine import render_blocks
from native_io import native_rectangles


def io_extra(card):
    value = render_blocks(
        [b for b in card["blocks"] if b["kind"] == "text" and b.get("text")]
    )
    canvas = card["io"]["canvas"]
    originals = canvas["originals"]
    if len(originals) > 1:
        value += (
            "<details><summary>Images sources non modifiées</summary>"
            + "".join(
                '<img src="' + html.escape(n, quote=True) + '" style="max-width:100%">'
                for n in originals
            )
            + "</details>"
        )
    return value


def build_native_apkg(cards, plan, deck_name, digest, legacy_builder):
    from exporter import fields_for, cloze_numbers

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "input-media").mkdir()
        other = {i for i in plan["included"] if cards[i]["type"] != "CARTE OCCLUSION"}
        if other:
            legacy, _ = legacy_builder(cards, other, deck_name, digest, selected=other)
            (root / "base.apkg").write_bytes(legacy)
        entries = []
        media = {}
        for i in plan["included"]:
            card = cards[i]
            kind = card["type"]
            entry = dict(
                kind=kind, guid=genanki.guid_for("anki-studio-v8", digest, i, kind)
            )
            if kind == "CARTE OCCLUSION":
                entry.update(
                    header=card["front"],
                    extra=io_extra(card),
                    image=card["io"]["canvas"]["name"],
                    masks=card["io"]["masks"],
                    occlusions=native_rectangles(card["io"]["masks"]),
                )
            else:
                entry.update(
                    fields=fields_for(card),
                    ords=sorted(n - 1 for n in cloze_numbers(fields_for(card)[0]))
                    if kind == "CARTE CLOZE"
                    else [0],
                )
            entries.append(entry)
            for name, raw in card["media"]:
                if Path(name).name != name:
                    raise ValueError("Nom de média invalide.")
                if name in media and media[name] != hashlib.sha256(raw).hexdigest():
                    raise ValueError("Collision de médias.")
                media[name] = hashlib.sha256(raw).hexdigest()
                (root / "input-media" / name).write_bytes(raw)
        manifest = dict(
            deck_name=deck_name, notes=entries, cards=plan["cards"], media=media
        )
        (root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                str(Path(__file__).with_name("native_export_worker.py")),
                str(root),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode:
            raise RuntimeError("Export Anki natif refusé : " + result.stderr[-2500:])
        receipt = json.loads((root / "verified.json").read_text())
        if receipt["notes"] != plan["notes"] or receipt["cards"] != plan["cards"]:
            raise ValueError("La vérification native ne correspond pas à la sélection.")
        return (root / "native.apkg").read_bytes(), plan
