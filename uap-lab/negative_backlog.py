"""Bound the machine-negative review sample without touching reviewed evidence."""
import argparse,collections,fcntl,hashlib,json,math,os,re,sqlite3,sys,time
from pathlib import Path
from backlog_safety import read,protected,bookmark_lease
from backlog_media import MEDIA
from retired_data import save
from review_playback import media_dir,event_lease

DEFAULTS=dict(enabled=False,max_items=1000,max_bytes=25*1024**3,grace_seconds=900)

def policy(data):
    value=dict(DEFAULTS,**read(Path(data)/'negative-backlog-policy.json',{}))
    if type(value['enabled']) is not bool:raise ValueError('Invalid enable setting')
    for key in ('max_items','max_bytes','grace_seconds'):
        if type(value[key]) is not int or value[key]<=0:raise ValueError('Invalid '+key)
    return value

def review_version(data):
    paths=['training-manifest.json','examples','pending-index']
    return tuple((Path(data)/'email-reviews'/p).stat().st_mtime_ns if (Path(data)/'email-reviews'/p).exists() else None for p in paths)

def human_events(data):
    root=Path(data)/'email-reviews'
    manifest=read(root/'training-manifest.json')
    if manifest is None and (root/'examples').exists() and any((root/'examples').iterdir()):
        raise ValueError('Review index missing; cleanup deferred')
    rows=(manifest or {}).get('examples',[])
    # A saved crop can precede its manifest commit. Protect pending annotations too.
    events={r['event_id'] for r in rows if r.get('human_confirmed') and not r.get('deleted')}
    for marker in (root/'pending-index').glob('*.json'):
        if not re.fullmatch('[a-f0-9]{32}',marker.stem):raise ValueError('Invalid pending review')
        row=read(root/'examples'/marker.stem/'review.json')
        if row is None:raise ValueError('Review save in progress')
        events.add(row['event_id'])
    return events

def candidate(event):
    return (event.get('classification')=='not_anomalous' and not any(event.get(k) for k in
            ('human_confirmed','starred','manual_session_id','manual_recording'))
            and event.get('kind')!='manual_recording' and event.get('capture_origin')!='manual')

def files(data,key):
    outbox=Path(data).parent/'notifications/outbox'/key
    folders={outbox,media_dir(data,key)}
    result=[]
    for folder in folders:
        if folder.is_symlink():raise ValueError('Unsafe media folder')
        for p in folder.rglob('*'):
            if p.is_symlink():raise ValueError('Unsafe media link')
            if p.is_file() and (p.suffix.lower() in MEDIA or p.name=='source'):result.append(p)
    return result

def features(folder,event):
    """Coarse appearance buckets, not model labels; preserve visual diversity."""
    from PIL import Image,ImageStat
    name=event.get('native_crop','native-object.png')
    if name not in ('native-object.png','object.png'):raise ValueError('Unexpected crop')
    path=folder/name
    if path.is_symlink():raise ValueError('Unsafe crop')
    with Image.open(path) as image:
        rgb=image.convert('RGB').resize((16,16));means=ImageStat.Stat(rgb).mean
        small=rgb.convert('L').resize((5,4));gray=[small.getpixel((x,y)) for y in range(4) for x in range(5)]
    bits=''.join('1' if gray[y*5+x]>gray[y*5+x+1] else '0' for y in range(4) for x in range(4))
    # Broad color/brightness and edge signature distinguish recurring scenes.
    return '-'.join(str(int(v)//64) for v in means)+':'+hex(int(bits,2))[2:]

def select(rows,limit,budget):
    """25% uncertainty priority, then round-robin appearance/hour diversity."""
    chosen=[];seen=set();used=0
    def add(row):
        nonlocal used
        if row['id'] in seen or len(chosen)>=limit or used+row['bytes']>budget:return
        chosen.append(row);seen.add(row['id']);used+=row['bytes']
    for row in sorted(rows,key=lambda r:(-r['uncertainty'],-r['created'],r['id'])):
        if len(chosen)>=max(1,limit//4):break
        add(row)
    groups=collections.defaultdict(list)
    for row in sorted(rows,key=lambda r:(-r['created'],r['id'])):
        if row['id'] not in seen:groups[(row['appearance'],int(row['captured']//3600))].append(row)
    groups=[collections.deque(v) for _,v in sorted(groups.items(),key=lambda item:(-item[1][0]['created'],str(item[0])))]
    while groups and len(chosen)<limit:
        for group in groups:add(group.popleft())
        groups=[g for g in groups if g]
    return seen

def discover(data,reviewed,retired,cache):
    from recognition.recognition_alerts import recent_detections
    from queue_index import ordered
    root=data.parent/'notifications/outbox'
    cutoff=read(data/'review-queue-cleared.json',{}).get('cutoff_epoch',float('-inf'))
    arrivals,complete=recent_detections(root,cutoff)
    keys=[r['id'] for r in arrivals if r.get('model_label')=='not_anomalous'] if complete else [key for _,key in ordered(root)]
    pending={p.stem for p in (data/'negative-backlog-pending').glob('*.json')}
    keys=sorted(set(keys)|pending)
    active={r.get('id') for r in read(root/'producer-state.json',{}).get('groups',[])}
    result=[];errors=[]
    for key in keys:
        if not re.fullmatch('[a-f0-9]{32}',key) or key in reviewed or (key in retired and key not in pending) or key in active:continue
        folder=root/key
        try:
            event=read(folder/'event.json')
            if not event or not candidate(event) or event.get('created_epoch',0)<=cutoff:continue
            if read(folder/'label-queue-dismissed.json',{}).get('dismissed') and key not in pending:continue
            if protected(data,dict(kind='detection',id=key)):continue
            paths=files(data,key);size=sum(p.stat().st_size for p in paths)
            if key in pending:
                result.append(dict(id=key,created=event['created_epoch'],captured=event.get('detected_epoch',event['created_epoch']),bytes=size,uncertainty=0,appearance='pending',resume=True))
                continue
            if not paths:continue
            native=folder/event.get('native_crop','native-object.png');stamp=native.stat().st_mtime_ns
            old=cache.execute('SELECT stamp,appearance FROM features WHERE id=?',(key,)).fetchone()
            appearance=old[1] if old and old[0]==stamp else features(folder,event)
            if not old or old[0]!=stamp:cache.execute('INSERT OR REPLACE INTO features VALUES(?,?,?)',(key,stamp,appearance))
            score=event.get('score');uncertainty=1-2*abs(score-.5) if type(score) in (int,float) and math.isfinite(score) and 0<=score<=1 else 1.
            created=float(event['created_epoch']);captured=float(event.get('detected_epoch',created))
            if not math.isfinite(created) or not math.isfinite(captured):raise ValueError('Invalid capture time')
            result.append(dict(id=key,created=created,captured=captured,bytes=size,uncertainty=uncertainty,appearance=appearance))
        except (OSError,ValueError,KeyError) as exc:errors.append(dict(id=key,error=str(exc)))
    cache.commit()
    return result,errors

def cycle(data,apply=False,now=None):
    data=Path(data);now=time.time() if now is None else now;settings=policy(data)
    if not settings['enabled']:return dict(enabled=False)
    with (data/'negative-backlog.lock').open('a') as worker:
        try:fcntl.flock(worker,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return dict(busy=True)
        started=time.monotonic()
        if apply:save(data/'negative-backlog-status.json',dict(read(data/'negative-backlog-status.json',{}),phase='scanning',scan_started_epoch=time.time()))
        result=run(data,settings,now,apply)
        result.update(phase='idle',finished_epoch=time.time(),seconds=time.monotonic()-started)
        if apply:save(data/'negative-backlog-status.json',result)
        return result

def run(data,settings,now,apply):
    root=data.parent/'notifications/outbox';version=review_version(data);reviewed=human_events(data)
    if version!=review_version(data):return dict(deferred='Reviews changed during discovery')
    retired=read(data/'retired-objects.json',{});retired_keys=set(retired.get('events',[]))
    cache=sqlite3.connect(data/'negative-backlog-features.sqlite',timeout=2)
    try:
        cache.execute('CREATE TABLE IF NOT EXISTS features(id TEXT PRIMARY KEY,stamp INTEGER,appearance TEXT)')
        rows,errors=discover(data,reviewed,retired_keys,cache)
    finally:cache.close()
    resume=[r for r in rows if r.get('resume')]
    fresh=[r for r in rows if not r.get('resume') and now-r['created']<settings['grace_seconds']]
    mature=[r for r in rows if not r.get('resume') and now-r['created']>=settings['grace_seconds']]
    fresh_bytes=sum(r['bytes'] for r in fresh)
    keep=select(mature,max(0,settings['max_items']-len(fresh)),max(0,settings['max_bytes']-fresh_bytes))
    victims=resume+[r for r in mature if r['id'] not in keep]
    result=dict(epoch=now,enabled=True,applied=apply,policy=settings,eligible=len(rows),eligible_bytes=sum(r['bytes'] for r in rows),fresh=len(fresh),planned=len(victims),deleted=0,unlinked_bytes=0,deferred=0,errors=errors)
    if not apply:return result
    audit=data/'negative-backlog-history';audit.mkdir(exist_ok=True)
    receipt=audit/(str(time.time_ns())+'.jsonl')
    # Short bounded passes yield to interactive labeling. Subsequent passes converge.
    started=time.monotonic()
    with (data/'review-media.lock').open('a') as media_lock:
        try:fcntl.flock(media_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return dict(result,deferred=len(victims),reason='Media maintenance busy')
        with receipt.open('a') as log:
            for row in victims:
                if result['deleted']>=250 or time.monotonic()-started>20:break
                key=row['id'];folder=root/key
                try:
                    with bookmark_lease(data),event_lease(folder) as available,(data/'email-reviews/review.lock').open('a') as lock:
                        if not available:result['deferred']+=1;continue
                        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                        except BlockingIOError:result['deferred']+=1;continue
                        if version!=review_version(data):result['reason']='Reviews changed; retry next pass';break
                        if key in reviewed or protected(data,dict(kind='detection',id=key)):continue
                        event=read(folder/'event.json',{})
                        if not candidate(event) or now-event.get('created_epoch',now)<settings['grace_seconds']:continue
                        if read(data/'review-leases.json',{}).get(key,0)>time.time():result['deferred']+=1;continue
                        if key in {g.get('id') for g in read(root/'producer-state.json',{}).get('groups',[])}:continue
                        paths=files(data,key)
                        # Publish exclusion before removing media; cached lists honor tombstones.
                        current=read(data/'retired-objects.json',{});events=set(current.get('events',[]));events.add(key)
                        entry=dict(id=key,reason='bounded_machine_negative_sample',epoch=time.time(),files=[dict(path=str(p),bytes=p.stat().st_size) for p in paths])
                        log.write(json.dumps(entry)+'\n');log.flush();os.fsync(log.fileno())
                        pending=data/'negative-backlog-pending'/(key+'.json');save(pending,entry)
                        save(data/'retired-objects.json',dict(current,events=sorted(events),updated_epoch=time.time()))
                        save(folder/'label-queue-dismissed.json',dict(dismissed=True,deleted=True,reason=entry['reason'],epoch=time.time()))
                        for p in paths:
                            size=p.stat().st_size;p.unlink();result['unlinked_bytes']+=size
                        save(folder/'local-media-retired.json',dict(reason=entry['reason'],epoch=time.time(),review_fingerprint=hashlib.sha256(b'[]').hexdigest()))
                        pending.unlink()
                        result['deleted']+=1
                except (OSError,ValueError,KeyError) as exc:result['errors'].append(dict(id=key,error=str(exc)))
    result['remaining_estimate']=len(rows)-result['deleted'];result['audit']=str(receipt)
    save(data/'negative-backlog-status.json',result)
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data',required=True);parser.add_argument('--apply',action='store_true');parser.add_argument('--watch',action='store_true');args=parser.parse_args()
    data=Path(args.data)
    os.nice(10)
    while True:
        try:
            # Never recreate a disappeared external volume on the startup disk.
            if not data.is_dir() or not data.parent.is_mount():raise ValueError('Field volume unavailable')
            print(json.dumps(cycle(data,args.apply)),flush=True)
        except Exception as exc:
            failure=dict(error=str(exc),epoch=time.time())
            print(json.dumps(failure),file=sys.stderr,flush=True)
            try:
                if data.is_dir() and data.parent.is_mount():save(data/'negative-backlog-status.json',failure)
            except OSError:pass
        if not args.watch:break
        time.sleep(60)

if __name__=='__main__':main()
