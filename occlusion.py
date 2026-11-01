"""Unmasked source canvases and explicit per-card review state for native IO."""

import copy
import hashlib
import json
import math

import pymupdf as fitz
from native_io import native_rectangles


def prepare_occlusion(card):
    """Prepare image pixels only. Never creates masks or a validation."""
    images = [b for b in card["blocks"] if b["kind"] == "image"]
    card["io"] = {
        "masks": [],
        "previewed": [],
        "reviewed": [],
        "verified": None,
        "draft": False,
        "epoch": 0,
        "last_event": None,
        "canvas": None,
    }
    if not images:
        return
    media = dict(card["media"])
    if len(images) == 1:
        name = images[0]["media_name"]
        raw = media[name]
        pix = fitz.Pixmap(raw)
        width, height = pix.width, pix.height
    else:
        if len({b["page"] for b in images}) != 1:
            card["warnings"].append(
                "Occlusion sur plusieurs pages : préparer une image par note."
            )
            return
        rect = fitz.Rect(images[0]["bbox"])
        for b in images[1:]:
            rect |= fitz.Rect(b["bbox"])
        scale = max(
            max(
                fitz.Pixmap(media[b["media_name"]]).width / fitz.Rect(b["bbox"]).width,
                fitz.Pixmap(media[b["media_name"]]).height
                / fitz.Rect(b["bbox"]).height,
            )
            for b in images
        )
        limit = math.sqrt(16_000_000 / max(1, rect.get_area()))
        if scale > limit:
            card["warnings"].append(
                "Canevas limité à 16 mégapixels ; images sources conservées séparément."
            )
        scale = min(scale, limit)
        with fitz.open() as doc:
            page = doc.new_page(width=rect.width, height=rect.height)
            for b in images:
                box = fitz.Rect(b["bbox"])
                box = fitz.Rect(
                    box.x0 - rect.x0,
                    box.y0 - rect.y0,
                    box.x1 - rect.x0,
                    box.y1 - rect.y0,
                )
                page.insert_image(
                    box, stream=media[b["media_name"]], keep_proportion=False
                )
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            raw = pix.tobytes("png")
            width, height = pix.width, pix.height
        name = hashlib.sha256(raw).hexdigest() + ".png"
        if name not in media:
            card["media"].append((name, raw))
    if not card["front"].strip():
        card["warnings"] = [
            w for w in card["warnings"] if not w.startswith("Titre absent")
        ]
        card["warnings"].append(
            "Aucun titre textuel hors de l’image ; le titre est facultatif pour une Occlusion native."
        )
    card["io"]["canvas"] = {
        "name": name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "width": width,
        "height": height,
        "originals": [b["media_name"] for b in images],
    }


def canonical_masks(masks):
    if not isinstance(masks, list) or len(masks) > 500:
        raise ValueError("Maximum : 500 rectangles.")
    result = []
    ids = set()
    for item in masks:
        ident = item.get("id")
        if not isinstance(ident, str) or not ident or len(ident) > 100 or ident in ids:
            raise ValueError("Identifiant de rectangle invalide ou répété.")
        ids.add(ident)
        values = {k: float(item[k]) for k in ("left", "top", "width", "height")}
        if not all(math.isfinite(v) for v in values.values()):
            raise ValueError("Coordonnées non finies.")
        if any(v < 0 or v > 1 for v in values.values()):
            raise ValueError("Rectangle hors image.")
        if (
            values["left"] + values["width"] > 1 + 1e-9
            or values["top"] + values["height"] > 1 + 1e-9
        ):
            raise ValueError("Rectangle hors image.")
        values = {k: round(v, 8) for k, v in values.items()}
        values["width"] = min(values["width"], 1 - values["left"])
        values["height"] = min(values["height"], 1 - values["top"])
        m = dict(id=ident, number=item["number"], **values)
        native_rectangles([m])
        result.append(m)
    return result


def groups(card):
    return sorted({m["number"] for m in card.get("io", {}).get("masks", [])})


def fingerprint(card):
    from engine import render_blocks

    state = card["io"]
    value = {
        "canvas": state["canvas"],
        "masks": canonical_masks(state["masks"]),
        "front": card["front"],
        "back": render_blocks(card["blocks"]),
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def invalidate(card):
    io = card["io"]
    io.update(previewed=[], reviewed=[], verified=None)
    io["epoch"] += 1


def apply_editor_event(card, event, editor_id):
    """Validate component messages; reject stale image/card sessions and repeat events."""
    if not isinstance(event, dict) or event.get("editor_id") != editor_id:
        return card, False
    io = card["io"]
    if event.get("canvas_hash") != io["canvas"]["sha256"]:
        return card, False
    eid = event.get("event_id")
    if not isinstance(eid, str) or not eid or eid == io.get("last_event"):
        return card, False
    previous = io.get("last_event") or ""
    if ":" in eid and ":" in previous:
        namespace, seq = eid.rsplit(":", 1)
        old_namespace, old_seq = previous.rsplit(":", 1)
        if (
            namespace == old_namespace
            and seq.isdigit()
            and old_seq.isdigit()
            and int(seq) <= int(old_seq)
        ):
            return card, False
    updated = copy.deepcopy(card)
    state = updated["io"]
    state["last_event"] = eid
    kind = event.get("kind")
    if kind == "editing":
        invalidate(updated)
        state["draft"] = True
    elif kind == "commit":
        masks = canonical_masks(event.get("masks"))
        if masks != state["masks"]:
            invalidate(updated)
        state["masks"] = masks
        state["draft"] = False
    elif kind == "preview":
        # Streamlit can coalesce a quick pointer-up and preview into the last
        # widget message. Reconcile its committed snapshot, invalidating reviews.
        masks = canonical_masks(event.get("masks"))
        if masks != state["masks"]:
            invalidate(updated)
            state["masks"] = masks
        state["draft"] = False
        n = event.get("number")
        if type(n) is not int or n not in groups(updated):
            return card, False
        state["previewed"] = sorted(set(state["previewed"]) | {n})
    else:
        return card, False
    return updated, True


def review_group(card, number, checked):
    state = card["io"]
    if checked and (state["draft"] or number not in state["previewed"]):
        raise ValueError("Prévisualiser la carte masquée avant validation.")
    reviewed = set(state["reviewed"])
    if checked:
        reviewed.add(number)
    else:
        reviewed.discard(number)
        state["verified"] = None
    state["reviewed"] = sorted(reviewed)


def ready_to_confirm(card):
    state = card.get("io", {})
    return (
        bool(groups(card))
        and not state.get("draft")
        and set(state["reviewed"]) == set(groups(card))
    )


def confirm_note(card):
    if not ready_to_confirm(card):
        raise ValueError("Valider chaque carte Anki générée.")
    card["io"]["verified"] = fingerprint(card)


def export_issue(card):
    state = card.get("io", {})
    canvas = state.get("canvas")
    if not canvas:
        return "Aucune image disponible pour cette Occlusion."
    media = dict(card["media"])
    if (
        canvas["name"] not in media
        or hashlib.sha256(media[canvas["name"]]).hexdigest() != canvas["sha256"]
    ):
        return "Image originale modifiée ou manquante : refaire les zones et leur validation."
    try:
        canonical_masks(state["masks"])
    except (ValueError, KeyError, TypeError) as error:
        return str(error)
    if not groups(card):
        return "Dessiner au moins une zone ; aucun masque n’est créé automatiquement."
    if not ready_to_confirm(card) or state.get("verified") != fingerprint(card):
        return "Prévisualiser et valider chaque carte Occlusion après la dernière modification."
    return None
