import json,tempfile,unittest
from pathlib import Path
from datetime import datetime
from youtube_sessions import cycle,slot,ZONE
class API:
 def __init__(self,states):self.states=states;self.calls=[]
 def status(self,ids):return {i:self.states[i] for i in ids if i in self.states}
 def create(self,e,c):self.calls.append(('create',e['key']));return 'new'
 def configure(self,v):self.calls.append(('configure',v))
 def thumbnail(self,v,settings):self.calls.append(('thumbnail',v,settings['revision']))
 def bind(self,v):self.calls.append(('bind',v))
 def start(self,v):self.calls.append(('start',v))
 def complete(self,v):self.calls.append(('complete',v))
class SessionTests(unittest.TestCase):
 def test_four_wall_clock_slots_and_dst(self):
  for hour in range(24):
   s=slot(datetime(2026,11,11,hour,tzinfo=ZONE).timestamp());self.assertEqual(datetime.fromtimestamp(s['start'],ZONE).hour,(hour//6)*6)
  s=slot(datetime(2026,11,1,0,tzinfo=ZONE).timestamp());self.assertEqual(s['end']-s['start'],7*3600)
 def state(self,p,now):
  a=slot(now);b=slot(a['end']+1);old=slot(a['start']-1)
  state=dict(active_video_id='old',sessions={a['key']:dict(a,video_id='next',watch_url='next-url',configured=True),b['key']:dict(b,video_id='future',configured=True),old['key']:dict(old,video_id='old',watch_url='old-url',configured=True,state='live')});(p/'sessions.json').write_text(json.dumps(state));return state
 def test_complete_then_start_and_preserve_replay(self):
  now=datetime(2026,11,11,12,tzinfo=ZONE).timestamp()
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);self.state(root,now);api=API({'old':dict(lifeCycleStatus='LIFE_CYCLE_LIVE'),'next':dict(lifeCycleStatus='LIFE_CYCLE_TESTING',ingestionStatus='INGESTION_STATUS_ACTIVE')})
   cycle({},root,api,now);self.assertEqual(api.calls,[('complete','old')])
   api.states['old']['lifeCycleStatus']='LIFE_CYCLE_COMPLETE';cycle({},root,api,now+15);self.assertEqual(api.calls[-1],('start','next'))
   api.states['next']['lifeCycleStatus']='LIFE_CYCLE_LIVE';state=cycle({},root,api,now+30);self.assertEqual(state['active_video_id'],'next');self.assertTrue(any(e.get('watch_url')=='old-url' and e.get('state')=='complete' for e in state['sessions'].values()))
 def test_no_encoder_or_missing_status_does_not_end_live_session(self):
  now=datetime(2026,11,11,12,tzinfo=ZONE).timestamp()
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);self.state(root,now);api=API({'old':dict(lifeCycleStatus='LIFE_CYCLE_LIVE'),'next':dict(lifeCycleStatus='LIFE_CYCLE_READY',ingestionStatus='INGESTION_STATUS_INACTIVE')});cycle({},root,api,now);self.assertNotIn(('complete','old'),api.calls)
   api.states.pop('old')
   with self.assertRaises(RuntimeError):cycle({},root,api,now)
 def test_restart_does_not_duplicate_existing_sessions(self):
  now=datetime(2026,11,11,12,tzinfo=ZONE).timestamp()
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);s=self.state(root,now);s['active_video_id']='next';s['last_api_check']=now;s['sessions'][slot(now)['key']]['state']='live';s['sessions'][slot(now)['key']]['live_embedding_verified']=True;(root/'sessions.json').write_text(json.dumps(s));api=API({});cycle({},root,api,now);self.assertEqual(api.calls,[])

class ThumbnailTests(SessionTests):
 def active(self,root,now):
  s=self.state(root,now);s['active_video_id']='next';s['last_api_check']=now;s['sessions'][slot(now)['key']]['state']='live';s['sessions'][slot(now)['key']]['live_embedding_verified']=True;(root/'sessions.json').write_text(json.dumps(s))
 def test_current_and_upcoming_once_per_revision_and_after_restart(self):
  now=datetime(2026,11,11,12,tzinfo=ZONE).timestamp()
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);self.active(root,now);api=API({});config={'thumbnail':{'revision':'art-1','video_still':{'image':{}}}}
   cycle(config,root,api,now);self.assertEqual(api.calls,[('thumbnail','next','art-1'),('thumbnail','future','art-1')])
   cycle(config,root,api,now+15);self.assertEqual(len(api.calls),2)
   config['thumbnail']['revision']='art-2';cycle(config,root,api,now+30);self.assertEqual(len(api.calls),4)
   self.assertEqual(json.loads((root/'thumbnail-status.json').read_text())['state'],'ready')
 def test_failure_retries_without_blocking_live_session(self):
  now=datetime(2026,11,11,12,tzinfo=ZONE).timestamp()
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);self.active(root,now);api=API({'next':{'lifeCycleStatus':'LIFE_CYCLE_LIVE'}});config={'thumbnail':{'revision':'art-1','video_still':{'image':{}}}}
   def fail(v,c):api.calls.append(('failed',v));raise RuntimeError('Upload unavailable')
   api.thumbnail=fail
   state=cycle(config,root,api,now);self.assertEqual(state['active_video_id'],'next');self.assertNotIn('thumbnail_revision',state['sessions'][slot(now)['key']])
   self.assertEqual(json.loads((root/'thumbnail-status.json').read_text())['state'],'retry_pending')
   cycle(config,root,api,now+15);self.assertEqual(len(api.calls),2)
   api.thumbnail=API.thumbnail.__get__(api);cycle(config,root,api,now+301)
   self.assertEqual(json.loads((root/'thumbnail-status.json').read_text())['state'],'ready')
 def test_rejected_metadata_is_not_a_success_receipt(self):
  from youtube_sessions import Studio
  api=Studio();api.post=lambda p,b:{'overallResult':{'resultCode':'UPDATE_FAILED'},'videoStill':{'success':False}}
  with self.assertRaises(RuntimeError):api.thumbnail('next',{'video_still':{}})

class DashboardRecoveryTests(unittest.TestCase):
 def test_status_timeout_refreshes_for_next_cycle(self):
  from youtube_sessions import Studio
  api=Studio();calls=[]
  def timeout(*args):raise TimeoutError('stalled')
  api.post=timeout;api.refresh_dashboard=lambda:calls.append('refresh')
  with self.assertRaises(TimeoutError):api.status(['example'])
  self.assertEqual(calls,['refresh'])
 def test_rejected_status_does_not_reload_or_retry(self):
  from youtube_sessions import Studio
  api=Studio();calls=[]
  def rejected(*args):raise RuntimeError('permission denied')
  api.post=rejected;api.refresh_dashboard=lambda:calls.append('refresh')
  with self.assertRaises(RuntimeError):api.status(['example'])
  self.assertEqual(calls,[])

class EmbeddingTests(unittest.TestCase):
 def test_partial_or_rejected_configuration_is_not_success(self):
  from youtube_sessions import Studio
  api=Studio()
  for result in [{}, {'overallResult':{'resultCode':'UPDATE_SUCCESS'}}, {'overallResult':{'resultCode':'UPDATE_SUCCESS'},'distributionOptions':{'success':False},'madeForKids':{'success':True}}]:
   api.post=lambda p,b:result
   with self.assertRaises(RuntimeError):api.configure('video')
  api.post=lambda p,b:{'overallResult':{'resultCode':'UPDATE_SUCCESS'},'distributionOptions':{'success':True},'madeForKids':{'success':True}}
  api.configure('video')
 def test_live_upgrade_retries_failed_embedding_without_losing_active_stream(self):
  now=datetime(2026,11,11,12,tzinfo=ZONE).timestamp()
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);s=SessionTests().state(root,now);s['active_video_id']='next';s['last_api_check']=now;s['sessions'][slot(now)['key']]['state']='live';(root/'sessions.json').write_text(json.dumps(s))
   api=API({})
   def fail(v):raise RuntimeError('rejected')
   api.configure=fail
   with self.assertRaises(RuntimeError):cycle({},root,api,now)
   saved=json.loads((root/'sessions.json').read_text());self.assertEqual(saved['active_video_id'],'next');self.assertFalse(saved['sessions'][slot(now)['key']].get('live_embedding_verified'))
   api.configure=API.configure.__get__(api);cycle({},root,api,now+15);cycle({},root,api,now+30)
   self.assertEqual(api.calls,[('configure','next')])

class RolloverPriorityTests(unittest.TestCase):
 def test_missing_future_cannot_delay_current_handoff(self):
  now=datetime(2026,11,11,12,tzinfo=ZONE).timestamp()
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);s=SessionTests().state(root,now);future=slot(slot(now)['end']+1);s['sessions'].pop(future['key']);(root/'sessions.json').write_text(json.dumps(s))
   api=API({'old':dict(lifeCycleStatus='LIFE_CYCLE_LIVE'),'next':dict(lifeCycleStatus='LIFE_CYCLE_TESTING',ingestionStatus='INGESTION_STATUS_ACTIVE')})
   def fail(*args):raise AssertionError('Future preparation must wait until handoff completes')
   api.create=fail;cycle({},root,api,now);self.assertEqual(api.calls,[('complete','old')])
 def test_future_failure_does_not_skip_live_health_check(self):
  now=datetime(2026,11,11,12,tzinfo=ZONE).timestamp()
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);s=SessionTests().state(root,now);s['active_video_id']='next';s['sessions'][slot(now)['key']].update(state='live',live_embedding_verified=True);s['sessions'].pop(slot(slot(now)['end']+1)['key']);(root/'sessions.json').write_text(json.dumps(s))
   api=API({'next':dict(lifeCycleStatus='LIFE_CYCLE_LIVE')})
   def fail(*args):raise TimeoutError('Future creation timed out')
   api.create=fail;result=cycle({},root,api,now)
   self.assertEqual(result['last_api_check'],now)
   self.assertEqual(json.loads((root/'session-status.json').read_text())['state'],'live')
   self.assertIn('Future creation timed out',json.loads((root/'sessions.json').read_text())['upcoming_error'])

class CreationRecoveryTests(unittest.TestCase):
 def test_pending_creation_reuses_recovered_id_without_duplicate(self):
  now=datetime(2026,11,11,12,tzinfo=ZONE).timestamp()
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);s=SessionTests().state(root,now);entry=s['sessions'][slot(now)['key']];entry.pop('video_id');entry['creation_pending']=True;(root/'sessions.json').write_text(json.dumps(s))
   api=API({'old':dict(lifeCycleStatus='LIFE_CYCLE_LIVE'),'next':dict(lifeCycleStatus='LIFE_CYCLE_TESTING',ingestionStatus='INGESTION_STATUS_ACTIVE')});api.recover=lambda e:'next'
   result=cycle({},root,api,now);self.assertEqual(api.calls,[('complete','old')]);self.assertFalse(result['sessions'][slot(now)['key']]['creation_pending'])
 def test_live_starting_waits_without_repeating_start(self):
  now=datetime(2026,11,11,12,tzinfo=ZONE).timestamp()
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);SessionTests().state(root,now);api=API({'old':dict(lifeCycleStatus='LIFE_CYCLE_COMPLETE'),'next':dict(lifeCycleStatus='LIFE_CYCLE_LIVE_STARTING')})
   cycle({},root,api,now);self.assertEqual(api.calls,[])
