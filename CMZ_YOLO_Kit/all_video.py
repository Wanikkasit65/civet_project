"""Full-folder inference. Predictions and human observations remain separate.

MegaDetector supplies animal proposals, not species identity. A newly fitted RF
uses detector-derived crops in both training and inference. Original files and
the previous human-ROI pilot are read only. SQLite checkpoints permit resume.
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import csv, hashlib, json, math, re, sqlite3, sys, time, uuid, zipfile
import phase2_core as core

EXTENSIONS={'.mp4','.avi','.mov','.mkv','.m4v','.wmv','.mts','.m2ts'}
WINDOW=2.0

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def clock_info(name):
    m=re.fullmatch(r'(A\d+)_(\d{14})(?:[^\d].*)?\.[^.]+',name)
    if not m:return 'Unknown',None
    try:return m[1],datetime.strptime(m[2],'%Y%m%d%H%M%S')
    except ValueError:return m[1],None

def discover(roots,excluded_roots=()):
    paths=set()
    excluded=[Path(p).resolve() for p in excluded_roots]
    for root in roots:
        folder=Path(root).expanduser().resolve()
        if not folder.is_dir():raise ValueError('Video folder not found: '+str(folder))
        paths.update(p.resolve() for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS and not any(p.resolve().is_relative_to(x) for x in excluded))
    if not paths:raise ValueError('No video files found in the selected folders.')
    return sorted(paths,key=str)

def database(folder):
    db=sqlite3.connect(str(Path(folder)/'run.sqlite'),timeout=60)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''CREATE TABLE IF NOT EXISTS files (
      id TEXT PRIMARY KEY,path TEXT,name TEXT,camera TEXT,clock TEXT,seconds REAL,fps REAL,
      bytes INTEGER,status TEXT,error TEXT);
      CREATE TABLE IF NOT EXISTS copies(path TEXT PRIMARY KEY,file_id TEXT);
      CREATE TABLE IF NOT EXISTS windows(
      file_id TEXT,start REAL,end REAL,behavior TEXT,score REAL,status TEXT,
      animal_score REAL,roi TEXT,PRIMARY KEY(file_id,start));
      CREATE TABLE IF NOT EXISTS audit_samples(file_id TEXT,start REAL,behavior TEXT,image TEXT,clip TEXT,PRIMARY KEY(file_id,start));
      CREATE TABLE IF NOT EXISTS progress(id INTEGER PRIMARY KEY,data TEXT);''')
    return db

def progress(db,**values):
    old=db.execute('SELECT data FROM progress WHERE id=1').fetchone()
    state=json.loads(old[0]) if old else {}
    state.update(values,updated_utc=datetime.now(timezone.utc).isoformat())
    db.execute('INSERT OR REPLACE INTO progress VALUES(1,?)',(json.dumps(state),));db.commit()

def inventory(db,roots,workspace=None):
    import cv2
    paths=discover(roots,[workspace] if workspace else [])
    for i,path in enumerate(paths):
        progress(db,phase='Inventory: hashing and checking every video',files_found=len(paths),files_checked=i,current_file=path.name)
        sha=digest(path)
        previous=db.execute('SELECT file_id FROM copies WHERE path=?',(str(path),)).fetchone()
        if previous and previous[0]!=sha:raise ValueError('An original video changed since this run started. Start a NEW run: '+str(path))
        db.execute('INSERT OR IGNORE INTO copies VALUES(?,?)',(str(path),sha))
        if db.execute('SELECT 1 FROM files WHERE id=?',(sha,)).fetchone():continue
        camera,clock=clock_info(path.name);cap=cv2.VideoCapture(str(path))
        fps=cap.get(cv2.CAP_PROP_FPS);count=cap.get(cv2.CAP_PROP_FRAME_COUNT)
        okay=cap.isOpened() and math.isfinite(fps) and fps>0 and math.isfinite(count) and count>0
        cap.release()
        duration=count/fps if okay else None
        db.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?,?,?,?)',(sha,str(path),path.name,camera,clock.isoformat() if clock else None,duration,fps if okay else None,path.stat().st_size,'pending' if okay else 'unreadable','' if okay else 'Cannot obtain reliable video duration/frame rate'))
        db.commit()
    progress(db,files_checked=len(paths),unique_videos=db.execute('SELECT COUNT(*) FROM files').fetchone()[0])

def sampled_windows(path,window=WINDOW,start=0.,end=None):
    """Read sequentially, retrieve approximately 4 fps, retain one short buffer."""
    import cv2
    cap=cv2.VideoCapture(str(path));fps=cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or not math.isfinite(fps) or fps<=0:
        cap.release();raise ValueError('Unreadable video: '+str(path))
    first=max(0,int(math.floor(start*fps)));cap.set(cv2.CAP_PROP_POS_FRAMES,first)
    i=first;bucket=0;frames=[];next_sample=start
    try:
        while True:
            timestamp=i/fps
            if end is not None and timestamp>=end-1e-7:break
            if not cap.grab():break
            if timestamp+1e-7>=next_sample and timestamp>=start:
                next_sample=start+(math.floor((timestamp-start)*4+1e-7)+1)/4
                ok,frame=cap.retrieve()
                if not ok:raise ValueError('Frame decode failed near '+str(timestamp))
                k=int((timestamp-start+1e-7)//window)
                if k!=bucket:
                    if frames:yield start+bucket*window,min(start+(bucket+1)*window,end if end is not None else timestamp),frames
                    frames=[];bucket=k
                h,w=frame.shape[:2]
                if w>1280:frame=cv2.resize(frame,(1280,round(h*1280/w)))
                frames.append(frame)
            i+=1
        if frames:yield start+bucket*window,min(end if end is not None else i/fps,start+(bucket+1)*window),frames
    finally:cap.release()

def features(frames,roi):
    import cv2,numpy as np
    previous=None;steps=[]
    for frame in frames:
        h,w=frame.shape[:2];x1,y1,x2,y2=roi
        crop=frame[int(y1*h):max(int(y1*h)+1,int(y2*h)),int(x1*w):max(int(x1*w)+1,int(x2*w))]
        gray=cv2.resize(cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY),(96,96))
        if previous is not None:
            flow=cv2.calcOpticalFlowFarneback(previous,gray,None,.5,3,15,3,5,1.2,0)
            mag=np.linalg.norm(flow,axis=2);d=gray.astype(float)-previous.astype(float);d=np.abs(d-np.median(d))/255
            steps.append([d.mean(),np.quantile(d,.9),mag.mean(),np.quantile(mag,.9),(mag>1).mean(),np.linalg.norm(flow.mean(axis=(0,1)))])
        previous=gray
    if len(steps)<4:raise ValueError('Too few decoded frames for temporal features.')
    a=np.asarray(steps);result=np.concatenate([a.mean(0),a.std(0),np.quantile(a,.9,axis=0)])
    if not np.isfinite(result).all():raise ValueError('Non-finite video features.')
    return result

class AnimalDetector:
    def __init__(self,cpu=False):
        from megadetector.detection import run_detector
        self.model=run_detector.load_detector('MDV5A',force_cpu=cpu)
    def __call__(self,frame):
        import cv2
        from PIL import Image
        result=self.model.generate_detections_one_image(Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)),image_id='local_frame',detection_threshold=.05)
        if result.get('failure'):raise RuntimeError(str(result['failure']))
        return result.get('detections',[])

def animal_crop(frames,detector,threshold=.4):
    """Require a single animal at both endpoints. A missed detection is Unknown."""
    if len(frames)<5:return None,0.,'too_few_frames'
    boxes=[];scores=[]
    for frame in (frames[0],frames[-1]):
        detections=detector(frame)
        if any(str(d['category'])=='2' and d['conf']>=.3 for d in detections):return None,0.,'person_present'
        candidates=[d for d in detections if str(d['category'])=='1' and d['conf']>=threshold]
        if len(candidates)!=1:return None,max([d['conf'] for d in candidates] or [0.]),'animal_not_reliably_detected' if not candidates else 'multiple_animal_proposals'
        x,y,w,h=map(float,candidates[0]['bbox'])
        if not all(math.isfinite(v) for v in (x,y,w,h)) or w<=0 or h<=0:return None,0.,'invalid_detector_box'
        boxes.append((x,y,x+w,y+h));scores.append(float(candidates[0]['conf']))
    x1=min(b[0] for b in boxes);y1=min(b[1] for b in boxes);x2=max(b[2] for b in boxes);y2=max(b[3] for b in boxes)
    dx=(x2-x1)*.15;dy=(y2-y1)*.15
    roi=[max(0.,x1-dx),max(0.,y1-dy),min(1.,x2+dx),min(1.,y2+dy)]
    if not 0<=roi[0]<roi[2]<=1 or not 0<=roi[1]<roi[3]<=1:return None,0.,'invalid_detector_box'
    return roi,min(scores),'animal_proposal'

def train_batch_model(workspace,folder,detector,threshold):
    import joblib,numpy as np
    from sklearn.ensemble import RandomForestClassifier
    rows=core.read_records(workspace);signature=core.annotation_signature(rows)
    model_path=Path(folder)/'batch_behavior.joblib'
    if model_path.exists():
        saved=joblib.load(model_path)
        if saved['metadata']['annotation_signature']!=signature:raise ValueError('Labels changed after this run started. Start a NEW run to preserve the previous run.')
        return saved['model'],saved['metadata']
    catalog=core.sample_catalog(workspace);X=[];y=[];audit=[]
    for r in rows:
        if r['behavior'] not in core.ACTIVITY:continue
        sample=core.resolve_sample(catalog,r);offset=r['start_second']-sample['start_second']
        for begin,finish,frames in sampled_windows(sample['local_clip'],start=offset,end=offset+r['end_second']-r['start_second']):
            item=dict(source=r['source'],start_second=sample['start_second']+begin,end_second=sample['start_second']+finish,behavior=r['behavior'])
            roi,animal_score,status=animal_crop(frames,detector,threshold)
            item.update(detector_status=status,animal_score=animal_score,roi=roi)
            try:
                if roi is None:raise ValueError(status)
                if finish-begin<1.4:raise ValueError('Short tail segment excluded')
                X.append(features(frames,roi));y.append(r['behavior']);item['used']=True
            except ValueError as e:item.update(used=False,reason=str(e))
            audit.append(item)
    (Path(folder)/'TRAINING_SEGMENTS.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    counts={b:y.count(b) for b in sorted(set(y))}
    if len(counts)<2 or min(counts.values())<2:
        raise ValueError('Animal detector could not recover enough labeled training segments in two classes. See TRAINING_SEGMENTS.json. Full inference stopped rather than generating unusable behavior totals.')
    model=RandomForestClassifier(n_estimators=200,max_depth=8,min_samples_leaf=2,class_weight='balanced',random_state=42,n_jobs=2).fit(np.stack(X),y)
    metadata=dict(task='Detector-crop behavior proposals',detector='Pretrained MegaDetector V5A animal category',model='RandomForest + Farneback',window_seconds=WINDOW,source_annotation_intervals=len([r for r in rows if r['behavior'] in core.ACTIVITY]),derived_training_segments=len(y),class_counts=counts,supported_classes=list(model.classes_),unsupported_classes=[b for b in core.ACTIVITY if b not in model.classes_],annotation_signature=signature,evaluation=None,whole_period_behavior_accuracy=None,notes=['New crop-consistent model, separate from the earlier human-ROI pilot.','Derived segments share the original recording events and are not independent examples.','All predictions remain unconfirmed. Score rejection does not validate unknown-behavior rejection.','MegaDetector detects animals, not civet species identity.','Detector endpoint samples may miss brief appearances.'])
    joblib.dump(dict(model=model,metadata=metadata),model_path)
    (Path(folder)/'BATCH_TRAINING_REPORT.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    return model,metadata

def replay_known_walking_checks(folder,db,detector,model,config):
    """Previously exposed user-confirmed clips: development checks, not fresh tests."""
    import numpy as np
    sources=db.execute('SELECT * FROM files WHERE name=?',('A03_20260405000000.mp4',)).fetchall()
    result=dict(scope='Previously exposed Walking checks; one class only. Not a fresh held-out test.',human_reference_source='User confirmed all three whole clips show Walking in project chat.',overall_accuracy=None,checks=[])
    if len(sources)!=1:result['unavailable_reason']='Could not uniquely locate the source video in the selected folders.'
    else:
        for start in (5632.5,5806.5,12558.5):
            segments=[]
            for a,b,frames in sampled_windows(sources[0]['path'],start=start,end=start+10):
                roi,animal_score,status=animal_crop(frames,detector,config['animal_threshold']);label='Unknown';score=None
                if roi is not None:
                    try:
                        values=model.predict_proba([features(frames,roi)])[0];i=int(values.argmax());score=float(values[i])
                        if score>=config['behavior_threshold']:label=str(model.classes_[i])
                    except ValueError:status='feature_error'
                segments.append(dict(start_second=a,end_second=b,expected='Walking',proposed_behavior=label,model_score=score,animal_score=animal_score,roi=roi,status=status))
            result['checks'].append(dict(source=sources[0]['name'],start_second=start,end_second=start+10,segments=segments))
    (Path(folder)/'REPLAY_WALKING_CHECKS.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

def hour_parts(start,end):
    while start<end:
        right=min(end,start.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1))
        yield start.replace(minute=0,second=0,microsecond=0).isoformat(),(right-start).total_seconds()
        start=right

def fused_intervals(rows):
    """One-animal clock union: agree on a label or emit Unknown; never sum views."""
    events=defaultdict(list)
    for index,(start,end,behavior) in enumerate(rows):
        if start>=end:continue
        events[start].append((index,behavior));events[end].append((index,None))
    active={};previous=None
    for moment in sorted(events):
        if previous is not None and moment>previous and active:
            labels={b for b in active.values() if b!='Unknown'}
            yield previous,moment,next(iter(labels)) if len(labels)==1 else 'Unknown'
        for index,behavior in events[moment]:
            if behavior is None:active.pop(index,None)
            else:active[index]=behavior
        previous=moment

def write_csv(path,items,fields):
    with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(items)

def environment_info():
    import importlib.metadata,torch
    versions={}
    for p in ('megadetector','torch','torchvision','scikit-learn','numpy','opencv-python'):
        try:versions[p]=importlib.metadata.version(p)
        except importlib.metadata.PackageNotFoundError:versions[p]=None
    return dict(versions=versions,cuda_available=torch.cuda.is_available(),cuda_version=torch.version.cuda)

def save_audit_sample(folder,file_id,start,frames,roi):
    import cv2,imageio_ffmpeg
    folder=Path(folder);stem=file_id[:12]+'_'+str(round(start,3));small=[]
    for frame in frames:
        h,w=frame.shape[:2];width=min(w,640);height=2*round(h*width/w/2)
        image=cv2.resize(frame,(width,height))
        if roi:cv2.rectangle(image,(int(roi[0]*width),int(roi[1]*height)),(int(roi[2]*width),int(roi[3]*height)),(0,0,255),1)
        small.append(image)
    cv2.imwrite(str(folder/(stem+'.jpg')),small[len(small)//2])
    writer=imageio_ffmpeg.write_frames(str(folder/(stem+'.mp4')),(width,height),fps=4,codec='libx264',macro_block_size=1,output_params=['-crf','28','-preset','fast'])
    writer.send(None)
    try:
        for image in small:writer.send(cv2.cvtColor(image,cv2.COLOR_BGR2RGB).tobytes())
    finally:writer.close()
    return 'review_samples/'+stem+'.jpg','review_samples/'+stem+'.mp4'

def export_results(folder,db,config,metadata):
    folder=Path(folder);files=[dict(r) for r in db.execute('SELECT * FROM files ORDER BY name')]
    write_csv(folder/'VIDEO_INVENTORY.csv',files,list(files[0]) if files else ['path','status'])
    write_csv(folder/'DUPLICATE_COPIES.csv',[dict(r) for r in db.execute('SELECT * FROM copies')],['path','file_id'])
    known={r['source'] for r in core.sample_catalog(config['workspace']).values()}
    present={Path(r[0]).name for r in db.execute('SELECT path FROM copies')}
    missing=sorted(known-present)
    write_csv(folder/'KNOWN_VIDEOS_NOT_FOUND.csv',[dict(source=s) for s in missing],['source'])
    query='SELECT f.name AS source,f.camera,f.clock,w.* FROM windows w JOIN files f ON f.id=w.file_id ORDER BY f.name,w.start'
    fields=['source','camera','start','end','behavior','score','status','animal_score','roi','file_id']
    write_csv(folder/'ALL_WINDOW_PREDICTIONS.csv',(dict(r) for r in db.execute(query)),fields)
    audit_query='SELECT f.name AS source,a.start,w.end,a.behavior,w.score,w.status,a.image,a.clip FROM audit_samples a JOIN files f ON f.id=a.file_id JOIN windows w ON w.file_id=a.file_id AND w.start=a.start ORDER BY f.name,a.start'
    write_csv(folder/'AUDIT_SAMPLES.csv',[dict(r) for r in db.execute(audit_query)],['source','start','end','behavior','score','status','image','clip'])
    by_file=defaultdict(lambda:defaultdict(float));hourly=defaultdict(lambda:defaultdict(float));statuses=defaultdict(float);fusion=[]
    for raw in db.execute(query):
        r=dict(raw);label=r['behavior'];by_file[(r['file_id'],r['source'],r['camera'])][label]+=r['end']-r['start']
        statuses[(r['camera'],r['status'])]+=r['end']-r['start']
        if r['clock']:
            base=datetime.fromisoformat(r['clock']);a=base+timedelta(seconds=r['start']);b=base+timedelta(seconds=r['end'])
            for hour,seconds in hour_parts(a,b):hourly[(r['camera'],hour)][label]+=seconds
            if config.get('clocks_verified'):fusion.append((a,b,label))
    def totals(values):
        supported=metadata.get('supported_classes',[])
        total=sum(values.values());pct=lambda n:round(100*n/total,4) if total else None
        return dict(walking_proposal_seconds=round(values['Walking'],4),feeding_proposal_seconds=round(values['Feeding'],4),resting_proposal_seconds=round(values['Resting'],4) if 'Resting' in supported else None,sleeping_proposal_seconds=round(values['Sleeping'],4) if 'Sleeping' in supported else None,active_model_proposal_seconds=round(values['Walking']+values['Feeding'],4),inactive_model_proposal_seconds=round(values['Resting']+values['Sleeping'],4) if all(b in supported for b in ('Resting','Sleeping')) else None,unknown_seconds=round(values['Unknown'],4),walking_model_percent_of_processed_windows=pct(values['Walking']),feeding_model_percent_of_processed_windows=pct(values['Feeding']),unknown_percent_of_processed_windows=pct(values['Unknown']),window_seconds_accounted=round(total,4),human_confirmed=False)
    basefields=['walking_proposal_seconds','feeding_proposal_seconds','resting_proposal_seconds','sleeping_proposal_seconds','active_model_proposal_seconds','inactive_model_proposal_seconds','unknown_seconds','walking_model_percent_of_processed_windows','feeding_model_percent_of_processed_windows','unknown_percent_of_processed_windows','window_seconds_accounted','human_confirmed']
    write_csv(folder/'PER_VIDEO_MODEL_TABLE.csv',[dict(file_id=i,source=s,camera=c,**totals(v)) for (i,s,c),v in by_file.items()],['file_id','source','camera']+basefields)
    write_csv(folder/'PER_CAMERA_HOUR_MODEL_TABLE.csv',[dict(camera=c,hour=h,**totals(v)) for (c,h),v in sorted(hourly.items())],['camera','hour']+basefields)
    write_csv(folder/'WINDOW_STATUS_COUNTS.csv',[dict(camera=c,status=s,seconds=round(v,4)) for (c,s),v in sorted(statuses.items())],['camera','status','seconds'])
    fused=defaultdict(lambda:defaultdict(float))
    if config.get('clocks_verified'):
        for a,b,label in fused_intervals(fusion):
            for hour,seconds in hour_parts(a,b):fused[hour][label]+=seconds
        write_csv(folder/'ONE_ANIMAL_HOURLY_ESTIMATES.csv',[dict(hour=h,**totals(v)) for h,v in sorted(fused.items())],['hour']+basefields)
    scope=dict(all_results_are_model_proposals=True,clocks_verified=config.get('clocks_verified',False),readable_video_count=sum(f['seconds'] is not None for f in files),completed_video_count=sum(f['status']=='complete' for f in files),files_with_errors=[f['name'] for f in files if f['status'] in ('unreadable','error')],known_videos_not_found=missing,unique_video_count=len(files),camera_video_hours=sum(f['seconds'] or 0 for f in files)/3600,window_seconds=WINDOW,unsupported_behaviors=metadata.get('unsupported_classes',[]),warnings=['Model proposals are not human-confirmed observations.','Resting/Sleeping blank means unsupported, never zero.','A missed animal detection is Unknown, never Inactive.','Endpoint detections approximate visibility over each 2-second window. Transitions and brief appearances can be missed.','Two-class models can mislabel unseen behaviors. Score rejection is unvalidated.','Per-camera/hour rows count camera video windows and can overlap. Use the fused table only after checking camera clocks.','Fused table is still an unvalidated model estimate, not a measured activity budget.','All videos include training footage. This is inference coverage, not held-out accuracy.'])
    (folder/'RESULT_SCOPE.json').write_text(json.dumps(scope,indent=2),encoding='utf-8')
    write_csv(folder/'HUMAN_CONFIRMED_ONLY.csv',core.tables(core.read_records(config['workspace']))[0],['source','start_second','end_second','behavior','activity','interval_seconds','evidence'])
    archive=folder/'ALL_VIDEO_RESULTS.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in folder.iterdir():
            if p.suffix in ('.csv','.json') and p.name!='config.json':z.write(p,p.name)
        for p in sorted((folder/'review_samples').glob('*')):
            if p.suffix in ('.jpg','.mp4'):z.write(p,'review_samples/'+p.name)
    return scope

def run(folder):
    import cv2,numpy as np
    cv2.setNumThreads(2)
    folder=Path(folder);config=json.loads((folder/'config.json').read_text(encoding='utf-8'));db=database(folder)
    try:
        progress(db,status='running',phase='Inventory')
        inventory(db,config['video_roots'],config['workspace'])
        progress(db,phase='Loading animal detector (first run downloads model weights)')
        detector=AnimalDetector(config.get('cpu',False))
        progress(db,phase='Training crop-consistent behavior model from existing labels')
        model,metadata=train_batch_model(config['workspace'],folder,detector,config['animal_threshold'])
        (folder/'ENVIRONMENT.json').write_text(json.dumps(environment_info(),indent=2),encoding='utf-8')
        if not (folder/'REPLAY_WALKING_CHECKS.json').exists():
            progress(db,phase='Replaying the three previously confirmed Walking clips with the NEW pipeline')
            replay_known_walking_checks(folder,db,detector,model,config)
        files=[dict(r) for r in db.execute("SELECT * FROM files WHERE seconds IS NOT NULL ORDER BY name")]
        review=folder/'review_samples';review.mkdir(exist_ok=True)
        began=time.monotonic();initial_done=db.execute('SELECT COALESCE(SUM(end-start),0) FROM windows').fetchone()[0];total=sum(f['seconds'] for f in files)
        processed=0;done=initial_done;initial_count=db.execute('SELECT COUNT(*) FROM windows').fetchone()[0]
        for f in files:
            if f['status']=='complete':continue
            start=db.execute('SELECT COALESCE(MAX(end),0) FROM windows WHERE file_id=?',(f['id'],)).fetchone()[0]
            progress(db,phase='Analyzing every video',current_file=f['name'])
            audited_labels={r[0] for r in db.execute('SELECT DISTINCT behavior FROM audit_samples WHERE file_id=?',(f['id'],))}
            try:
                for a,b,frames in sampled_windows(f['path'],start=start,end=f['seconds']):
                    if (folder/'PAUSE').exists():
                        export_results(folder,db,config,metadata);progress(db,status='paused',phase='Paused safely. Resume this run to continue.');return
                    if b-a<=0:continue
                    roi,animal_score,status=animal_crop(frames,detector,config['animal_threshold'])
                    label='Unknown';score=None
                    if roi is not None:
                        try:
                            probabilities=model.predict_proba([features(frames,roi)])[0];k=int(probabilities.argmax());score=float(probabilities[k])
                            if score>=config['behavior_threshold']:label=str(model.classes_[k]);status='unconfirmed_model_proposal'
                            else:status='low_model_score'
                        except ValueError as e:status='feature_error: '+str(e)
                    db.execute('INSERT OR REPLACE INTO windows VALUES(?,?,?,?,?,?,?,?)',(f['id'],a,b,label,score,status,animal_score,json.dumps(roi)))
                    db.commit();processed+=1;done+=b-a
                    # First proposal of each class plus 3 uniform times PER FILE.
                    # These convenience samples are biased and not an accuracy estimate.
                    uniform=any(a<=q*f['seconds']<b for q in (.1,.5,.9))
                    if label not in audited_labels or uniform:
                        image,clip=save_audit_sample(review,f['id'],a,frames,roi)
                        db.execute('INSERT OR REPLACE INTO audit_samples VALUES(?,?,?,?,?)',(f['id'],a,label,image,clip));db.commit();audited_labels.add(label)
                    if processed%10==0:
                        elapsed=time.monotonic()-began
                        rate=(done-initial_done)/elapsed if elapsed>0 else 0
                        progress(db,covered_camera_hours=done/3600,total_camera_hours=total/3600,completed_windows=initial_count+processed,elapsed_seconds=elapsed,estimated_remaining_hours=max(0.,total-done)/rate/3600 if rate>0 else None)
                    start=b
                # Metadata duration is not treated as successfully decoded if decoding ended early.
                if f['seconds']-start>max(.2,2/f['fps']):raise ValueError('Video ended before its declared duration; missing tail remains unprocessed.')
                db.execute("UPDATE files SET status='complete',error='' WHERE id=?",(f['id'],));db.commit()
            except Exception as e:
                db.execute("UPDATE files SET status='error',error=? WHERE id=?",(str(e),f['id']));db.commit()
                export_results(folder,db,config,metadata)
                raise RuntimeError('Stopped on '+f['name']+': '+str(e)) from e
            export_results(folder,db,config,metadata)
        scope=export_results(folder,db,config,metadata)
        progress(db,status='complete_with_errors' if scope['files_with_errors'] or scope['known_videos_not_found'] else 'complete',phase='Finished. Export includes every discovered file and explicit errors.',scope=scope)
    except Exception as e:
        progress(db,status='error',phase='Stopped. Previous completed windows are retained.',error=str(e))
        (folder/'ERROR_REPORT.json').write_text(json.dumps(dict(error=str(e)),indent=2),encoding='utf-8')
        try:export_results(folder,db,config,locals().get('metadata',{'supported_classes':[],'unsupported_classes':list(core.ACTIVITY)}))
        except Exception:pass
        raise
    finally:db.close()

def locked_run(folder):
    with (Path(folder)/'worker.lock').open('a+b') as lock:
        lock.write(b'0');lock.flush();lock.seek(0)
        if sys.platform=='win32':
            import msvcrt
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run(folder)

if __name__=='__main__':locked_run(sys.argv[1])
