"""Separate bounded HQ evaluator; telemetry never waits on model inference."""
import fcntl,hashlib,json,time,sys
from pathlib import Path
ROOT=Path('/Volumes/UFO-Work/field/research-v1');sys.path.insert(0,str(ROOT))
from prospective_evaluate import evaluate
from research_worker import read,save

def main():
 if not Path('/Volumes/UFO-Work').is_mount():raise ValueError('External research volume unavailable')
 with (ROOT/'evaluation.lock').open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return
  manifest=ROOT/'holdout/manifest.json';protocol=ROOT/'frozen-comparison.json'
  if not manifest.exists() or not protocol.exists():return
  key=hashlib.sha256(manifest.read_bytes()+protocol.read_bytes()).hexdigest();state=read(ROOT/'evaluation-status.json',{})
  if state.get('completed_input')==key:return
  try:
   save(ROOT/'evaluation-status.json',dict(state='evaluating',input=key,updated_epoch=time.time()))
   result=evaluate(ROOT);save(ROOT/'confirmatory-summary.json',{k:v for k,v in result.items() if k!='models'});save(ROOT/'evaluation-status.json',dict(state=result['state'],completed_input=key,updated_epoch=time.time(),error=None))
  except Exception as exc:save(ROOT/'evaluation-status.json',dict(state='retrying',error=str(exc),updated_epoch=time.time()));raise
if __name__=='__main__':main()
