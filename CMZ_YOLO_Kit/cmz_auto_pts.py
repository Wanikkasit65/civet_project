"""Sequential FFmpeg presentation-time reader for misleading CCTV frame rates.

No frame-count/FPS timestamps and no duplicated frames to bridge missing footage.
Sampling selects actual decoded frames by their PTS, approximately four per second.
Large timestamp gaps stop the file so downstream code can record missing coverage.
"""
from collections import deque
import math
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading

SAMPLE_SECONDS = .25
MAX_SAMPLE_GAP = .75


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        result = shutil.which('ffmpeg')
        if not result:
            raise RuntimeError('Install imageio-ffmpeg in this Python environment.')
        return result


def probe(path):
    """Read demuxed duration plus diagnostic stream properties, never count/FPS."""
    result = subprocess.run(
        [ffmpeg_exe(), '-hide_banner', '-nostdin', '-i', str(path),
         '-map', '0:v:0', '-frames:v', '1', '-an', '-f', 'null', '-'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    log = result.stderr.decode('utf-8', errors='replace')
    duration = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', log)
    video = next((line for line in log.splitlines() if 'Stream #' in line and 'Video:' in line), '')
    size = re.search(r'\b(\d{2,6})x(\d{2,6})\b', video)
    rate = re.search(r'([\d.]+)\s+fps\b', video)
    if result.returncode or not duration or not size:
        raise ValueError('Cannot probe video with FFmpeg: '+str(path)+'\n'+log[-2000:])
    seconds = sum(float(v)*factor for v,factor in zip(duration.groups(),(3600,60,1)))
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('Invalid FFmpeg duration: '+str(path))
    return dict(duration=seconds, duration_seconds=seconds,
                fps=float(rate[1]) if rate else 4., width=int(size[1]), height=int(size[2]),
                timing_method='FFmpeg demuxer duration and decoded presentation timestamps',
                probe_log=log)


def _read_exact(stream, count):
    result = bytearray()
    while len(result) < count:
        part = stream.read(count-len(result))
        if not part:
            if result:
                raise ValueError('FFmpeg ended inside an output frame.')
            return None
        result.extend(part)
    return bytes(result)


def sampled_frames(path, start=0., end=None, max_width=1280):
    """Yield (source-relative PTS seconds, BGR ndarray), preserving gaps.

    Input -ss is relative to FFmpeg's demuxer start_time by default. A short
    preroll permits inter-frame decoding before an exact PTS trim. The explicit
    setpts offset preserves the requested origin; PTS-STARTPTS is never used.
    """
    import numpy as np
    start=float(start)
    if not math.isfinite(start) or start<0:
        raise ValueError('Invalid start time.')
    info=probe(path)
    if end is None:end=info['duration']
    end=float(end)
    if not math.isfinite(end) or end<=start:
        return
    width=min(info['width'],int(max_width))
    width=2*max(1,width//2)
    height=2*max(1,round(info['height']*width/info['width']/2))
    seek=max(0.,start-2.)
    offset=start-seek
    selection="select=isnan(prev_selected_t)+gte(t-prev_selected_t\\,0.249999)"
    filters=('trim=start='+str(offset)+':end='+str(end-seek)+
             ',setpts=PTS-'+str(offset)+'/TB,'+selection+
             ',scale='+str(width)+':'+str(height)+',showinfo')
    command=[ffmpeg_exe(),'-hide_banner','-nostdin','-loglevel','info',
             '-ss',str(seek),'-i',str(path),'-t',str(end-start),
             '-map','0:v:0','-an','-sn','-dn','-vf',filters,
             '-fps_mode','passthrough','-pix_fmt','bgr24','-c:v','rawvideo',
             '-threads','1','-f','rawvideo','pipe:1']
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             stdin=subprocess.DEVNULL,bufsize=0)
    timestamps=queue.Queue();diagnostics=deque(maxlen=80)
    pattern=re.compile(r'\bn:\s*\d+.*?\bpts_time:\s*([-+\d.eE]+)')
    def drain():
        try:
            for line in iter(process.stderr.readline,b''):
                decoded=line.decode('utf-8',errors='replace');diagnostics.append(decoded)
                match=pattern.search(decoded)
                if match:timestamps.put(float(match[1]))
        finally:timestamps.put(None)
    worker=threading.Thread(target=drain,daemon=True);worker.start()
    previous=None
    try:
        while True:
            raw=_read_exact(process.stdout,width*height*3)
            if raw is None:break
            try:relative=timestamps.get(timeout=10)
            except queue.Empty:raise RuntimeError('FFmpeg frame timestamp was not emitted.')
            if relative is None:raise RuntimeError('FFmpeg frame lacked a presentation timestamp.')
            t=start+relative
            if not math.isfinite(t):raise ValueError('Non-finite video timestamp.')
            if t<start-1e-4:raise ValueError('FFmpeg returned a frame before the requested start.')
            if t>=end-1e-7:break
            if previous is not None:
                if t<=previous:raise ValueError('Non-increasing presentation timestamps.')
                if t-previous>MAX_SAMPLE_GAP:
                    raise ValueError('Decoded timestamp gap from %.6f to %.6f seconds; coverage is missing.'%(previous,t))
            elif t-start>.35:
                raise ValueError('No decoded frame near requested start %.6f; first PTS %.6f.'%(start,t))
            previous=t
            yield t,np.frombuffer(raw,dtype=np.uint8).reshape(height,width,3).copy()
        returncode=process.wait(timeout=30)
        if returncode:
            raise ValueError('FFmpeg decode failed (%s): %s'%(returncode,''.join(diagnostics)[-2500:]))
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        process.stdout.close();worker.join(timeout=5);process.stderr.close()


def sampled_windows(path,window=2.,start=0.,end=None):
    """Yield (begin,end,frames) with actual PTS-selected frames in fixed windows.

    Final coverage stops at the last observed frame plus one sample period,
    bounded by requested end. A long PTS gap raises instead of inventing Unknown.
    """
    if not math.isfinite(window) or window<=0:raise ValueError('Invalid window.')
    if end is None:end=probe(path)['duration']
    frames=[];bucket=None;last=None
    generator=sampled_frames(path,start,end)
    try:
        for timestamp,frame in generator:
            k=int(math.floor((timestamp-start+1e-7)/window))
            if bucket is not None and k!=bucket:
                yield start+bucket*window,min(end,start+(bucket+1)*window),frames
                frames=[]
            bucket=k;frames.append(frame);last=timestamp
        if frames:
            right=min(end,start+(bucket+1)*window,last+SAMPLE_SECONDS)
            if right>start+bucket*window:
                yield start+bucket*window,right,frames
    finally:generator.close()


# The FFmpeg PTS reader above is bundled with this entrypoint for one-file delivery.
pts_sampled_windows = sampled_windows
pts_probe = probe

import ast
import csv
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from collections import Counter

PIPELINE_VERSION = 'cmz-pts-full-enclosure-v1'


def setup_pipeline():
    import all_video as base
    import phase2_core as core
    original_inventory = base.inventory
    original_features = base.features
    original_export = base.export_results

    # Same spatial representation during training and inference. Animal detector
    # gates presence only; no detector crop rejects human-confirmed training clips.
    def enclosure_features(frames, roi=None):
        return original_features(frames, [0.,0.,1.,1.])

    def inventory(db, roots, workspace=None):
        original_inventory(db, roots, workspace)
        logs=[]
        for f in [dict(r) for r in db.execute('SELECT * FROM files')]:
            base.progress(db,phase='Verifying original video duration with FFmpeg',current_file=f['name'])
            try:
                info=pts_probe(f['path'])
                status='pending' if f['status']=='unreadable' else f['status']
                db.execute('UPDATE files SET seconds=?,fps=?,status=?,error=? WHERE id=?',
                    (info['duration'], info['fps'],status,'' if status=='pending' else f['error'],f['id']))
                logs.append(dict(source=f['name'],**info))
            except Exception as e:
                db.execute("UPDATE files SET seconds=NULL,status='unreadable',error=? WHERE id=?",(str(e),f['id']))
                logs.append(dict(source=f['name'],error=str(e)))
            db.commit()
        db_path=Path(db.execute('PRAGMA database_list').fetchone()[2])
        if str(db_path)!='.':
            (db_path.parent/'FFMPEG_SOURCE_PROBES.json').write_text(json.dumps(logs,indent=2),encoding='utf-8')
        return logs

    def animal_crop(frames, detector, threshold=.4):
        import math
        if len(frames)<5:return None,0.,'too_few_frames'
        boxes=[];scores=[];counts=[];people=False
        for frame in (frames[0],frames[-1]):
            detections=detector(frame)
            people=people or any(str(d['category'])=='2' and d['conf']>=.3 for d in detections)
            candidates=[d for d in detections if str(d['category'])=='1' and d['conf']>=threshold]
            counts.append(len(candidates))
            if len(candidates)==1:
                x,y,w,h=map(float,candidates[0]['bbox'])
                if not all(math.isfinite(v) for v in (x,y,w,h)) or w<=0 or h<=0:return None,0.,'invalid_detector_box'
                boxes.append((x,y,x+w,y+h));scores.append(float(candidates[0]['conf']))
        if people:return None,0.,'person_present'
        if any(n>1 for n in counts):return None,0.,'multiple_animal_proposals'
        if counts==[0,0]:return None,0.,'no_animal_proposal_at_either_endpoint'
        if counts!=[1,1]:return None,max(scores or [0.]),'animal_detection_incomplete'
        x1=min(b[0] for b in boxes);y1=min(b[1] for b in boxes);x2=max(b[2] for b in boxes);y2=max(b[3] for b in boxes)
        roi=[max(0.,x1),max(0.,y1),min(1.,x2),min(1.,y2)]
        if not 0<=roi[0]<roi[2]<=1 or not 0<=roi[1]<roi[3]<=1:return None,0.,'invalid_detector_box'
        return roi,min(scores),'animal_proposal'

    def train(workspace, folder, detector, threshold):
        import numpy as np
        import joblib
        from sklearn.ensemble import RandomForestClassifier
        folder=Path(folder);saved_path=folder/'batch_behavior.joblib'
        rows=core.read_records(workspace);signature=core.annotation_signature(rows)
        if saved_path.exists():
            saved=joblib.load(saved_path)
            if saved['metadata'].get('pipeline_version')!=PIPELINE_VERSION or saved['metadata']['annotation_signature']!=signature:
                raise ValueError('Model or labels changed; start a separate new PTS run.')
            check=folder/'REPLAY_WALKING_CHECKS.json'
            if check.exists() and not json.loads(check.read_text(encoding='utf-8')).get('basic_engineering_gate_passed'):
                raise ValueError('Previous basic Walking check failed; resume cannot bypass it. Send PREFLIGHT_RESULTS.zip.')
            return saved['model'],saved['metadata']
        X=[];y=[];groups=[];segments=[];catalog=core.sample_catalog(workspace)
        for index,r in enumerate(rows):
            if r['behavior'] not in ('Walking','Feeding'):continue
            sample=core.resolve_sample(catalog,r);offset=r['start_second']-float(sample['start_second'])
            for a,b,frames in pts_sampled_windows(sample['local_clip'],start=offset,end=offset+r['end_second']-r['start_second']):
                item=dict(parent_annotation=index,source=r['source'],nominal_source_start=r['start_second'],local_clip_start=a,local_clip_end=b,behavior=r['behavior'],source_time_verified=False)
                try:
                    if b-a<1.4:raise ValueError('Short tail omitted')
                    vector=enclosure_features(frames)
                    X.append(vector);y.append(r['behavior']);groups.append(index);item['used']=True
                except ValueError as e:item.update(used=False,reason=str(e))
                segments.append(item)
        (folder/'TRAINING_SEGMENTS.json').write_text(json.dumps(segments,indent=2),encoding='utf-8')
        counts=dict(Counter(y))
        if set(counts)!= {'Walking','Feeding'} or min(counts.values())<3:
            raise ValueError('Too few recovered temporal segments in both classes; inference not started.')
        X=np.asarray(X);y=np.asarray(y);groups=np.asarray(groups)
        def make():return RandomForestClassifier(n_estimators=200,max_depth=8,min_samples_leaf=2,class_weight='balanced',random_state=42,n_jobs=2)
        diagnostics={b:dict(correct=0,total=0) for b in counts}
        for group in sorted(set(groups)):
            test=groups==group;training=~test
            if len(set(y[training]))<2:continue
            pred=make().fit(X[training],y[training]).predict(X[test])
            for truth,guess in zip(y[test],pred):
                diagnostics[str(truth)]['total']+=1
                diagnostics[str(truth)]['correct']+=int(truth==guess)
        model=make().fit(X,y)
        metadata=dict(pipeline_version=PIPELINE_VERSION,model='RandomForest + Farneback full-enclosure motion features',
            detector='Pretrained MegaDetector V5A animal category, presence gate only',
            spatial_representation='Full frame resized to 96x96 in both training and inference; no detector crop used for features',
            source_annotation_intervals=len(set(groups)),derived_training_segments=len(y),class_counts=counts,
            supported_classes=list(model.classes_),unsupported_classes=['Resting','Sleeping'],annotation_signature=signature,
            evaluation=None,whole_period_behavior_accuracy=None,window_seconds=2.,
            development_leave_one_annotation_out=diagnostics,
            notes=['Adjacent intervals and segments share recording events; leave-one-annotation-out is a development diagnostic, NOT independent test accuracy.',
                   'Human confirmation refers to existing reviewed clip content. Historical source offsets require separate timestamp mapping.',
                   'Full-enclosure motion can confuse feeding with stillness, grooming, lighting and background movement.',
                   'Detection is not species identification. All behavior outputs remain unvalidated model proposals.'])
        joblib.dump(dict(model=model,metadata=metadata),saved_path)
        (folder/'BATCH_TRAINING_REPORT.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        return model,metadata

    def replay(folder,db,detector,model,config):
        folder=Path(folder);checks=[];total=walking=0.
        sources=db.execute('SELECT * FROM files WHERE name=?',('A03_20260405000000.mp4',)).fetchall()
        if len(sources)!=1:raise ValueError('Cannot uniquely locate prior Walking development-check source.')
        for start in (5632.5,5806.5,12558.5):
            segments=[];cw=cf=0.
            for a,b,frames in pts_sampled_windows(sources[0]['path'],start=start,end=start+10):
                roi,animal_score,status=animal_crop(frames,detector,config['animal_threshold'])
                label='Unknown';score=None
                if roi is not None:
                    prob=model.predict_proba([enclosure_features(frames)])[0];k=int(prob.argmax());score=float(prob[k])
                    if score>=config['behavior_threshold']:label=str(model.classes_[k])
                seconds=b-a;total+=seconds
                if label=='Walking':walking+=seconds;cw+=seconds
                if label=='Feeding':cf+=seconds
                segments.append(dict(start_second=a,end_second=b,expected='Walking',proposed_behavior=label,model_score=score,animal_score=animal_score,status=status,roi=roi))
            checks.append(dict(source=sources[0]['name'],start_second=start,end_second=start+10,segments=segments,walking_seconds=cw,feeding_seconds=cf))
        passed=total>=28 and walking>=.5*total and all(c['walking_seconds']>c['feeding_seconds'] for c in checks)
        report=dict(scope='Previously exposed one-class development checks; not fresh independent evaluation.',checks=checks,
                    basic_engineering_gate_passed=passed,walking_seconds=walking,processed_seconds=total,
                    gate_rule='At least 28s decoded; at least half proposed Walking; Walking exceeds Feeding in each clip.',overall_accuracy=None)
        (folder/'REPLAY_WALKING_CHECKS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        # Always export preflight evidence, including timing previews for all cameras.
        audit=folder/'preflight_samples';audit.mkdir(exist_ok=True)
        for c in checks:
            start=c['start_second'];images=[]
            for a,b,frames in pts_sampled_windows(sources[0]['path'],start=start,end=start+10):images.extend(frames)
            base.save_audit_sample(audit,'walking_check',start,images,None)
        for camera in ('A01','A02','A03','A04'):
            f=db.execute('SELECT * FROM files WHERE camera=? AND seconds IS NOT NULL ORDER BY clock LIMIT 1',(camera,)).fetchone()
            if f:
                for q in (0.,.5):
                    at=2*int(q*f['seconds']/2)
                    for a,b,frames in pts_sampled_windows(f['path'],start=at,end=min(at+2,f['seconds'])):
                        base.save_audit_sample(audit,'clock_'+camera,at,frames,None)
        import zipfile
        with zipfile.ZipFile(folder/'PREFLIGHT_RESULTS.zip','w',zipfile.ZIP_DEFLATED) as z:
            for p in folder.glob('*.json'):
                if p.name not in ('config.json','worker_pid.json'):z.write(p,p.name)
            for p in audit.glob('*'):z.write(p,'preflight_samples/'+p.name)
        print('PREFLIGHT ZIP: '+str(folder/'PREFLIGHT_RESULTS.zip'),flush=True)
        if not passed:raise ValueError('Basic Walking check failed. Full inference stopped; send PREFLIGHT_RESULTS.zip for inspection.')
        return report

    def export(folder,db,config,metadata):
        scope=original_export(folder,db,config,metadata)
        # Keep historical clip annotation coordinates explicit, not verified source times.
        path=Path(folder)/'HUMAN_CONFIRMED_ONLY.csv'
        with path.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f);fields=list(reader.fieldnames or []);rows=list(reader)
        for r in rows:r['original_source_time_verified']=False
        base.write_csv(path,rows,fields+['original_source_time_verified'])
        scope['pipeline_version']=PIPELINE_VERSION
        scope['timing_method']='FFmpeg actual decoded presentation timestamps, no frame-count/FPS time calculation'
        scope['warnings'].extend(['Human label source coordinates remain historical; confirmed clip content does not verify original source offset.',
                                 'No animal proposal at sampled endpoints is not proof of shelter occupancy or sleep.',
                                 'Shelter assumption requires all four cameras covering verified shared clock time; missing/failed footage never qualifies.'])
        (Path(folder)/'RESULT_SCOPE.json').write_text(json.dumps(scope,indent=2),encoding='utf-8')
        # Original export created the archive before these additional scope fields.
        import zipfile
        with zipfile.ZipFile(Path(folder)/'ALL_VIDEO_RESULTS.zip','w',zipfile.ZIP_DEFLATED) as z:
            for p in Path(folder).iterdir():
                if p.suffix in ('.json','.csv') and p.name!='config.json':z.write(p,p.name)
            for sub in ('review_samples','preflight_samples'):
                for p in (Path(folder)/sub).glob('*'):
                    if p.suffix in ('.jpg','.mp4'):z.write(p,sub+'/'+p.name)
        return scope

    base.inventory=inventory;base.sampled_windows=pts_sampled_windows
    base.features=enclosure_features;base.animal_crop=animal_crop
    base.train_batch_model=train;base.replay_known_walking_checks=replay
    base.export_results=export
    # Preserve all per-file error/coverage handling, but continue other videos.
    source=Path(base.__file__).read_text(encoding='utf-8-sig');tree=ast.parse(source)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
    changed=0
    class ContinueFiles(ast.NodeTransformer):
        def visit_Raise(self,n):
            nonlocal changed
            text=ast.get_source_segment(source,n) or ''
            if "'Stopped on '" in text and "f['name']" in text:
                changed+=1;return ast.copy_location(ast.Continue(),n)
            return n
    node=ContinueFiles().visit(node)
    if changed!=1:raise RuntimeError('Unexpected original runner version; no originals changed.')
    # Tail coverage tolerance reflects ~4 fps PTS sampling, not stream nominal FPS.
    run_source=ast.unparse(node).replace('max(0.2, 2 / f[\'fps\'])','max(0.35, 2 / f[\'fps\'])')
    exec(compile(run_source,'PTS batch runner','exec'),base.__dict__)
    return base


def main():
    root=Path(__file__).resolve().parent
    old=root/'workspace'/'all_video_runs'/'full_20261101_153841_fd2014'
    resume=len(sys.argv)>2 and sys.argv[1]=='--resume'
    if resume:
        folder=Path(sys.argv[2]).resolve();config=json.loads((folder/'config.json').read_text(encoding='utf-8-sig'))
        if config.get('pipeline_version')!=PIPELINE_VERSION:raise SystemExit('Resume only a run created by this PTS version.')
    else:
        if len(sys.argv)>1:old=Path(sys.argv[1]).resolve()
        config=json.loads((old/'config.json').read_text(encoding='utf-8-sig'))
        if not old.is_dir():raise SystemExit('Previous run folder was not found.')
        config.update(pipeline_version=PIPELINE_VERSION,clocks_verified=False,cpu=False,animal_threshold=.4,behavior_threshold=.7)
        folder=Path(config['workspace'])/'all_video_runs'/('full_pts_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
        folder.mkdir(parents=True,exist_ok=False)
        (folder/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    import torch
    if not torch.cuda.is_available():raise SystemExit('CUDA unavailable; no CPU fallback started.')
    (folder/'worker_pid.json').write_text(json.dumps(dict(pid=os.getpid())),encoding='utf-8')
    print('NEW PTS RUN: '+str(folder),flush=True)
    print('All behavior outputs are model proposals. Historical wrong-time run is retained.',flush=True)
    base=setup_pipeline()
    try:base.locked_run(folder)
    except Exception as e:
        print('STOPPED: '+str(e),flush=True)
        print('Send PREFLIGHT_RESULTS.zip or ALL_VIDEO_RESULTS.zip from: '+str(folder),flush=True)
        raise
    print('DONE: '+str(folder/'ALL_VIDEO_RESULTS.zip'),flush=True)


if __name__=='__main__':main()
