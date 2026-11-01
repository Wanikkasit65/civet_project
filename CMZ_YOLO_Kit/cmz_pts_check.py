"""Read-only timestamp/label evidence collection. No training or originals changed."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import json
import re
import shutil
import subprocess
import sys
import uuid
import zipfile


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        exe = shutil.which('ffmpeg')
        if not exe:
            raise RuntimeError('imageio-ffmpeg is required in this environment.')
        return exe


def call(args, timeout=180):
    p = subprocess.run([ffmpeg_exe(), '-hide_banner', '-nostdin', *args],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stderr.decode('utf-8', errors='replace')


def probe(path):
    code, log = call(['-i', str(path), '-map', '0:v:0', '-frames:v', '1',
                      '-an', '-f', 'null', '-'])
    match = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', log)
    duration = sum(float(x)*k for x,k in zip(match.groups(),(3600,60,1))) if match else None
    return dict(returncode=code, duration_seconds=duration, log=log)


def preview(path, start, duration, target):
    # Input -ss seeks relative to the demuxer's start time (not frame count/FPS).
    # Explicitly no -copyts / -seek_timestamp. fps uses presentation timestamps.
    code, log = call(['-ss', str(start), '-i', str(path), '-t', str(duration),
        '-map', '0:v:0', '-an', '-vf', 'fps=4,scale=640:-2',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '25', '-pix_fmt', 'yuv420p',
        '-n', str(target)], timeout=300)
    okay = code == 0 and target.exists() and target.stat().st_size > 1000
    return dict(okay=okay, returncode=code, log=log)


def run(run_folder):
    import phase2_core as core
    run_folder = Path(run_folder).resolve()
    config = json.loads((run_folder/'config.json').read_text(encoding='utf-8-sig'))
    workspace = Path(config['workspace'])
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
    out = workspace/'timing_checks'/('check_'+stamp)
    out.mkdir(parents=True, exist_ok=False)
    report = dict(scope='Timestamp and previously confirmed clip audit, not new labels or model accuracy.',
                  original_run=str(run_folder), originals_modified=False,
                  source_probes=[], previews=[], errors=[])
    files = list(csv.DictReader((run_folder/'VIDEO_INVENTORY.csv').open(encoding='utf-8-sig')))
    byname = {}
    for f in files:
        byname.setdefault(f['name'], []).append(f)
    def add(path, start, seconds, name, **extra):
        print('Extracting',name,flush=True)
        item = dict(file=name+'.mp4', requested_start_second=start, requested_duration=seconds, **extra)
        try:
            result = preview(path,start,seconds,out/item['file'])
            (out/(name+'.log')).write_text(result.pop('log'),encoding='utf-8')
            item.update(result)
        except Exception as e:
            item.update(okay=False,error=str(e));report['errors'].append(str(e))
        report['previews'].append(item)
    # Four presentation-time checks of the file whose displayed clock drifted.
    first = byname.get('A01_20260405000000.mp4',[])
    if len(first)==1:
        f = first[0];p = probe(f['path'])
        (out/'A01_original_probe.log').write_text(p.pop('log'),encoding='utf-8')
        report['source_probes'].append(dict(source=f['name'],opencv_inventory_seconds=f['seconds'],**p))
        for t in (0.,1114.,2216.,4430.):
            add(f['path'],t,1.5,'A01_pts_'+str(int(t)),source=f['name'],timing_method='FFmpeg presentation timestamps')
    else: report['errors'].append('Cannot uniquely locate the original A01 midnight video.')
    rows = core.read_records(workspace)
    catalog = core.sample_catalog(workspace)
    # Preserve reviewed clip content: source offsets from the old decoder are not corrected by guessing.
    for i,row in enumerate(rows):
        if row['behavior'] not in core.ACTIVITY:continue
        try:
            sample=core.resolve_sample(catalog,row)
            offset=row['start_second']-float(sample['start_second'])
            duration=row['end_second']-row['start_second']
            add(sample['local_clip'],offset,duration,'label_%02d_%s'%(i,row['behavior']),
                annotation=row,parent_sample_start=sample['start_second'],parent_sample_end=sample['end_second'],
                timing_method='FFmpeg within existing human-reviewed clip; original source offset remains unverified')
        except Exception as e: report['errors'].append('Label '+str(i)+': '+str(e))
    # Compare prior source offsets using the new reader. These are development checks only.
    walking=byname.get('A03_20260405000000.mp4',[])
    if len(walking)==1:
        for t in (5632.5,5806.5,12558.5):
            add(walking[0]['path'],t,10.,'prior_walking_pts_'+str(t).replace('.','_'),
                source=walking[0]['name'],expected_from_previous_chat='Walking',
                caution='Prior offsets used a different decoder; verify content before treating this as a reference.')
    (out/'CHECK_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=out/'CMZ_TIMING_CHECK.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.iterdir()):
            if p.suffix in ('.json','.log','.mp4'):z.write(p,p.name)
    print('\nDONE. Send this ZIP to ChatGPT:\n'+str(archive),flush=True)
    return archive


if __name__=='__main__':
    default=Path(__file__).resolve().parent/'workspace'/'all_video_runs'/'full_20261101_153841_fd2014'
    run(sys.argv[1] if len(sys.argv)>1 else default)
