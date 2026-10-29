
"""Anki Studio V7 — PDF geometry extraction."""
import base64
import hashlib
import html
import re
import fitz

MARKER = re.compile(
    r"^CARTE(?:\s+(?:CLOZE|OCCLUSION))?$", re.I
)
BULLETS = set("•●○◦▪▫□■◆◇◊–−-·§")
NOISE = {"®", "©", "™"}
SYMBOLS = ["●", "○", "■", "◇", "◆", "◦"]

def tidy(s):
    return re.sub(r"\s+", " ", s).strip()

def is_bullet(s):
    return s in BULLETS or bool(
        re.fullmatch(r"\d+[.)]", s)
    )

def line_html(spans):
    parts = []
    for span in spans:
        text = span["text"]
        if not text:
            continue
        value = html.escape(text)
        font = span.get("font", "").lower()
        flags = span.get("flags", 0)
        bold = (
            "bold" in font
            or bool(flags & 16)
        )
        if bold:
            value = "<strong>" + value + "</strong>"
        parts.append(value)
    return "".join(parts)

def extract_lines(page):
    result = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] == 1:
            result.append({
                "kind": "image",
                "bbox": tuple(block["bbox"]),
                "x": block["bbox"][0],
                "y": block["bbox"][1],
                "end": block["bbox"][3]
            })
            continue
        if block["type"] != 0:
            continue

        for line in block["lines"]:
            spans = sorted(
                [s for s in line["spans"]
                 if s["text"].strip()],
                key=lambda s: s["bbox"][0]
            )
            if not spans:
                continue

            value = tidy(
                "".join(s["text"] for s in spans)
            )
            if not value:
                continue

            first = tidy(spans[0]["text"])
            bullet = False
            x = spans[0]["bbox"][0]

            if is_bullet(first) and len(spans) > 1:
                bullet = True
                x = spans[1]["bbox"][0]
                value = tidy(
                    "".join(s["text"] for s in spans[1:])
                )
                rich = line_html(spans[1:])
            else:
                match = re.match(
                    r"^([•●○◦▪▫□■◆◇◊–−\-·§])\s+",
                    value
                )
                bullet = bool(match)
                rich = line_html(spans)
                if match:
                    value = value[match.end():]
                    rich = html.escape(value)
                    x += 10

            result.append({
                "kind": "text",
                "text": value,
                "rich": rich,
                "x": float(x),
                "bullet": bullet,
                "bbox": tuple(line["bbox"]),
                "y": line["bbox"][1],
                "end": line["bbox"][3]
            })

    return sorted(
        result,
        key=lambda it: (round(it["y"], 1), it["x"])
    )

def normalize(items):
    result = []
    used = set()

    for i, item in enumerate(items):
        if item["kind"] != "text":
            continue
        if not is_bullet(item["text"]):
            continue

        for j, other in enumerate(items):
            if i == j or other["kind"] != "text":
                continue
            if is_bullet(other["text"]):
                continue

            same_line = abs(
                item["y"] - other["y"]
            ) < 5

            to_right = (
                0 <= other["x"] - item["x"] < 90
            )

            if same_line and to_right:
                used.add(i)
                other["bullet"] = True
                break

    for i, item in enumerate(items):
        if i in used:
            continue

        if (
            item["kind"] == "text"
            and is_bullet(item["text"])
        ):
            result.append({
                "kind": "orphan",
                "x": item["x"],
                "y": item["y"],
                "end": item["end"],
                "bbox": item["bbox"]
            })
        else:
            result.append(item.copy())

    return result

def join_wrapped(items):
    result = []

    for item in items:
        current = item.copy()

        if (
            current["kind"] == "text"
            and result
            and result[-1]["kind"] == "text"
        ):
            previous = result[-1]
            gap = current["y"] - previous["end"]

            if (
                not current["bullet"]
                and not MARKER.fullmatch(current["text"])
                and abs(
                    current["x"] - previous["x"]
                ) <= 2
                and -1 <= gap <= 2
                and not re.search(
                    r"[.!?:;]$", previous["text"]
                )
            ):
                previous["text"] += " " + current["text"]
                previous["rich"] += " " + current["rich"]
                previous["end"] = current["end"]
                continue

        result.append(current)

    return result

def levels_for(items):
    xs = sorted(
        it["x"] for it in items
        if it["kind"] == "text"
        and it["text"] not in NOISE
    )

    groups = []
    for x in xs:
        if not groups or x - groups[-1][-1] > 7:
            groups.append([x])
        else:
            groups[-1].append(x)

    return [
        sum(group) / len(group)
        for group in groups
    ]

def level_for(x, levels):
    if not levels:
        return 0
    return min(
        range(len(levels)),
        key=lambda i: abs(x - levels[i])
    )

def context_candidates(items, marker_index, title):
    """Only suggest context; never silently add it."""
    candidates = []
    before = items[:marker_index]

    for item in reversed(before):
        if item["kind"] != "text":
            continue

        value = tidy(item["text"])

        if (
            not value
            or MARKER.fullmatch(value)
            or is_bullet(value)
            or value in NOISE
            or value.lower() in title.lower()
        ):
            continue

        if len(value) <= 95:
            candidates.append(value)

        if len(candidates) == 2:
            break

    return list(reversed(candidates))

def render_body(items, page, levels):
    output = []
    media = []
    warnings = []
    last_level = 0

    for i, item in enumerate(items):
        if item["kind"] == "orphan":
            nearby_image = any(
                other["kind"] == "image"
                and -8 <= other["y"] - item["y"] < 35
                for other in items[i+1:i+5]
            )

            if not nearby_image:
                warnings.append(
                    "Puce isolée : association à vérifier."
                )
            continue

        if item["kind"] == "image":
            rect = fitz.Rect(item["bbox"]) & page.rect
            if rect.is_empty:
                continue

            scale = min(
                2.0,
                1300 / max(rect.width, 1),
                1300 / max(rect.height, 1)
            )

            raw = page.get_pixmap(
                matrix=fitz.Matrix(scale, scale),
                clip=rect,
                alpha=False
            ).tobytes("png")

            name = (
                hashlib.sha1(raw).hexdigest()[:18]
                + ".png"
            )
            media.append((name, raw))

            margin = (last_level + 1) * 24
            output.append(
                '<div style="margin:8px 0 8px '
                f'{margin}px">'
                f'<img src="{name}" '
                'style="max-width:100%;height:auto">'
                '</div>'
            )
            continue

        value = item["text"]
        if value in NOISE:
            warnings.append(
                "Caractère suspect isolé : vérifier le PDF."
            )
            continue

        if not value:
            continue

        level = level_for(item["x"], levels)
        last_level = level
        symbol = SYMBOLS[level % len(SYMBOLS)]

        output.append(
            '<div style="display:flex;'
            'align-items:flex-start;'
            'gap:8px;line-height:1.5;'
            f'margin:5px 0 5px {level*24}px">'
            '<span style="flex:none;width:16px;'
            'font-weight:normal">'
            f'{symbol}</span>'
            '<span style="min-width:0">'
            f'{item["rich"]}</span></div>'
        )

    return "\n".join(output), media, warnings

def parse_pdf(data):
    cards = []

    with fitz.open(stream=data, filetype="pdf") as doc:
        for page_number, page in enumerate(doc):
            all_items = extract_lines(page)

            markers = [
                i for i, item in enumerate(all_items)
                if item["kind"] == "text"
                and MARKER.fullmatch(item["text"])
            ]

            for n, start in enumerate(markers):
                stop = (
                    markers[n+1]
                    if n+1 < len(markers)
                    else len(all_items)
                )

                raw = all_items[start+1:stop]
                if not raw:
                    continue

                items = join_wrapped(
                    normalize([it.copy() for it in raw])
                )

                headings = [
                    it for it in items
                    if it["kind"] == "text"
                    and it["text"] not in NOISE
                ]
                if not headings:
                    continue

                heading = headings[0]
                body = items[
                    items.index(heading)+1:
                ]

                levels = levels_for(body)
                back, media, warnings = render_body(
                    body, page, levels
                )

                context = context_candidates(
                    all_items, start, heading["text"]
                )

                title = heading["text"]
                suggested = " — ".join(
                    context + [title]
                ) if context else title

                if len(levels) > 3:
                    warnings.append(
                        f"{len(levels)} niveaux détectés : "
                        "vérifier les retraits."
                    )

                kind = all_items[start]["text"].upper()
                if kind != "CARTE":
                    warnings.append(
                        "Cloze/Occlusion : export indisponible."
                    )

                visible = [
                    it["bbox"]
                    for it in [all_items[start]] + raw
                    if it["kind"] in ("text", "image")
                ]

                bottom = (
                    all_items[stop]["y"]
                    if stop < len(all_items)
                    else max(r[3] for r in visible) + 12
                )

                cards.append({
                    "page": page_number,
                    "type": kind,
                    "front": html.escape(title),
                    "suggested_front": html.escape(suggested),
                    "back": back,
                    "media": media,
                    "bbox": (
                        max(0, min(r[0] for r in visible)-16),
                        max(0, all_items[start]["y"]-8),
                        min(
                            page.rect.x1,
                            max(r[2] for r in visible)+16
                        ),
                        min(page.rect.y1, bottom)
                    ),
                    "warnings": list(dict.fromkeys(warnings)),
                    "levels": levels
                })

    return cards

def preview_html(back, media):
    for filename, raw in media:
        encoded = base64.b64encode(raw).decode()
        back = back.replace(
            'src="' + filename + '"',
            'src="data:image/png;base64,'
            + encoded + '"'
        )
    return back

def crop(data, card, scale=2):
    with fitz.open(stream=data, filetype="pdf") as doc:
        page = doc[card["page"]]
        rect = fitz.Rect(card["bbox"]) & page.rect

        zoom = min(
            scale,
            1900 / max(rect.width, 1),
            5500 / max(rect.height, 1)
        )

        return page.get_pixmap(
            matrix=fitz.Matrix(zoom, zoom),
            clip=rect,
            alpha=False
        ).tobytes("png")
