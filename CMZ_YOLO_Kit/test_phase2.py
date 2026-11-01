import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import phase2_core as c

def row(source='A03_20260405140327.mp4',start=5720,end=5730,label='Feeding',**kw):
    return dict(source=source,start_second=start,end_second=end,behavior=label,
                label_source='human_review',human_confirmed=True,**kw)

class Phase2Tests(unittest.TestCase):
    def test_unknown_never_becomes_inactive(self):
        for label in ['Unknown','Not visible','Other','Mixed']:
            detail,_=c.tables([c.normalize(row(label=label))])
            self.assertEqual(detail[0]['activity'],'Unknown')

    def test_unobserved_class_is_blank_not_zero_and_overlap_is_merged(self):
        records=[c.normalize(row()),c.normalize(row(start=5725,end=5735))]
        _,summary=c.tables(records)
        self.assertEqual(next(r for r in summary if r['behavior']=='Feeding')['confirmed_seconds'],15)
        self.assertIsNone(next(r for r in summary if r['behavior']=='Sleeping')['confirmed_seconds'])

    def test_conflicting_intervals_do_not_mutate_history(self):
        with tempfile.TemporaryDirectory() as d:
            c.save_records(d,[row()]);before=list((Path(d)/'phase2'/'annotations').glob('*.json'))
            with self.assertRaises(ValueError):c.save_records(d,[row(start=5725,end=5735,label='Walking')])
            self.assertEqual(before,list((Path(d)/'phase2'/'annotations').glob('*.json')))
            self.assertEqual(len(c.read_records(d)),1)

    def test_import_requires_actual_human_confirmation(self):
        for extra in [dict(human_confirmed=False),dict(label_source='assistant_visual_review')]:
            with self.assertRaises(ValueError):c.normalize(dict(row(),**extra))
        with self.assertRaises(ValueError):c.normalize(row(roi=[.5,.5,.4,.9]))

    def test_same_recording_clock_cross_camera_cannot_split(self):
        records=[row(source='A01_20260405000000.mp4',start=120,end=130),
                 row(source='A04_20260405000100.mp4',start=60,end=70)]
        self.assertEqual(len(set(c.grouped_ids(records))),1)

    def test_event_union_covers_other_clock_blocks_and_cameras(self):
        records=[row(source='A01_20260405000000.mp4',start=100,end=110,event_group='one-event'),
                 row(source='A01_20260405000000.mp4',start=1900,end=1910,event_group='one-event'),
                 row(source='A02_20260405000000.mp4',start=1920,end=1930)]
        self.assertEqual(len(set(c.grouped_ids(records))),1)

    def test_crossing_boundary_joins_both_blocks(self):
        records=[row(source='A01_20260405000000.mp4',start=1798,end=1802),
                 row(source='A02_20260405000000.mp4',start=1805,end=1810)]
        self.assertEqual(len(set(c.grouped_ids(records))),1)

    def test_missing_test_evidence_has_no_manufactured_scores(self):
        import numpy as np
        records=[c.normalize(row(start=5720+i*20,end=5730+i*20,label='Feeding' if i<3 else 'Walking',roi=[.1,.1,.9,.9],event_group='single-event')) for i in range(6)]
        catalog={c.key(r):dict(r,local_clip='synthetic') for r in records}
        with tempfile.TemporaryDirectory() as d,patch.object(c,'sample_catalog',return_value=catalog),patch.object(c,'motion_features',side_effect=lambda *a,**k:np.arange(18,dtype=float)):
            c.save_records(d,records)
            folder,report=c.train_pilot(d,records,clocks_verified=True)
            self.assertTrue((folder/'behavior_pilot.joblib').is_file())
            self.assertTrue(report['trained']);self.assertIsNone(report['evaluation'])
            self.assertFalse(report['automatic_activity_status_enabled'])
            proposal=c.propose(d,folder/'behavior_pilot.joblib',dict(records[0],local_clip='synthetic'),[.1,.1,.9,.9])
            self.assertEqual(proposal['activity'],'Unknown');self.assertFalse(proposal['human_confirmed'])
            c.correct_interval(d,records[0],records[0]['start_second']+1,records[0]['end_second']-1)
            with self.assertRaisesRegex(ValueError,'predates'):
                c.propose(d,folder/'behavior_pilot.joblib',dict(records[0],local_clip='synthetic'),[.1,.1,.9,.9])

    def test_corrected_interval_replaces_count_without_editing_original(self):
        with tempfile.TemporaryDirectory() as d:
            original=c.normalize(row(start=5981.5,end=5991.5,label='Walking'))
            saved=c.save_records(d,[original]);before=saved.read_bytes()
            c.correct_interval(d,original,5985.5,5987.5)
            current=c.read_records(d);self.assertEqual(len(current),1)
            self.assertEqual(current[0]['end_second']-current[0]['start_second'],2)
            self.assertEqual(saved.read_bytes(),before)
            with self.assertRaises(ValueError):c.correct_interval(d,original,5985.5,5986.5)
            with self.assertRaises(ValueError):c.correct_interval(d,current[0],5980,5995)

    def test_report_scope_and_path_redaction(self):
        with tempfile.TemporaryDirectory() as d:
            p=c.write_report(d,[c.normalize(row())])
            doc=json.loads((p/'REPORT_SCOPE.json').read_text())
            self.assertFalse(doc['model_predictions']);self.assertIn('Sleeping',doc['missing_classes'])
            self.assertNotIn(d,(p/'confirmed_intervals.csv').read_text(encoding='utf-8-sig'))

    def test_independent_test_exposure_not_scored_twice(self):
        import numpy as np
        import hashlib
        blocks={}
        for hour in range(24):
            g=f'2026-04-05T{hour:02d}:00:00'
            v=int(hashlib.sha256(('cmz-phase2-v1:'+g).encode()).hexdigest()[:8],16)%10
            blocks.setdefault('test' if v<2 else 'train',hour)
        self.assertEqual(set(blocks),{'train','test'})
        records=[]
        for hour in blocks.values():
            for i in range(6):
                records.append(c.normalize(row(source=f'A01_20260405{hour:02d}0000.mp4',start=100+i*20,end=110+i*20,
                    label='Feeding' if i<3 else 'Walking',roi=[.1,.1,.9,.9])))
        catalog={c.key(r):dict(r,local_clip='synthetic') for r in records}
        with tempfile.TemporaryDirectory() as d,patch.object(c,'sample_catalog',return_value=catalog),patch.object(c,'motion_features',return_value=np.arange(18,dtype=float)):
            _,first=c.train_pilot(d,records,True)
            self.assertIsNotNone(first['evaluation'])
            self.assertFalse(set(first['training_groups']) & set(first['evaluation']['test_groups']))
            _,second=c.train_pilot(d,records,True)
            self.assertIsNone(second['evaluation'])
            self.assertIn('previously',second['evaluation_limitation'])

if __name__=='__main__':unittest.main()
