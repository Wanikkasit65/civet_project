"""Recompute historical exported totals without running a model or video."""
from pathlib import Path
from collections import Counter
import csv,json,argparse
import cmz_fast_sample as fast

def verify(folder):
    def read(name):return list(csv.DictReader((folder/name).open(encoding='utf-8-sig')))
    rows=read('SAMPLED_WINDOWS.csv'); stored=read('FUSED_SAMPLED_TIMES.csv')
    for r in rows:r['statistical_sample']=r['statistical_sample']=='True'
    fused=fast.fused_samples(rows)
    assert len(fused)==len(stored),'Fused count mismatch'
    for a,b in zip(fused,stored):
        for key in ['nominal_time','available_cameras','behavior_proposal','activity_proposal']:
            assert a[key]==b[key],(key,a,b)
        assert a['conditional_possible_shelter']==(b['conditional_possible_shelter']=='True')
    per_video=read('PER_VIDEO_SAMPLING_TABLE.csv'); hourly=read('HOURLY_SAMPLED_TIME_TABLE.csv')
    for r in per_video:
        rr=[x for x in rows if x['source']==r['source'] and x['statistical_sample']]
        assert len(rr)==int(r['random_sample_points'])
        counts=Counter(x['behavior'] for x in rr)
        for key,label in [('walking_points','Walking'),('feeding_points','Feeding'),('unknown_points','Unknown')]:
            assert int(r[key])==counts[label]
    for r in hourly:
        rr=[x for x in fused if x['nominal_time'][:13]==r['hour']]
        assert len(rr)==int(r['sampled_time_points'])
        counts=Counter(x['behavior_proposal'] for x in rr)
        for key,label in [('walking_points','Walking'),('feeding_points','Feeding'),('unknown_points','Unknown')]:
            assert int(r[key])==counts[label]
    scope=json.loads((folder/'RESULT_SCOPE.json').read_text())
    assert len(rows)==scope['windows_processed']
    assert len(set(r['source'] for r in rows))==scope['videos_inspected']
    assert sum(float(r['end'])-float(r['start']) for r in rows)==scope['sampled_camera_seconds']
    result=dict(status='passed',camera_windows=len(rows),unique_videos=len(per_video),
                fused_times=len(fused),hourly_bins=len(hourly),
                fused_counts=dict(Counter(r['behavior_proposal'] for r in fused)),
                possible_shelter_points=sum(r['conditional_possible_shelter'] for r in fused),
                scope='Data integrity and arithmetic checks, not behavior accuracy')
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);ap.add_argument('--output',type=Path)
    a=ap.parse_args();result=verify(a.folder);s=json.dumps(result,indent=2)
    if a.output:a.output.write_text(s)
    print(s)
