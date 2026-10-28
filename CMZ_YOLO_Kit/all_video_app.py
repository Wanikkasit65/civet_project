"""One local page for a complete video-folder inference run."""
from pathlib import Path
from datetime import datetime
import json,os,sqlite3,subprocess,sys,uuid
import pandas as pd
import streamlit as st
import all_video as a
import phase2_core as c

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='CMZ All Videos',layout='wide')
st.title('CMZ · Analyze all videos')
st.write('Process every discovered video through animal detection and behavior proposals. Original videos, annotations and the previous trained model stay in place.')
st.warning('The current labels support Walking and Feeding. Resting/Sleeping remain unavailable. Output durations are unvalidated model estimates, not confirmed whole-day behavior measurements.')
workspace=Path(st.text_input('1. Existing workspace folder',r'E:\mod stardewS\CMZ\CMZ_YOLO_Kit\workspace'))
roots_text=st.text_area('2. Video folders (one per line; subfolders are included)',r'E:\mod stardewS\ชะมดแผงสันหางดำ-20261020T181928Z-1-009 (2)'+'\n'+r'E:\mod stardewS\test',height=104)
clocks=st.checkbox('I verified that filename times and all camera clocks agree (enables one-animal time fusion)',value=False)
st.caption('Without clock verification, the system exports per-video and per-camera/hour tables. Camera hours must not be summed as animal time.')
with st.expander('Advanced settings (keep defaults for the first run)'):
    threshold=st.slider('Animal detection score threshold',.1,.9,.4,.05)
    behavior_threshold=st.slider('Behavior proposal score threshold (uncalibrated)',.5,.95,.7,.05)
    cpu=st.checkbox('Allow CPU processing (much slower)',value=False)

def start_process(folder):
    import psutil
    pid_file=folder/'worker_pid.json'
    if pid_file.exists():
        try:
            old=psutil.Process(json.loads(pid_file.read_text())['pid'])
            if str(folder) in old.cmdline() and any('all_video.py' in x for x in old.cmdline()):raise ValueError('This run already has a live worker. Use Refresh progress.')
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    with (folder/'worker.log').open('ab') as log:
        child=subprocess.Popen([sys.executable,str(ROOT/'all_video.py'),str(folder)],stdout=log,stderr=log,cwd=ROOT,creationflags=flags)
    st.session_state['run']=str(folder)
    (folder/'worker_pid.json').write_text(json.dumps({'pid':child.pid}),encoding='utf-8')

if st.button('3. Start a NEW full-folder analysis',type='primary'):
    try:
        import torch
        if not torch.cuda.is_available() and not cpu:raise ValueError('CUDA is unavailable in this environment. Check the installer output. CPU mode is available in Advanced settings, but can be very slow for all videos.')
        if not c.read_records(workspace):raise ValueError('No confirmed labels found. This must point to the OLD workspace containing phase2/annotations and the review-clip folders.')
        roots=[x.strip().strip('"') for x in roots_text.splitlines() if x.strip()]
        found=a.discover(roots,[workspace])
        folder=workspace/'all_video_runs'/('full_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]);folder.mkdir(parents=True)
        config=dict(workspace=str(workspace.resolve()),video_roots=roots,clocks_verified=clocks,animal_threshold=threshold,behavior_threshold=behavior_threshold,cpu=cpu)
        (folder/'config.json').write_text(json.dumps(config,indent=2,ensure_ascii=False),encoding='utf-8')
        start_process(folder);st.success(f'Started. Found {len(found)} video paths. The worker checks exact duplicate content automatically.');st.rerun()
    except Exception as e:st.error(str(e))

runs=sorted((workspace/'all_video_runs').glob('full_*'),reverse=True)
if runs:
    preferred=st.session_state.get('run')
    selected=st.selectbox('Current / previous run',runs,index=next((i for i,p in enumerate(runs) if str(p)==preferred),0),format_func=lambda p:p.name)
    st.caption('The analysis continues if this page closes. To pause, use the button below and wait for paused status before closing the command window.')
    if st.button('Refresh progress'):st.rerun()
    state={}
    try:
        db=sqlite3.connect(f'file:{selected/"run.sqlite"}?mode=ro',uri=True,timeout=2)
        row=db.execute('SELECT data FROM progress WHERE id=1').fetchone();db.close()
        state=json.loads(row[0]) if row else {};st.json(state)
    except (sqlite3.Error,OSError) as e:st.info('Worker is starting. Refresh shortly.')
    left,right=st.columns(2)
    if left.button('Pause safely after the current window'):
        (selected/'PAUSE').touch(exist_ok=True);st.info('Pause requested. Refresh until status says paused.')
    if state.get('status')=='running' and (selected/'worker_pid.json').exists():
        import psutil
        try:
            proc=psutil.Process(json.loads((selected/'worker_pid.json').read_text())['pid'])
            if str(selected) not in proc.cmdline():state['status']='interrupted'
        except psutil.NoSuchProcess:state['status']='interrupted'
        except psutil.AccessDenied:pass
    if state.get('status')=='interrupted':st.warning('The previous worker stopped. Resume this run to retain completed windows.')
    if right.button('Resume selected paused / error run',disabled=state.get('status') not in ('paused','error','interrupted')):
        try:
            pause=selected/'PAUSE'
            if pause.exists():pause.unlink()
            start_process(selected);st.success('Resuming completed work, not starting from zero.');st.rerun()
        except Exception as e:st.error(str(e))
    if (selected/'ALL_VIDEO_RESULTS.zip').exists():
        st.download_button('Download ALL_VIDEO_RESULTS.zip',data=(selected/'ALL_VIDEO_RESULTS.zip').read_bytes(),file_name='ALL_VIDEO_RESULTS.zip',mime='application/zip')
        st.caption('While running/paused, this is a PARTIAL export. Use complete status and RESULT_SCOPE.json to check final coverage.')
    for name in ['VIDEO_INVENTORY.csv','PER_VIDEO_MODEL_TABLE.csv','PER_CAMERA_HOUR_MODEL_TABLE.csv','ONE_ANIMAL_HOURLY_ESTIMATES.csv']:
        p=selected/name
        if p.exists():
            with st.expander(name):st.dataframe(pd.read_csv(p).head(500),hide_index=True)
    if state.get('status')=='error' and (selected/'worker.log').exists():
        st.code((selected/'worker.log').read_text(encoding='utf-8',errors='replace')[-6000:])
