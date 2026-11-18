import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from negative_backlog import cycle,select
from retired_data import save

class SampleTests(unittest.TestCase):
    def rows(self,n):
        return [dict(id=str(i),created=i,captured=i*3600,uncertainty=i/n,bytes=10,appearance=str(i%3)) for i in range(n)]
    def test_count_and_byte_limits(self):
        rows=self.rows(100)
        self.assertEqual(len(select(rows,10,10000)),10)
        self.assertEqual(len(select(rows,10,40)),4)
        self.assertEqual(select(rows,0,100),set())
    def test_uncertain_and_diverse_examples_survive(self):
        rows=self.rows(40)
        for row in rows:row.update(captured=0,appearance='repeat',uncertainty=0)
        rows[0]['uncertainty']=1;rows[1]['appearance']='different'
        kept=select(rows,4,1000)
        self.assertIn('0',kept);self.assertIn('1',kept)
    def test_oversized_item_does_not_block_small_items(self):
        rows=self.rows(5);rows[-1]['bytes']=1000
        self.assertEqual(len(select(rows,4,40)),4)

class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.data=Path(self.tmp.name)/'lab';(self.data/'email-reviews/examples').mkdir(parents=True)
        self.now=time.time();save(self.data/'negative-backlog-policy.json',dict(enabled=True,max_items=1,max_bytes=1000000,grace_seconds=900))
        save(self.data/'email-reviews/training-manifest.json',dict(examples=[]))
        self.env=patch.dict('os.environ',{'XDG_RUNTIME_DIR':str(Path(self.tmp.name)/'runtime')});self.env.start();self.addCleanup(self.env.stop)
        self.events=[]
    def event(self,**extra):
        key=f'{len(self.events)+1:032x}';folder=self.data.parent/'notifications/outbox'/key;folder.mkdir(parents=True)
        e=dict(id=key,created_epoch=self.now-3600+len(self.events),detected_epoch=self.now-3600,classification='not_anomalous',score=.01)
        e.update(extra);save(folder/'event.json',e);Image.new('RGB',(16,16),'black').save(folder/'native-object.png')
        self.events.append((key,folder));return key,folder
    def run_cycle(self,apply=True):return cycle(self.data,apply=apply,now=self.now)
    def test_dry_run_and_delete_preserve_metadata(self):
        key,folder=self.event();self.event()
        self.assertEqual(self.run_cycle(False)['planned'],1);self.assertTrue((folder/'native-object.png').exists())
        result=self.run_cycle();self.assertEqual(result['deleted'],1);self.assertFalse((folder/'native-object.png').exists());self.assertTrue((folder/'event.json').exists())
        self.assertIn(key,json.loads((self.data/'retired-objects.json').read_text())['events'])
        self.assertEqual(self.run_cycle()['deleted'],0)
    def test_human_star_manual_positive_and_pending_annotations_protected(self):
        reviewed,rf=self.event();star,sf=self.event();manual,mf=self.event(capture_origin='manual');positive,pf=self.event(classification='anomalous');pending,qf=self.event()
        sample='f'*32;save(self.data/'email-reviews/training-manifest.json',dict(examples=[dict(event_id=reviewed,sample_id='e'*32,human_confirmed=True)]))
        save(self.data/'starred-objects.json',dict(objects={'review:'+star+':'+star:{}}))
        save(self.data/'email-reviews/pending-index'/(sample+'.json'),{})
        save(self.data/'email-reviews/examples'/sample/'review.json',dict(event_id=pending,human_confirmed=True))
        self.event();self.event();self.assertEqual(self.run_cycle()['deleted'],1)
        for folder in [rf,sf,mf,pf,qf]:self.assertTrue((folder/'native-object.png').exists())
    def test_fresh_and_inspected_frames_deferred(self):
        old,folder=self.event();self.event(created_epoch=self.now)
        save(self.data/'review-leases.json',{old:self.now+500})
        self.assertEqual(self.run_cycle()['deleted'],0);self.assertTrue((folder/'native-object.png').exists())
    def test_review_change_after_planning_aborts_deletion(self):
        self.event();self.event()
        from negative_backlog import select as original
        def changed(*args):
            result=original(*args);save(self.data/'email-reviews/training-manifest.json',dict(examples=[dict(event_id=self.events[0][0],human_confirmed=True)]));return result
        with patch('negative_backlog.select',side_effect=changed):self.assertEqual(self.run_cycle()['deleted'],0)
        self.assertTrue(all((f/'native-object.png').exists() for _,f in self.events))
    def test_corrupt_protection_metadata_fails_closed(self):
        self.event();self.event();(self.data/'starred-objects.json').write_text('{')
        result=self.run_cycle();self.assertEqual(result['deleted'],0);self.assertTrue(result['errors'])
    def test_shared_original_is_never_unlinked(self):
        _,folder=self.event();self.event()
        shared=self.data.parent/'notifications/evidence/run-abc/segment.mkv';shared.parent.mkdir(parents=True);shared.write_bytes(b'original')
        self.run_cycle();self.assertEqual(shared.read_bytes(),b'original')
    def test_interrupted_unlink_resumes_without_resurrecting_card(self):
        key,folder=self.event();self.event();original=Path.unlink
        def fail(path,*args,**kwargs):
            if path==folder/'native-object.png':raise OSError('Disconnected drive')
            return original(path,*args,**kwargs)
        with patch.object(Path,'unlink',fail):
            result=self.run_cycle();self.assertTrue(result['errors'])
        self.assertTrue((self.data/'negative-backlog-pending'/(key+'.json')).exists())
        self.assertEqual(self.run_cycle()['deleted'],1)
        self.assertFalse((folder/'native-object.png').exists())
        self.assertFalse((self.data/'negative-backlog-pending'/(key+'.json')).exists())
    def test_symlink_preserved(self):
        key,folder=self.event();self.event();target=folder/'native-object.png'
        (folder/'source').symlink_to(target)
        result=self.run_cycle();self.assertTrue(result['errors']);self.assertTrue(target.exists())
    def test_disabled_does_nothing(self):
        save(self.data/'negative-backlog-policy.json',dict(enabled=False));self.event();self.event()
        self.assertEqual(self.run_cycle(),dict(enabled=False))

if __name__=='__main__':unittest.main()
