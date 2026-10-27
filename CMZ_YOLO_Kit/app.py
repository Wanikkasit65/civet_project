from pathlib import Path
import json,subprocess,sys
import streamlit as st
from PIL import Image,ImageDraw
import scout as s
st.set_page_config(page_title='CMZ · Scout and YOLO',layout='wide')
st.title('CMZ · Scout → Human boxes → YOLO')
st.caption('Runs locally · original videos read only · separate from the previous kit')
st.warning('Motion priority is NOT animal detection. A still animal may have low motion. No trained civet detector is included.')
s.WORK.mkdir(exist_ok=True)
page=st.sidebar.radio('Steps',['1 · Scan long videos','2 · Review & draw boxes','3 · Export YOLO data','4 · Send review ZIP'])
runs=sorted(s.WORK.glob('scan_*'),reverse=True)
run=st.sidebar.selectbox('Scan',runs,format_func=lambda p:p.name) if runs else None
if st.sidebar.button('Refresh status / results'):st.rerun()
if run:
 try:status=json.loads((run/'status.json').read_text(encoding='utf-8'));st.sidebar.json(status)
 except Exception:status={}
else:status={}
if page.startswith('1'):
 st.write('Scan at 1 frame/second. This can still miss appearances shorter than the sampling gap. Every sampled frame remains available, including still/low-motion frames.')
 folder=st.text_input('Folder containing downloaded videos',placeholder=r'E:\mod stardewS\test')
 if st.button('Find videos'):
  try:st.session_state['videos']=s.files(folder)
  except Exception as e:st.error(str(e))
 videos=st.session_state.get('videos',[])
 chosen=st.multiselect('Choose videos',videos,format_func=lambda p:p.name)
 minutes=st.number_input('Minutes to scan from start (0 = whole video)',min_value=0,max_value=1440,value=0)
 st.caption('Uses CPU to decode video. Long recordings can take time and roughly 100–250 MB of image space per hour, depending on scene complexity. Start with one downloaded file. No new download is required for a first software check.')
 if st.button('Start new scan',disabled=not chosen or status.get('status')=='running'):
  try:
   r=s.newrun();request=r/'request.json';request.write_text(json.dumps(dict(run=str(r),paths=[str(p) for p in chosen],limit=int(minutes)*60)),encoding='utf-8')
   s.state(r,status='running',frames=0,file=chosen[0].name)
   with (r/'worker.log').open('w',encoding='utf-8') as log:
    subprocess.Popen([sys.executable,str(s.ROOT/'scout.py'),str(request)],cwd=s.ROOT,stdout=log,stderr=subprocess.STDOUT)
   st.success('Scan started. Click Refresh status / results. If several scans exist, select the newest one.');st.rerun()
  except Exception as e:st.error(str(e))
elif run is None or not (run/'index.csv').exists():st.info('Create a scan first.')
elif page.startswith('2'):
 df=s.load(run);ann=s.labels(run)
 if not len(df):st.info('No frames yet. Refresh after decoding starts.');st.stop()
 st.write(f'{len(df)} sampled frames · {len(ann)} reviewed frames')
 st.caption('Approximate seconds refer to clip playback, not wall-clock time. Check the on-screen clock/full video before relying on filename timestamps for data splitting.')
 order=st.radio('Review order',['Highest motion first (candidates only)','Chronological (includes still animals)'])
 minimum=st.number_input('From clip second',min_value=0.,value=0.)
 maximum=st.number_input('Through clip second (0 = no limit)',min_value=0.,value=0.)
 names=st.multiselect('Source files',df.name.unique().tolist(),default=df.name.unique().tolist())
 view=df[df.name.isin(names)&(df.approx_second>=minimum)]
 if maximum>0:view=view[view.approx_second<=maximum]
 if order.startswith('Highest'):
  # Spread priority suggestions across ten-second bins so one burst does not fill every page.
  view=view.assign(bin=(view.approx_second//10).astype(int)).sort_values('motion',ascending=False).drop_duplicates(['name','bin'])
 else:view=view.sort_values(['name','approx_second'])
 if st.checkbox('Hide already reviewed frames',value=False):view=view[~view.id.isin(ann)]
 pages=max(1,(len(view)+23)//24);pg=st.number_input('Page',1,pages,1)
 part=view.iloc[(pg-1)*24:pg*24]
 for start in range(0,len(part),4):
  for col,(_,row) in zip(st.columns(4),part.iloc[start:start+4].iterrows()):
   col.image(str(run/row.image),caption=f'{row["name"]} | ~{row.approx_second:.1f}s | {ann.get(row.id,{}).get("kind","unreviewed")}')
   if col.button('Open full frame',key=row.id):st.session_state['frame_id']=row.id
 ident=st.session_state.get('frame_id')
 if ident and ident in set(df.id):
  row=df[df.id==ident].iloc[0];st.divider();st.subheader(row['name']+f' · ~{row.approx_second:.1f}s')
  try:src=s.full_frame(run,row);im=Image.open(src).convert('RGB')
  except Exception as e:st.error(str(e));st.stop()
  prev=ann.get(ident,{});reviewer=st.text_input('Reviewer name',value=st.session_state.get('reviewer','Wanikkasit'));st.session_state['reviewer']=reviewer
  st.image(im,caption='Full-resolution frame. Check source video around this second if unsure.')
  st.write('One clearly visible civet: set the box around the whole visible animal. Uncertain/occluded/too small: use uncertain; do not label that as empty.')
  box=prev.get('box') or [0.,0.,1.,1.]
  x1,x2=st.slider('Left / right',0.,1.,(float(box[0]),float(box[2])),.005,key='x'+ident)
  y1,y2=st.slider('Top / bottom',0.,1.,(float(box[1]),float(box[3])),.005,key='y'+ident)
  preview=im.copy();d=ImageDraw.Draw(preview);w,h=im.size;d.rectangle((x1*w,y1*h,x2*w,y2*h),outline='red',width=4);st.image(preview,caption='Box preview')
  note=st.text_input('Note',value=prev.get('note',''),key='note'+ident)
  for col,kind,label in zip(st.columns(3),['civet','empty','uncertain'],['Save civet + box','Save verified empty','Save uncertain / skip']):
   if col.button(label):
    try:s.save(run,row,kind,[x1,y1,x2,y2],reviewer,note);st.success('Saved');st.rerun()
    except Exception as e:st.error(str(e))
elif page.startswith('3'):
 st.write('Creates a YOLO detector dataset with one class: civet. Only explicitly reviewed images enter this dataset. Unreviewed and uncertain images are excluded.')
 st.warning('This trains DETECTION, not Active/Inactive. Do not call an empty or missed detection Inactive. Clocks must agree across cameras. Separate time blocks are assigned to train/val/test; nearby frames stay together.')
 checks=st.checkbox('I verified visible animals, boxes, negative images, original filenames and recording clocks.')
 if st.button('Build new YOLO dataset',disabled=not checks):
  try:out=s.build(run);st.success('Created '+str(out));st.code(str(out/'data.yaml'))
  except Exception as e:st.error(str(e))
 st.write('After data review, use TRAIN_YOLO_WINDOWS.bat. It asks for the generated data.yaml path, checks GPU availability, trains YOLO11n, then evaluates a held-out detection test set once. Dependencies/weights may download on first use. See the Thai guide before installing YOLO.')
else:
 st.write('Export review metadata. Include two overview images only if you want ChatGPT to inspect candidate frames. No original video is included.')
 include=st.checkbox('Include overview images (up to 24 uniform + 24 motion-priority samples)',value=True)
 if st.button('Create review ZIP'):
  try:
   z=s.review_zip(run,include);st.download_button('Download REVIEW.zip',z.read_bytes(),file_name='CMZ_REVIEW.zip',mime='application/zip');st.success(str(z))
  except Exception as e:st.error(str(e))
