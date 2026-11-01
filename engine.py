"""Coordinate-first PDF conversion. Ambiguity is retained and reported, never dropped.

Stages: extract_elements -> detect_boundaries -> reconstruct_lines -> heading_context
-> assign_indentation -> associate_images -> render_blocks. Physical lines remain
separate unless a continuation has geometric evidence; no course text is invented.
"""

import base64
import copy
import hashlib
import html
import math
import re

import pymupdf as fitz

from reviewed_notes import recipe_for

MARKER = re.compile(r"^CARTE(?:\s+(CLOZE|OCCLUSION))?$", re.I)
BULLETS = set("•●○◦▪▫□■◆◇◊–−-·§")
BULLET_PREFIX = re.compile(r"^(?:[•●○◦▪▫□■◆◇◊–−\-·§]|\d+[.)])(?:\s+|$)")


def _order(item):
    return item["page"], round(item["bbox"][1], 1), item["bbox"][0]


def extract_elements(doc):
    """Extract physical lines, original glyph positions and displayed image regions."""
    elements = []
    for page in doc:
        raw = page.get_text("rawdict")
        for bi, block in enumerate(raw["blocks"]):
            if block["type"] == 1:
                rect = fitz.Rect(block["bbox"]) & page.rect
                if rect.is_empty:
                    continue
                scale = max(
                    2, block["width"] / rect.width, block["height"] / rect.height
                )
                warnings = []
                if rect.width * rect.height * scale * scale > 16_000_000:
                    scale = math.sqrt(16_000_000 / (rect.width * rect.height))
                    warnings.append(
                        "Image limitée à 16 mégapixels ; comparer avec le PDF source."
                    )
                # Render at native resolution to preserve masks, rotation and overlays.
                image = page.get_pixmap(
                    matrix=fitz.Matrix(scale, scale), clip=rect, alpha=False
                ).tobytes("png")
                name = hashlib.sha256(image).hexdigest() + ".png"
                elements.append(
                    dict(
                        kind="image",
                        page=page.number,
                        bbox=tuple(rect),
                        media_name=name,
                        image=image,
                        warnings=warnings,
                        source_id=f"{page.number}:{bi}:image",
                    )
                )
            elif block["type"] == 0:
                for li, line in enumerate(block["lines"]):
                    chars = [c for s in line["spans"] for c in s["chars"]]
                    text = "".join(c["c"] for c in chars).strip()
                    if not text:
                        continue
                    rect = tuple(line["bbox"])
                    prefix = BULLET_PREFIX.match(text)
                    spans = line["spans"]
                    # Wingdings sometimes maps a bullet to ®. Treat it as a bullet
                    # only in its actual symbol font; preserve a literal ® otherwise.
                    symbol = len(text) == 1 and any(
                        "wingding" in s["font"].lower() for s in spans
                    )
                    bullet = bool(prefix) or symbol
                    content = (
                        text[prefix.end() :] if prefix else ("" if symbol else text)
                    )
                    stripped = len("".join(c["c"] for c in chars)) - len(
                        "".join(c["c"] for c in chars).lstrip()
                    )
                    offset = stripped + (
                        prefix.end() if prefix else (1 if symbol else 0)
                    )
                    x = chars[offset]["bbox"][0] if offset < len(chars) else rect[0]
                    # Preserve small/lowered/raised scientific glyphs without
                    # rewriting their characters (e.g. O + a smaller digit 2).
                    largest = max(spans, key=lambda s: s["size"])
                    baseline = largest["origin"][1]
                    runs = []
                    cursor = 0
                    text_end = len("".join(c["c"] for c in chars).rstrip())
                    for span in spans:
                        start = max(0, offset - cursor)
                        stop = min(len(span["chars"]), text_end - cursor)
                        if stop > start:
                            runs.append(
                                dict(
                                    text="".join(
                                        c["c"] for c in span["chars"][start:stop]
                                    ),
                                    ratio=span["size"] / largest["size"],
                                    rise=(baseline - span["origin"][1]) / span["size"],
                                )
                            )
                        cursor += len(span["chars"])
                    elements.append(
                        dict(
                            kind="text",
                            page=page.number,
                            bbox=rect,
                            text=content,
                            layout_text=content,
                            text_runs=runs,
                            original_text=text,
                            bullet=bullet,
                            bullet_text=text[: prefix.end()].strip()
                            if prefix
                            else (text if symbol else ""),
                            text_x=x,
                            font_size=max(s["size"] for s in spans),
                            uniform_font=len({s["font"] for s in spans if s["chars"]})
                            == 1,
                            bold=all(
                                bool(s["flags"] & 16) for s in spans if s["chars"]
                            ),
                            direction=tuple(line["dir"]),
                            source_id=f"{page.number}:{bi}:{li}",
                        )
                    )
        # Vector-only diagrams are not text/image blocks. Preserve their source
        # in a reviewable region instead of pretending extraction covered them.
        drawings = [
            d
            for d in page.get_drawings()
            if not (
                len(d["items"]) == 1
                and d["items"][0][0] == "re"
                and (fitz.Rect(d["rect"]) & page.rect).get_area()
                > page.rect.get_area() * 0.9
            )
        ]
        for cluster in page.cluster_drawings(drawings=drawings):
            rect = fitz.Rect(cluster) & page.rect
            if rect.is_empty or rect.width < 8 or rect.height < 8:
                continue
            if any(
                e["kind"] == "image"
                and e["page"] == page.number
                and fitz.Rect(e["bbox"]).contains(rect)
                for e in elements
            ):
                continue
            scale = min(2, math.sqrt(16_000_000 / max(rect.get_area(), 1)))
            image = page.get_pixmap(
                matrix=fitz.Matrix(scale, scale), clip=rect, alpha=False
            ).tobytes("png")
            elements.append(
                dict(
                    kind="image",
                    page=page.number,
                    bbox=tuple(rect),
                    image=image,
                    media_name=hashlib.sha256(image).hexdigest() + ".png",
                    warnings=[
                        "Schéma vectoriel conservé comme image ; vérifier les superpositions."
                    ],
                    source_id=f"{page.number}:vector:{len(elements)}",
                )
            )
    return sorted(elements, key=_order)


def detect_boundaries(elements):
    """Global boundaries: a card may span pages. Return every marker, even empty."""
    markers = [
        (i, e)
        for i, e in enumerate(elements)
        if e["kind"] == "text" and MARKER.fullmatch(e["original_text"])
    ]
    return [
        (
            marker,
            elements[i + 1 : markers[n + 1][0]]
            if n + 1 < len(markers)
            else elements[i + 1 :],
        )
        for n, (i, marker) in enumerate(markers)
    ]


def reconstruct_lines(elements):
    """Attach separately encoded bullet glyphs to the closest baseline, retaining provenance."""
    items = copy.deepcopy(elements)
    consumed = set()
    for i, item in enumerate(items):
        if item["kind"] != "text" or item["text"] or not item["bullet"]:
            continue
        matches = [
            (
                abs(other["bbox"][1] - item["bbox"][1]),
                other["bbox"][0] - item["bbox"][2],
                j,
            )
            for j, other in enumerate(items)
            if j != i
            and other["kind"] == "text"
            and other["text"]
            and other["page"] == item["page"]
            and abs(other["bbox"][1] - item["bbox"][1])
            <= max(4, item["font_size"] * 0.28)
            and 0 <= other["bbox"][0] - item["bbox"][2] <= 70
        ]
        if len(matches) > 1:
            item["warnings"] = [
                "Puce ambiguë conservée séparément : vérifier son association."
            ]
            continue
        if matches:
            j = min(matches)[2]
            if not items[j]["bullet"]:
                items[j]["bullet"] = True
                items[j]["bullet_text"] = item["bullet_text"]
                items[j]["bullet_source"] = item["source_id"]
                consumed.add(i)
    return [e for i, e in enumerate(items) if i not in consumed]


def _is_continuation(previous, current):
    return (
        previous["kind"] == current["kind"] == "text"
        and current["text"]
        and not current["bullet"]
        and previous["page"] == current["page"]
        and abs(current["text_x"] - previous["text_x"]) <= 4
        and -0.15 * current["font_size"]
        <= current["bbox"][1] - previous["bbox"][3]
        <= 0.4 * current["font_size"]
        and abs(previous["font_size"] - current["font_size"]) < 1
    )


def heading_context(items, stack):
    """Use typographic/indent evidence, never arbitrary preceding body lines.

    A stack follows typography and the measured bullet outline. Wrapped prose
    is never reused as a section label without explicit heading typography.
    Equal-indent, equal-style
    headings are siblings; a deeper heading may inherit a shallower parent.
    Ambiguous first paragraphs are retained whole, without invented parents.
    """
    if not items or items[0]["kind"] != "text" or not items[0]["text"]:
        return [], [], ["Titre absent ou ambigu : saisir un titre avant validation."]
    first = items[0]
    title_lines = [first]
    for item in items[1:]:
        if _is_continuation(title_lines[-1], item) and not (
            title_lines[-1]["bold"] and not item["bold"]
        ):
            title_lines.append(item)
        else:
            break
    styled = first["bold"] or any(
        e["kind"] == "text" and first["font_size"] > e["font_size"] * 1.15
        for e in items[len(title_lines) :]
    )
    # A plain heading can also be established by a uniform text style and
    # multiple indented bullet children. Mixed-style prose is not promoted.
    geometric = (
        not first["bullet"]
        and first.get("uniform_font", False)
        and sum(
            e["kind"] == "text"
            and e.get("bullet")
            and bool(e.get("text"))
            and e["text_x"] > first["text_x"] + 6
            for e in items[len(title_lines) :]
        )
        >= 2
    )
    warnings = []
    if styled or geometric or (stack and first["bullet"]):
        while stack and not (
            stack[-1]["x"] < first["text_x"] - 6
            or stack[-1]["size"] > first["font_size"] * 1.15
        ):
            stack.pop()
        context = [s["title"] for s in stack if s.get("context_allowed", True)]
        stack.append(
            dict(
                title="\n".join(e["text"] for e in title_lines),
                context_allowed=styled or len(title_lines) == 1,
                x=first["text_x"],
                size=first["font_size"],
            )
        )
    else:
        # Only strictly shallower, explicitly styled ancestors can be used.
        context = [
            s["title"]
            for s in stack
            if s["x"] < first["text_x"] - 6 and s.get("context_allowed", True)
        ]
        warnings.append(
            "Premier paragraphe proposé comme titre ; contexte à confirmer."
        )
    if not styled and len(title_lines) > 1:
        warnings.append(
            "Titre issu d’un paragraphe sur plusieurs lignes : confirmer le concept et les parents."
        )
    return title_lines, context, warnings


def assign_indentation(items):
    text = [e for e in items if e["kind"] == "text" and e["text"]]
    positions = []
    for x in sorted(e["text_x"] for e in text):
        if not positions or x - positions[-1] > 4:
            positions.append(x)
    anchors = [
        e.get("text_x", e["bbox"][0])
        for e in items
        if e["kind"] == "image" or e.get("text")
    ]
    origin = min(anchors) if anchors else min((e["bbox"][0] for e in items), default=0)
    previous = None
    for item in items:
        x = item.get("text_x", item["bbox"][0])
        item["indent"] = round(max(0, x - origin), 2)
        item["level"] = (
            min(range(len(positions)), key=lambda n: abs(positions[n] - x))
            if positions
            else 0
        )
        item["continuation"] = bool(previous and _is_continuation(previous, item))
        previous = item
    return positions


def associate_images(items):
    """An orphan bullet beside an image stays visible and adopts its image's row."""
    warnings = []
    for item in items:
        if item["kind"] != "text" or item["text"]:
            continue
        images = [
            e
            for e in items
            if e["kind"] == "image"
            and e["page"] == item["page"]
            and e["bbox"][0] >= item["bbox"][2]
            and e["bbox"][1] - 8 <= item["bbox"][1] <= e["bbox"][3] + 8
        ]
        if images:
            item["image_association"] = images[0]["media_name"]
            item["image_source_id"] = images[0]["source_id"]
        else:
            warnings.append("Puce isolée conservée : association à vérifier.")
    return warnings


def render_text(block):
    """Retain PDF script sizing while original text is unchanged in the editor."""
    value = block.get("text", "")
    runs = block.get("text_runs", [])
    if value != block.get("layout_text") or not runs:
        return html.escape(value)
    output = []
    for run in runs:
        text = html.escape(run["text"])
        if abs(run["ratio"] - 1) > 0.01 or abs(run["rise"]) > 0.01:
            text = (
                f'<span style="font-size:{run["ratio"] * 100:.6g}%;'
                f'vertical-align:{run["rise"]:.6g}em">{text}</span>'
            )
        output.append(text)
    return "".join(output)


def _display_bullet(value):
    # Wingdings' Unicode mappings (§, ®, }) do not represent the printed
    # bullet. Keep numbering; normalize other glyphs for ordinary HTML fonts.
    return value if re.fullmatch(r"\d+[.)]", value) else "•"


def render_blocks(blocks):
    """HTML derived from editable text + physical indentation, preserving line order."""
    result = []
    image_ids = {b.get("source_id") for b in blocks if b["kind"] == "image"}
    associated = {}
    for b in blocks:
        if b.get("image_source_id") in image_ids and not b.get("text"):
            associated.setdefault(b["image_source_id"], []).append(b)
    for block in blocks:
        if block.get("image_source_id") in associated and not block.get("text"):
            continue  # Its glyph is rendered beside the associated image below.
        margin = float(block.get("indent", 0))
        if not math.isfinite(margin) or not 0 <= margin <= 10000:
            raise ValueError("Retrait invalide.")
        style = f"position:relative;margin-left:{margin + 24:g}px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.4;"
        if block["kind"] == "image":
            glyphs = ""
            for linked in associated.get(block.get("source_id"), []):
                if linked.get("bullet"):
                    fraction = max(
                        0,
                        min(
                            100,
                            100
                            * (linked["bbox"][1] - block["bbox"][1])
                            / max(1, block["bbox"][3] - block["bbox"][1]),
                        ),
                    )
                    glyphs += (
                        f'<span style="position:absolute;right:100%;margin-right:8px;top:{fraction:g}%">'
                        f"{html.escape(_display_bullet(linked.get('bullet_text', '•')))}</span>"
                    )
            result.append(
                f'<div style="{style}">{glyphs}<img src="{html.escape(block["media_name"], quote=True)}" '
                'style="max-width:100%;height:auto" alt="Image du PDF"></div>'
            )
        else:
            bullet = block.get("bullet_text", "") if block.get("bullet") else ""
            # Separate display lines preserve uncertain wraps and each bullet point.
            # Hanging bullets must not shift text relative to wrapped lines.
            glyph = (
                (
                    f'<span style="position:absolute;right:100%;margin-right:8px">'
                    f"{html.escape(_display_bullet(bullet))}</span>"
                )
                if bullet
                else ""
            )
            value = render_text(block)
            result.append(
                f'<div data-level="{block.get("level", 0)}" style="{style}">{glyph}{value}</div>'
            )
    return "\n".join(result)


def parse_pdf(data):
    cards = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        elements = extract_elements(doc)
        boundaries = detect_boundaries(elements)
        stack = []
        # Only explicit styling creates context before the first marker.
        if boundaries:
            first_marker = elements.index(boundaries[0][0])
            for e in reconstruct_lines(elements[:first_marker]):
                if e["kind"] == "text" and e["bold"]:
                    heading_context([e], stack)
        for number, (marker, raw) in enumerate(boundaries):
            items = reconstruct_lines(raw)
            title_lines, context, warnings = heading_context(items, stack)
            title = "\n".join(e["text"] for e in title_lines)
            body = items[len(title_lines) :]
            if not body:
                warnings.append(
                    "Aucun verso distinct : vérifier la répartition titre/contenu."
                )
            text_items = [e for e in items if e["kind"] == "text" and e["text"]]
            for a, b in zip(text_items, text_items[1:]):
                if a["page"] == b["page"] and abs(a["bbox"][1] - b["bbox"][1]) < 3:
                    warnings.append(
                        "Colonnes ou fragments sur une même ligne : ordre à vérifier."
                    )
            for image in (e for e in items if e["kind"] == "image"):
                if any(
                    t["page"] == image["page"]
                    and (fitz.Rect(t["bbox"]) & fitz.Rect(image["bbox"])).get_area() > 4
                    for t in text_items
                ):
                    warnings.append(
                        "Texte superposé à une image : vérifier les doublons et les associations."
                    )
            # Walk only bullet-defined outline nodes beneath an established
            # heading. Wrapped lines are never new parents. This carries the
            # actual indentation tree across CARTE markers, including section
            # transitions that occur at the end of the preceding card.
            if stack and title_lines:
                previous = None
                for element in body:
                    if element["kind"] != "text" or not element["text"]:
                        continue
                    if previous and _is_continuation(previous, element):
                        if (
                            stack
                            and stack[-1].get("source_id") == previous["source_id"]
                        ):
                            stack[-1]["title"] += "\n" + element["text"]
                            stack[-1]["source_id"] = element["source_id"]
                            stack[-1]["context_allowed"] = False
                        previous = element
                        continue
                    previous = element
                    if not element["bullet"]:
                        continue
                    x = element["text_x"]
                    while stack and stack[-1]["x"] >= x - 4:
                        stack.pop()
                    if stack:
                        stack.append(
                            dict(
                                title=element["text"],
                                context_allowed=True,
                                x=x,
                                size=element["font_size"],
                                source_id=element["source_id"],
                            )
                        )
            positions = assign_indentation(body)
            warnings += associate_images(body)
            for e in items:
                warnings.extend(e.get("warnings", []))
                if e["kind"] == "text" and e.get("direction") != (1.0, 0.0):
                    warnings.append(
                        "Texte tourné : vérifier l’ordre de lecture dans le PDF."
                    )
                if e["kind"] == "text" and "\ufffd" in e["text"]:
                    warnings.append("Caractère non décodé : consulter le PDF source.")
            if any(
                e["kind"] == "text"
                and not e.get("bullet")
                and not e.get("continuation")
                for e in body
            ):
                warnings.append(
                    "Lignes sans puce conservées avec leur retrait ; vérifier les paragraphes."
                )
            kind = " ".join(marker["original_text"].upper().split())
            if kind == "CARTE CLOZE":
                warnings.append(
                    "Cloze : ajouter/vérifier les suppressions {{c1::texte}} avant export."
                )
            regions = []
            # Full card source is reviewable across page boundaries, including markers.
            for page_no in sorted({marker["page"]} | {e["page"] for e in raw}):
                page = doc[page_no]
                page_items = [e for e in [marker] + raw if e["page"] == page_no]
                rect = fitz.Rect(page_items[0]["bbox"])
                for e in page_items[1:]:
                    rect |= fitz.Rect(e["bbox"])
                rect = (
                    fitz.Rect(rect.x0 - 8, rect.y0 - 6, rect.x1 + 8, rect.y1 + 6)
                    & page.rect
                )
                regions.append(dict(page=page_no, bbox=tuple(rect)))
            media = list(
                {
                    e["media_name"]: (e["media_name"], e["image"])
                    for e in raw
                    if e["kind"] == "image"
                }.values()
            )
            # Keep coordinates and source text for audits/editing without embedding bytes.
            blocks = [
                {k: v for k, v in e.items() if k not in ("image", "warnings")}
                for e in body
            ]
            title_html = "\n".join(render_text(e) for e in title_lines)
            cards.append(
                dict(
                    id=number,
                    type=kind,
                    front=(html.escape(" — ".join(context)) + " — " if context else "")
                    + title_html
                    if title
                    else "",
                    title=title,
                    title_html=title_html,
                    context=context,
                    back=render_blocks(blocks),
                    blocks=blocks,
                    media=media,
                    warnings=list(dict.fromkeys(warnings)),
                    levels=positions,
                    page=marker["page"],
                    bbox=regions[0]["bbox"],
                    regions=regions,
                    source_elements=[
                        {k: v for k, v in e.items() if k not in ("image", "warnings")}
                        for e in raw
                    ],
                    title_source_ids=[e["source_id"] for e in title_lines]
                    + [e["bullet_source"] for e in title_lines if "bullet_source" in e],
                )
            )
    for card in cards:
        apply_reviewed_partition(card)
        if card["type"] == "CARTE OCCLUSION":
            from occlusion import prepare_occlusion

            prepare_occlusion(card)
    return cards


def apply_reviewed_partition(card):
    """Resolve only the ten exact passages reviewed against the supplied PDFs."""
    if card["blocks"]:
        return
    recipe = recipe_for(card["type"], card["title"])
    if recipe is None:
        return
    body = reconstruct_lines(card["source_elements"])
    source_title = card["title"]
    if recipe["title"] not in source_title:
        card["warnings"].append(
            "Passage reconnu, mais titre coupé différemment : répartition à confirmer dans l’éditeur."
        )
        return
    deletion = recipe.get("deletion")
    if deletion:
        matches = [b for b in body if b["kind"] == "text" and deletion in b["text"]]
        if len(matches) != 1 or matches[0]["text"].count(deletion) != 1:
            card["warnings"].append(
                "Passage reconnu, mais suppression ambiguë ou coupée : annoter dans l’éditeur."
            )
            return
        b = matches[0]
        b["text"] = b["text"].replace(deletion, "{{c1::" + deletion + "}}", 1)
    card["title"] = recipe["title"]
    card["title_html"] = html.escape(recipe["title"])
    card["front"] = (
        html.escape(" — ".join(card["context"])) + " — " if card["context"] else ""
    ) + card["title_html"]
    card["source_title"] = source_title
    card["source_title_restored"] = True
    card["source_partitioned"] = True
    card["title_source_ids"] = []
    card["reviewed_recipe"] = recipe["id"]
    card["blocks"] = body
    card["levels"] = assign_indentation(body)
    card["back"] = render_blocks(body)
    card["warnings"] = [
        w
        for w in card["warnings"]
        if not w.startswith(
            (
                "Aucun verso distinct",
                "Cloze : ajouter",
                "Premier paragraphe",
                "Titre issu d’un paragraphe",
            )
        )
    ]
    if deletion:
        card["cloze_body_only"] = True
        card["proposed_deletion"] = deletion
        card["warnings"].append(
            "Cible Cloze proposée depuis le texte original : "
            + deletion
            + ". À confirmer avant validation."
        )
    else:
        card["warnings"].append(
            "Recto extrait littéralement du passage ; le texte source intégral est conservé au verso. À vérifier avant validation."
        )


def restore_source_title(card, source_title):
    """Recover a heading misclassified as the whole question, once only."""
    if source_title and not card.get("source_title_restored"):
        card["blocks"].insert(
            0,
            dict(
                kind="text",
                text=source_title,
                indent=0,
                level=0,
                bullet=False,
                restored_source_title=True,
            ),
        )
        card["source_title_restored"] = True


def update_edited_levels(blocks):
    """Keep exported level metadata in step with explicit editor indents."""
    positions = []
    for value in sorted(
        float(b["indent"]) for b in blocks if b["kind"] == "text" and b.get("text")
    ):
        if not positions or value - positions[-1] > 4:
            positions.append(value)
    for b in blocks:
        b["level"] = (
            min(range(len(positions)), key=lambda n: abs(positions[n] - b["indent"]))
            if positions
            else 0
        )
    return positions


def preview_html(back, media):
    for name, raw in media:
        back = back.replace(
            'src="' + name + '"',
            'src="data:image/png;base64,' + base64.b64encode(raw).decode() + '"',
        )
    return back


def crop(data, card, scale=2, region_index=0):
    region = card.get("regions", [dict(page=card["page"], bbox=card["bbox"])])[
        region_index
    ]
    with fitz.open(stream=data, filetype="pdf") as doc:
        page = doc[region["page"]]
        rect = fitz.Rect(region["bbox"]) & page.rect
        zoom = min(scale, math.sqrt(16_000_000 / max(rect.get_area(), 1)))
        return page.get_pixmap(
            matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False
        ).tobytes("png")
