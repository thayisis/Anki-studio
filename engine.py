
"""Experimental, geometry-first extraction. No AI and no inferred missing content."""
import base64
import hashlib
import html
import re
import fitz

MARKER = re.compile(r'^CARTE(?:\s+(?:CLOZE|OCCLUSION))?$', re.I)
BULLETS = {'•','○','◦','▪','▫','□','■','-','–','−','§','◊','®','·','●','o'}

def tidy(s):
    return re.sub(r'\s+', ' ', s).strip()

def extract_lines(page):
    out=[]
    for block in page.get_text('dict', sort=False)['blocks']:
        if block['type']==1:
            out.append(dict(kind='image', bbox=tuple(block['bbox']), x=block['bbox'][0],y=block['bbox'][1],end=block['bbox'][3]))
            continue
        if block['type']!=0: continue
        for ln in block['lines']:
            spans=[s for s in ln['spans'] if s['text'].strip()]
            if not spans: continue
            spans.sort(key=lambda s:s['bbox'][0])
            s=tidy(' '.join(v['text'] for v in spans))
            if not s:continue
            first=tidy(spans[0]['text'])
            glyph=(first in BULLETS or bool(re.fullmatch(r'\d+[.)]',first)))
            if not glyph and re.match(r'^(?:[•○◦▪▫□■–−§◊®]|\d+[.)])\s+',s): glyph=True
            text_x=spans[1]['bbox'][0] if glyph and len(spans)>1 else spans[0]['bbox'][0]
            out.append(dict(kind='text',text=s,x=float(text_x),bullet=glyph,bbox=tuple(ln['bbox']),y=ln['bbox'][1],end=ln['bbox'][3]))
    return sorted(out,key=lambda i:(round(i['y'],1),i['x']))

def join_wrapped(items):
    merged=[]
    for item in items:
        if item['kind']!='text': merged.append(item.copy());continue
        current=item.copy()
        if merged and merged[-1]['kind']=='text':
            prev=merged[-1]
            gap=current['y']-prev['end']
            if (not current['bullet'] and not MARKER.fullmatch(current['text'])
                and abs(current['x']-prev['x'])<=5 and -3<=gap<=14
                and not MARKER.fullmatch(prev['text'])):
                prev['text'] += ' '+current['text']
                prev['end']=current['end']
                prev['bbox']=(min(prev['bbox'][0],current['bbox'][0]),prev['bbox'][1],max(prev['bbox'][2],current['bbox'][2]),current['bbox'][3])
                continue
        merged.append(current)
    return merged

def infer_level(items):
    xs=sorted([it['x'] for it in items if it['kind']=='text' and it['text'] not in BULLETS])
    levels=[]
    for x in xs:
        if not levels or x-levels[-1]>7:levels.append(x)
    return levels

def assign_level(x,levels):
    return min(range(len(levels)),key=lambda i:abs(x-levels[i])) if levels else 0

def section_html(items,page,levels):
    fragments=[]; media=[]; issues=[]
    for it in items:
        if it['kind']=='image':
            rect=fitz.Rect(it['bbox']) & page.rect
            if rect.is_empty:continue
            z=min(2.2,1400/max(rect.width,1),1400/max(rect.height,1))
            raw=page.get_pixmap(matrix=fitz.Matrix(z,z),clip=rect,alpha=False).tobytes('png')
            key=hashlib.sha1(raw).hexdigest()[:16]+'.png'
            media.append((key,raw))
            fragments.append(f'<div style="margin:7px 0"><img src="{key}" style="max-width:100%;height:auto"></div>')
        else:
            if it['text'] in BULLETS:
                issues.append('Symbole de puce isolé dans le PDF : vérifier la zone.');continue
            level=assign_level(it['x'],levels)
            indent=min(240,level*22)
            fragments.append(f'<div style="margin-left:{indent}px;margin-bottom:5px;white-space:normal">{html.escape(it["text"])}</div>')
    return '\n'.join(fragments),media,issues

def parse_pdf(data):
    doc=fitz.open(stream=data,filetype='pdf'); cards=[]
    for page_number,page in enumerate(doc):
        all_items=extract_lines(page)
        marks=[i for i,v in enumerate(all_items) if v['kind']=='text' and MARKER.fullmatch(v['text'])]
        for k,start in enumerate(marks):
            stop=marks[k+1] if k+1<len(marks) else len(all_items)
            raw=all_items[start+1:stop]
            if not raw:continue
            items=join_wrapped(raw)
            texts=[v for v in items if v['kind']=='text' and v['text'] not in BULLETS]
            if not texts: continue
            heading=texts[0]
            title=heading['text']
            body=items[items.index(heading)+1:]
            levels=infer_level(body)
            back,media,issues=section_html(body,page,levels)
            marker=all_items[start]
            last=max([v['end'] for v in raw],default=marker['end'])
            bottom=min(page.rect.y1,all_items[stop]['y'] if stop<len(all_items) else last+12)
            card_type=marker['text'].upper()
            if card_type!='CARTE':issues.append('Cloze/Occlusion : export non implémenté.')
            if any(v['kind']=='image' for v in raw):issues.append('Vérifier manuellement la position des images et les éventuelles annotations.')
            if len(levels)>3:issues.append(f'{len(levels)} niveaux de retrait détectés : contrôler les niveaux complexes.')
            cards.append(dict(page=page_number,type=card_type,front=html.escape(title),back=back,
                              media=media,bbox=(0,max(0,marker['y']-7),page.rect.x1,max(marker['y']+1,bottom)),
                              warnings=list(dict.fromkeys(issues)),levels=levels))
    doc.close();return cards

def preview_html(back,media):
    for filename,raw in media:
        back=back.replace('src="'+filename+'"','src="data:image/png;base64,'+base64.b64encode(raw).decode()+'"')
    return back

def crop(data,card,scale=1.8):
    with fitz.open(stream=data,filetype='pdf') as doc:
        page=doc[card['page']]
        rect=fitz.Rect(card['bbox']) & page.rect
        z=min(scale,2200/max(rect.width,1),5200/max(rect.height,1))
        return page.get_pixmap(matrix=fitz.Matrix(z,z),clip=rect,alpha=False).tobytes('png')
