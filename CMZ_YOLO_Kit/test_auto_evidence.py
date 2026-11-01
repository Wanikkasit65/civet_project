import unittest
from auto_evidence import summarize_track

def track(xs,ts=None):
    ts=ts if ts is not None else [i*.5 for i in range(len(xs))]
    return [dict(animal_count=1,person_present=False,clip_second=t,
                 center_x=x,center_y=.4,box_width=.2,box_height=.1)
            for t,x in zip(ts,xs)]

class EvidenceTests(unittest.TestCase):
    def test_missing_animal_never_means_rest(self):
        self.assertEqual(summarize_track([],8)['motion_proxy'],'Unknown')
    def test_short_still_clip_cannot_establish_rest(self):
        self.assertEqual(summarize_track(track([.5]*4),2)['motion_proxy'],'Unknown')
    def test_visible_stationary_is_only_a_proxy(self):
        self.assertEqual(summarize_track(track([.5]*15),8)['motion_proxy'],'Stationary proposal')
    def test_reappearance_does_not_prove_walking(self):
        self.assertEqual(summarize_track(track([.2,.8],[0,7]),8)['motion_proxy'],'Unknown')
    def test_displacement_and_speed_required(self):
        self.assertEqual(summarize_track(track([.2,.25,.3,.35]),2)['motion_proxy'],'Moving proposal')
    def test_person_blocks_reliable_track(self):
        a=track([.2,.4,.6]);a[1]['person_present']=True
        self.assertEqual(summarize_track(a,2)['motion_proxy'],'Unknown')

if __name__=='__main__':unittest.main()
