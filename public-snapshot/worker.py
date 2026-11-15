"""Refresh every 15 minutes via launchd; failed cycles preserve the published snapshot."""
import fcntl,json,os,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path('/Volumes/UFO-Work/services/public-data-snapshot');CODE=Path(__file__).parent
if not Path('/Volumes/UFO-Work').is_mount():raise SystemExit('HQ SSD unavailable')
ROOT.mkdir(parents=True,exist_ok=True)
with (ROOT/'refresh.lock').open('a') as lock:
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise SystemExit(0)
 def status(**v):
  p=ROOT/'status.next.json';p.write_text(json.dumps(v));p.replace(ROOT/'status.json')
 def run(script,*args):subprocess.run([sys.executable,str(CODE/script),*map(str,args)],check=True,timeout=900)
 stage=ROOT/'incoming'
 if stage.exists():shutil.rmtree(stage)
 previous=json.loads((ROOT/'site/snapshot/manifest.json').read_text()) if (ROOT/'site/snapshot/manifest.json').exists() else {}
 status(state='syncing',started_epoch=time.time(),last_success_epoch=previous.get('captured_epoch'))
 try:
  helper='/Users/ufo-files-agent/field-migration/ssh-field.py'
  run('pull.py','--helper',helper,'--output',stage)
  training=Path('/Volumes/UFO-Work/backups/field-training-restore/current')
  run('build.py','--source',stage,'--output',ROOT/'site','--training',training)
  if json.loads((stage/'missing-thumbnails.json').read_text()):
   run('pull_missing.py','--source',stage,'--helper',helper)
   run('complete_media.py','--source',stage,'--output',ROOT/'site')
  run('publish.py','--site',ROOT/'site')
  source=ROOT/'source'
  if source.exists():shutil.rmtree(source)
  stage.rename(source)
  value=json.loads((ROOT/'site/snapshot/manifest.json').read_text());status(state='published',last_success_epoch=value['captured_epoch'],objects=value['objects'],finished_epoch=time.time())
 except Exception as e:
  status(state='retry',last_success_epoch=previous.get('captured_epoch'),error=type(e).__name__,checked_epoch=time.time());raise
