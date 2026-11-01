from pathlib import Path
import os, subprocess, sys

def main():
    root=Path(__file__).resolve().parent
    if not (3,10)<=sys.version_info[:2]<(3,14):
        raise ValueError('Use Python 3.10–3.13; recommended 3.12.')
    if os.name=='nt' and len(str(root))>70:
        raise ValueError('Use a short folder such as E:\\CMZ to avoid Windows path-length installation errors.')
    env=root/'.phase2_venv';py=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not py.exists():subprocess.check_call([sys.executable,'-m','venv',str(env)])
    marker=env/'phase2_ready_v1'
    if not marker.exists():
        subprocess.check_call([str(py),'-m','pip','install','-r',str(root/'requirements_phase2.txt')])
        marker.write_text('ready')
    subprocess.check_call([str(py),'-m','streamlit','run',str(root/'phase2_app.py'),'--server.address=127.0.0.1','--server.port=8503','--browser.gatherUsageStats=false'],cwd=root)

if __name__=='__main__':
    try:main()
    except Exception as e:print('Stopped:',e);sys.exit(1)
