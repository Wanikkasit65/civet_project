import unittest,tempfile,json
from pathlib import Path
from datetime import datetime,timedelta
import numpy as np
from PIL import Image
import scout as s

class ScoutTests(unittest.TestCase):
 def test_group_shared_across_cameras(self):
  self.assertEqual(s.split_for('A01_20260405010000.mp4',30),s.split_for('A03_20260405010020.mp4',10))
  self.assertEqual(s.split_for('A01_20260405010000.mp4',1),(None,None))
 def test_invalid_names_refused(self):
  with self.assertRaises(ValueError):s.split_for('renamed.mp4',0)
 def test_labels_and_positive_box_validation(self):
  with tempfile.TemporaryDirectory() as td:
   row=dict(id='x',name='A01_20260405010000.mp4',source='x.mp4',approx_second=30)
   with self.assertRaises(ValueError):s.save(td,row,'civet',[.9,0,.1,1],'Test','')
   s.save(td,row,'uncertain',[0,0,1,1],'Test','occluded')
   self.assertEqual(s.labels(td)['x']['kind'],'uncertain')
   with self.assertRaises(ValueError):s.build(td)
 def test_yolo_export_and_no_unreviewed_backgrounds(self):
  with tempfile.TemporaryDirectory() as td:
   run=Path(td);(run/'full').mkdir();data={};groups={k:[] for k in ['train','val','test']}
   for i in range(100):
    t=datetime(2026,4,5)+timedelta(minutes=30*i,seconds=30)
    name='A01_'+t.strftime('%Y%m%d%H%M%S')+'.mp4';split,g=s.split_for(name,0);groups[split].append(name)
   n=0
   for split,names in groups.items():
    for j in range(30 if split=='train' else 20):
     ident=str(n);source=names[j%2];kind='civet' if j<(25 if split=='train' else 15) else 'empty'
     row=dict(id=ident,name=source,source='not-needed.mp4',approx_second=float(j*2),kind=kind,box=[.1,.2,.6,.8] if kind=='civet' else None,reviewer='SYNTHETIC_TEST',note='test only')
     data[ident]=row;f=np.zeros((40,50,3),np.uint8);f[:,:,0]=n*3;Image.fromarray(f).save(run/'full'/(ident+'.jpg'));n+=1
   (run/'annotations.json').write_text(json.dumps(data))
   # Extra unreviewed frame is never assumed to be a negative.
   Image.new('RGB',(50,40)).save(run/'full'/'unreviewed.jpg')
   out=s.build(run);audit=json.loads((out/'audit.json').read_text());self.assertEqual(len(audit),len(data))
   first=next(a for a in audit if a['kind']=='civet');nums=(out/'labels'/first['split']/(first['id']+'.txt')).read_text().split()
   self.assertAlmostEqual(float(nums[1]),.35);self.assertAlmostEqual(float(nums[4]),.6)
   seen={}
   for a in audit:
    seen.setdefault(a['group'],set()).add(a['split'])
   self.assertTrue(all(len(v)==1 for v in seen.values()))
if __name__=='__main__':unittest.main()
