
"""Anki Studio V6 — conservative PDF geometry extraction, not a fidelity guarantee."""
import base64
import hashlib
import html
import re
import fitz

MARKER = re.compile(r'^CARTE(?:\s+(?:CLOZE|OCCLUSION))?$', re.I)
BULLET = re.compile(r'^(?:[•●○◦▪▫□■◆◇◊–−\-·§]|\d+[.)])(?:\s+|$)')
LONE = {'•','●','○','◦','▪','▫','□','■','◆','◇','◊','–','−','-','·','§'}
GLYPHS = ['●','○','■','◇','◆','◦']
NOISE = {'®', '©', '™'}

def tidy(value):
    return re.sub(r'\s+', ' ', value).strip()

def extract_lines(page):
    result = []
    for block in page.get_text('dict', sort=False)['blocks']:
        if block['type'] == 1:
            result.append(dict(kind='image', bbox=tuple(block['bbox']), x=block['bbox'][0], y=block['bbox'][1], end=block['bbox'][3]))
        elif block['type'] == 0:
            for line in block['lines']:
                spans = sorted((s for s in line['spans'] if s['text'].strip()), key=lambda s: s['bbox'][0])
                if not spans:
                    continue
                value = tidy(' '.join(s['text'] for s in spans))
                if not value:
                    continue
                first = tidy(spans[0]['text'])
                bullet = bool(BULLET.match(value))
                x = spans[1]['bbox'][0] if first in LONE and len(spans) > 1 else spans[0]['bbox'][0]
                if bullet and len(spans) == 1:
                    x += min(22, max(7, spans[0]['size'] * .48))
                result.append(dict(kind='text', text=value, x=float(x), bullet=bullet,
                                   bbox=tuple(line['bbox']), y=line['bbox'][1], end=line['bbox'][3]))
    return sorted(result, key=lambda it: (round(it['y'], 1), it['x']))

def normalize_bullets(items):
    """Associate glyph-only text with nearby text; keep image-only glyphs out of HTML."""
    out = []
    for i, original in enumerate(items):
        it = original.copy()
        if it['kind'] != 'text' or it['text'] not in LONE:
            out.append(it)
            continue
        candidate = None
        for j, other in enumerate(items):
            if i == j or other['kind'] != 'text' or other['text'] in LONE:
                continue
            if abs(other['y'] - it['y']) < 6 and 0 <= other['x'] - it['x'] < 85:
                candidate = j
                break
        if candidate is not None:
            items[candidate]['bullet'] = True
        else:
            # Glyph-only line can introduce an image. Preserve the visual image, not an empty bullet.
            out.append(dict(kind='orphan', y=it['y'], end=it['end'], x=it['x'], bbox=it['bbox']))
    for it in out:
        if it['kind'] == 'text':
            for source in items:
                if source['kind'] == 'text' and source['bbox'] == it['bbox']:
                    it['bullet'] = source['bullet']
                    break
    return out

def join_wrapped(items):
    out = []
    for item in items:
        cur = item.copy()
        if cur['kind'] == 'text' and out and out[-1]['kind'] == 'text':
            prev = out[-1]
            gap = cur['y'] - prev['end']
            # Only very close, same-indent, non-bullet lines. Prefer false split to lost list item.
            if (not cur['bullet'] and not MARKER.fullmatch(cur['text'])
                    and abs(cur['x'] - prev['x']) <= 2
                    and -1 <= gap <= 2
                    and not re.search(r'[.!?:;]$', prev['text'])):
                prev['text'] += ' ' + cur['text']
                prev['end'] = cur['end']
                prev['bbox'] = (min(prev['bbox'][0],cur['bbox'][0]),prev['bbox'][1],max(prev['bbox'][2],cur['bbox'][2]),cur['bbox'][3])
                continue
        out.append(cur)
    return out

def levels_for(items):
    xs = sorted(it['x'] for it in items if it['kind'] == 'text' and it['text'] not in NOISE)
    clusters = []
    for x in xs:
        if not clusters or x - clusters[-1][-1] > 7:
            clusters.append([x])
        else:
            clusters[-1].append(x)
    return [sum(group)/len(group) for group in clusters]

def level_for(x, levels):
    return min(range(len(levels)), key=lambda i: abs(x-levels[i])) if levels else 0

def heading_context(all_items, marker_index, heading):
    """Use nearby preceding text as *candidate* context; expose it for review."""
    candidates = []
    for it in reversed(all_items[:marker_index]):
        if it['kind'] != 'text' or MARKER.fullmatch(it['text']):
            continue
        value = tidy(it['text'])
        if (not value or value in LONE or value in NOISE or BULLET.fullmatch(value)
                or re.search(r'\b\d{1,2}:\d{2}\b', value)
                or re.search(r'\b(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\b', value, re.I)):
            continue
        # The immediate text before CARTE can be a parent bullet or a section label.
        if value.lower() not in heading.lower() and len(value) <= 95:
            candidates.append(value)
        if len(candidates) >= 2:
            break
    candidates.reverse()
    return candidates

def section_html(items, page, levels):
    out, media, warnings = [], [], []
    prev_level = 0
    for index, it in enumerate(items):
        if it['kind'] == 'orphan':
            # Do not manufacture empty bullets; a symbol next to an image is not text.
            nearby_image = any(other['kind'] == 'image' and 0 <= other['y'] - it['y'] < 28 for other in items[index+1:index+4])
            if not nearby_image:
                warnings.append('Symbole isolé ignoré : vérifier la zone du PDF.')
            continue
        if it['kind'] == 'image':
            rect = fitz.Rect(it['bbox']) & page.rect
            if rect.is_empty:
                continue
            scale = min(2.0, 1300/max(rect.width,1), 1300/max(rect.height,1))
            raw = page.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=rect,alpha=False).tobytes('png')
            name = hashlib.sha1(raw).hexdigest()[:18] + '.png'
            media.append((name,raw))
            out.append(f'<div style="margin:8px 0 8px {prev_level*23+22}px"><img src="{name}" style="max-width:100%;height:auto"></div>')
            continue
        value = BULLET.sub('',it['text'],count=1).strip() if it['bullet'] else it['text']
        if value in NOISE:
            warnings.append('Caractère isolé suspect ignoré : vérifier le PDF.')
            continue
        if not value:
            continue
        level = level_for(it['x'], levels)
        prev_level = level
        symbol = GLYPHS[level % len(GLYPHS)]
        out.append('<div style="display:flex;align-items:flex-start;gap:7px;line-height:1.45;'
                   f'margin:4px 0 4px {level*23}px">'
                   f'<span style="flex:none;width:15px">{symbol}</span>'
                   f'<span style="min-width:0">{html.escape(value)}</span></div>')
    return '\n'.join(out),media,warnings

def parse_pdf(data):
    cards = []
    with fitz.open(stream=data,filetype='pdf') as doc:
        for p,page in enumerate(doc):
            all_items = extract_lines(page)
            markers = [i for i,it in enumerate(all_items) if it['kind']=='text' and MARKER.fullmatch(it['text'])]
            for n,start in enumerate(markers):
                stop = markers[n+1] if n+1<len(markers) else len(all_items)
                raw = all_items[start+1:stop]
                if not raw:
                    continue
                items = join_wrapped(normalize_bullets([it.copy() for it in raw]))
                headings = [it for it in items if it['kind']=='text' and it['text'] not in LONE and it['text'] not in NOISE]
                if not headings:
                    continue
                heading = headings[0]
                body = items[items.index(heading)+1:]
                levels = levels_for(body)
                back,media,warnings = section_html(body,page,levels)
                context = heading_context(all_items,start,heading['text'])
                # Context is a suggestion only: surrounding text can belong to the previous card.
                if context:
                    warnings.append('Contexte du titre proposé automatiquement : vérifier les titres parents.')
                if len(levels)>3:
                    warnings.append(f'{len(levels)} niveaux de retrait détectés : contrôler la hiérarchie.')
                kind = all_items[start]['text'].upper()
                if kind != 'CARTE':
                    warnings.append('Cloze/Occlusion non exportable.')
                visible = [it['bbox'] for it in [all_items[start]]+raw if it['kind'] in ('text','image')]
                bottom = min(page.rect.y1,all_items[stop]['y'] if stop<len(all_items) else max(r[3] for r in visible)+12)
                cards.append(dict(page=p,type=kind,front=html.escape(heading['text']),
                                  suggested_front=html.escape(' — '.join(context+[heading['text']])) if context else html.escape(heading['text']),
                                  back=back,media=media,
                                  bbox=(max(0,min(r[0] for r in visible)-16),max(0,all_items[start]['y']-8),
                                        min(page.rect.x1,max(r[2] for r in visible)+16),max(all_items[start]['y']+1,bottom)),
                                  warnings=list(dict.fromkeys(warnings)),levels=levels))
    return cards

def preview_html(back,media):
    for filename,raw in media:
        back = back.replace('src="'+filename+'"','src="data:image/png;base64,'+base64.b64encode(raw).decode()+'"')
    return back

def crop(data,card,scale=2):
    with fitz.open(stream=data,filetype='pdf') as doc:
        page=doc[card['page']]
        rect=fitz.Rect(card['bbox']) & page.rect
        zoom=min(scale,1900/max(rect.width,1),5500/max(rect.height,1))
        return page.get_pixmap(matrix=fitz.Matrix(zoom,zoom),clip=rect,alpha=False).tobytes('png')
