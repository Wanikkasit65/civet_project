"""Export consecutive short copies around the observed food-placement event."""
import argparse, json, sys, uuid, zipfile
from pathlib import Path
from datetime import datetime
from auto_review import ROOT, read_indexes, ffmpeg_exe, make_clip, make_strip, write_html

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,default=ROOT/'workspace')
    p.add_argument('--source-name',default='A03_20260405140327.mp4')
    p.add_argument('--start',type=float,default=5380)
    p.add_argument('--end',type=float,default=6580)
    a=p.parse_args()
    if not 0<=a.start<a.end or a.end-a.start>3600:
        p.error('Use a positive interval no longer than one hour.')
    sources=read_indexes(a.workspace)
    matches=[(s,rows) for s,rows in sources.items() if Path(s).name==a.source_name]
    if not matches:
        raise RuntimeError('Source video not found through scan indexes. Keep original videos in place.')
    source,rows=max(matches,key=lambda pair:len(pair[1]))
    indexed_end=max(float(r['approx_second']) for r in rows)+.5
    if a.end>indexed_end:
        raise RuntimeError('Requested interval extends beyond the indexed recording.')
    out=a.workspace/('meal_review_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    out.mkdir(parents=True);(out/'clips').mkdir();(out/'previews').mkdir()
    ffmpeg=ffmpeg_exe();records=[];failures=[];start=a.start
    while start<a.end:
        end=min(start+10,a.end);ident=f'meal_{len(records)+len(failures):04d}'
        clip=out/'clips'/(ident+'.mp4')
        try:
            with (out/'decoder.log').open('a',encoding='utf-8') as log:
                make_clip(ffmpeg,source,start,end-start,clip,log)
                make_strip(ffmpeg,clip,out/'previews'/ident,log)
            records.append(dict(id=ident,source=Path(source).name,start_second=start,
                                end_second=end,selection='targeted_food_event',clip='clips/'+clip.name,
                                preview='previews/'+ident+'.jpg',behavior=None,label_source=None))
            print(f'{len(records)} ready: {start:.1f}-{end:.1f}s',flush=True)
        except Exception as e:
            failures.append(dict(start_second=start,end_second=end,error=type(e).__name__))
            print('A sample failed; see local decoder.log.',flush=True)
        start=end
    report=dict(status='complete' if not failures else 'partial',scope='targeted_food_event_only',
                source=Path(source).name,start_second=a.start,end_second=a.end,
                samples=records,failures=failures,
                limitations=['A food-placement event is not proof of feeding.',
                             'Behavior labels remain unassigned until reviewed.',
                             'Consecutive clips share the same event: keep them in the same dataset split.',
                             'Do not infer whole-night behavior percentages from this targeted interval.'])
    (out/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    write_html(out,records)
    archive=out.with_suffix('.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for f in out.rglob('*'):
            if f.is_file() and f.name!='decoder.log' and not f.name.startswith('frame_'):
                z.write(f,str(f.relative_to(out)))
    print('\nREVIEW ZIP: '+str(archive.resolve()))
    print('Original videos, scan results and previous annotations were not changed.')
    if not records:
        raise RuntimeError('No clips succeeded. Check the local decoder.log.')

if __name__=='__main__':
    try:
        main()
    except Exception as e:
        print('Stopped: '+str(e));sys.exit(1)
