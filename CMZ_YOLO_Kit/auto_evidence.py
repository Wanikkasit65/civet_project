"""Automatic evidence pass over saved audit clips and optional original videos.

Never turns detector labels into human observations. Original videos are read
only. Every output directory must be new. PTS decoding comes from cmz_auto_pts.
"""
from pathlib import Path
import argparse, csv, hashlib, json, math, time
from collections import Counter
import numpy as np


def write_csv(path, rows, fields=None):
    fields = fields or (list(rows[0]) if rows else ['status'])
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()


def summarize_track(detections, duration):
    """Image-plane geometry proxy, not an ethological ground-truth label."""
    valid = [d for d in detections if d['animal_count'] == 1 and not d['person_present']]
    coverage = len(valid) / len(detections) if detections else 0.
    if len(valid) < 2 or coverage < .75:
        return dict(motion_proxy='Unknown', displacement_body_lengths=None,
                    detection_coverage=coverage)
    # Reject large gaps so a reappearance does not create a false walking bout.
    if any(b['clip_second'] - a['clip_second'] > 1.1 for a,b in zip(valid,valid[1:])):
        return dict(motion_proxy='Unknown', displacement_body_lengths=None,
                    detection_coverage=coverage)
    a,b=valid[0],valid[-1]
    # x,y use pixels relative to frame width so vertical and horizontal scales agree.
    scale=np.median([max(d['box_width'],d['box_height']) for d in valid])
    dist=math.hypot(b['center_x']-a['center_x'],b['center_y']-a['center_y']) / max(scale,1e-9)
    span=b['clip_second']-a['clip_second']
    speed=dist/max(span,1e-9)
    if dist >= .5 and speed >= .25:
        label='Moving proposal'
    elif span >= 6 and dist < .25 and speed < .04:
        label='Stationary proposal'
    else: label='Unknown'
    return dict(motion_proxy=label,displacement_body_lengths=float(dist),
                detection_coverage=coverage)


def train_from_reviewed_clips(timing, out):
    """Reconstruct the pilot from supplied reviewed clip bytes, not source offsets."""
    import joblib
    import all_video as base
    import cmz_auto_pts as pts
    from sklearn.ensemble import RandomForestClassifier
    report=json.loads((timing/'CHECK_REPORT.json').read_text())
    X=[];y=[];register=[]
    for item in report['previews']:
        ann=item.get('annotation')
        if not ann: continue
        p=timing/item['file']
        for a,b,frames in pts.sampled_windows(p):
            if b-a<1.95 or len(frames)<5: continue
            X.append(base.features(frames,[0,0,1,1])); y.append(ann['behavior'])
            register.append(dict(clip=p.name,clip_start=a,clip_end=b,label=ann['behavior'],
                                 label_source='existing human_review, retained',
                                 source=ann['source'],historical_source_start=ann['start_second'],
                                 original_offset_verified=False,clip_sha256=sha256(p),
                                 event_group=ann.get('event_group') or 'same_source_recording'))
    if len(set(y))<2: raise ValueError('Need two existing reviewed classes.')
    model=RandomForestClassifier(n_estimators=200,max_depth=8,min_samples_leaf=2,
                                 class_weight='balanced',random_state=42,n_jobs=2)
    model.fit(np.asarray(X),y)
    joblib.dump(model,out/'reconstructed_behavior.joblib')
    write_csv(out/'RECONSTRUCTED_TRAINING_SEGMENTS.csv',register)
    metadata=dict(model='RandomForest',n_estimators=200,max_depth=8,min_samples_leaf=2,
                  class_weight='balanced',random_state=42,features=18,frame_size=[96,96],
                  spatial_representation='full frame',training_segments=len(y),
                  class_counts=dict(Counter(y)),independent_test_metrics=None,
                  model_scope='Reconstructed from encoded review clips. Distinct from historical saved model.',
                  provenance='Existing clip labels retained. Original long-video offsets unverified.')
    (out/'RECONSTRUCTED_TRAINING_REPORT.json').write_text(json.dumps(metadata,indent=2))
    return model,metadata


def build_tasks(audit, sampled_csv, originals, interval, window):
    import cmz_auto_pts as pts
    rows=list(csv.DictReader(sampled_csv.open(encoding='utf-8-sig')))
    index={(r['file_id'][:12],float(r['start'])):r for r in rows}
    tasks=[]
    for p in sorted(audit.glob('*.mp4')):
        key,offset=p.stem.rsplit('_',1); r=index.get((key,float(offset)))
        tasks.append(dict(path=p,source=r['source'] if r else p.name,
                          camera=r['camera'] if r else 'Unknown',start=0.,
                          end=pts.probe(p)['duration'],source_start=float(offset),
                          source_offset_verified=True,
                          cohort='saved_convenience_audit',old_proposal=r['behavior'] if r else '',
                          statistical_sample=False))
    for folder in originals:
        for p in sorted(folder.rglob('*.mp4')):
            seconds=pts.probe(p)['duration']
            for start in np.arange(0,max(0,seconds-window)+1e-6,interval):
                tasks.append(dict(path=p,source=p.name,camera=p.name.split('_')[0],
                                  start=float(start),end=float(start+window),source_start=float(start),
                                  source_offset_verified=True,cohort='additional_systematic_windows',
                                  old_proposal='',statistical_sample=False))
    return tasks


def run(args):
    import cv2,torch,all_video as base,cmz_auto_pts as pts
    from PIL import Image
    from megadetector.detection import run_detector
    out=args.output.resolve(); out.mkdir(parents=True,exist_ok=args.resume)
    (out/'annotated_examples').mkdir(exist_ok=args.resume)
    torch.set_num_threads(2);cv2.setNumThreads(2)
    began=time.monotonic()
    model,training=train_from_reviewed_clips(args.timing,out)
    detector=run_detector.load_detector(str(args.detector.resolve()),force_cpu=not torch.cuda.is_available())
    tasks=build_tasks(args.audit,args.sampled,args.originals,args.interval,args.window)
    windows=[];all_detections=[];errors=[];manifest=[]
    if args.resume:
        for name,target in [('AUTO_WINDOWS.csv',windows),('AUTO_DETECTIONS.csv',all_detections)]:
            if (out/name).exists():target.extend(csv.DictReader((out/name).open(encoding='utf-8-sig')))
    done={r['window_id'] for r in windows}
    config=dict(detector_sha256=sha256(args.detector),image_size=args.image_size,
                threshold=args.threshold,interval=args.interval,window=args.window)
    config_path=out/'RUN_CONFIG.json'
    if config_path.exists() and json.loads(config_path.read_text())!=config:
        raise ValueError('Resume configuration changed. Use a new output directory.')
    config_path.write_text(json.dumps(config,indent=2))
    for task in tasks:
        p=task['path']
        if not any(m['clip']==p.name for m in manifest):
            manifest.append(dict(clip=p.name,sha256=sha256(p),bytes=p.stat().st_size,
                                 cohort=task['cohort'],source=task['source']))
    for i,task in enumerate(tasks):
        p=task['path']; key=hashlib.sha256((str(p)+str(task['start'])).encode()).hexdigest()[:16]
        if key in done:continue
        try:
            decoded=list(pts.sampled_frames(p,start=task['start'],end=task['end']))
            if len(decoded)<5:raise ValueError('Insufficient temporal frames')
            frames=[f for t,f in decoded]; detection_rows=[]
            # 2 detector frames per second. Keep 4 fps for the RF motion vector.
            for j,(t,frame) in enumerate(decoded):
                if j%2 and j!=len(decoded)-1:continue
                result=detector.generate_detections_one_image(
                    Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)),
                    image_id=key,image_size=args.image_size,detection_threshold=.05)
                if result.get('failure'):raise RuntimeError(result['failure'])
                dd=result.get('detections',[])
                animals=[d for d in dd if str(d['category'])=='1' and d['conf']>=args.threshold]
                person=any(str(d['category'])=='2' and d['conf']>=.3 for d in dd)
                row=dict(window_id=key,source=task['source'],camera=task['camera'],
                         cohort=task['cohort'],clip_second=t-task['start'],
                         source_second=task['source_start']+t-task['start'],
                         animal_count=len(animals),person_present=person,
                         animal_score=max([d['conf'] for d in animals] or [0.]),
                         center_x=None,center_y=None,box_width=None,box_height=None,
                         x_norm=None,y_norm=None,human_confirmed=False)
                if len(animals)==1:
                    x,y,w,h=animals[0]['bbox']; H,W=frame.shape[:2]
                    row.update(center_x=x+w/2,center_y=(y+h/2)*H/W,
                               box_width=w,box_height=h*H/W,x_norm=x+w/2,y_norm=y+h/2)
                detection_rows.append(row)
                if j==0:
                    preview=frame.copy()
                    for d in animals:
                        x,y,w,h=d['bbox'];H,W=preview.shape[:2]
                        cv2.rectangle(preview,(int(x*W),int(y*H)),(int((x+w)*W),int((y+h)*H)),(0,220,255),2)
                    cv2.imwrite(str(out/'annotated_examples'/f'{key}.jpg'),preview)
            motion=summarize_track(detection_rows,task['end']-task['start'])
            # Preserve the 2-second temporal feature window used in training,
            # including when a longer window is supplied for geometry tracking.
            votes=[];scores=[];raw_classes=[]
            for left in np.arange(task['start'],task['end']-1.2,2.):
                segment=[f for t,f in decoded if left<=t<left+2.-1e-7]
                if len(segment)<5:
                    votes.append('Unknown');continue
                prob=model.predict_proba([base.features(segment,[0,0,1,1])])[0]
                s=float(max(prob));lab=str(model.classes_[int(np.argmax(prob))])
                raw_classes.append(lab);scores.append(s)
                votes.append(lab if s>=.7 else 'Unknown')
            score=min(scores) if scores else 0.
            label=votes[0] if votes and len(set(votes))==1 else 'Unknown'
            endpoints=detection_rows[0],detection_rows[-1]
            reliable=all(r['animal_count']==1 and not r['person_present'] for r in endpoints)
            behavior=label if reliable and score>=.7 else 'Unknown'
            # Resting/feeding are never derived from a stationary bounding box.
            win=dict(window_id=key,source=task['source'],camera=task['camera'],
                     cohort=task['cohort'],clip=p.name,source_start=task['source_start'],
                     source_end=task['source_start']+task['end']-task['start'],
                     decoded_frames=len(frames),detector_frames=len(detection_rows),
                     behavior_proposal=behavior,rf_raw_class=';'.join(raw_classes),rf_score=score,
                     old_proposal=task['old_proposal'],**motion,
                     activity_proposal='Active' if behavior in ('Walking','Feeding') else 'Unknown',
                     human_confirmed=False,status='complete',
                     observed_rest_sleep_seconds=None)
            windows.append(win);all_detections.extend(detection_rows)
            if not any(m['clip']==p.name for m in manifest):
                manifest.append(dict(clip=p.name,sha256=sha256(p),bytes=p.stat().st_size,
                                     cohort=task['cohort'],source=task['source']))
        except Exception as e:
            errors.append(dict(window_id=key,source=task['source'],start=task['start'],error=str(e)))
        write_csv(out/'AUTO_WINDOWS.csv',windows)
        write_csv(out/'AUTO_DETECTIONS.csv',all_detections)
        (out/'PROGRESS.json').write_text(json.dumps(dict(completed=i+1,total=len(tasks),errors=len(errors))))
        print(f'{i+1}/{len(tasks)} {p.name} errors={len(errors)}',flush=True)
    write_csv(out/'ERRORS.csv',errors,['window_id','source','start','error'])
    write_csv(out/'INPUT_MANIFEST.csv',manifest)
    summary=dict(status='complete' if not errors else 'complete_with_errors',
                 elapsed_seconds=time.monotonic()-began,planned_windows=len(tasks),
                 processed_windows=len(windows),errors=len(errors),
                 detector='MegaDetector V5A (YOLOv5)',detector_sha256=sha256(args.detector),
                 image_size=args.image_size,animal_threshold=args.threshold,
                 device='cuda' if torch.cuda.is_available() else 'cpu',
                 behavior_counts_by_cohort={c:dict(Counter(r['behavior_proposal'] for r in windows if r['cohort']==c)) for c in sorted(set(r['cohort'] for r in windows))},
                 motion_counts=dict(Counter(r['motion_proxy'] for r in windows)),
                 detected_frames=sum(int(r['animal_count'])>0 for r in all_detections),
                 detector_frames=len(all_detections),independent_accuracy=None,
                 human_review_required_to_run=False,
                 notes=['All labels are automated proposals.',
                        'Convenience audit clips and extra systematic windows are separate from the historical random-sample totals.',
                        'An animal detection cannot establish feeding, sleep, species or welfare.',
                        'Bounding-box displacement is a perspective-dependent motion proxy.',
                        'Stationary proposal is not observed rest or sleep.',
                        'Additional windows use 640-pixel detection, not the previous detector resolution.',
                        'Original annotation offsets remain unverified; reviewed clip content is retained.'])
    (out/'AUTO_SUMMARY.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--timing',type=Path,required=True)
    ap.add_argument('--audit',type=Path,required=True)
    ap.add_argument('--sampled',type=Path,required=True)
    ap.add_argument('--detector',type=Path,required=True)
    ap.add_argument('--originals',type=Path,nargs='*',default=[])
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--interval',type=float,default=30.)
    ap.add_argument('--window',type=float,default=8.)
    ap.add_argument('--image-size',type=int,default=1280)
    ap.add_argument('--threshold',type=float,default=.4)
    ap.add_argument('--resume',action='store_true')
    args=ap.parse_args()
    if args.window<2 or args.interval<args.window:ap.error('Require 2 <= window <= interval')
    run(args)
