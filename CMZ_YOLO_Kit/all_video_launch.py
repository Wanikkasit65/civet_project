"""Separate environment: does not change the user's existing Phase 2 setup."""
from pathlib import Path
import os,re,subprocess,sys

def main():
    root=Path(__file__).resolve().parent
    if sys.version_info[:2]!=(3,12):raise ValueError('Use the existing Python 3.12 installation for this kit.')
    if os.name=='nt' and len(str(root))>55:raise ValueError(r'Extract this NEW kit to E:\CMZ_ALL, to avoid Windows path-length errors. Keep the OLD project and workspace where they are.')
    env=root/'.allvideo_venv';py=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not py.exists():subprocess.check_call([sys.executable,'-m','venv',str(env)])
    marker=env/'all_video_ready_v1'
    if not marker.exists():
        subprocess.check_call([str(py),'-m','pip','install','--upgrade','pip'])
        wheel='cpu';diagnostic='nvidia-smi unavailable'
        try:
            result=subprocess.run(['nvidia-smi'],capture_output=True,text=True,timeout=20);diagnostic=result.stdout+'\n'+result.stderr
            m=re.search(r'CUDA Version:\s*(\d+)\.(\d+)',diagnostic)
            if m:
                version=tuple(map(int,m.groups()))
                wheel='cu126' if version>=(12,6) else ('cu124' if version>=(12,4) else ('cu118' if version>=(11,8) else 'cpu'))
        except (OSError,subprocess.SubprocessError):pass
        (root/'ALL_VIDEO_GPU_INFO.txt').write_text(diagnostic,encoding='utf-8')
        print('Installing a separate PyTorch environment. Wheel:',wheel,flush=True)
        subprocess.check_call([str(py),'-m','pip','install','torch==2.6.0','torchvision==0.21.0','--index-url','https://download.pytorch.org/whl/'+wheel])
        subprocess.check_call([str(py),'-m','pip','install','-r',str(root/'requirements_all_video.txt')])
        subprocess.check_call([str(py),'-c','import torch,cv2,sklearn; from megadetector.detection import run_detector; print("CUDA available:",torch.cuda.is_available())'])
        marker.write_text('ready',encoding='utf-8')
    subprocess.check_call([str(py),'-m','streamlit','run',str(root/'all_video_app.py'),'--server.address=127.0.0.1','--server.port=8504','--browser.gatherUsageStats=false'],cwd=root)

if __name__=='__main__':
    try:main()
    except Exception as e:print('Stopped:',e);sys.exit(1)
