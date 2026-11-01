"""Create short review copies from existing scan indexes; never infer labels."""
from pathlib import Path
import argparse, csv, hashlib, html, json, shutil, subprocess, sys, uuid, zipfile
from datetime import datetime

ROOT = Path(__file__).resolve().parent

def select_samples(rows, per_method=8, separation=60):
    rows = sorted(rows, key=lambda r: float(r['approx_second']))
    if not rows:
        return []
    chosen = []
    # Uniform coverage is retained even when motion scores are low.
    for i in range(per_method):
        pos = round(i * (len(rows)-1) / max(1, per_method-1))
        row = rows[pos]
        if all(abs(float(row['approx_second'])-float(x['approx_second'])) >= separation for x in chosen):
            chosen.append(dict(row, selection='uniform'))
    for row in sorted(rows, key=lambda r: float(r.get('motion') or 0), reverse=True):
        if sum(x['selection']=='motion_candidate' for x in chosen) >= per_method:
            break
        if all(abs(float(row['approx_second'])-float(x['approx_second'])) >= separation for x in chosen):
            chosen.append(dict(row, selection='motion_candidate'))
    return sorted(chosen, key=lambda r: float(r['approx_second']))

def read_indexes(workspace):
    grouped = {}
    for index in sorted(Path(workspace).glob('scan_*/index.csv')):
        with index.open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                source = Path(row['source'])
                if source.is_file():
                    grouped.setdefault(str(source.resolve()), {})[float(row['approx_second'])] = row
    return {k:list(v.values()) for k,v in grouped.items()}

def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        found = shutil.which('ffmpeg')
        if found:
            return found
        raise RuntimeError('Run with the Python environment used by the CMZ scout app.')

def make_clip(ffmpeg, source, start, duration, dest, log):
    # Accurate output seeking with short preroll for CCTV HEVC recordings.
    pre = max(0, start-5)
    cmd = [ffmpeg,'-hide_banner','-loglevel','warning','-nostdin','-n',
           '-ss',str(pre),'-i',str(source),'-ss',str(start-pre),'-t',str(duration),
           '-an','-vf','fps=8,scale=640:-2','-c:v','libx264','-preset','fast',
           '-crf','28','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)]
    subprocess.run(cmd, check=True, stdout=log, stderr=log, timeout=180)
    if not dest.is_file() or dest.stat().st_size < 1000:
        raise RuntimeError('No usable clip was produced: '+dest.name)

def make_strip(ffmpeg, clip, folder, log):
    from PIL import Image, ImageDraw
    folder.mkdir()
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','warning','-nostdin','-n',
                    '-i',str(clip),'-vf','fps=1,scale=320:-2','-frames:v','10',
                    str(folder/'frame_%02d.jpg')], check=True, stdout=log, stderr=log, timeout=60)
    frames=sorted(folder.glob('frame_*.jpg'))
    if not frames:
        raise RuntimeError('No preview frames: '+clip.name)
    with Image.open(frames[0]) as first:
        height=first.height
    sheet=Image.new('RGB',(320*5,(height+24)*2),'#202020')
    draw=ImageDraw.Draw(sheet)
    for i,p in enumerate(frames[:10]):
        with Image.open(p) as im:
            x=(i%5)*320;y=(i//5)*(height+24)
            sheet.paste(im,(x,y));draw.text((x+4,y+height+4),f'~+{i}s',fill='white')
    sheet.save(folder.parent/(folder.name+'.jpg'),quality=82)

def write_html(out, records):
    cards=[]
    for r in records:
        label=html.escape(f"{r['id']} | {r['source']} | {r['start_second']:.1f}-{r['end_second']:.1f}s | {r['selection']}")
        cards.append(f'<article><h3>{label}</h3><video controls preload="none" src="{r["clip"]}"></video>'
                     f'<p><select data-id="{r["id"]}"><option value="">Not reviewed</option>'
                     '<option>Walking</option><option>Feeding</option><option>Resting</option>'
                     '<option>Sleeping</option><option>Other</option><option>Unknown</option>'
                     '<option>No visible animal</option><option>Mixed / transition</option></select></p></article>')
    # Labels are manual observations, kept separate from model predictions.
    page='''<!doctype html><meta charset="utf-8"><title>CMZ short clip review</title>
<style>body{font:17px system-ui;background:#111;color:#eee;max-width:1000px;margin:30px auto;padding:16px}video{width:100%;max-width:640px}article{border-top:1px solid #555;padding:18px 0}select,button{font:inherit;padding:10px}h3{font-size:16px}</style>
<h1>CMZ short clip review</h1><p>These are selected samples, not a full recording activity budget. Motion is not an animal or behavior label. Low-motion and uniform samples are included. Watch each clip before labeling. Do not infer sleeping from stillness or feeding from proximity to a bowl. Use Unknown or Mixed when necessary.</p>
<p>Labels below are human observations, not predictions. Download labels before closing this page; reload does not retain selections. A blank label means not reviewed.</p>
<button id="save">Download human observations JSON</button>'''+''.join(cards)+'''
<script>const records=RECORDS;document.getElementById('save').onclick=()=>{const labels=Array.from(document.querySelectorAll('select')).filter(s=>s.value).map(s=>({...records.find(r=>r.id===s.dataset.id),behavior:s.value,label_source:'human_review'}));const u=URL.createObjectURL(new Blob([JSON.stringify({scope:'selected_clips_only',observations:labels},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='CMZ_HUMAN_OBSERVATIONS.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};</script>'''.replace('RECORDS',json.dumps(records).replace('<','\\u003c'))
    (out/'OPEN_REVIEW.html').write_text(page,encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,default=ROOT/'workspace')
    parser.add_argument('--per-method',type=int,default=8)
    args=parser.parse_args()
    if not 1<=args.per_method<=24:
        parser.error('--per-method must be between 1 and 24')
    groups=read_indexes(args.workspace)
    if not groups:
        raise RuntimeError('No readable source videos found through workspace/scan_*/index.csv. Keep videos at their original locations and workspace beside this script.')
    ffmpeg=ffmpeg_exe()
    out=args.workspace/('behavior_review_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    out.mkdir(parents=True);(out/'clips').mkdir();(out/'previews').mkdir()
    records=[];failures=[];coverage=[]
    for source,rows in groups.items():
        sampled_end=max(float(r['approx_second']) for r in rows)+0.5
        coverage.append(dict(source=Path(source).name,indexed_frames=len(rows),scanned_through_second=sampled_end))
        chosen=select_samples(rows,args.per_method)
        print(f'{Path(source).name}: {len(chosen)} short clips',flush=True)
        for row in chosen:
            center=float(row['approx_second']);start=max(0,min(center-5,sampled_end-10));duration=min(10,sampled_end-start)
            ident=hashlib.sha256((source+':'+str(center)).encode()).hexdigest()[:12]
            clip=out/'clips'/(ident+'.mp4')
            try:
                with (out/'decoder.log').open('a',encoding='utf-8') as log:
                    make_clip(ffmpeg,source,start,duration,clip,log)
                    make_strip(ffmpeg,clip,out/'previews'/ident,log)
                records.append(dict(id=ident,source=Path(source).name,start_second=start,
                                    end_second=start+duration,selection=row['selection'],
                                    clip='clips/'+clip.name,preview='previews/'+ident+'.jpg',
                                    behavior=None,label_source=None))
                print(f'  {len(records)} ready: {center:.1f}s',flush=True)
            except (OSError,subprocess.SubprocessError,RuntimeError) as e:
                failures.append(dict(source=Path(source).name,center_second=center,error=type(e).__name__))
                print('  Could not extract this sample; see local decoder.log.',flush=True)
    report=dict(status='complete' if not failures else 'partial',scope='selected_clips_only',
                coverage=coverage,samples=records,failures=failures,
                limitations=['Only previously indexed sources are included, not every video on disk.',
                             'Motion selection can miss animals and behavior; uniform samples are not a guarantee of complete coverage.',
                             'No animal boxes or behavior labels are automatically assigned.',
                             'Do not estimate whole-night behavior percentages from these selected samples.'])
    (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    write_html(out,records)
    archive=out.with_suffix('.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for p in out.rglob('*'):
            # Keep diagnostic logs local; they may contain full local paths.
            if p.is_file() and p.name!='decoder.log' and not (p.name.startswith('frame_') and p.suffix=='.jpg'):
                z.write(p,str(p.relative_to(out)))
    print('\nREVIEW ZIP: '+str(archive.resolve()))
    print('Send this ZIP for review. No original videos or previous annotations were changed.')
    if not records:
        raise RuntimeError('No clips succeeded. Check decoder.log in the new output folder.')

if __name__=='__main__':
    try:
        main()
    except Exception as e:
        print('Stopped: '+str(e));sys.exit(1)
