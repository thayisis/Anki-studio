import io
import re
import html
import hashlib
import streamlit as st
import fitz

st.set_page_config(page_title='Anki Studio', page_icon='📚', layout='wide')
st.title('📚 Anki Studio')
st.caption('Prototype gratuit • PDF ↔ cartes • aperçu et correction avant export')

MARKER = re.compile(r'^\s*(CARTE(?:\s+CLOZE|\s+OCCLUSION)?)\s*$', re.I)

def extract_cards(data):
    doc = fitz.open(stream=data, filetype='pdf')
    cards, current = [], None
    for page_i, page in enumerate(doc):
        blocks = page.get_text('dict')['blocks']
        lines = []
        for b in blocks:
            if 'lines' not in b: continue
            for ln in b['lines']:
                spans = ln['spans']
                if not spans: continue
                text = ''.join(s['text'] for s in spans).strip()
                if text: lines.append((round(min(s['bbox'][0] for s in spans), 1), round(min(s['bbox'][1] for s in spans),1), text))
        lines.sort(key=lambda x:(x[1],x[0]))
        for x,y,t in lines:
            m=MARKER.fullmatch(t)
            if m:
                if current: cards.append(current)
                current={'type':m.group(1).upper(),'page':page_i,'lines':[]}
            elif current:
                current['lines'].append((x,t))
    if current: cards.append(current)
    out=[]
    for c in cards:
        if not c['lines']: continue
        xs=sorted(set(x for x,t in c['lines']))
        # Geometry-based indentation; tolerance for minor PDF rounding.
        levels=[]
        for x,t in c['lines']:
            candidates=[v for v in xs if abs(v-x)<=5]
            level=xs.index(min(candidates, key=lambda v:abs(v-x))) if candidates else xs.index(x)
            levels.append((level,t))
        # First line is the front; remainder preserved as separate indented lines.
        front=html.escape(levels[0][1])
        back=''.join(f'<div style="margin-left:{min(level,8)*18}px;white-space:pre-wrap">{html.escape(t)}</div>' for level,t in levels[1:])
        out.append({'front':front,'back':back,'page':c['page'],'type':c['type']})
    return out, len(doc)

upload=st.file_uploader('Importer un PDF balisé CARTE', type=['pdf'])
if upload:
    data=upload.getvalue()
    digest=hashlib.sha256(data).hexdigest()
    if st.session_state.get('digest')!=digest:
        try:
            cards,pages=extract_cards(data)
        except Exception as e:
            st.error(f'Lecture impossible : {e}')
            st.stop()
        st.session_state.update(digest=digest,cards=cards,pages=pages,index=0)
    cards=st.session_state['cards']
    if not cards:
        st.warning('Aucune carte détectée. Le PDF doit contenir des lignes CARTE, CARTE CLOZE ou CARTE OCCLUSION.')
        st.stop()
    st.warning('Prototype : la conversion géométrique reste approximative. Les images, les clozes et les occlusions ne sont PAS encore prises en charge. Vérifie chaque carte avant export.')
    idx=st.number_input('Carte', min_value=1,max_value=len(cards),value=min(st.session_state.get('index',0)+1,len(cards)),step=1)-1
    st.session_state['index']=idx
    c=cards[idx]
    left,right=st.columns(2)
    with left:
        st.subheader(f'PDF original — page {c["page"]+1}')
        doc=fitz.open(stream=data,filetype='pdf')
        pix=doc[c['page']].get_pixmap(matrix=fitz.Matrix(1.35,1.35),alpha=False)
        st.image(pix.tobytes('png'),use_container_width=True)
    with right:
        st.subheader(f'Carte {idx+1} / {len(cards)}')
        c['front']=st.text_area('Recto (HTML)',value=c['front'],height=90,key=f'f_{digest}_{idx}')
        c['back']=st.text_area('Verso (HTML)',value=c['back'],height=190,key=f'b_{digest}_{idx}')
        side=st.radio('Aperçu', ['Recto','Verso'],horizontal=True)
        st.markdown('<div style="padding:22px;border:1px solid #bbb;border-radius:12px;min-height:120px">'+(c['front'] if side=='Recto' else c['back'])+'</div>',unsafe_allow_html=True)
        st.caption(f'Type source : {c["type"]} • Les corrections restent dans cette session.')
    st.divider()
    if any(c['type']!='CARTE' for c in cards):
        st.error('Export désactivé : des cartes CLOZE/OCCLUSION nécessitent une implémentation spécifique pour éviter un paquet incorrect.')
    else:
        try:
            import genanki
            model=genanki.Model(1607392319,'Anki Studio Basic',fields=[{'name':'Front'},{'name':'Back'}],templates=[{'name':'Card 1','qfmt':'{{Front}}','afmt':'{{FrontSide}}<hr id="answer">{{Back}}'}])
            deck_name=st.text_input('Nom du paquet','Anki Studio — Import')
            deck=genanki.Deck(2059400110,deck_name)
            for card in cards:
                deck.add_note(genanki.Note(model=model,fields=[card['front'],card['back']]))
            out=io.BytesIO()
            genanki.Package(deck).write_to_file(out)
            st.download_button('⬇️ Télécharger le paquet .apkg',out.getvalue(),file_name='anki_studio.apkg',mime='application/octet-stream')
        except ImportError:
            st.error('Installe les dépendances du fichier requirements.txt.')
else:
    st.info('Importe un PDF avec des marqueurs CARTE pour commencer. Aucun fichier n’est envoyé à un service d’IA.')
