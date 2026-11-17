"""Experimental is Stable's immutable artifact with an independent decision profile."""
import fcntl,json,time
from pathlib import Path
from worker import read,save,model_folder

def bind(human_root,experimental_root,source=None):
 human_root=Path(human_root);root=Path(experimental_root);root.mkdir(parents=True,exist_ok=True)
 with (root/'worker.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  human=read(human_root/'status.json',{});folder=Path(source) if source else model_folder(human_root,human['active_version'])
  policy=read(folder/'candidate-policy.json');version=policy['version']
  if not (folder/'candidate-weights.pt').is_file() or not (folder/'candidate.mlpackage').is_dir():raise ValueError('Stable artifacts unavailable; experimental binding unchanged')
  old=read(root/'status.json',{});previous=old.get('shadow_version');publication=read(human_root/'model-publication/status.json',{})
  if previous!=version or old.get('experiment_mode')!='decision_profile':
   if old:save(root/'profile-history'/(str(time.time_ns())+'.json'),old)
   value=dict(old,phase='shadow_ready',experiment_mode='decision_profile',training_lane='human_experimental',shadow_folder=str(folder),run_directory=str(folder),shadow_version=version,shadow_seed_only=False,baseline_copy=True,baseline_version=version,trained_epoch=human.get('trained_epoch'),error=None,reason='Same learned weights as Stable; independent decision settings.',updated_epoch=time.time(),publication=publication if publication.get('version')==version else None)
   value.pop('publication_error',None);save(root/'status.json',value)
  return dict(version=version,folder=str(folder),previous_version=previous,publication=publication if publication.get('version')==version else None,mode='decision_profile')

def sync(cfg):
 result=bind(cfg['human_root'],cfg['experimental_root'])
 # Carry the experiment's own choices forward; never copy Stable's overrides.
 from model_inspector_sync import rpc
 code="import sys,json;from pathlib import Path;sys.path.insert(0,'/Users/ufo-field/ufo-field/uap-lab');from model_settings import rebase_experimental;print(json.dumps(rebase_experimental(Path('/Volumes/UFO-Field/uap-lab'),"+repr(result['version'])+","+repr(read(Path(result['folder'])/'candidate-policy.json'))+")))"
 rpc(cfg,code);return result
