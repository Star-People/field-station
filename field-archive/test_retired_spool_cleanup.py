import tempfile,unittest,json
from pathlib import Path
from retired_spool_cleanup import cleanup
class Tests(unittest.TestCase):
 def test_preserves_manual_active_review_context_and_training(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);g='run-abc';run=r/'capture-spool'/g;run.mkdir(parents=True);(r/'uap-lab').mkdir();(r/'notifications/outbox').mkdir(parents=True)
   def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
   save(run/'closed.json',{});save(run/'recognition-ack.json',dict(generation=g,integrity_ok=True,last_pts_seconds=1000))
   rows=[]
   for i in range(4):
    name=f'segment-{i:09d}.mkv';(run/name).write_bytes(b'video');rows.append(dict(file=name,start=i*100,end=i*100+1,end_epoch=1))
    save(r/'sessions'/str(i)/'manifest.json',dict(spool_generation=g,capture_origin='manual' if i==1 else 'provisional_motion',state='completed',session_media_removed=i!=3))
    save(r/'sessions'/str(i)/'buffer-state.json',dict(segments=[rows[-1]]))
   (run/'segments-index.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
   save(r/'notifications/outbox/review/event.json',dict(generation=g,pts_seconds=200))
   crop=r/'uap-lab/training.png';crop.write_bytes(b'training')
   dry=cleanup(r,{g},now=200000);self.assertEqual(dry['eligible_files'],1)
   self.assertTrue((run/rows[0]['file']).exists())
   result=cleanup(r,{g},apply=True,now=200000);self.assertEqual(result['deleted_files'],1)
   self.assertFalse((run/rows[0]['file']).exists());self.assertTrue(all((run/x['file']).exists() for x in rows[1:]));self.assertEqual(crop.read_bytes(),b'training')
if __name__=='__main__':unittest.main()
