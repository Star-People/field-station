"""Remove expired duplicate buffer segments of explicitly retired automatic sessions."""
import collections,fcntl,json,os,re,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

def read(path):
 try:return json.loads(path.read_text())
 except FileNotFoundError:return {}

def collect(root, generations):
 root=Path(root);candidates=collections.defaultdict(set);needed=collections.defaultdict(set);pins=collections.defaultdict(list);guards={}
 def session(p):
  m=read(p/'manifest.json');g=m.get('spool_generation')
  if g not in generations:return None
  raw=(p/'manifest.json').read_bytes();m=json.loads(raw);b=read(p/'buffer-state.json');decision=read(p/'archive-decision.json')
  names={s['file'] for s in b.get('segments',[])}
  retired=m.get('capture_origin')=='provisional_motion' and m.get('state')=='completed' and m.get('session_media_removed') is True and not decision.get('confirmed_anomalous')
  return p,g,names,retired,raw
 with ThreadPoolExecutor(max_workers=8) as pool:
  for item in pool.map(session,(root/'sessions').iterdir()):
   if item:
    p,g,names,retired,raw=item
    (candidates if retired else needed)[g].update(names);guards[p/'manifest.json']=raw
 def alert(p):
  if not p.is_dir():return None
  if {'local-media-retired.json','label-queue-dismissed.json'} & set(os.listdir(p)):return None
  e=read(p/'event.json');g=e.get('generation');pts=e.get('pts_seconds')
  return (g,pts) if g in generations and isinstance(pts,(int,float)) else None
 with ThreadPoolExecutor(max_workers=16) as pool:
  for item in pool.map(alert,(root/'notifications/outbox').iterdir()):
   if item:pins[item[0]].append((item[1]-5,item[1]+5))
 # Preserve human-confirmed anomalous source; negative reviews retain their training crops.
 manifest=root/'uap-lab/email-reviews/training-manifest.json'
 if manifest.exists():
  raw=manifest.read_bytes();guards[manifest]=raw
  for e in json.loads(raw).get('examples',[]):
   g=e.get('generation');pts=e.get('pts_seconds')
   if e.get('human_confirmed') and not e.get('deleted') and not e.get('retired') and e.get('label') not in ['not_anomalous','bird','insect','airplane','cloud','star','satellite','drone'] and g in generations and isinstance(pts,(int,float)):pins[g].append((pts-5,pts+5))
 return candidates,needed,pins,guards

def cleanup(root,generations,apply=False,now=None):
 root=Path(root);now=now or time.time();audit=root/'operations/storage-audit';audit.mkdir(parents=True,exist_ok=True)
 with (root/'capture-spool/retention.lock').open('a') as lock,(root/'uap-lab/review-media.lock').open('a') as reviewlock:
  if apply:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(reviewlock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  candidates,needed,pins,guards=collect(root,generations);plan=[];counts=collections.Counter();active=read(root/'capture-spool/active.json').get('generation')
  for gen in generations:
   run=root/'capture-spool'/gen
   if gen==active or not (run/'closed.json').exists():continue
   ack=read(run/'recognition-ack.json')
   if ack.get('generation')!=gen or ack.get('integrity_ok') is not True:continue
   for line in (run/'segments-index.jsonl').read_text().splitlines():
    e=json.loads(line);name=e['file']
    if name not in candidates[gen] or name in needed[gen]:continue
    if e['end_epoch']>now-32*3600 or e['end']>=ack.get('last_pts_seconds',0)-30:continue
    if any(e['start']<=end and e['end']>=start for start,end in pins[gen]):counts['review_context_retained']+=1;continue
    if not re.fullmatch(r'segment-\d+\.mkv',name):raise ValueError('Unsafe segment name')
    p=run/name
    if p.is_symlink():raise ValueError('Unsafe segment symlink')
    try:st=p.stat()
    except FileNotFoundError:continue
    plan.append((p,st,e));counts[gen]+=1
  report=dict(apply=apply,eligible_files=len(plan),eligible_bytes=sum(st.st_size for p,st,e in plan),counts=dict(counts),deleted_files=0,unlinked_bytes=0)
  if apply:
   from capacity_retention import checked
   for p,st,e in plan:checked(root,str(p.relative_to(root)))
   if any(p.read_bytes()!=raw for p,raw in guards.items()):raise RuntimeError('Review or session changed; retry cleanup')
   with (audit/'retired-spool-deletions.jsonl').open('a') as journal:
    for p,st,e in plan:
     current=p.stat()
     if (current.st_ino,current.st_size,current.st_mtime_ns)!=(st.st_ino,st.st_size,st.st_mtime_ns):raise RuntimeError('Segment changed')
     journal.write(json.dumps(dict(path=str(p),bytes=st.st_size,sha256=e.get('sha256'),epoch=now,reason='expired_duplicate_of_explicitly_retired_automatic_session'))+'\n')
    journal.flush();os.fsync(journal.fileno())
    for p,st,e in plan:
     p.unlink();report['deleted_files']+=1;report['unlinked_bytes']+=st.st_size
  (audit/'retired-spool-status.json').write_text(json.dumps(report));return report
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--generation',action='append');p.add_argument('--apply',action='store_true');a=p.parse_args()
 generations=set(a.generation or [p.name for p in (a.root/'capture-spool').glob('run-*') if (p/'closed.json').exists()])
 try:print(json.dumps(cleanup(a.root,generations,apply=a.apply)))
 except BlockingIOError:print(json.dumps(dict(busy=True,deleted_files=0)))
