"""HQ research observer. No capture controls, model activation or source deletions."""
import fcntl,hashlib,json,os,shutil,sqlite3,sys,time
from pathlib import Path
from PIL import Image
ROOT=Path('/Volumes/UFO-Work/field/research-v1')
sys.path.insert(0,str(ROOT))
sys.path[:0]=['/Volumes/UFO-Work/services/hybrid-training','/Volumes/UFO-Work/projects/field-station/uap-lab/auto_training']
from prospective import partition
def rpc(cfg,code):
 import subprocess,shlex
 command=shlex.join(['/Users/ufo-field/ufo-field/venv/bin/python','-c',code])
 return subprocess.check_output(['/usr/bin/python3',cfg['ssh_helper'],command],text=True,timeout=90)

def save(path,value):
 p=path.with_suffix('.tmp');p.write_text(json.dumps(value,indent=2,allow_nan=False));p.replace(path)
def read(path,default):return json.loads(path.read_text()) if path.exists() else default

def collect_holdout(state):
 paths=list(Path('/Volumes/UFO-Work/field/auto-training/reviews').glob('*/reviews.json'))
 if not paths:return
 path=max(paths,key=lambda p:p.stat().st_mtime);manifest=read(path,{})
 if state.get('snapshot')==manifest.get('fingerprint'):return
 _,admission=partition(ROOT,manifest['samples']);reserved={r['origin'] for r in admission['excluded'] if r['role']=='holdout'};samples=[]
 images=ROOT/'holdout/images';images.mkdir(parents=True,exist_ok=True)
 for row in manifest['samples']:
  if row['origin'] not in reserved:continue
  source=path.parent/row['image']
  if source.is_symlink() or not source.resolve().is_relative_to(path.parent.resolve()):raise ValueError('Unsafe reserved image')
  with Image.open(source) as image:
   image=image.convert('RGB');pixel=hashlib.sha256(f'{image.width}x{image.height}:RGB:'.encode()+image.tobytes()).hexdigest()
  if pixel!=row['pixel_sha256']:raise ValueError('Reserved image checksum mismatch')
  name=hashlib.sha256((row['origin']+':'+row['pixel_sha256']).encode()).hexdigest()+'.png';target=images/name
  if not target.exists():shutil.copyfile(source,target)
  samples.append(dict(row,image='images/'+name))
 enrich_capture_times(samples)
 save(ROOT/'holdout/manifest.json',dict(protocol=admission['protocol'],snapshot=manifest['fingerprint'],samples=samples,updated_epoch=time.time(),evaluation_status='awaiting_preregistered_model_comparison' if samples else 'awaiting_new_independent_recordings'))
 state.update(snapshot=manifest['fingerprint'],reserved_reviewed_images=len(samples),reserved_recordings=len({r['group'] for r in samples}))

def enrich_capture_times(samples):
 if not samples:return
 cfg=read(Path('/Users/ufo-files-agent/field-migration/model-comparisons.json'),{});boundary=read(ROOT/'research-protocol.json',{})['started_epoch']
 from datetime import datetime
 from zoneinfo import ZoneInfo
 sys.path.insert(0,'/Volumes/UFO-Work/projects/field-station/uap-lab/recognition')
 from night_context import boundaries
 unresolved=[]
 for row in samples:
  epoch=row.get('captured_epoch')
  if isinstance(epoch,(int,float)) and epoch>0 and row.get('capture_provenance')=='event_clock_plus_same_generation_pts':
   rise,setting=boundaries(datetime.fromtimestamp(epoch,ZoneInfo('America/Los_Angeles')).date());row.update(prospective_eligible=epoch>=boundary,period='daytime' if rise<=epoch<setting else 'nighttime')
  else:unresolved.append(row)
 samples=unresolved
 for start in range(0,len(samples),64):
  chunk=samples[start:start+64]
  code="""import json,re,math,sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0,'/Users/ufo-field/ufo-field/uap-lab/recognition')
from night_context import boundaries
out={};root=Path('/Volumes/UFO-Field')
for origin in ORIGINS:
 result=dict(prospective_eligible=False,period='unknown');out[origin]=result
 if not origin.startswith('email:'):continue
 key=origin.split(':',1)[1]
 if not re.fullmatch('[a-f0-9]{32}',key):continue
 path=root/'uap-lab/email-reviews/examples'/key/'review.json'
 if not path.exists():continue
 review=json.loads(path.read_text());event_id=review.get('event_id','')
 if not re.fullmatch('[a-f0-9]{32}',event_id):continue
 path=root/'notifications/outbox'/event_id/'event.json'
 if not path.exists():continue
 event=json.loads(path.read_text())
 if not review.get('generation') or review.get('generation')!=event.get('generation'):continue
 values=[event.get('detected_epoch'),review.get('pts_seconds'),event.get('pts_seconds')]
 if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in values):continue
 epoch=values[0]+values[1]-values[2]
 if epoch<=0:continue
 local=datetime.fromtimestamp(epoch,ZoneInfo('America/Los_Angeles'));rise,setting=boundaries(local.date())
 result.update(captured_epoch=epoch,period='daytime' if rise<=epoch<setting else 'nighttime',capture_provenance='event_clock_plus_same_generation_pts',current_label=review.get('label'))
print(json.dumps(out))
""".replace('ORIGINS',repr([r['origin'] for r in chunk]))
  metadata=json.loads(rpc(cfg,code))
  for row in chunk:
   meta=metadata.get(row['origin'],{});row.update(meta);row['prospective_eligible']=meta.get('captured_epoch',0)>=boundary and meta.get('current_label')==row['label']

def telemetry(state):
 cfg=read(Path('/Users/ufo-files-agent/field-migration/model-comparisons.json'),{})
 cursor=state.get('cursor',{});started=read(ROOT/'research-protocol.json',{})['started_epoch']
 code="""import sqlite3,json,time,math
from pathlib import Path
p=Path('/Volumes/UFO-Field/uap-lab/recognition/results.sqlite')
db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=1);db.execute('PRAGMA query_only=ON')
rows=list(db.execute('SELECT generation,sequence,pts,epoch,model,observations FROM frames ORDER BY rowid DESC LIMIT 6000'));db.close();rows.reverse()
cursor=CURSOR;started=STARTED;minutes={};tracks={};new=0
for g,seq,pts,epoch,model,raw in rows:
 if epoch<started:continue
 previous=cursor.get(g)
 if previous and seq<=previous['sequence']:continue
 new+=1;key=str(int(epoch//60))+':'+model;m=minutes.setdefault(key,dict(epoch_minute=int(epoch//60)*60,model=model,observed_seconds=0,frames=0,proposal_observations=0))
 m['frames']+=1
 if previous and seq==previous['sequence']+1 and model==previous['model'] and 0<pts-previous['pts']<=1:m['observed_seconds']+=pts-previous['pts']
 cursor[g]=dict(sequence=seq,pts=pts,model=model,epoch=epoch)
 for ob in json.loads(raw):
  m['proposal_observations']+=1;tid=ob.get('proposed_track_id')
  if not tid:continue
  t=tracks.setdefault(g+':'+str(tid),dict(generation=g,track_id=str(tid),first_epoch=epoch,last_epoch=epoch,observations=0,ambiguous=False,discontinuity=False,speed_sum=0,speed_count=0,max_speed=None))
  t['last_epoch']=epoch;t['observations']+=1;t['ambiguous']|=bool(ob.get('ambiguous_link'));t['discontinuity']|=bool(ob.get('source_discontinuity'));v=ob.get('velocity_pixels_per_second')
  if isinstance(v,(list,tuple)) and len(v)==2 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in v):v=math.hypot(*v)
  if isinstance(v,(float,int)) and math.isfinite(v):t['speed_sum']+=v;t['speed_count']+=1;t['max_speed']=max(t['max_speed'] or 0,v)
print(json.dumps(dict(cursor=cursor,minutes=list(minutes.values()),tracks=list(tracks.values()),new_frames=new,source_limit=6000,observed_epoch=time.time())))
""".replace('CURSOR',repr(cursor)).replace('STARTED',repr(started))
 result=json.loads(rpc(cfg,code));db=sqlite3.connect(ROOT/'telemetry.sqlite')
 try:
  db.executescript('CREATE TABLE IF NOT EXISTS coverage(minute INTEGER,model TEXT,seconds REAL,frames INTEGER,proposals INTEGER,PRIMARY KEY(minute,model));CREATE TABLE IF NOT EXISTS tracks(id TEXT PRIMARY KEY,data TEXT);CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT);')
  # Telemetry and cursor commit together so retries cannot double-count coverage.
  for r in result['minutes']:db.execute('INSERT INTO coverage VALUES(?,?,?,?,?) ON CONFLICT(minute,model) DO UPDATE SET seconds=seconds+excluded.seconds,frames=frames+excluded.frames,proposals=proposals+excluded.proposals',(r['epoch_minute'],r['model'],r['observed_seconds'],r['frames'],r['proposal_observations']))
  for t in result['tracks']:
   key=t['generation']+':'+t['track_id'];old=db.execute('SELECT data FROM tracks WHERE id=?',(key,)).fetchone()
   if old:
    old=json.loads(old[0]);t.update(first_epoch=old['first_epoch'],observations=t['observations']+old['observations'],speed_sum=t['speed_sum']+old['speed_sum'],speed_count=t['speed_count']+old['speed_count'],max_speed=max(t['max_speed'] or 0,old['max_speed'] or 0),ambiguous=t['ambiguous'] or old['ambiguous'],discontinuity=t['discontinuity'] or old['discontinuity'])
   db.execute('INSERT OR REPLACE INTO tracks VALUES(?,?)',(key,json.dumps(t)))
  db.execute('INSERT OR REPLACE INTO state VALUES(?,?)',('cursor',json.dumps(result['cursor'])));db.commit()
  seconds,frames,proposals=db.execute('SELECT coalesce(sum(seconds),0),coalesce(sum(frames),0),coalesce(sum(proposals),0) FROM coverage').fetchone();tracks=db.execute('SELECT count(*) FROM tracks').fetchone()[0]
 finally:db.close()
 state.update(cursor=result['cursor'],observed_camera_hours=seconds/3600,observed_frames=frames,proposal_observations=proposals,observed_tracks=tracks,telemetry_updated_epoch=time.time(),false_alerts_per_camera_hour=None,event_recall=None,event_metrics_reason='Independent event truth and completeness of missed-event audit are not established',temporal_control=False)

def backup_research(state):
 registry=ROOT/'prospective.sqlite';manifest=ROOT/'holdout/manifest.json';signature=[registry.stat().st_mtime_ns,manifest.stat().st_mtime_ns]
 if state.get('backup_signature')==signature:return
 volume=Path('/Volumes/UFO-Training')
 if not volume.is_mount():raise ValueError('Separate research backup SSD unavailable')
 destination=volume/'model-research-backup';destination.mkdir(exist_ok=True)
 pending=destination/'prospective.pending.sqlite'
 with sqlite3.connect(registry) as source,sqlite3.connect(pending) as target:source.backup(target)
 pending.replace(destination/'prospective.sqlite')
 (destination/'holdout/images').mkdir(parents=True,exist_ok=True)
 for source in (ROOT/'holdout/images').glob('*.png'):
  target=destination/'holdout/images'/source.name
  if not target.exists():
   temp=target.with_suffix('.pending');shutil.copyfile(source,temp);temp.replace(target)
 for source,target in [(manifest,destination/'holdout/manifest.json'),(ROOT/'research-protocol.json',destination/'research-protocol.json'),(ROOT/'frozen-comparison.json',destination/'frozen-comparison.json')]:
  temp=target.with_suffix('.pending');shutil.copyfile(source,temp);temp.replace(target)
 state.update(backup_signature=signature,backup_epoch=time.time(),backup_error=None)

def main():
 if not Path('/Volumes/UFO-Work').is_mount():raise ValueError('External research volume unavailable')
 with (ROOT/'worker.lock').open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return
  state=read(ROOT/'status.json',{})
  dbpath=ROOT/'telemetry.sqlite'
  if dbpath.exists():
   with sqlite3.connect(dbpath) as db:
    row=db.execute("SELECT value FROM state WHERE key='cursor'").fetchone()
    if row:state['cursor']=json.loads(row[0])
  try:
   collect_holdout(state)
   state['confirmatory_state']=read(ROOT/'confirmatory-summary.json',{'state':'collecting'})['state']
   telemetry(state);backup_research(state);state.update(phase='observing',error=None,updated_epoch=time.time())
  except Exception as exc:state.update(phase='retrying',error=str(exc),updated_epoch=time.time())
  save(ROOT/'status.json',state)
  print(json.dumps({k:v for k,v in state.items() if k!='cursor'}),flush=True)
if __name__=='__main__':main()
