"""Create a new merged detector dataset; never change old scans or labels."""
from pathlib import Path
import csv, hashlib, json, shutil, sys, uuid
from datetime import datetime
import scout

def merge_scans(workspace):
    workspace=Path(workspace);selected={}
    for run in sorted(workspace.glob('scan_*')):
        for item in scout.labels(run).values():
            if item['kind'] not in ('civet','empty','uncertain'):continue
            k=(item['name'],float(item['approx_second']))
            previous=selected.get(k)
            if previous:
                old=Path(previous[1]['source']);new=Path(item['source'])
                if old.is_file() and new.is_file() and old.stat().st_size!=new.stat().st_size:
                    raise ValueError('Same filename refers to different file sizes; resolve before merging: '+item['name'])
            selected[k]=(run,item)
    if not selected:raise ValueError('No reviewed scout annotations found in this workspace.')
    out=workspace/('scan_merged_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    out.mkdir();(out/'full').mkdir();(out/'thumbs').mkdir()
    records=[];annotations={};provenance=[]
    for (name,sec),(old,item) in sorted(selected.items()):
        ident=hashlib.sha256((name+':'+str(sec)).encode()).hexdigest()[:20]
        updated=dict(item,id=ident)
        cached=old/'full'/(item['id']+'.jpg')
        if cached.is_file():shutil.copyfile(cached,out/'full'/(ident+'.jpg'))
        thumb=old/'thumbs'/(item['id']+'.jpg')
        if thumb.is_file():shutil.copyfile(thumb,out/'thumbs'/(ident+'.jpg'))
        annotations[ident]=updated
        records.append(dict(id=ident,name=name,source=item['source'],approx_second=sec,motion=0,image='thumbs/'+ident+'.jpg'))
        provenance.append(dict(id=ident,from_scan=old.name,original_id=item['id']))
    with (out/'index.csv').open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['id','name','source','approx_second','motion','image']);w.writeheader();w.writerows(records)
    (out/'annotations.json').write_text(json.dumps(annotations,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'merge_provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    scout.state(out,status='complete',frames=len(records),note='Merged reviewed frames only; original scans remain unchanged.')
    try:
        data=scout.build(out)
        result=dict(ready=True,dataset=str(data/'data.yaml'))
    except ValueError as e:
        result=dict(ready=False,reason=str(e),note='Existing data guards were not lowered. Add reviewed validation/test data in original scans, then create a fresh merged export.')
    (out/'MERGE_READY.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return out,result

if __name__=='__main__':
    try:
        out,result=merge_scans(Path(__file__).resolve().parent/'workspace')
        print('New merged scan:',out);print(json.dumps(result,indent=2))
    except Exception as e:print('Stopped:',e);sys.exit(1)
