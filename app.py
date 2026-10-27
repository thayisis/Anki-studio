import base64
import hashlib
import html
import io
import re
import tempfile
from pathlib import Path

import fitz
import streamlit as st

st.set_page_config(page_title='Anki Studio V2', page_icon='📚', layout='wide')
st.title('📚 Anki Studio V2')
st.caption('Comparaison avec le PDF original • aperçu et corrections • export prudent')
st.info('Les PDF sont traités par le serveur Streamlit, pas par une API d’IA. Sur un hébergement public, n’importez pas de documents confidentiels.')
MARKER = re.compile(r'^CARTE(?:\s+(?:CLOZE|OCCLUSION))?$', re.I)
PREFIX = re.compile(r'^\s*(?:[•○§□®◊–\-]|\d+[.)])\s*')

def parse_pdf(data):
    doc = fitz.open(stream=data, filetype='pdf')
    result = []
    for pno, page in enumerate(doc):
        blocks = page.get_text('dict', sort=False)['blocks']
        items = []
        for block in blocks:
            if block['type'] == 1:
                items.append({'kind':'image','bbox':fitz.Rect(block['bbox']),'y':block['bbox'][1], 'x':block['bbox'][0]})
            elif block['type'] == 0:
                for line in block['lines']:
                    spans = line['spans']
                    if not spans: continue
                    txt = ''.join(s['text'] for s in spans).strip()
                    if txt:
                        bbox=fitz.Rect(line['bbox'])
                        items.append({'kind':'text','text':txt,'bbox':bbox,'x':bbox.x0,'y':bbox.y0})
        items.sort(key=lambda it:(round(it['y'],1),it['x']))
        markers=[(i,it) for i,it in enumerate(items) if it['kind']=='text' and MARKER.fullmatch(it['text'])]
        for j,(start,marker) in enumerate(markers):
            end = markers[j+1][0] if j+1<len(markers) else len(items)
            # Marker blocks are delimited by the next marker, even if the page is very tall.
            contents=items[start+1:end]
            texts=[it for it in contents if it['kind']=='text']
            images=[it for it in contents if it['kind']=='image']
            if not texts and not images: continue
            title=texts[0]['text'] if texts else 'Carte image'
            # Only use a separate front title if first line is an unbulleted heading.
            is_heading=bool(texts) and not PREFIX.match(title)
            front=title if is_heading else (PREFIX.sub('',title) or title)
            body=texts[1:] if is_heading else texts
            # Preserve line positions, not inferred list semantics. This avoids fabricated hierarchy.
            base=min((it['x'] for it in body),default=0)
            fragments=[]
            for it in body:
                indent=max(0,min(240,round((it['x']-base)*0.85)))
                fragments.append(f'<div style="margin-left:{indent}px;white-space:pre-wrap">{html.escape(it["text"])}</div>')
            top=marker['bbox'].y0
            bottom=(markers[j+1][1]['bbox'].y0 if j+1<len(markers) else max([it['bbox'].y1 for it in contents],default=marker['bbox'].y1)+12)
            bottom=min(bottom,page.rect.y1)
            result.append({'page':pno,'type':marker['text'].upper(),'front':html.escape(front),
                           'back':'\n'.join(fragments),'images':images,'bbox':(0,max(0,top-8),page.rect.x1,max(top+1,bottom)),
                           'text_count':len(texts),'warnings':(['Image(s) présentes : leur position doit être contrôlée dans le verso.' ] if images else [])})
    doc.close()
    return result

def crop_png(doc,card,zoom=1.35):
    page=doc[card['page']]
    clip=fitz.Rect(card['bbox']) & page.rect
    if clip.is_empty or clip.height<=0: return None
    # Avoid oversized rasterization of extremely tall single-page exports.
    z=min(zoom, 1800/max(clip.width,1), 3400/max(clip.height,1))
    return page.get_pixmap(matrix=fitz.Matrix(z,z),clip=clip,alpha=False).tobytes('png')

def image_png(page,bbox):
    rect=fitz.Rect(bbox) & page.rect
    if rect.is_empty:return None
    z=min(1.7,1600/max(rect.width,1),1600/max(rect.height,1))
    return page.get_pixmap(matrix=fitz.Matrix(z,z),clip=rect,alpha=False).tobytes('png')

upload=st.file_uploader('Importer un PDF balisé CARTE',type=['pdf'])
if not upload:
    st.write('Importe un PDF pour afficher les cartes et leur extrait original côte à côte.')
    st.stop()
data=upload.getvalue()
digest=hashlib.sha256(data).hexdigest()
if st.session_state.get('source_digest')!=digest:
    with st.spinner('Analyse des marqueurs et positions du PDF…'):
        try: cards=parse_pdf(data)
        except Exception as exc:
            st.error(f'Impossible de lire le PDF : {exc}');st.stop()
    st.session_state.update(source_digest=digest,cards=cards,card_index=0)
cards=st.session_state['cards']
if not cards:
    st.warning('Aucun marqueur CARTE reconnu.');st.stop()
counts={t:sum(c['type']==t for c in cards) for t in ['CARTE','CARTE CLOZE','CARTE OCCLUSION']}
st.write(f'**{len(cards)} sections détectées** · {counts["CARTE"]} classiques · {counts["CARTE CLOZE"]} Cloze · {counts["CARTE OCCLUSION"]} occlusions')
idx=st.number_input('Carte à vérifier',min_value=1,max_value=len(cards),value=min(st.session_state['card_index']+1,len(cards)),step=1)-1
st.session_state['card_index']=idx
card=cards[idx]
doc=fitz.open(stream=data,filetype='pdf')
left,right=st.columns(2)
with left:
    st.subheader('PDF original — zone de la carte')
    try:
        png=crop_png(doc,card)
        if png: st.image(png,use_container_width=True)
    except Exception as exc:st.error(f'Aperçu PDF indisponible : {exc}')
    st.caption(f'Page source : {card["page"]+1} · Type : {card["type"]} · Images détectées : {len(card["images"])}')
with right:
    st.subheader('Carte générée — éditable')
    card['front']=st.text_area('Recto (HTML)',value=card['front'],height=90,key=f'front_{digest}_{idx}')
    card['back']=st.text_area('Verso (HTML)',value=card['back'],height=220,key=f'back_{digest}_{idx}')
    side=st.radio('Aperçu',['Recto','Verso'],horizontal=True)
    preview=card['front'] if side=='Recto' else card['back']
    if side=='Verso' and card['images']:
        for k,im in enumerate(card['images']):
            try:
                raw=image_png(doc[card['page']],im['bbox'])
                if raw: preview+=f'<p><img style="max-width:100%;height:auto" src="data:image/png;base64,{base64.b64encode(raw).decode()}"></p>'
            except Exception: pass
    st.markdown('<div style="border:1px solid #aaa;border-radius:12px;padding:18px;overflow-wrap:anywhere;max-height:550px;overflow-y:auto">'+preview+'</div>',unsafe_allow_html=True)
    if card['images']:st.warning('Les images sont montrées après le texte pour contrôle : leur emplacement exact dans la carte reste à valider.')
    if card['type']!='CARTE':st.warning('Type Cloze / Occlusion : aperçu seulement, export non pris en charge.')
doc.close()
st.divider()
st.subheader('Export Anki')
st.caption('Les types non implémentés sont bloqués : aucune conversion silencieuse en carte classique.')
unsupported=[c for c in cards if c['type']!='CARTE']
if unsupported:
    st.error(f'Export complet bloqué : {len(unsupported)} cartes Cloze/Occlusion non implémentées. Ne pas les perdre en exportant un paquet incomplet.')
else:
    try:
        import genanki
        name=st.text_input('Nom du paquet',value=f'Anki Studio — {Path(upload.name).stem}')
        if st.button('Préparer le paquet .apkg'):
            with st.spinner('Préparation des médias et du paquet…'):
                model=genanki.Model(1607392319,'Anki Studio Basic V2',fields=[{'name':'Front'},{'name':'Back'}],templates=[{'name':'Card 1','qfmt':'{{Front}}','afmt':'{{FrontSide}}<hr id="answer">{{Back}}'}])
                deck=genanki.Deck(2059400110,name)
                media=[]
                with tempfile.TemporaryDirectory() as temp:
                    source=fitz.open(stream=data,filetype='pdf')
                    for i,c in enumerate(cards):
                        back=c['back']
                        for j,im in enumerate(c['images']):
                            raw=image_png(source[c['page']],im['bbox'])
                            if raw:
                                filename=f'anki_{digest[:10]}_{i}_{j}.png'
                                path=Path(temp)/filename
                                path.write_bytes(raw)
                                media.append(str(path))
                                back+=f'<div><img src="{filename}"></div>'
                        deck.add_note(genanki.Note(model=model,fields=[c['front'],back],guid=genanki.guid_for(digest,i)))
                    source.close()
                    package=genanki.Package(deck);package.media_files=media
                    destination=Path(temp)/'cards.apkg';package.write_to_file(str(destination))
                    st.session_state['export_bytes']=destination.read_bytes()
                    st.session_state['export_digest']=digest
    except Exception as exc:st.error(f'Export impossible : {exc}')
    if st.session_state.get('export_digest')==digest and st.session_state.get('export_bytes'):
        st.download_button('⬇️ Télécharger .apkg',st.session_state['export_bytes'],file_name='anki_studio_v2.apkg',mime='application/octet-stream')
st.caption('V2 expérimentale : vérifier chaque ligne, image et indentation. Les retours à la ligne visuels du PDF et l’ordre de certaines images peuvent nécessiter une correction manuelle.')
