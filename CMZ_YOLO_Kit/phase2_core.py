"""Behavior annotations, conservative activity tables and a motion-feature pilot.

Original scans/videos are read only. All changes go to new phase2 files.
Unconfirmed predictions never become observed Active/Inactive time.
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import csv, hashlib, json, math, re, uuid

BEHAVIORS = ('Walking', 'Feeding', 'Resting', 'Sleeping', 'Other', 'Unknown', 'Not visible', 'Mixed')
ACTIVITY = {'Walking': 'Active', 'Feeding': 'Active', 'Resting': 'Inactive', 'Sleeping': 'Inactive'}

def normalize(row, event_group=None):
    name = str(row.get('source', row.get('name', ''))).replace('\\', '/').split('/')[-1]
    start, end = float(row['start_second']), float(row['end_second'])
    label = row['behavior']
    if not name or not all(math.isfinite(x) for x in (start, end)) or not 0 <= start < end:
        raise ValueError('Invalid filename or interval.')
    if label not in BEHAVIORS:
        raise ValueError('Unsupported behavior: '+str(label))
    if row.get('human_confirmed') is not True or row.get('label_source') != 'human_review':
        raise ValueError('Only explicit human-reviewed labels may enter confirmed tables.')
    roi = row.get('roi')
    if roi is not None:
        roi = [float(v) for v in roi]
        if len(roi) != 4 or not all(math.isfinite(v) for v in roi) or not (0 <= roi[0] < roi[2] <= 1 and 0 <= roi[1] < roi[3] <= 1):
            raise ValueError('ROI must contain x1,y1,x2,y2 within 0..1.')
    return dict(source=name, start_second=start, end_second=end, behavior=label,
                label_source='human_review', human_confirmed=True, roi=roi,
                event_group=event_group or row.get('event_group'), note=str(row.get('note', '')),
                id=str(row.get('id', '')))

def key(row):
    return (row['source'], float(row['start_second']), float(row['end_second']))

def validate_intervals(rows):
    """Overlap with different labels needs a human decision, never silent summation."""
    for source in sorted({r['source'] for r in rows}):
        ordered = sorted((r for r in rows if r['source'] == source), key=lambda r:r['start_second'])
        active = []
        for r in ordered:
            active = [p for p in active if p['end_second'] > r['start_second']]
            if any(p['behavior'] != r['behavior'] for p in active):
                raise ValueError(f'Conflicting overlapping labels in {source} near {r["start_second"]}s.')
            active.append(r)

def read_records(workspace):
    latest = {}
    for p in sorted((Path(workspace)/'phase2'/'annotations').glob('*.json')):
        doc = json.loads(p.read_text(encoding='utf-8'))
        for previous in doc.get('supersedes', []):
            latest.pop((str(previous[0]), float(previous[1]), float(previous[2])), None)
        for r in doc['observations']:
            r = normalize(r)
            latest[key(r)] = r
    result = list(latest.values())
    validate_intervals(result)
    return sorted(result, key=key)

def save_records(workspace, rows, event_group=None, supersedes=None):
    rows = [normalize(r, event_group) for r in rows]
    proposed = {key(r):r for r in read_records(workspace)}
    supersedes = supersedes or []
    for previous in supersedes:
        previous = (str(previous[0]), float(previous[1]), float(previous[2]))
        if previous not in proposed:
            raise ValueError('The original interval changed. Reload before correcting it.')
        del proposed[previous]
    proposed.update({key(r):r for r in rows})
    validate_intervals(list(proposed.values()))
    folder = Path(workspace)/'phase2'/'annotations'; folder.mkdir(parents=True, exist_ok=True)
    p = folder/(datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')+'_'+uuid.uuid4().hex[:6]+'.json')
    with p.open('x', encoding='utf-8') as f:
        json.dump(dict(observations=rows, supersedes=supersedes, created_utc=datetime.now(timezone.utc).isoformat()), f, ensure_ascii=False, indent=2)
    return p

def correct_interval(workspace, original, start, end, roi=None):
    """Append a shorter replacement; preserve the original annotation file."""
    if not original['start_second'] <= start < end <= original['end_second']:
        raise ValueError('Choose a non-empty interval inside the original interval.')
    updated=dict(original,start_second=start,end_second=end)
    if roi is not None:updated['roi']=roi
    return save_records(workspace,[updated],supersedes=[key(original)])

def annotation_signature(rows):
    selected=sorted((normalize(r) for r in rows if r['behavior'] in ACTIVITY),key=key)
    return hashlib.sha256(json.dumps(selected,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def union_seconds(intervals):
    total = 0.; right = None
    for left, end in sorted(intervals):
        if right is None or left > right:
            total += end-left; right = end
        elif end > right:
            total += end-right; right = end
    return total

def tables(rows):
    validate_intervals(rows)
    detail = [dict(source=r['source'], start_second=r['start_second'], end_second=r['end_second'],
                   behavior=r['behavior'], activity=ACTIVITY.get(r['behavior'], 'Unknown'),
                   interval_seconds=r['end_second']-r['start_second'], evidence='human_review') for r in rows]
    summary = []
    for source in sorted({r['source'] for r in rows}):
        for b in BEHAVIORS:
            subset = [r for r in rows if r['source']==source and r['behavior']==b]
            summary.append(dict(source=source, behavior=b, activity=ACTIVITY.get(b, 'Unknown'),
                                reviewed_intervals=len(subset),
                                confirmed_seconds=union_seconds([(r['start_second'],r['end_second']) for r in subset]) if subset else None,
                                status='observed_in_reviewed_intervals' if subset else 'not_annotated_not_zero'))
    return detail, summary

def recording_blocks(row):
    m = re.search(r'A\d+_(\d{14})', row['source'])
    if not m:
        raise ValueError('Original Axx_YYYYMMDDhhmmss names are needed for grouped training.')
    base = datetime.strptime(m.group(1), '%Y%m%d%H%M%S')
    start = base+timedelta(seconds=row['start_second'])
    end = base+timedelta(seconds=row['end_second']-1e-6)
    t = start.replace(minute=start.minute//30*30, second=0, microsecond=0)
    result=[]
    while t <= end:
        result.append(t.isoformat()); t += timedelta(minutes=30)
    return result

def grouped_ids(rows):
    """Union shared clock blocks across cameras AND explicit event groups."""
    parent = list(range(len(rows)))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    tokens={}
    for i,r in enumerate(rows):
        for token in ['clock:'+b for b in recording_blocks(r)]+(['event:'+r['event_group']] if r.get('event_group') else []):
            if token in tokens:
                parent[root(i)] = root(tokens[token])
            tokens[token]=i
    groups={}
    for i,r in enumerate(rows):
        groups.setdefault(root(i),[]).extend(recording_blocks(r))
    return [min(groups[root(i)]) for i in range(len(rows))]

def sample_catalog(workspace):
    """Match copied videos by original filename and interval, not absolute path."""
    catalog={}
    for p in sorted(Path(workspace).glob('*review_*/manifest.json')):
        try:
            doc=json.loads(p.read_text(encoding='utf-8'))
        except (OSError,ValueError):
            continue
        for r in doc.get('samples',[]):
            clip=(p.parent/r['clip']).resolve()
            # Do not accept references outside their generated review folder.
            if clip.is_relative_to(p.parent.resolve()) and clip.is_file():
                catalog[(r['source'],float(r['start_second']),float(r['end_second']))]=dict(r,local_clip=str(clip))
    return catalog

def resolve_sample(catalog, row):
    matches=[r for r in catalog.values() if r['source']==row['source'] and
             float(r['start_second'])<=row['start_second'] and float(r['end_second'])>=row['end_second']]
    if not matches:raise ValueError('Reviewed interval has no locally available parent clip.')
    return min(matches,key=lambda r:float(r['end_second'])-float(r['start_second']))

def motion_features(clip, roi, start_offset=0., duration=None):
    import cv2
    import numpy as np
    if roi is None:
        raise ValueError('Review an animal ROI covering its entire movement in the clip before training.')
    cap=cv2.VideoCapture(str(clip));fps=cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or not math.isfinite(fps) or fps<=0:
        cap.release();raise ValueError('Unreadable clip or frame rate.')
    previous=None;steps=[];n=0;stride=max(1,round(fps/4))
    try:
        while len(steps)<80:
            ok,frame=cap.read()
            if not ok:break
            n+=1
            timestamp=(n-1)/fps
            if timestamp<start_offset:continue
            if duration is not None and timestamp>=start_offset+duration:break
            if (n-1)%stride:continue
            h,w=frame.shape[:2];x1,y1,x2,y2=roi
            crop=frame[int(y1*h):max(int(y1*h)+1,int(y2*h)),int(x1*w):max(int(x1*w)+1,int(x2*w))]
            gray=cv2.resize(cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY),(96,96))
            if previous is not None:
                flow=cv2.calcOpticalFlowFarneback(previous,gray,None,.5,3,15,3,5,1.2,0)
                mag=np.linalg.norm(flow,axis=2)
                diff=gray.astype(float)-previous.astype(float);diff=np.abs(diff-np.median(diff))/255
                steps.append([float(diff.mean()),float(np.quantile(diff,.9)),float(mag.mean()),
                              float(np.quantile(mag,.9)),float((mag>1).mean()),float(np.linalg.norm(flow.mean(axis=(0,1))))])
            previous=gray
    finally:cap.release()
    if len(steps)<4:raise ValueError('Clip is too short for temporal features.')
    a=np.asarray(steps)
    return np.concatenate([a.mean(axis=0),a.std(axis=0),np.quantile(a,.9,axis=0)])

def train_pilot(workspace, rows, clocks_verified=False):
    import numpy as np
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report, confusion_matrix
    selected=[r for r in rows if r['behavior'] in ACTIVITY]
    catalog=sample_catalog(workspace)
    classes=sorted({r['behavior'] for r in selected})
    if len(classes)<2:raise ValueError('Need reviewed clips from at least two behavior classes. Feeding alone cannot train a behavior classifier.')
    counts={b:sum(r['behavior']==b for r in selected) for b in classes}
    if min(counts.values())<3:raise ValueError('Need at least 3 reviewed clips per supported class for a software pilot; this is not evidence of sufficient data.')
    missing=[r for r in selected if r.get('roi') is None]
    if missing:raise ValueError(f'{len(missing)} labeled clips need a reviewed ROI or a locally available review clip.')
    groups=grouped_ids(selected)
    split=lambda g:int(hashlib.sha256(('cmz-phase2-v1:'+g).encode()).hexdigest()[:8],16)%10
    train=[i for i,g in enumerate(groups) if split(g)>=2];test=[i for i,g in enumerate(groups) if split(g)<2]
    valid_eval=bool(clocks_verified and train and test and all(sum(selected[i]['behavior']==b for i in train)>=3 and sum(selected[i]['behavior']==b for i in test)>=3 for b in classes))
    # Without independent class support, train a clearly marked pilot on all labels.
    # No resubstitution accuracy or cross-validation score is manufactured.
    used=train if valid_eval else list(range(len(selected)))
    features=[]
    for r in selected:
        sample=resolve_sample(catalog,r)
        features.append(motion_features(sample['local_clip'],r['roi'],r['start_second']-sample['start_second'],r['end_second']-r['start_second']))
    X=np.stack(features);y=np.asarray([r['behavior'] for r in selected])
    model=RandomForestClassifier(n_estimators=200,max_depth=8,min_samples_leaf=2,class_weight='balanced',random_state=42,n_jobs=2)
    model.fit(X[used],y[used])
    root=Path(workspace)/'phase2';folder=root/('pilot_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]);folder.mkdir(parents=True)
    metrics=None;reason='No independent test set with sufficient examples of every supported class, or filename clocks not verified.'
    if valid_eval:
        # Never repeatedly score an already exposed recording group.
        exposed=set()
        for p in (root/'test_exposures').glob('*.json'):
            exposed.update(json.loads(p.read_text())['groups'])
        test_groups=set(groups[i] for i in test)
        if exposed.intersection(test_groups):
            reason='Test recording groups were evaluated previously; retained predictions are not a fresh test.'
        else:
            locks=root/'test_exposures';locks.mkdir(exist_ok=True)
            with (locks/(uuid.uuid4().hex+'.json')).open('x') as f:json.dump(dict(groups=sorted(test_groups)),f)
            pred=model.predict(X[test]);metrics=dict(report=classification_report(y[test],pred,labels=classes,output_dict=True,zero_division=0),
                confusion_matrix=confusion_matrix(y[test],pred,labels=classes).tolist(),class_order=classes,test_clips=len(test),test_groups=sorted(test_groups))
            reason=None
    metadata=dict(task='human-ROI motion-feature behavior pilot',model='RandomForest + Farneback optical flow',
                  trained=True,supported_classes=classes,unsupported_classes=[b for b in ACTIVITY if b not in classes],
                  training_clips=len(used),training_groups=sorted({groups[i] for i in used}),class_counts=counts,
                  annotation_signature=annotation_signature(rows),
                  evaluation=metrics,evaluation_limitation=reason,automatic_activity_status_enabled=False,
                  note='ROI motion can confuse feeding, grooming and stillness. Unsupported behaviors are not validated. Proposals require human review.')
    joblib.dump(dict(model=model,metadata=metadata),folder/'behavior_pilot.joblib')
    (folder/'TRAINING_REPORT.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    return folder,metadata

def propose(workspace, model_path, sample, roi):
    import joblib
    # UI only offers models produced by this app, never arbitrary uploaded pickle files.
    root=(Path(workspace)/'phase2').resolve();p=Path(model_path).resolve()
    if not p.is_relative_to(root) or p.name!='behavior_pilot.joblib':raise ValueError('Use a model created by this app.')
    saved=joblib.load(p)
    if saved['metadata'].get('annotation_signature') != annotation_signature(read_records(workspace)):
        raise ValueError('This model predates the current annotations or lacks a dataset signature. Retrain after correcting the labels; the old model is retained as history.')
    feature=motion_features(sample['local_clip'],roi)
    probabilities=saved['model'].predict_proba([feature])[0];i=int(probabilities.argmax())
    return dict(source=sample['source'],start_second=sample['start_second'],end_second=sample['end_second'],
                proposed_behavior=str(saved['model'].classes_[i]),vote_fraction=float(probabilities[i]),
                activity='Unknown',human_confirmed=False,
                note='Unvalidated proposal, not an observed behavior. Vote fraction is not calibrated confidence.')

def write_report(workspace,rows):
    detail,summary=tables(rows);p=Path(workspace)/'phase2'/('report_'+uuid.uuid4().hex[:8]);p.mkdir(parents=True)
    for name,items,fields in [('confirmed_intervals.csv',detail,['source','start_second','end_second','behavior','activity','interval_seconds','evidence']),
                              ('behavior_summary.csv',summary,['source','behavior','activity','reviewed_intervals','confirmed_seconds','status'])]:
        with (p/name).open('x',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(items)
    limitations=dict(scope='human_reviewed_intervals_only',model_predictions=False,
                     missing_classes=[b for b in ACTIVITY if not any(r['behavior']==b for r in rows)],
                     notes=['Blank seconds mean not annotated, not zero behavior.',
                            'Not visible and box entry do not establish resting or sleeping.',
                            'Do not sum overlapping camera views as animal time.',
                            'Selected clips are not a whole-night activity budget.'])
    (p/'REPORT_SCOPE.json').write_text(json.dumps(limitations,indent=2),encoding='utf-8')
    return p
