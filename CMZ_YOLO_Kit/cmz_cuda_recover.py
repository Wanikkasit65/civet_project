"""Fresh-process CUDA compatibility trial, then guarded resume of the PTS run.

Legacy cuDNN is a troubleshooting path, not a guaranteed fix or model validation.
No package, original video, annotation or trained model is replaced.
"""
import os
# These must be set before torch or MegaDetector imports.
os.environ['TORCH_CUDNN_V8_API_DISABLED'] = '1'
os.environ['CUDA_LAUNCH_BLOCKING'] = '1'

from pathlib import Path
from datetime import datetime, timezone
import json
import sys
import time
import uuid


class FatalDetectorError(BaseException):
    """Bypass the batch's per-video Exception handler: backend failure is global."""


def checked_detector_class(parent, torch_module):
    class CheckedDetector(parent):
        def __call__(self, frame):
            try:
                result = super().__call__(frame)
                # Detect asynchronous CUDA failures before another result is stored.
                torch_module.cuda.synchronize()
                return result
            except Exception as error:
                raise FatalDetectorError('Animal detector backend failed; batch stopped immediately: '+str(error)) from error
    return CheckedDetector


def mark_stopped(base, folder, error):
    db=base.database(folder)
    try:base.progress(db,status='error',phase='Global detector failure: stopped immediately, no other files attempted.',error=str(error))
    finally:db.close()


def main():
    root=Path(__file__).resolve().parent
    folder=(Path(sys.argv[1]) if len(sys.argv)>1 else
            root/'workspace'/'all_video_runs'/'full_pts_20261101_092658_1e0ad8').resolve()
    config=json.loads((folder/'config.json').read_text(encoding='utf-8-sig'))
    if config.get('pipeline_version')!='cmz-pts-full-enclosure-v1':
        raise SystemExit('Use only the PTS run; the historical wrong-time run cannot be resumed here.')
    # Refuse concurrent processing; do not touch pause markers, labels or weights.
    pid_file=folder/'worker_pid.json'
    if pid_file.exists():
        import psutil
        pid=json.loads(pid_file.read_text()).get('pid')
        if pid and psutil.pid_exists(pid):
            try:
                args=psutil.Process(pid).cmdline()
                if any('cmz_auto_pts.py' in a or 'cmz_cuda_recover.py' in a for a in args):
                    raise SystemExit('A PTS worker still runs. Pause it and wait for exit before recovery.')
            except psutil.NoSuchProcess:pass
    report_dir=folder/'cuda_checks'/('check_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    report_dir.mkdir(parents=True,exist_ok=False)
    report=dict(scope='CUDA compatibility/stability trial, not behavior accuracy.',mode='legacy_cudnn_v7',
                synchronous_cuda=True,benchmark=False,trial_inferences=200,completed=0,passed=False,
                warning='Passing a short stress test does not guarantee long-run GPU stability.')
    target=report_dir/'CUDA_CHECK.json'
    try:
        import cv2
        import torch
        import cmz_auto_pts as auto
        if not torch.cuda.is_available():raise RuntimeError('CUDA unavailable; CPU fallback was not started.')
        torch.backends.cudnn.benchmark=False
        torch.backends.cudnn.allow_tf32=False
        torch.backends.cuda.matmul.allow_tf32=False
        report.update(torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0))
        base=auto.setup_pipeline()
        checked=checked_detector_class(base.AnimalDetector,torch)
        detector=checked(False)
        images=[]
        # Actual 1280-wide original-video frames, plus all available preflight JPEGs.
        db=base.database(folder)
        try:
            for camera in ('A01','A02','A03','A04'):
                row=db.execute('SELECT * FROM files WHERE camera=? AND seconds IS NOT NULL ORDER BY clock LIMIT 1',(camera,)).fetchone()
                if row:
                    reader=base.sampled_windows(row['path'],start=0,end=2)
                    try:
                        a,b,frames=next(reader);images.append(frames[0])
                    finally:reader.close()
        finally:db.close()
        for p in sorted((folder/'preflight_samples').glob('*.jpg')):
            image=cv2.imread(str(p))
            if image is not None:images.append(image)
        if not images:raise RuntimeError('No local real frames available for the CUDA check.')
        began=time.monotonic()
        for i in range(200):
            detector(images[i%len(images)])
            report['completed']=i+1
            if (i+1)%20==0:print('GPU CHECK: %d/200'%(i+1),flush=True)
        report.update(passed=True,elapsed_seconds=time.monotonic()-began,distinct_images=len(images))
        target.write_text(json.dumps(report,indent=2),encoding='utf-8')
        (folder/('CUDA_RECOVERY_'+report_dir.name+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('GPU CHECK PASSED. Resuming the SAME PTS run with immediate backend-error stopping.',flush=True)
        # Reuse the checked detector; all timing, annotation and behavior logic stays identical.
        base.AnimalDetector=lambda cpu=False:detector
        auto.setup_pipeline=lambda:base
        sys.argv=[str(root/'cmz_auto_pts.py'),'--resume',str(folder)]
        auto.main()
    except (Exception,FatalDetectorError) as error:
        report['error']=str(error)
        target.write_text(json.dumps(report,indent=2),encoding='utf-8')
        try:
            if 'base' in locals():mark_stopped(base,folder,error)
        except Exception:pass
        print('STOPPED: '+str(error),flush=True)
        print('Send this report and the console text: '+str(target),flush=True)
        raise SystemExit(1)


if __name__=='__main__':main()
