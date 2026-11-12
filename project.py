"""Versioned portable projects; no filesystem extraction, executable HTML or remote media."""

import copy
import hashlib
import html
import io
import math
import zipfile
from pathlib import PurePosixPath

from engine import parse_pdf, render_blocks
from manual_workflow import SCHEMA, canonical, card_id, parse_json
from occlusion import canonical_masks

FORMAT = "anki-studio-project-v1"
MAX_PROJECT = 200 * 1024 * 1024


def save_project(data, cards, validated=(), name="Cours", exchange=None):
    digest = hashlib.sha256(data).hexdigest()
    entries, media = [], {}
    for c in cards:
        entry = {k: v for k, v in c.items() if k != "media"}
        entry["media"] = [n for n, _ in c["media"]]
        entry["stable_id"] = card_id(digest, c)
        entries.append(entry)
        for filename, raw in c["media"]:
            if PurePosixPath(filename).name != filename or "\\" in filename:
                raise ValueError("Nom de média invalide.")
            if filename in media and media[filename] != raw:
                raise ValueError("Collision de médias.")
            media[filename] = raw
    manifest = dict(
        format=FORMAT,
        document_id=digest,
        name=name,
        cards=entries,
        validated=sorted(validated),
        exchange=exchange,
    )
    manifest_text = canonical(manifest)
    if (
        len(media) + 2 > 10000
        or len(manifest_text.encode()) + len(data) + sum(map(len, media.values()))
        > MAX_PROJECT
    ):
        raise ValueError(
            "Projet trop volumineux pour le réimport (200 Mo décompressés maximum)."
        )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", manifest_text)
        archive.writestr("source.pdf", data)
        for filename, raw in media.items():
            archive.writestr("media/" + filename, raw)
    payload = output.getvalue()
    if len(payload) > MAX_PROJECT:
        raise ValueError("Projet trop volumineux pour le réimport (200 Mo maximum).")
    return payload


def _load(payload):
    if len(payload) > MAX_PROJECT:
        raise ValueError("Projet trop volumineux (200 Mo maximum).")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos]
        if len(names) != len(set(names)) or len(names) > 10000:
            raise ValueError("Entrées ZIP répétées ou trop nombreuses.")
        if sum(i.file_size for i in infos) > MAX_PROJECT:
            raise ValueError("Projet décompressé trop volumineux (200 Mo maximum).")
        if any(i.flag_bits & 1 for i in infos):
            raise ValueError("Projet chiffré non pris en charge.")
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name:
                raise ValueError("Chemin ZIP invalide.")
        manifest = parse_json(archive.read("project.json"))
        if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
            raise ValueError("Version de projet non prise en charge.")
        data = archive.read("source.pdf")
        digest = hashlib.sha256(data).hexdigest()
        if digest != manifest["document_id"]:
            raise ValueError("PDF source altéré.")
        originals = parse_pdf(data)
        entries = manifest["cards"]
        if not isinstance(entries, list) or len(entries) != len(originals):
            raise ValueError("Nombre de cartes différent du PDF source.")
        result = []
        for entry, original in zip(entries, originals):
            if (
                entry["stable_id"] != card_id(digest, original)
                or entry["id"] != original["id"]
                or entry["type"] != original["type"]
            ):
                raise ValueError("Identité ou type de carte altéré.")
            for key in (
                "source_elements",
                "regions",
                "page",
                "bbox",
                "original_title",
                "source_context",
            ):
                if canonical(entry.get(key)) != canonical(original.get(key)):
                    raise ValueError("Métadonnées source altérées : " + key)
            c = copy.deepcopy(original)
            # Only editable fields are restored; all provenance is re-read from PDF.
            for key in (
                "title",
                "context",
                "source_title_restored",
                "source_partitioned",
                "source_title",
                "manual_correction",
                "cloze_body_only",
                "proposed_deletion",
            ):
                if key in entry:
                    c[key] = entry[key]
            if (
                not isinstance(c["title"], str)
                or not isinstance(c["context"], list)
                or not all(isinstance(v, str) for v in c["context"])
            ):
                raise ValueError("Titre ou contexte invalide.")
            c["title_html"] = (
                original["title_html"]
                if c["title"] == original["title"]
                else html.escape(c["title"])
            )
            c["front"] = (
                html.escape(" — ".join(c["context"])) + " — " if c["context"] else ""
            ) + c["title_html"]
            if not c["title"]:
                c["front"] = ""
            templates = {
                b.get("source_id"): b
                for b in original["source_elements"] + original["blocks"]
            }
            blocks = []
            for saved in entry["blocks"]:
                if saved.get("source_id") in templates:
                    b = copy.deepcopy(templates[saved["source_id"]])
                elif (
                    saved.get("restored_source_title") is True
                    and saved.get("source_id") is None
                    and saved.get("kind") == "text"
                ):
                    b = dict(kind="text", restored_source_title=True)
                else:
                    raise ValueError("Élément de verso sans origine reconnue.")
                if saved["kind"] != b["kind"]:
                    raise ValueError("Type d’élément modifié.")
                indent = float(saved.get("indent", 0))
                if not math.isfinite(indent) or not 0 <= indent <= 10000:
                    raise ValueError("Retrait invalide.")
                b["indent"] = saved.get("indent", 0)
                level = saved.get("level", 0)
                if type(level) is not int or not 0 <= level <= 10000:
                    raise ValueError("Niveau invalide.")
                b["level"] = level
                if b["kind"] == "text":
                    if (
                        not isinstance(saved.get("text"), str)
                        or type(saved.get("bullet", False)) is not bool
                    ):
                        raise ValueError("Texte ou puce invalide.")
                    for key in (
                        "text",
                        "bullet",
                        "bullet_text",
                        "continuation",
                        "restored_source_title",
                    ):
                        if key in saved:
                            b[key] = saved[key]
                    if not isinstance(b.get("bullet_text", ""), str):
                        raise ValueError("Puce invalide.")
                elif saved["media_name"] != b["media_name"]:
                    raise ValueError("Image source modifiée.")
                blocks.append(b)
            source_images = [
                b["media_name"] for b in original["blocks"] if b["kind"] == "image"
            ]
            if [
                b["media_name"] for b in blocks if b["kind"] == "image"
            ] != source_images:
                raise ValueError("Images manquantes ou ordre modifié.")
            c["blocks"] = blocks
            c["levels"] = entry["levels"]
            c["back"] = render_blocks(blocks)
            # Preserve cleared/resolved warnings but do not accept injected messages.
            c["warnings"] = [
                w for w in original["warnings"] if w in entry.get("warnings", [])
            ]
            wanted_media = dict(original["media"])
            if set(entry["media"]) != set(wanted_media):
                raise ValueError("Liste de médias différente de la source.")
            c["media"] = []
            for filename in entry["media"]:
                raw = archive.read("media/" + filename)
                if raw != wanted_media[filename]:
                    raise ValueError("Média altéré : " + filename)
                c["media"].append((filename, raw))
            if original.get("io"):
                state = entry["io"]
                if state["canvas"] != original["io"]["canvas"]:
                    raise ValueError("Canevas d’occlusion différent de la source.")
                c["io"]["masks"] = canonical_masks(state["masks"])
                # A saved in-progress gesture is not a committed mask.
                c["io"]["draft"] = bool(state.get("draft"))
                c["io"]["epoch"] = 1
            result.append(c)
        validated = manifest.get("validated", [])
        if not isinstance(validated, list) or any(
            type(i) is not int or not 0 <= i < len(result) for i in validated
        ):
            raise ValueError("Liste de revue invalide.")
        name = manifest.get("name", "Cours")
        if not isinstance(name, str):
            raise ValueError("Nom de projet invalide.")
        exchange = manifest.get("exchange")
        if exchange is not None:
            req, states = exchange["request"], exchange["states"]
            if req["document_id"] != digest or not isinstance(states, dict):
                raise ValueError("Échange ChatGPT étranger au projet.")
            known = {card_id(digest, c) for c in result}
            identifiers = [e["id"] for e in req["cards"]]
            if (
                set(req) != {"schema", "document_id", "request_id", "cards"}
                or req["schema"] != SCHEMA
                or not identifiers
                or len(identifiers) != len(set(identifiers))
                or not set(identifiers) <= known
                or set(states) != set(identifiers)
                or any(not isinstance(v, str) or len(v) != 64 for v in states.values())
                or req["request_id"]
                != hashlib.sha256(
                    canonical(dict(document_id=digest, states=states)).encode()
                ).hexdigest()
                or any(
                    set(e)
                    != {"id", "type", "front", "source_title", "context", "lines"}
                    for e in req["cards"]
                )
            ):
                raise ValueError("Échange ChatGPT invalide.")
        return dict(
            data=data,
            digest=digest,
            cards=result,
            validated=set(validated),
            name=name,
            exchange=exchange,
        )


def load_project(payload):
    try:
        return _load(payload)
    except (
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        IndexError,
        OSError,
        RuntimeError,
        zipfile.BadZipFile,
    ) as error:
        raise ValueError("Projet refusé : " + str(error)) from error
