import unittest,tempfile,json
from pathlib import Path
from prospective import partition
class Holdout(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name);self.cfg=dict(id='test',salt='immutable',holdout_percent=100,registry=str(self.root/'registry.sqlite'));(self.root/'research-protocol.json').write_text(json.dumps(self.cfg));partition(self.root,[self.row('old','oldpixel')],exposed=True)
 def tearDown(self):self.t.cleanup()
 def row(self,g,p):return dict(origin=g+':'+p,group=g,pixel_sha256=p,label='anomalous')
 def test_historical_is_never_holdout(self):
  kept,a=partition(self.root,[self.row('old','fresh')]);self.assertEqual(len(kept),1)
 def test_new_group_reserved_and_persistent(self):
  r=self.row('new','newpixel');self.assertFalse(partition(self.root,[r])[0]);r['label']='not_anomalous';self.assertFalse(partition(self.root,[r])[0])
 def test_pixel_leakage_quarantines_connected_recordings(self):
  partition(self.root,[self.row('new','newpixel')]);kept,a=partition(self.root,[self.row('old','newpixel')]);self.assertFalse(kept);self.assertEqual(a['excluded'][0]['role'],'quarantine');self.assertFalse(partition(self.root,[self.row('new','otherpixel')])[0])
 def test_historical_duplicate_cannot_be_independent(self):
  kept,a=partition(self.root,[self.row('new','oldpixel')]);self.assertEqual(len(kept),1)
 def test_aliases_prevent_hashed_group_leak(self):
  partition(self.root,[self.row('new','pixel')]);r=self.row('hash','another');r['group_aliases']=['generation:new'];self.assertFalse(partition(self.root,[r])[0])
 def test_missing_provenance_quarantined(self):self.assertFalse(partition(self.root,[dict(origin='x',label='anomalous')])[0])
 def test_protocol_cannot_silently_change(self):
  self.cfg['holdout_percent']=0;(self.root/'research-protocol.json').write_text(json.dumps(self.cfg))
  with self.assertRaisesRegex(ValueError,'protocol changed'):partition(self.root,[])
 def test_duplicate_linked_recordings_share_uncertainty_group(self):
  _,audit=partition(self.root,[self.row('first','shared'),self.row('second','shared')]);self.assertEqual(audit['excluded'][0]['component_group'],audit['excluded'][1]['component_group'])
 def test_missing_registry_blocks(self):
  (self.root/'registry.sqlite').unlink()
  with self.assertRaisesRegex(ValueError,'missing'):partition(self.root,[])
if __name__=='__main__':unittest.main()
