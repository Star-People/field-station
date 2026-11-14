import json,tempfile,unittest
from pathlib import Path
from snapshot import capture_metadata
class CaptureTime(unittest.TestCase):
 def test_capture_clock_not_review_clock(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);eid='a'*32;folder=root/'notifications/outbox'/eid;folder.mkdir(parents=True);(folder/'event.json').write_text(json.dumps(dict(generation='g',detected_epoch=1000,pts_seconds=10)))
   result=capture_metadata(root/'uap-lab',dict(event_id=eid,generation='g',pts_seconds=15,reviewed_epoch=9000));self.assertEqual(result['captured_epoch'],1005)
 def test_mismatched_source_cannot_supply_time(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);eid='a'*32;folder=root/'notifications/outbox'/eid;folder.mkdir(parents=True);(folder/'event.json').write_text(json.dumps(dict(generation='old',detected_epoch=1000,pts_seconds=10)))
   self.assertNotIn('captured_epoch',capture_metadata(root/'uap-lab',dict(event_id=eid,generation='new',pts_seconds=15,reviewed_epoch=9000)))
 def test_missing_source_is_unknown(self):
  with tempfile.TemporaryDirectory() as t:self.assertNotIn('captured_epoch',capture_metadata(Path(t)/'lab',dict(event_id='a'*32,reviewed_epoch=9000)))
if __name__=='__main__':unittest.main()
