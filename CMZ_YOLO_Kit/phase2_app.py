"""Phase 2 local review, real pilot training and scope-aware activity tables."""
from pathlib import Path
import io, json, zipfile
import streamlit as st
import pandas as pd
import cv2
from PIL import Image, ImageDraw
import phase2_core as c

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='CMZ Phase 2',layout='wide')
st.title('CMZ · Behavior review, training & tables')
st.caption('Local processing · original videos and previous scans are read only')
st.info('Not visible = Unknown. Box entry does not prove resting or sleeping. Unconfirmed model proposals never count as observed Active/Inactive time.')
workspace=Path(st.sidebar.text_input('Existing workspace folder',str(ROOT/'workspace')))
page=st.sidebar.radio('Steps',['1 · Import confirmed labels','2 · Review behavior clips','3 · Train behavior pilot','4 · Tables & export','5 · Try a model proposal','6 · YOLO detector readiness'])
try:rows=c.read_records(workspace)
except Exception as e:st.error(str(e));st.stop()
st.sidebar.write(f'{len(rows)} confirmed intervals')
st.sidebar.caption('Review clips must stay in their generated folders inside this workspace. ZIP files alone are not enough for local training.')

@st.cache_data(show_spinner=False)
def preview(path):
    cap=cv2.VideoCapture(path)
    count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));cap.set(cv2.CAP_PROP_POS_FRAMES,max(0,count//2))
    ok,frame=cap.read();cap.release()
    if not ok:raise ValueError('Cannot read this preview.')
    return cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)

def roi_controls(sample,ident):
    st.video(sample['local_clip'])
    st.caption('Crop around the whole animal and its movement throughout the chosen interval. Inspect the video; a middle-frame preview alone cannot establish this.')
    left,right=st.slider('Left / right',0.,1.,(.15,.85),.005,key=ident+'x')
    top,bottom=st.slider('Top / bottom',0.,1.,(.25,.98),.005,key=ident+'y')
    roi=[left,top,right,bottom]
    im=Image.fromarray(preview(sample['local_clip']));d=ImageDraw.Draw(im)
    d.rectangle([left*im.width,top*im.height,right*im.width-1,bottom*im.height-1],outline='red',width=2)
    st.image(im,width=640)
    return roi

if page.startswith('1'):
    st.subheader('Import your human-confirmed JSON')
    upload=st.file_uploader('CMZ_FEEDING_CONFIRMED.json or another review JSON',type=['json'])
    if upload:
        try:
            doc=json.loads(upload.getvalue());incoming=[c.normalize(r,doc.get('same_event_group')) for r in doc.get('observations',[])]
            if not incoming:raise ValueError('No human-confirmed observations found.')
            st.dataframe(pd.DataFrame(incoming)[['source','start_second','end_second','behavior']],hide_index=True)
            if st.button('Import confirmed intervals'):
                c.save_records(workspace,incoming);st.success('Imported. Original JSON was not changed. Go to step 2 to add animal crops and review other behavior classes.');st.rerun()
        except Exception as e:st.error(str(e))
    st.caption('Import does not convert AI proposals into human labels. Existing reviewed intervals remain in an append-only history.')
elif page.startswith('2'):
    catalog=c.sample_catalog(workspace)
    if not catalog:st.warning('No generated review clip folders found. Point the sidebar to the workspace used by AUTO_REVIEW.');st.stop()
    mode=st.radio('Review mode',['Add a new labeled interval','Add crop to existing confirmed labels'])
    if mode.startswith('Add crop'):
        choices=[r for r in rows if r['behavior'] in c.ACTIVITY]
        if not choices:st.info('Import confirmed labels in step 1 first.');st.stop()
        selected=st.selectbox('Confirmed interval',choices,format_func=lambda r:f"{r['source']} | {r['start_second']:.1f}–{r['end_second']:.1f}s | {r['behavior']}")
        try:sample=c.resolve_sample(catalog,selected)
        except Exception as e:st.error(str(e));st.stop()
        roi=roi_controls(sample,'existing_'+str(c.key(selected)))
        st.caption('Saving a crop creates a new annotation-history record; it does not edit the imported JSON.')
        same=[r for r in choices if r['source']==selected['source'] and r['behavior']==selected['behavior']]
        apply_many=st.checkbox('Apply this crop to all confirmed intervals of this behavior from this source',value=False)
        st.warning('Only apply to several intervals after checking that this rectangle includes the whole animal in every one. Walking intervals often need different crops.')
        if st.button('Save reviewed crop'):
            try:
                targets=same if apply_many else [selected]
                c.save_records(workspace,[dict(r,roi=roi) for r in targets]);st.success(f'Saved crops for {len(targets)} intervals.');st.rerun()
            except Exception as e:st.error(str(e))
    else:
        source=st.selectbox('Source video',sorted({r['source'] for r in catalog.values()}))
        choices=sorted((r for r in catalog.values() if r['source']==source),key=lambda r:r['start_second'])
        method=st.radio('Samples',['All','Motion candidates','Uniform samples'])
        if method=='Motion candidates':choices=[r for r in choices if r.get('selection')=='motion_candidate']
        if method=='Uniform samples':choices=[r for r in choices if r.get('selection')=='uniform']
        if not choices:st.info('No samples for this filter.');st.stop()
        sample=st.selectbox('Short clip',choices,format_func=lambda r:f"{r['start_second']:.1f}–{r['end_second']:.1f}s | {r.get('selection')}")
        roi=roi_controls(sample,'new_'+str(c.key(sample)))
        length=float(sample['end_second']-sample['start_second'])
        start,end=st.slider('Label only this section of the clip (seconds from clip start)',0.,length,(0.,length),.25)
        label=st.selectbox('What is visible in the ENTIRE selected section?',['Choose a behavior']+list(c.BEHAVIORS))
        st.caption('Walking: animal travels by stepping. Feeding: visible food handling/consumption. Resting: visible rest, no feeding/grooming. Sleeping needs observable evidence; stillness alone is insufficient. Trim transitions, otherwise use Mixed or Unknown.')
        note=st.text_input('Note / visible evidence')
        if st.button('Save human-reviewed interval',disabled=label=='Choose a behavior'):
            try:
                c.save_records(workspace,[dict(source=source,start_second=sample['start_second']+start,end_second=sample['start_second']+end,
                    behavior=label,label_source='human_review',human_confirmed=True,roi=roi if label in c.ACTIVITY else None,note=note,id=sample['id'])]);st.success('Saved.');st.rerun()
            except Exception as e:st.error(str(e))
elif page.startswith('3'):
    st.subheader('Train a real motion-feature behavior pilot')
    st.write('This second-stage pilot uses Random Forest with Farneback optical-flow features from human-reviewed animal crops. It is separate from YOLO object detection.')
    st.dataframe(pd.DataFrame(rows)[['source','start_second','end_second','behavior','roi']] if rows else pd.DataFrame(),hide_index=True)
    st.warning('With only one feeding event there may be no independent feeding test. In that case the app can fit a pilot but reports no accuracy, F1 or confusion matrix. Resting/Sleeping remain unsupported until real examples exist.')
    clocks=st.checkbox('I checked that original filename timestamps agree with recording clocks across cameras')
    if st.button('Train behavior pilot'):
        try:
            with st.spinner('Extracting motion features and fitting the model...'):folder,report=c.train_pilot(workspace,rows,clocks)
            st.success('Actual training finished: '+str(folder));st.json(report)
        except Exception as e:st.error(str(e))
    for p in sorted((workspace/'phase2').glob('pilot_*/TRAINING_REPORT.json'),reverse=True)[:3]:
        with st.expander(p.parent.name):st.json(json.loads(p.read_text()))
elif page.startswith('4'):
    st.subheader('Confirmed observations — not whole-night percentages')
    if not rows:st.info('Import confirmed labels in step 1.');st.stop()
    detail,summary=c.tables(rows)
    st.dataframe(pd.DataFrame(detail),hide_index=True)
    st.dataframe(pd.DataFrame(summary),hide_index=True)
    st.caption('Blank seconds = not annotated / cannot evaluate, not zero. Overlapping intervals of the same behavior are merged within each source. Camera views are never summed as a single animal activity budget.')
    visible=[r for r in summary if r['confirmed_seconds'] is not None]
    if visible:
        chart=pd.DataFrame(visible);chart['series']=chart['source']+' · '+chart['behavior'];st.bar_chart(chart.set_index('series')['confirmed_seconds'])
    missing=[b for b in c.ACTIVITY if not any(r['behavior']==b for r in rows)]
    st.warning('No confirmed annotations for: '+', '.join(missing)) if missing else st.success('Every target behavior has at least one annotation; this alone does not establish a sufficient dataset.')
    if st.button('Create new results ZIP'):
        folder=c.write_report(workspace,rows);b=io.BytesIO()
        with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
            for p in folder.iterdir():z.write(p,p.name)
            for p in (workspace/'phase2').glob('pilot_*/TRAINING_REPORT.json'):z.write(p,p.parent.name+'/'+p.name)
            # Redacted annotation export contains filenames, not local paths.
            z.writestr('confirmed_annotations.json',json.dumps(dict(observations=rows),ensure_ascii=False,indent=2))
        st.download_button('Download PHASE2_RESULTS.zip',b.getvalue(),file_name='PHASE2_RESULTS.zip',mime='application/zip')
elif page.startswith('5'):
    models=sorted((workspace/'phase2').glob('pilot_*/behavior_pilot.joblib'),reverse=True)
    if not models:st.info('Train a pilot in step 3 first.');st.stop()
    model=st.selectbox('Model generated by this app',models,format_func=lambda p:p.parent.name)
    catalog=c.sample_catalog(workspace)
    source=st.selectbox('Source video',sorted({r['source'] for r in catalog.values()})) if catalog else None
    if not source:st.stop()
    sample=st.selectbox('Clip',sorted((r for r in catalog.values() if r['source']==source),key=lambda r:r['start_second']),format_func=lambda r:f"{r['start_second']}–{r['end_second']}s")
    roi=roi_controls(sample,'proposal_'+str(c.key(sample)))
    if st.button('Generate unconfirmed proposal'):
        try:st.json(c.propose(workspace,model,sample,roi))
        except Exception as e:st.error(str(e))
    st.caption('Proposal activity stays Unknown until reviewed. High RF vote fractions do not prove the animal is active, and unsupported behaviors may be misclassified. This pilot cannot autonomously certify sleep or rest.')
else:
    st.subheader('YOLO custom civet detection — separate training task')
    st.write('Use the scout to review animal boxes and verified empty frames. The existing YOLO training scripts remain available. COCO weights alone are not a custom civet detector.')
    all_annotations=[]
    for p in workspace.glob('scan_*/annotations.json'):
        try:all_annotations.extend(json.loads(p.read_text(encoding='utf-8')).values())
        except (OSError,ValueError):pass
    counts={}
    for r in all_annotations:
        k=(r.get('name'),r.get('approx_second'));counts[k]=r
    st.write(f'{sum(r.get("kind")=="civet" for r in counts.values())} unique animal frames · {sum(r.get("kind")=="empty" for r in counts.values())} verified-empty frames across scans')
    st.info('A merged export utility is included: MERGE_YOLO_WINDOWS.bat. It creates a new merged scan, preserves originals, and applies the existing train/validation/test data guards. Then use TRAIN_YOLO_WINDOWS.bat with its data.yaml. Missing evaluation data are not bypassed.')
    st.caption('YOLO detector metrics do not establish walking/feeding/resting/sleeping accuracy. Automatic end-to-end behavior monitoring is still unvalidated.')
