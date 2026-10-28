import tempfile,unittest,json,csv,shutil
from pathlib import Path
from datetime import datetime,timedelta
from unittest.mock import patch
import cv2,numpy as np
import all_video as a

def video(path,seconds=4.5):
    out=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),16,(128,96))
    if not out.isOpened():raise RuntimeError('Test codec unavailable')
    for i in range(int(seconds*16)):
        frame=np.zeros((96,128,3),np.uint8);cv2.rectangle(frame,(10+i%30,25),(35+i%30,55),(200,200,200),-1);out.write(frame)
    out.release()

class BatchTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_recursive_discovery_and_content_deduplication(self):
        child=self.root/'nested';child.mkdir();p=self.root/'A01_20260405000000.mp4';video(p);shutil.copyfile(p,child/p.name)
        db=a.database(self.root);a.inventory(db,[self.root,child])
        self.assertEqual(db.execute('SELECT COUNT(*) FROM files').fetchone()[0],1)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM copies').fetchone()[0],2);db.close()
    def test_windows_account_for_tail_and_resume(self):
        p=self.root/'video.mp4';video(p)
        windows=list(a.sampled_windows(p,end=4.5))
        self.assertEqual([(r[0],r[1]) for r in windows],[(0.,2.),(2.,4.),(4.,4.5)])
        resumed=list(a.sampled_windows(p,start=2.,end=4.5));self.assertEqual(resumed[0][:2],(2.,4.))
        self.assertEqual(len(a.features(windows[0][2],[0,0,1,1])),18)
    def test_absence_is_unknown_not_inactive(self):
        frames=[np.zeros((96,128,3),np.uint8)]*8
        roi,score,status=a.animal_crop(frames,lambda f:[])
        self.assertIsNone(roi);self.assertEqual(status,'animal_not_reliably_detected')
    def test_person_and_multiple_animals_are_rejected(self):
        frames=[np.zeros((96,128,3),np.uint8)]*8
        animal={'category':'1','conf':.9,'bbox':[.2,.2,.3,.4]}
        self.assertEqual(a.animal_crop(frames,lambda f:[animal,{'category':'2','conf':.8}])[2],'person_present')
        self.assertEqual(a.animal_crop(frames,lambda f:[animal,animal])[2],'multiple_animal_proposals')
        self.assertIsNotNone(a.animal_crop(frames,lambda f:[animal])[0])
    def test_fusion_does_not_multiply_animal_time(self):
        t=datetime(2026,4,5)
        result=list(a.fused_intervals([(t,t+timedelta(seconds=10),'Walking'),(t,t+timedelta(seconds=10),'Walking')]))
        self.assertEqual(sum((b-x).total_seconds() for x,b,label in result),10)
    def test_conflicting_views_become_unknown(self):
        t=datetime(2026,4,5)
        result=list(a.fused_intervals([(t,t+timedelta(seconds=10),'Walking'),(t+timedelta(seconds=5),t+timedelta(seconds=10),'Feeding')]))
        self.assertEqual([(int((b-x).total_seconds()),label) for x,b,label in result],[(5,'Walking'),(5,'Unknown')])
    def test_hour_boundaries_are_split_by_duration(self):
        result=list(a.hour_parts(datetime(2026,4,5,0,59,59),datetime(2026,4,5,1,0,1)))
        self.assertEqual([x[1] for x in result],[1,1])
    def test_export_preserves_unavailable_classes_and_errors(self):
        db=a.database(self.root)
        db.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?,?,?,?)',('id','fake','A03_20260405000000.mp4','A03','2026-04-05T00:00:00',4,30,10,'error','tail decode error'))
        db.execute('INSERT INTO windows VALUES(?,?,?,?,?,?,?,?)',('id',0,2,'Walking',.8,'unconfirmed_model_proposal',.9,'[]'))
        db.execute('INSERT INTO windows VALUES(?,?,?,?,?,?,?,?)',('id',2,4,'Unknown',None,'animal_not_reliably_detected',0,'null'));db.commit()
        config={'workspace':str(self.root),'clocks_verified':True}
        scope=a.export_results(self.root,db,config,{'supported_classes':['Walking','Feeding'],'unsupported_classes':['Resting','Sleeping']})
        self.assertEqual(scope['files_with_errors'],['A03_20260405000000.mp4'])
        with (self.root/'PER_VIDEO_MODEL_TABLE.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
        self.assertEqual(rows[0]['resting_proposal_seconds'],'');self.assertEqual(float(rows[0]['unknown_seconds']),2)
        self.assertEqual(float(rows[0]['window_seconds_accounted']),4);db.close()
        self.assertEqual(rows[0]['inactive_model_proposal_seconds'],'')
        self.assertEqual(float(rows[0]['active_model_proposal_seconds']),2)
    def test_unknown_camera_clocks_do_not_get_invented(self):
        self.assertEqual(a.clock_info('renamed.mp4'),('Unknown',None))
        self.assertEqual(a.clock_info('A03_20260405000000.mp4')[0],'A03')
    def test_full_worker_accounts_for_all_video_and_resume_is_idempotent(self):
        import phase2_core as c
        videos=self.root/'videos';videos.mkdir();workspace=self.root/'workspace';workspace.mkdir();folder=workspace/'run';folder.mkdir()
        p=videos/'A03_20260405140327.mp4';video(p,8)
        rows=[dict(source=p.name,start_second=i,end_second=i+2,behavior='Walking' if i<4 else 'Feeding',roi=[0,0,1,1],label_source='human_review',human_confirmed=True,id=str(i)) for i in (0,2,4,6)]
        c.save_records(workspace,rows)
        catalog={(p.name,0,8):dict(source=p.name,start_second=0,end_second=8,local_clip=str(p))}
        animal={'category':'1','conf':.9,'bbox':[.1,.1,.8,.8]}
        config=dict(workspace=str(workspace),video_roots=[str(videos)],clocks_verified=True,animal_threshold=.4,behavior_threshold=.5,cpu=True)
        (folder/'config.json').write_text(json.dumps(config))
        with patch.object(c,'sample_catalog',return_value=catalog),patch.object(a,'AnimalDetector',return_value=lambda f:[animal]),patch.object(a,'environment_info',return_value={'software_test_fixture':True}):
            a.run(folder);a.run(folder)
        db=a.database(folder)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],4)
        self.assertAlmostEqual(db.execute('SELECT SUM(end-start) FROM windows').fetchone()[0],8)
        self.assertEqual(json.loads(db.execute('SELECT data FROM progress').fetchone()[0])['status'],'complete');db.close()
        self.assertTrue((folder/'ALL_VIDEO_RESULTS.zip').exists())
    def test_crop_model_fitting_has_no_fake_accuracy(self):
        import phase2_core as c
        p=self.root/'A03_20260405000000.mp4';video(p,8)
        rows=[dict(source=p.name,start_second=i,end_second=i+2,behavior='Walking' if i<4 else 'Feeding',roi=[0,0,1,1],label_source='human_review',human_confirmed=True,id=str(i)) for i in (0,2,4,6)]
        c.save_records(self.root,rows)
        catalog={(p.name,0,8):dict(source=p.name,start_second=0,end_second=8,local_clip=str(p))}
        animal={'category':'1','conf':.9,'bbox':[.1,.1,.8,.8]}
        with patch.object(c,'sample_catalog',return_value=catalog):model,report=a.train_batch_model(self.root,self.root,lambda f:[animal],.4)
        self.assertIsNone(report['evaluation']);self.assertEqual(report['derived_training_segments'],4)
        self.assertEqual(set(model.classes_),{'Walking','Feeding'})

if __name__=='__main__':unittest.main()
