"""Paired detector sensitivity experiment; increased detections are not accuracy."""
from pathlib import Path
import argparse,csv,hashlib,json,time
import numpy as np
from auto_evidence import write_csv,sha256

def transform(image,variant):
    import cv2
    if variant=='raw': return image.copy()
    if variant=='clahe':
        lab=cv2.cvtColor(image,cv2.COLOR_BGR2LAB)
        lab[:,:,0]=cv2.createCLAHE(clipLimit=2.,tileGridSize=(8,8)).apply(lab[:,:,0])
        return cv2.cvtColor(lab,cv2.COLOR_LAB2BGR)
    if variant=='gamma_0.7':
        lut=np.round((np.arange(256)/255.)**.7*255).astype('uint8')
        return cv2.LUT(image,lut)
    raise ValueError(variant)

def run(a):
    import torch,cv2
    from PIL import Image
    from megadetector.detection import run_detector
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'images').mkdir()
    torch.set_num_threads(2);cv2.setNumThreads(2)
    m=run_detector.load_detector(str(a.detector.resolve()),force_cpu=not torch.cuda.is_available())
    windows=list(csv.DictReader(a.sampled.open(encoding='utf-8-sig')))
    lookup={(r['file_id'][:12],float(r['start'])):r for r in windows}
    candidates=[]
    for p in a.audit.glob('*.jpg'):
        fid,sec=p.stem.rsplit('_',1);r=lookup.get((fid,float(sec)))
        if r:candidates.append((r['behavior'],p,r))
    selected=[]
    # Fixed hash ordering prevents choosing images because an enhancement worked.
    for label in ['Walking','Feeding','Unknown']:
        cc=sorted((x for x in candidates if x[0]==label),key=lambda x:hashlib.sha256(x[1].name.encode()).hexdigest())
        selected.extend(cc[:4])
    rows=[];manifest=[];began=time.monotonic()
    for i,(old,p,source) in enumerate(selected):
        image=cv2.imread(str(p))
        if image is None: raise ValueError('Unreadable image '+str(p))
        manifest.append(dict(image=p.name,sha256=sha256(p),selection_stratum=old,
                             source=source['source'],source_second=source['start']))
        for variant,size in [('raw',640),('raw',1280),('clahe',1280),('gamma_0.7',1280)]:
            frame=transform(image,variant)
            result=m.generate_detections_one_image(Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)),
                                                   image_id=p.name,image_size=size,detection_threshold=.05)
            if result.get('failure'):raise RuntimeError(result['failure'])
            animals=[d for d in result.get('detections',[]) if str(d['category'])=='1']
            score=max([d['conf'] for d in animals] or [0.])
            row=dict(image=p.name,source=source['source'],source_second=source['start'],
                     original_proposal=old,variant=variant,image_size=size,
                     maximum_animal_score=score,animal_proposals_at_0_4=sum(d['conf']>=.4 for d in animals),
                     animal_proposals_at_0_2=sum(d['conf']>=.2 for d in animals),
                     human_confirmed=False)
            rows.append(row)
            preview=frame.copy();H,W=preview.shape[:2]
            for d in animals:
                if d['conf']<.2:continue
                x,y,w,h=d['bbox'];cv2.rectangle(preview,(int(x*W),int(y*H)),(int((x+w)*W),int((y+h)*H)),(0,200,255),2)
                cv2.putText(preview,f"animal proposal {d['conf']:.2f}",(int(x*W),max(15,int(y*H)-4)),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,200,255),1)
            cv2.imwrite(str(a.output/'images'/f'{p.stem}_{variant}_{size}.jpg'),preview)
            write_csv(a.output/'ENHANCEMENT_RESULTS.csv',rows)
        print(f'Enhancement {i+1}/{len(selected)}',flush=True)
    write_csv(a.output/'ENHANCEMENT_INPUTS.csv',manifest)
    summaries=[]
    for variant,size in [('raw',640),('raw',1280),('clahe',1280),('gamma_0.7',1280)]:
        rr=[r for r in rows if r['variant']==variant and r['image_size']==size]
        summaries.append(dict(variant=variant,image_size=size,images=len(rr),
                              images_with_proposal_at_0_4=sum(r['animal_proposals_at_0_4']>0 for r in rr),
                              images_with_proposal_at_0_2=sum(r['animal_proposals_at_0_2']>0 for r in rr)))
    write_csv(a.output/'ENHANCEMENT_SUMMARY.csv',summaries)
    (a.output/'EXPERIMENT_SCOPE.json').write_text(json.dumps(dict(images=len(selected),inference_calls=len(rows),
        elapsed_seconds=time.monotonic()-began,detector_sha256=sha256(a.detector),
        selection='Four saved frames per historical proposal stratum, fixed SHA-256 filename ordering',
        purpose='Exploratory paired sensitivity check, not independent accuracy evaluation',
        modifies_originals=False,notes=['Higher detector scores can include false positives.',
        'Upscaling does not restore missing image detail.','Contrast enhancement can amplify mesh and noise.',
        'Historical results are unchanged.','No automatic adoption of the best-looking score.']),indent=2))
    print(json.dumps(summaries),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['audit','sampled','detector','output']:p.add_argument('--'+name,type=Path,required=True)
    run(p.parse_args())
