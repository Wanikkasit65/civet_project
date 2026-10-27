import subprocess,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
 if not (3,10)<=sys.version_info[:2]<(3,14):
  print('Please install Python 3.12 64-bit alongside your existing Python.');return
 train='train' in sys.argv
 py=None
 # Read-only reuse of the original environment if all scout dependencies import.
 if not train:
  candidates=[ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')]
  for base in [ROOT.parent,ROOT.parent.parent]:
   candidates += list(base.glob('CMZ_Phase2_Kit*/CMZ_Phase2_Kit/.venv/Scripts/python.exe'))
   candidates += list(base.glob('CMZ_Phase2_Kit/.venv/Scripts/python.exe'))
  for c in candidates:
   if c.is_file() and subprocess.run([str(c),'-c','import streamlit, numpy, cv2, PIL, imageio_ffmpeg, pandas'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
    py=c;break
 if py is None:
  env=ROOT/('.yolo_venv' if train else '.venv');py=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
  if not py.exists():subprocess.check_call([sys.executable,'-m','venv',str(env)])
  marker=env/'cmz_ready'
  if not marker.exists():
   req=ROOT/('requirements_yolo.txt' if train else 'requirements.txt')
   subprocess.check_call([str(py),'-m','pip','install','-r',str(req)]);marker.write_text('ready')
 if train:
  subprocess.call([str(py),str(ROOT/'train_yolo.py')],cwd=ROOT)
 else:
  subprocess.call([str(py),'-m','streamlit','run',str(ROOT/'app.py'),'--server.address=127.0.0.1','--server.port=8502','--browser.gatherUsageStats=false'],cwd=ROOT)
if __name__=='__main__':
 try:main()
 except Exception as e:print('Stopped:',e);print('Copy this message to ChatGPT for help.')
