"""Read-only video scout. Motion is a review priority, never an animal label."""
from pathlib import Path
from datetime import datetime,timedelta
import csv,hashlib,json,subprocess,sys,uuid,re,zipfile
import numpy as np
import cv2
from PIL import Image
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parent
WORK=ROOT/'workspace'

def newrun():
 p=WORK/('scan_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]);p.mkdir(parents=True);return p

def state(run,**kw):
 p=Path(run);tmp=p/'status.tmp';tmp.write_text(json.dumps(kw,ensure_ascii=False),encoding='utf-8');tmp.replace(p/'status.json')

def files(folder):
 p=Path(folder).expanduser()
 if not p.is_dir():raise ValueError('Paste an existing local folder path, not a Drive link.')
 return sorted(x.resolve() for x in p.rglob('*') if x.suffix.lower() in ['.mp4','.mkv','.avi','.mov'])

def scan(run,paths,limit=0):
 run=Path(run);(run/'thumbs').mkdir(exist_ok=True);(run/'full').mkdir(exist_ok=True)
 fields=['id','name','source','approx_second','motion','image']
 count=0
 with (run/'decoder.log').open('w',encoding='utf-8') as log,(run/'index.csv').open('w',newline='',encoding='utf-8') as fh:
  writer=csv.DictWriter(fh,fieldnames=fields);writer.writeheader();fh.flush()
  try:
   for path in paths:
    path=Path(path);key=hashlib.sha256(str(path).encode()).hexdigest()[:12]
    cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','warning','-i',str(path)]
    if limit:cmd+=['-t',str(limit)]
    cmd+=['-an','-vf','fps=1,scale=640:360','-pix_fmt','rgb24','-f','rawvideo','pipe:1']
    proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=log);prev=None;n=0;size=640*360*3
    try:
     while True:
      # Buffered reads may return short chunks; accumulate one complete frame.
      raw=bytearray()
      while len(raw)<size:
       part=proc.stdout.read(size-len(raw))
       if not part:break
       raw.extend(part)
      if not raw:break
      if len(raw)!=size:raise ValueError('Truncated decoded frame: '+path.name)
      frame=np.frombuffer(raw,dtype=np.uint8).reshape(360,640,3)
      gray=cv2.cvtColor(frame,cv2.COLOR_RGB2GRAY);small=cv2.resize(gray,(160,90))
      motion=float(np.mean(cv2.absdiff(prev,small)))/255 if prev is not None else 0.
      ident=f'{key}_{n:07d}';dest=run/'thumbs'/(ident+'.jpg')
      Image.fromarray(frame).save(dest,quality=70)
      writer.writerow(dict(id=ident,name=path.name,source=str(path),approx_second=n+.5,motion=motion,image='thumbs/'+dest.name));fh.flush()
      prev=small;n+=1;count+=1
      if n%15==0:state(run,status='running',file=path.name,frames=count,approx_second=n)
    finally:
     proc.stdout.close()
     if sys.exc_info()[0] is not None and proc.poll() is None:proc.terminate()
     code=proc.wait(timeout=30)
    if code:raise ValueError('FFmpeg failed; see decoder.log. Completed frames remain available for review.')
   state(run,status='complete',frames=count)
  except Exception as e:state(run,status='error',frames=count,error=str(e));raise

def load(run):
 import pandas as pd
 return pd.read_csv(Path(run)/'index.csv',keep_default_na=False)

def labels(run):
 p=Path(run)/'annotations.json'
 return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}

def full_frame(run,row):
 """Frame near a selected second, preserving original image dimensions."""
 run=Path(run);dest=run/'full'/(row['id']+'.jpg')
 if dest.exists():return dest
 sec=float(row['approx_second']);preroll=min(5.,sec)
 cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-ss',str(sec-preroll),'-i',str(row['source']),'-ss',str(preroll),'-frames:v','1','-f','image2pipe','-vcodec','mjpeg','pipe:1']
 r=subprocess.run(cmd,capture_output=True,timeout=120)
 if r.returncode or not r.stdout:raise ValueError('Could not read full frame. '+r.stderr.decode(errors='replace')[-300:])
 import io
 Image.open(io.BytesIO(r.stdout)).verify();dest.write_bytes(r.stdout);return dest

def save(run,row,kind,box,reviewer,note):
 if kind not in ['civet','empty','uncertain']:raise ValueError('Invalid label')
 if not reviewer.strip():raise ValueError('Enter reviewer name')
 if kind=='civet' and not (0<=box[0]<box[2]<=1 and 0<=box[1]<box[3]<=1):raise ValueError('Invalid box')
 run=Path(run);data=labels(run);key=str(row['id'])
 item=dict(id=key,name=str(row['name']),source=str(row['source']),approx_second=float(row['approx_second']),kind=kind,box=list(box) if kind=='civet' else None,reviewer=reviewer,note=note)
 with (run/'history.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'before':data.get(key),'after':item,'time':datetime.now().isoformat()},ensure_ascii=False)+'\n')
 data[key]=item;tmp=run/'annotations.tmp';tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8');tmp.replace(run/'annotations.json')

def split_for(name,sec):
 m=re.search(r'A\d+_(\d{14})',name)
 if not m:raise ValueError('Keep original Axx_YYYYMMDDhhmmss filenames for recording-time grouping.')
 t=datetime.strptime(m.group(1),'%Y%m%d%H%M%S')+timedelta(seconds=sec)
 offset=(t.minute%30)*60+t.second
 if offset<15 or offset>1785:return None,None
 g=t.replace(minute=t.minute//30*30,second=0,microsecond=0).isoformat()
 v=int(hashlib.sha256(('cmz-v1:'+g).encode()).hexdigest()[:8],16)%10
 return ('test' if v<2 else 'val' if v<4 else 'train'),g

def build(run):
 """Only explicitly reviewed positives/backgrounds become detector training data."""
 import shutil
 run=Path(run);data=labels(run);items=[];counts={s:{'civet':0,'empty':0,'groups':set()} for s in ['train','val','test']}
 for item in data.values():
  if item['kind']=='uncertain':continue
  split,g=split_for(item['name'],item['approx_second'])
  if split is None:continue
  item=dict(item,split=split,group=g);items.append(item);counts[split][item['kind']]+=1;counts[split]['groups'].add(g)
 for s,c in counts.items():
  minimum=20 if s=='train' else 10
  if c['civet']<minimum or c['empty']<5 or len(c['groups'])<2:
   raise ValueError(f'{s}: need >= {minimum} civet images, 5 verified empty images and 2 recording blocks. Have {c["civet"]} civet, {c["empty"]} empty, {len(c["groups"])} blocks. These are pilot guards, not proof that data are sufficient.')
 out=run/('yolo_data_'+uuid.uuid4().hex[:8]);out.mkdir()
 for s in counts:
  (out/'images'/s).mkdir(parents=True);(out/'labels'/s).mkdir(parents=True)
 seen=set();audit=[]
 for item in items:
  src=full_frame(run,item);digest=hashlib.sha256(src.read_bytes()).hexdigest()
  if digest in seen:raise ValueError('Exact duplicate images detected. Review duplicates before building a training set.')
  seen.add(digest);ident=item['id'];s=item['split'];shutil.copyfile(src,out/'images'/s/(ident+'.jpg'))
  text=''
  if item['kind']=='civet':
   x1,y1,x2,y2=item['box'];text=f'0 {(x1+x2)/2:.6f} {(y1+y2)/2:.6f} {x2-x1:.6f} {y2-y1:.6f}\n'
  (out/'labels'/s/(ident+'.txt')).write_text(text)
  audit.append(dict(item,image_sha256=digest))
 (out/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
 # JSON is valid YAML; avoids quoting bugs with spaces in Windows paths.
 (out/'data.yaml').write_text(json.dumps(dict(path=out.resolve().as_posix(),train='images/train',val='images/val',test='images/test',names={'0':'civet'}),indent=2))
 return out

def review_zip(run,include_images=False):
 run=Path(run);dest=run/('REVIEW_'+uuid.uuid4().hex[:6]+'.zip');df=load(run)
 with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('status.json',(run/'status.json').read_bytes())
  df['source']=df['name'];z.writestr('index.csv',df.to_csv(index=False))
  cleaned=labels(run)
  for v in cleaned.values():v['source']=v['name']
  z.writestr('annotations.json',json.dumps(cleaned,ensure_ascii=False,indent=2))
  if include_images:
   # Uniform temporal coverage and motion-priority coverage, clearly separate.
   uniform=df.iloc[np.linspace(0,len(df)-1,min(24,len(df)),dtype=int)] if len(df) else df
   priority=df.assign(time_bin=(df.approx_second//10).astype(int)).sort_values('motion',ascending=False).drop_duplicates(['name', 'time_bin']).head(24)
   for tag,part in [('uniform',uniform),('motion_priority_NOT_labels',priority)]:
    if not len(part):continue
    from PIL import ImageDraw
    canvas=Image.new('RGB',(1280,4*205),'#202020');draw=ImageDraw.Draw(canvas)
    for j,(_,r) in enumerate(part.head(24).iterrows()):
     x=(j%4)*320;y=(j//4)*205
     # 24 images require six rows.
     if j==0:canvas=Image.new('RGB',(1280,6*205),'#202020');draw=ImageDraw.Draw(canvas)
     im=Image.open(run/r['image']);im.thumbnail((320,180));canvas.paste(im,(x,y));draw.text((x,y+181),f'{r["name"]} ~{r["approx_second"]:.1f}s',fill='white')
    import io
    b=io.BytesIO();canvas.save(b,format='JPEG',quality=85);z.writestr(tag+'.jpg',b.getvalue())
 return dest

if __name__=='__main__':
 request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'));scan(request['run'],request['paths'],request.get('limit',0))
