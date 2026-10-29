
"""Anki Studio V5: experimental geometry-based PDF extraction."""
import base64
import hashlib
import html
import re
import fitz

MARKER = re.compile(r'^CARTE(?:\s+(?:CLOZE|OCCLUSION))?$', re.I)
BULLET = re.compile(r'^(?:[•●○◦▪▫□■◆◇◊–−\-·§]|\d+[.)])(?:\s+|$)')
LONE = {'•','●','○','◦','▪','▫','□','■','◆','◇','◊','–','−','-','·','§'}
GLYPHS = ['●','○','■','◇','◆','◦']

def tidy(s):
    return re.sub(r'\s+', ' ', s).strip()

def extract_lines(page):
    items=[]
    for block in page.get_text('dict',sort=False)['blocks']:
        if block['type']==1:
            items.append(dict(kind='image',bbox=tuple(block['bbox']),x=block['bbox'][0],y=block['bbox'][1],end=block['bbox'][3]))
            continue
        if block['type']!=0:
            continue
        for line in block['lines']:
            spans=sorted(
                (s for s in line['spans'] if s['text'].strip()),
                key=lambda s:s['bbox'][0]
            )
            if not spans:
                continue
            content=tidy(' '.join(s['text'] for s in spans))
            if not content:
                continue
            first=tidy(spans[0]['text'])
            explicit=bool(BULLET.match(content))
            x=spans[0]['bbox'][0]
            if first in LONE and len(spans)>1:
                x=spans[1]['bbox'][0]
            elif explicit and len(spans)==1:
                lead=BULLET.match(content).group()
                x+=min(22,max(7,len(lead)*spans[0]['size']*.48))
            items.append(dict(
                kind='text',
                text=content,
                x=float(x),
                bullet=explicit,
                bbox=tuple(line['bbox']),
                y=line['bbox'][1],
                end=line['bbox'][3]
            ))
    items.sort(key=lambda a:(round(a['y'],1),a['x']))
    return items

def normalize_bullets(items):
    """Attach separately extracted glyphs to adjacent text."""
    result=[]
    for item in items:
        it=item.copy()
        if it['kind']!='text':
            result.append(it)
            continue
        if it['text'] in LONE:
            match=None
            for candidate in items:
                if candidate is item or candidate['kind']!='text' or candidate['text'] in LONE:
                    continue
                if (abs(candidate['y']-it['y'])<7
                    and candidate['x']>=it['x']
                    and candidate['x']-it['x']<70):
                    match=candidate
                    break
            if match is not None:
                match['_bullet_from_glyph']=True
                continue
            result.append(dict(
                kind='orphan',
                y=it['y'],
                end=it['end'],
                bbox=it['bbox']
            ))
            continue
        it['bullet']=it['bullet'] or item.get('_bullet_from_glyph',False)
        result.append(it)

    originals=[
        i for i in items
        if i['kind']!='text' or i['text'] not in LONE
    ]
    copies=[i for i in result if i['kind']!='orphan']
    for original,copy in zip(originals,copies):
        if original.get('_bullet_from_glyph') and copy['kind']=='text':
            copy['bullet']=True
    return result

def join_wrapped(items):
    result=[]
    for item in items:
        cur=item.copy()
        if cur['kind']!='text':
            result.append(cur)
            continue
        if result and result[-1]['kind']=='text':
            prev=result[-1]
            gap=cur['y']-prev['end']
            if (not cur['bullet']
                and not MARKER.fullmatch(cur['text'])
                and abs(cur['x']-prev['x'])<=3
                and -2<=gap<=3.5
                and not re.search(r'[.!?:;]$',prev['text'])):
                prev['text']+=' '+cur['text']
                prev['end']=cur['end']
                continue
        result.append(cur)
    return result

def levels_for(items):
    xs=sorted(
        i['x'] for i in items
        if i['kind']=='text' and i['text'] not in LONE
    )
    if not xs:
        return []
    groups=[]
    for x in xs:
        if not groups or x-groups[-1][-1]>6:
            groups.append([x])
        else:
            groups[-1].append(x)
    return [sum(g)/len(g) for g in groups]

def level_for(x,levels):
    return min(
        range(len(levels)),
        key=lambda i:abs(x-levels[i])
    ) if levels else 0

def section_html(items,page,levels):
    out=[]
    media=[]
    issues=[]
    for it in items:
        if it['kind']=='orphan':
            issues.append(
                'Une puce sans texte associé a été ignorée : vérifier le PDF.'
            )
            continue

        if it['kind']=='image':
            rect=fitz.Rect(it['bbox']) & page.rect
            if rect.is_empty:
                continue
            zoom=min(
                2.0,
                1300/max(rect.width,1),
                1300/max(rect.height,1)
            )
            raw=page.get_pixmap(
                matrix=fitz.Matrix(zoom,zoom),
                clip=rect,
                alpha=False
            ).tobytes('png')
            name=hashlib.sha1(raw).hexdigest()[:18]+'.png'
            media.append((name,raw))
            out.append(
                f'<div style="margin:9px 0">'
                f'<img src="{name}" '
                f'style="max-width:100%;height:auto"></div>'
            )
            continue

        text=(
            BULLET.sub('',it['text'],count=1).strip()
            if it['bullet']
            else it['text']
        )
        if not text:
            issues.append('Une ligne vide a été ignorée.')
            continue

        level=level_for(it['x'],levels)
        indent=level*23
        symbol=GLYPHS[level%len(GLYPHS)]

        out.append(
            '<div style="display:flex;align-items:flex-start;gap:7px;'
            f'margin:4px 0 4px {indent}px;line-height:1.45">'
            f'<span style="flex:none;width:15px">{symbol}</span>'
            f'<span style="min-width:0">{html.escape(text)}</span>'
            '</div>'
        )
    return '\n'.join(out),media,issues

def parse_pdf(data):
    cards=[]
    with fitz.open(stream=data,filetype='pdf') as doc:
        for p,page in enumerate(doc):
            all_items=extract_lines(page)
            marks=[
                i for i,it in enumerate(all_items)
                if it['kind']=='text' and MARKER.fullmatch(it['text'])
            ]

            for n,start in enumerate(marks):
                stop=(
                    marks[n+1]
                    if n+1<len(marks)
                    else len(all_items)
                )
                raw=all_items[start+1:stop]
                if not raw:
                    continue

                items=join_wrapped(normalize_bullets(raw))
                headings=[
                    i for i in items
                    if i['kind']=='text' and i['text'] not in LONE
                ]
                if not headings:
                    continue

                heading=headings[0]
                body=items[items.index(heading)+1:]
                levels=levels_for(body)
                back,media,issues=section_html(body,page,levels)
                marker=all_items[start]

                last=max(
                    (it['end'] for it in raw),
                    default=marker['end']
                )
                bottom=min(
                    page.rect.y1,
                    all_items[stop]['y']
                    if stop<len(all_items)
                    else last+12
                )
                kind=marker['text'].upper()

                if kind!='CARTE':
                    issues.append(
                        'Cloze/Occlusion : export non implémenté.'
                    )
                if media:
                    issues.append(
                        'Vérifier la position et le contenu des images dans le PDF.'
                    )
                if len(levels)>3:
                    issues.append(
                        f'{len(levels)} niveaux de retrait détectés : vérifier leur hiérarchie.'
                    )

                visible=[
                    it['bbox']
                    for it in [marker]+raw
                    if it['kind'] in ('text','image')
                ]
                x0=max(0,min(r[0] for r in visible)-16)
                x1=min(
                    page.rect.x1,
                    max(r[2] for r in visible)+16
                )

                cards.append(dict(
                    page=p,
                    type=kind,
                    front=html.escape(heading['text']),
                    back=back,
                    media=media,
                    bbox=(
                        x0,
                        max(0,marker['y']-8),
                        x1,
                        max(marker['y']+1,bottom)
                    ),
                    warnings=list(dict.fromkeys(issues)),
                    levels=levels
                ))
    return cards

def preview_html(back,media):
    for filename,raw in media:
        back=back.replace(
            'src="'+filename+'"',
            'src="data:image/png;base64,'
            +base64.b64encode(raw).decode()+'"'
        )
    return back

def crop(data,card,scale=1.8):
    with fitz.open(stream=data,filetype='pdf') as doc:
        page=doc[card['page']]
        rect=fitz.Rect(card['bbox']) & page.rect
        zoom=min(
            scale,
            1900/max(rect.width,1),
            5500/max(rect.height,1)
        )
        return page.get_pixmap(
            matrix=fitz.Matrix(zoom,zoom),
            clip=rect,
            alpha=False
        ).tobytes('png')
