"""Automatic export preflight, explicit warnings and independent occlusion readiness."""

import math
import hashlib
import html
import io
import json
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import genanki

from engine import crop, render_blocks

CSS = ".card {font-family:Arial,sans-serif;font-size:20px;text-align:left;} img {max-width:100%;height:auto;}"
BASIC = genanki.Model(
    1987343001,
    "Anki Studio Basic",
    fields=[{"name": "Front"}, {"name": "Back"}],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "{{Front}}",
            "afmt": "{{FrontSide}}<hr id=answer>{{Back}}",
        }
    ],
    css=CSS,
)
CLOZE = genanki.Model(
    1987343002,
    "Anki Studio Cloze",
    model_type=genanki.Model.CLOZE,
    fields=[{"name": "Text"}, {"name": "Extra"}],
    templates=[
        {
            "name": "Cloze",
            "qfmt": "{{cloze:Text}}",
            "afmt": "{{cloze:Text}}<br>{{Extra}}",
        }
    ],
    css=CSS,
)


def cloze_numbers(text):
    """Conservative syntax gate: explicit, nonempty, nonnested Anki deletions."""
    found = list(re.finditer(r"{{c([1-9]\d*)::([^{}]+?)}}", text, re.S))
    remainder = re.sub(r"{{c([1-9]\d*)::([^{}]+?)}}", "", text, flags=re.S)
    if "{{" in remainder or "}}" in remainder:
        return set()
    if any(not re.sub("<[^>]+>", "", m[2].split("::")[0]).strip() for m in found):
        return set()
    return {int(m[1]) for m in found}


def fields_for(card):
    front = card["front"]
    back = render_blocks(card["blocks"]) if "blocks" in card else card["back"]
    if card["type"] == "CARTE CLOZE":
        return [back if card.get("cloze_body_only") else front + "<hr>" + back, ""]
    return [front, back]


def export_reason(card):
    try:
        for block in card.get("blocks", []):
            indent = float(block.get("indent", 0))
            if not math.isfinite(indent) or not 0 <= indent <= 10000:
                return "Hiérarchie invalide : retrait impossible."
        media = dict(card["media"])
        for name, raw in card["media"]:
            if Path(name).name != name or not raw:
                return "Média invalide ou vide."
            if (
                re.fullmatch(r"[a-f0-9]{64}\.png", name)
                and hashlib.sha256(raw).hexdigest() + ".png" != name
            ):
                return "Média altéré : les pixels diffèrent de la source."
        source_images = [
            e["media_name"]
            for e in card.get("source_elements", [])
            if e["kind"] == "image"
        ]
        images = [
            b["media_name"] for b in card.get("blocks", []) if b["kind"] == "image"
        ]
        if source_images != images:
            return "Images sources manquantes ou ordre modifié."
        if any(name not in media for name in images):
            return "Média manquant."
        return _export_reason(card)
    except (ValueError, TypeError, KeyError) as error:
        return "Structure non exportable : " + str(error)


def content_warnings(card):
    from reviewed_notes import without_cloze

    warnings = list(card.get("warnings", []))
    if card.get("source_elements"):
        source = " ".join(
            e.get("text", "") for e in card["source_elements"] if e["kind"] == "text"
        )
        body = " ".join(
            b.get("text", "") for b in card.get("blocks", []) if b["kind"] == "text"
        )
        actual = body if card.get("source_partitioned") else card["title"] + " " + body
        tokenize = lambda value: re.findall(r"\w+|[^\w\s]", without_cloze(value))
        if tokenize(source) != tokenize(actual):
            warnings.append(
                "Texte modifié ou incomplet par rapport au PDF : comparer et corriger ; fidélité non validée."
            )
    if len(card.get("title", "")) > 180:
        warnings.append(
            "Notion longue ou ambiguë : titre exact conservé pour éviter une suppression de texte."
        )
    return list(dict.fromkeys(warnings))


def _export_reason(card):
    if card["type"] == "CARTE OCCLUSION":
        from occlusion import export_issue

        return export_issue(card)
    if card["type"] not in ("CARTE", "CARTE CLOZE"):
        return "Type inconnu."
    if not html.unescape(re.sub("<[^>]+>", "", card["front"])).strip():
        return "Titre à renseigner."
    if card["type"] == "CARTE":
        meaningful = (
            any(
                b["kind"] == "image" or str(b.get("text", "")).strip()
                for b in card["blocks"]
            )
            if "blocks" in card
            else bool(
                re.sub("<[^>]+>", "", card["back"]).strip()
                or re.search(r"<img\b", card["back"])
            )
        )
        if not meaningful:
            return (
                "Verso vide : corriger le titre et replacer le texte source au verso."
            )
    if card["type"] == "CARTE CLOZE" and not cloze_numbers(fields_for(card)[0]):
        return "Cloze sans suppression valide {{c1::texte}} (imbrication non prise en charge)."
    media = dict(card["media"])
    back = fields_for(card)[0] if card["type"] == "CARTE CLOZE" else fields_for(card)[1]
    if any(name not in media for name in re.findall(r'<img[^>]*src="([^"]+)"', back)):
        return "Média manquant."
    return None


def export_plan(cards, validated=None):
    included, excluded = [], []
    for i, card in enumerate(cards):
        reason = export_reason(card)
        if reason:
            excluded.append(dict(index=i, type=card["type"], reason=reason))
        else:
            included.append(i)
    return dict(
        included=included,
        excluded=excluded,
        awaiting=0,
        warnings=[
            dict(index=i, reason=w)
            for i, c in enumerate(cards)
            for w in content_warnings(c)
        ],
        notes=len(included),
        cards=sum(
            len({m["number"] for m in cards[i]["io"]["masks"]})
            if cards[i]["type"] == "CARTE OCCLUSION"
            else len(cloze_numbers(fields_for(cards[i])[0]))
            if cards[i]["type"] == "CARTE CLOZE"
            else 1
            for i in included
        ),
    )


def build_apkg(cards, validated, deck_name, document_digest):
    plan = export_plan(cards, validated)
    if any(cards[i]["type"] == "CARTE OCCLUSION" for i in plan["included"]):
        from native_export import build_native_apkg

        return build_native_apkg(
            cards, plan, deck_name, document_digest, _build_legacy_apkg
        )
    return _build_legacy_apkg(cards, validated, deck_name, document_digest)


def _build_legacy_apkg(cards, validated, deck_name, document_digest, *, selected=None):
    plan = export_plan(cards, validated)
    if selected is not None:
        plan["included"] = [i for i in plan["included"] if i in selected]
        plan["notes"] = len(plan["included"])
        plan["cards"] = sum(
            len(cloze_numbers(fields_for(cards[i])[0]))
            if cards[i]["type"] == "CARTE CLOZE"
            else 1
            for i in plan["included"]
        )
    if not plan["included"]:
        raise ValueError("Aucune note exportable.")
    # One stable deck per source; independent documents cannot collide.
    deck_id = int(
        hashlib.sha256(("anki-studio:" + document_digest).encode()).hexdigest()[:12], 16
    )
    deck = genanki.Deck(deck_id, deck_name)
    expected = []
    with tempfile.TemporaryDirectory() as tmp:
        paths = {}
        for i in plan["included"]:
            card = cards[i]
            model = CLOZE if card["type"] == "CARTE CLOZE" else BASIC
            fields = fields_for(card)
            guid = genanki.guid_for("anki-studio-v8", document_digest, i, card["type"])
            deck.add_note(genanki.Note(model=model, fields=fields, guid=guid))
            expected.append((model.model_id, fields, guid))
            for name, raw in card["media"]:
                if Path(name).name != name:
                    raise ValueError("Nom de média invalide.")
                if name in paths and paths[name].read_bytes() != raw:
                    raise ValueError("Collision de médias.")
                path = Path(tmp) / name
                path.write_bytes(raw)
                paths[name] = path
        package = genanki.Package(deck)
        package.media_files = [str(p) for p in paths.values()]
        out = Path(tmp) / "cards.apkg"
        package.write_to_file(str(out))
        payload = out.read_bytes()
    verify_apkg(
        payload,
        expected,
        plan["cards"],
        {n: p for i in plan["included"] for n, p in cards[i]["media"]},
    )
    return payload, plan


def verify_apkg(payload, expected, expected_cards, expected_media):
    """Verify current output's DB, model types/templates, fields, ordinals and all media bytes."""
    with (
        zipfile.ZipFile(io.BytesIO(payload)) as archive,
        tempfile.TemporaryDirectory() as tmp,
    ):
        if archive.testzip() is not None:
            raise ValueError("Archive corrompue.")
        media = json.loads(archive.read("media"))
        actual_media = {name: archive.read(key) for key, name in media.items()}
        if actual_media != expected_media:
            raise ValueError("Les médias exportés diffèrent des sources.")
        path = Path(tmp) / "collection.anki2"
        path.write_bytes(archive.read("collection.anki2"))
        with sqlite3.connect(path) as db:
            notes = db.execute("select mid,flds,guid from notes order by id").fetchall()
            if notes != [
                (mid, "\x1f".join(fields), guid) for mid, fields, guid in expected
            ]:
                raise ValueError("Notes ou champs exportés incorrects.")
            if db.execute("select count(*) from cards").fetchone()[0] != expected_cards:
                raise ValueError("Nombre de cartes incorrect.")
            models = json.loads(db.execute("select models from col").fetchone()[0])
            for mid, fields, guid in expected:
                model = models[str(mid)]
                wanted = BASIC if mid == BASIC.model_id else CLOZE
                if (
                    model["type"] != wanted.model_type
                    or len(model["flds"]) != len(fields)
                    or [f["name"] for f in model["flds"]]
                    != [f["name"] for f in wanted.fields]
                    or model["tmpls"][0]["qfmt"] != wanted.templates[0]["qfmt"]
                    or model["tmpls"][0]["afmt"] != wanted.templates[0]["afmt"]
                ):
                    raise ValueError("Modèle Anki incorrect.")
                nid = db.execute(
                    "select id from notes where guid=?", (guid,)
                ).fetchone()[0]
                ords = {
                    row[0]
                    for row in db.execute("select ord from cards where nid=?", (nid,))
                }
                wanted_ords = (
                    {n - 1 for n in cloze_numbers(fields[0])}
                    if mid == CLOZE.model_id
                    else {0}
                )
                if ords != wanted_ords:
                    raise ValueError("Numéros de cartes Cloze incorrects.")


def source_bundle(data, cards, validated):
    """Safe fallback: original PDF + editable manifest + media + per-page source crops.

    This is deliberately a ZIP, never advertised as native Image Occlusion.
    """
    output = io.BytesIO()
    plan = export_plan(cards, validated)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("source.pdf", data)
        manifest = []
        for i, card in enumerate(cards):
            entry = {k: v for k, v in card.items() if k != "media"}
            entry["back"] = render_blocks(card["blocks"])
            entry["media"] = [n for n, _ in card["media"]]
            entry["validated"] = i in validated
            entry["export_reason"] = export_reason(card)
            manifest.append(entry)
            for ri in range(len(card["regions"])):
                archive.writestr(
                    f"cards/{i + 1:03d}/source-{ri + 1}.png", crop(data, card, 2, ri)
                )
        for name, raw in {name: raw for c in cards for name, raw in c["media"]}.items():
            archive.writestr("media/" + name, raw)
        archive.writestr(
            "cards.json", json.dumps(manifest, ensure_ascii=False, indent=2)
        )
        archive.writestr(
            "export-report.json", json.dumps(plan, ensure_ascii=False, indent=2)
        )
        archive.writestr(
            "LIRE-MOI.txt",
            "Ce ZIP est un dossier source, pas un paquet Anki. Toutes les cartes sont conservées.\n"
            "Les masques validés figurent dans cards.json ; les images restent non masquées. "
            "Occlusion : l’éditeur web permet le dessin puis l’export natif. Ouvrir une image dans un client Anki "
            "compatible Occlusion d’image native (Anki 23.10+ ou client compatible), créer les "
            "masques manuellement et vérifier le résultat. Aucune zone n’est créée automatiquement ; dessiner et valider les zones dans l’éditeur.\n"
            "L’application reste gratuite et utilisable dans Safari sans installation. La création "
            "manuelle d’occlusions peut se faire dans l’éditeur web ; les masques natifs restent éditables "
            "après import dans un client Anki compatible. Le PDF original reste dans source.pdf.\n",
        )
    return output.getvalue()
