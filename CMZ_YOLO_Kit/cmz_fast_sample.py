"""Five-minute stratified random sampling across every available video.

Two-second windows at shared nominal camera times. Results summarize sampled
points only. No unsampled minutes are assigned a behavior or called observed sleep.
"""
import os
os.environ['TORCH_CUDNN_V8_API_DISABLED']='1'
os.environ['CUDA_LAUNCH_BLOCKING']='1'
from pathlib import Path
from datetime import datetime,timedelta,timezone
from collections import defaultdict,Counter
import csv,hashlib,json,math,random,sqlite3,sys,time,uuid,zipfile

INTERVAL=300
EPOCH=datetime(1970,1,1)
CAMERAS=('A01','A02','A03','A04')


def sample_plan(files):
    """One shared reproducible random 2s point per complete 5m time stratum.

    Extra midpoint audits guarantee a short/overlapped file is inspected, but
    those convenience samples are explicitly excluded from sampling statistics.
    """
    result=[]
    for f in files:
        if not f.get('clock') or not f.get('seconds'):continue
        begin=datetime.fromisoformat(f['clock']);duration=float(f['seconds'])
        if duration<2:continue
        left=(begin-EPOCH).total_seconds();right=left+duration
        selected=[]
        for block in range(math.floor(left/INTERVAL),math.floor(right/INTERVAL)+1):
            seed=int(hashlib.sha256(('cmz-fast-sampling-v1:'+str(block)).encode()).hexdigest()[:16],16)
            point=block*INTERVAL+random.Random(seed).randrange(1,INTERVAL*4-8)/4
            if left<=point and point+2<=right:
                selected.append(dict(file_id=f['id'],source=f['name'],camera=f['camera'],path=f['path'],
                    start=point-left,end=point-left+2,nominal_time=(EPOCH+timedelta(seconds=point)).isoformat(),
                    stratum=block,statistical_sample=True))
        if not selected:
            a=max(0.,(duration-2)/2)
            selected=[dict(file_id=f['id'],source=f['name'],camera=f['camera'],path=f['path'],
                start=a,end=a+2,nominal_time=(begin+timedelta(seconds=a)).isoformat(),stratum=None,statistical_sample=False)]
        result.extend(selected)
    return sorted(result,key=lambda x:(x['nominal_time'],x['camera'],x['source']))


def write_csv(path,rows,fields):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)


def fused_samples(rows):
    times=defaultdict(list)
    for r in rows:
        if r['statistical_sample']:times[r['nominal_time']].append(r)
    output=[]
    for moment,group in sorted(times.items()):
        cameras=defaultdict(list)
        for r in group:cameras[r['camera']].append(r)
        labels=set();all_absent=True;available=[]
        for cam in CAMERAS:
            observations=cameras.get(cam,[])
            valid=[r for r in observations if r['status']!='decode_error']
            if not valid:all_absent=False;continue
            available.append(cam)
            if not all(r['status']=='no_animal_proposal_at_either_endpoint' for r in valid):all_absent=False
            labels.update(r['behavior'] for r in valid if r['behavior']!='Unknown')
        label=next(iter(labels)) if len(labels)==1 else 'Unknown'
        possible=len(available)==4 and all_absent
        output.append(dict(nominal_time=moment,available_cameras=';'.join(available),
            behavior_proposal=label,activity_proposal='Active' if label in ('Walking','Feeding') else 'Unknown',
            conditional_possible_shelter=possible,
            shelter_interpretation='Possibly in shelter; behavior unknown; assumes aligned camera clocks' if possible else '',
            clocks_fully_verified=False,human_confirmed=False,
            observed_rest_or_sleep_seconds=None,sampled_window_seconds=2.))
    return output


def export(folder,files,rows,state):
    fields=['file_id','source','camera','start','end','nominal_time','stratum','statistical_sample','behavior','score','animal_score','status','error','human_confirmed']
    write_csv(folder/'SAMPLED_WINDOWS.csv',rows,fields)
    fused=fused_samples(rows)
    write_csv(folder/'FUSED_SAMPLED_TIMES.csv',fused,
        ['nominal_time','available_cameras','behavior_proposal','activity_proposal','conditional_possible_shelter','shelter_interpretation','clocks_fully_verified','human_confirmed','observed_rest_or_sleep_seconds','sampled_window_seconds'])
    summary=[]
    for f in files:
        selected=[r for r in rows if r['file_id']==f['id']];stat=[r for r in selected if r['statistical_sample']]
        counts=Counter(r['behavior'] for r in stat);n=len(stat)
        summary.append(dict(source=f['name'],camera=f['camera'],duration_seconds=f['seconds'],
            windows_processed=len(selected),random_sample_points=n,
            walking_points=counts['Walking'],feeding_points=counts['Feeding'],unknown_points=counts['Unknown'],
            walking_percent_of_sample_points=100*counts['Walking']/n if n else None,
            feeding_percent_of_sample_points=100*counts['Feeding']/n if n else None,
            unknown_percent_of_sample_points=100*counts['Unknown']/n if n else None,
            sampled_seconds=2*len(selected),decode_error_points=sum(r['status']=='decode_error' for r in selected),
            whole_video_observed_behavior_seconds=None))
    write_csv(folder/'PER_VIDEO_SAMPLING_TABLE.csv',summary,list(summary[0]) if summary else ['source'])
    groups=defaultdict(list)
    for r in fused:groups[r['nominal_time'][:13]].append(r)
    hourly=[]
    for hour,rr in sorted(groups.items()):
        counts=Counter(r['behavior_proposal'] for r in rr)
        hourly.append(dict(hour=hour,sampled_time_points=len(rr),walking_points=counts['Walking'],
            feeding_points=counts['Feeding'],unknown_points=counts['Unknown'],
            conditional_possible_shelter_points=sum(r['conditional_possible_shelter'] for r in rr),
            observed_rest_or_sleep_minutes=None))
    write_csv(folder/'HOURLY_SAMPLED_TIME_TABLE.csv',hourly,list(hourly[0]) if hourly else ['hour'])
    scope=dict(method='One reproducible random 2-second window per 5-minute stratum, shared nominal times across cameras.',
        unique_videos=len(files),videos_inspected=sum(any(r['file_id']==f['id'] for r in rows) for f in files),
        full_video_camera_hours=sum(float(f['seconds']) for f in files)/3600,
        windows_processed=len(rows),sampled_camera_seconds=2*len(rows),
        sampling_interval_seconds=INTERVAL,whole_video_dense_analysis=False,
        model_outputs_are_unvalidated=True,unsupported_behaviors=['Resting','Sleeping'],
        clocks_fully_verified=False,scope='Percentages describe sampled points, not fully observed whole-night durations.',
        shelter_rule='Only a conditional assumption: all four cameras supply a decoded window at the same nominal filename-clock time and no animal proposal occurs at either endpoint. Missing cameras, decode errors and incomplete detections never qualify.',
        limitations=['Short behaviors can fall between samples.','Animal detector misses can create false shelter assumptions.',
            'Camera clock alignment has only been spot-checked, not verified throughout every source file.',
            'Overlapping camera records are fused once per nominal time. Conflicting behavior proposals become Unknown.',
            'Midpoint-only fallback audits are excluded from random-sample statistics.',
            'Two-class motion model has no independent multi-class accuracy estimate. Unknown is not observed rest or sleep.'],
        state=state)
    (folder/'RESULT_SCOPE.json').write_text(json.dumps(scope,indent=2),encoding='utf-8')
    with zipfile.ZipFile(folder/'FAST_RESULTS.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in folder.iterdir():
            if p.suffix in ('.csv','.json') and p.name!='config.json':z.write(p,p.name)
        for p in (folder/'review_samples').glob('*'):
            if p.suffix in ('.mp4','.jpg'):z.write(p,'review_samples/'+p.name)


def pause_dense_run(folder):
    import psutil
    pid_path=folder/'worker_pid.json'
    if not pid_path.exists():return
    pid=json.loads(pid_path.read_text()).get('pid')
    if not pid or not psutil.pid_exists(pid):return
    try:args=psutil.Process(pid).cmdline()
    except psutil.NoSuchProcess:return
    if not any('cmz_cuda_recover.py' in a or 'cmz_auto_pts.py' in a for a in args):return
    print('Requesting safe pause of the slow run; keeping all saved windows.',flush=True)
    (folder/'PAUSE').touch(exist_ok=True)
    for _ in range(90):
        if not psutil.pid_exists(pid):return
        time.sleep(1)
    raise RuntimeError('Slow worker has not exited; fast GPU processing was not started. Check its CMD.')


def main():
    root=Path(__file__).resolve().parent
    old=root/'workspace'/'all_video_runs'/'full_pts_20261101_092658_1e0ad8'
    resume=len(sys.argv)>2 and sys.argv[1]=='--resume'
    if resume:
        folder=Path(sys.argv[2]).resolve();config=json.loads((folder/'config.json').read_text());old=Path(config['source_run'])
    else:folder=None
    pause_dense_run(old)
    import cv2,torch,joblib
    import cmz_auto_pts as auto
    from cmz_cuda_recover import checked_detector_class,FatalDetectorError
    if not torch.cuda.is_available():raise RuntimeError('GPU unavailable; no slow CPU fallback started.')
    cv2.setNumThreads(2);torch.backends.cudnn.benchmark=False
    torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
    base=auto.setup_pipeline()
    db=sqlite3.connect('file:'+str(old/'run.sqlite')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:files=[dict(r) for r in db.execute('SELECT * FROM files WHERE seconds IS NOT NULL ORDER BY name')]
    finally:db.close()
    if not files:raise RuntimeError('No video inventory available.')
    for f in files:
        if not Path(f['path']).is_file() or Path(f['path']).stat().st_size!=f['bytes']:
            raise RuntimeError('Original file missing or size changed: '+f['name'])
    plan=sample_plan(files)
    if {p['file_id'] for p in plan}!={f['id'] for f in files}:raise RuntimeError('Sampling plan cannot inspect every file.')
    if folder is None:
        config0=json.loads((old/'config.json').read_text(encoding='utf-8-sig'))
        folder=Path(config0['workspace'])/'fast_runs'/('fast5m_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
        folder.mkdir(parents=True,exist_ok=False)
        (folder/'config.json').write_text(json.dumps(dict(source_run=str(old)),indent=2))
        (folder/'SOURCE_INVENTORY.json').write_text(json.dumps(files,indent=2),encoding='utf-8')
    (folder/'review_samples').mkdir(exist_ok=True)
    print('FAST RUN: '+str(folder),flush=True)
    print('PLAN: %d sampled windows across %d videos; percentages will describe sampled points only.'%(len(plan),len(files)),flush=True)
    saved=joblib.load(old/'batch_behavior.joblib')
    if saved['metadata'].get('pipeline_version')!='cmz-pts-full-enclosure-v1':raise RuntimeError('Wrong behavior model version.')
    import phase2_core as core
    if saved['metadata']['annotation_signature']!=core.annotation_signature(core.read_records(json.loads((old/'config.json').read_text())['workspace'])):
        raise RuntimeError('Annotations changed; previous model cannot silently be reused.')
    model=saved['model'];(folder/'BATCH_TRAINING_REPORT.json').write_text(json.dumps(saved['metadata'],indent=2))
    detector=checked_detector_class(base.AnimalDetector,torch)(False)
    checkpoint=folder/'checkpoint.jsonl';rows=[]
    if checkpoint.exists():
        for line in checkpoint.read_text(encoding='utf-8').splitlines():
            try:rows.append(json.loads(line))
            except ValueError:raise RuntimeError('Incomplete checkpoint record; do not resume blindly.')
    done={(r['file_id'],r['nominal_time']) for r in rows}
    audited={(r['file_id'],r['behavior']) for r in rows if r.get('audit_saved')}
    began=time.monotonic();initial=len(rows);state=dict(status='running',completed_windows=len(rows),total_windows=len(plan))
    try:
        for p in plan:
            if (p['file_id'],p['nominal_time']) in done:continue
            if (folder/'PAUSE').exists():state['status']='paused';break
            r=dict(p,behavior='Unknown',score=None,animal_score=None,status='decode_error',error='',human_confirmed=False)
            frames=[]
            try:
                for a,b,ff in base.sampled_windows(p['path'],start=p['start'],end=p['end']):frames.extend(ff)
                if len(frames)<5:raise ValueError('Too few decoded frames at sample point.')
                roi,animal_score,status=base.animal_crop(frames,detector,.4)
                r.update(animal_score=animal_score,status=status)
                if roi is not None:
                    prob=model.predict_proba([base.features(frames,roi)])[0];i=int(prob.argmax());r['score']=float(prob[i])
                    if r['score']>=.7:r.update(behavior=str(model.classes_[i]),status='unconfirmed_model_proposal')
                    else:r['status']='low_model_score'
                if (p['file_id'],r['behavior']) not in audited:
                    base.save_audit_sample(folder/'review_samples',p['file_id'],p['start'],frames,roi)
                    audited.add((p['file_id'],r['behavior']));r['audit_saved']=True
            except (ValueError,OSError,RuntimeError) as e:
                r.update(status='decode_error',error=str(e))
            # FatalDetectorError inherits BaseException, so a backend failure stops globally.
            rows.append(r);done.add((p['file_id'],p['nominal_time']))
            with checkpoint.open('a',encoding='utf-8') as f:f.write(json.dumps(r)+'\n')
            n=len(rows)-initial;elapsed=time.monotonic()-began
            eta=(len(plan)-len(rows))*elapsed/n/60 if n else None
            state.update(completed_windows=len(rows),total_windows=len(plan),elapsed_seconds=elapsed,
                estimated_remaining_minutes=eta,current_file=p['source'],updated_utc=datetime.now(timezone.utc).isoformat())
            (folder/'PROGRESS.json').write_text(json.dumps(state,indent=2))
            if n%10==0:
                print('PROGRESS %d/%d | estimated remaining %.1f min'%(len(rows),len(plan),eta),flush=True)
                export(folder,files,rows,state)
        else:state['status']='complete_with_sample_errors' if any(r['status']=='decode_error' for r in rows) else 'complete'
    except BaseException as e:
        state.update(status='error',error=str(e));print('STOPPED: '+str(e),flush=True)
        raise
    finally:
        (folder/'PROGRESS.json').write_text(json.dumps(state,indent=2))
        export(folder,files,rows,state)
        print('RESULT ZIP: '+str(folder/'FAST_RESULTS.zip'),flush=True)
    print('FINISHED: '+state['status'],flush=True)


if __name__=='__main__':main()
