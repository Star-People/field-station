import json,sys,hashlib,time,joblib,shutil
from prospective_evaluate import package_digest
from pathlib import Path
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
sys.path[:0]=['/Volumes/UFO-Work/services/hybrid-training','/Volumes/UFO-Work/projects/field-station/uap-lab','/Volumes/UFO-Work/projects/field-station/uap-lab/auto_training']
from human_nonlinear import sample_weights
from model_settings import effective
from worker import model_folder
R=Path('/Volumes/UFO-Work/field/research-v1')
if (R/'frozen-comparison.json').exists():raise SystemExit('Comparison already frozen; use a new protocol for a new challenger')
d=json.loads((R/'development.json').read_text());x=np.load(R/'dinov2-features.npy');rows=d['samples'];y=np.array([r['label']=='anomalous' for r in rows]);scale=StandardScaler().fit(x);model=LogisticRegression(C=.5,max_iter=1000,random_state=731).fit(scale.transform(x),y,sample_weight=sample_weights(rows));oof=np.load(R/'dinov2-linear-recording-731.npz')['prob'];threshold=float(np.quantile(oof[y],.1,method='lower'));artifact=R/'dinov2-linear-challenger.joblib';joblib.dump(dict(scale=scale,model=model,threshold=threshold),artifact)
cfg=json.load(open('/Users/ufo-files-agent/field-migration/model-comparisons.json'));status=json.load(open(Path(cfg['root'])/'status.json'));settings=json.load(open(Path(cfg['root'])/'model-settings.json'));models=[]
for lane,version in status['versions'].items():
 root=Path(cfg['human_root'] if lane in ['human','experimental'] else cfg[lane+'_root']);folder=model_folder(root,version);policy=effective(json.load(open(folder/'candidate-policy.json')),lane,settings);models.append(dict(lane=lane,version=version,folder=str(folder),policy=policy,policy_sha256=hashlib.sha256(json.dumps(policy,sort_keys=True).encode()).hexdigest()))
protocol=dict(id='confirmatory-v1',frozen_epoch=time.time(),models=models,challenger=dict(name='dinov2-linear-recording',artifact=str(artifact),sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),threshold=threshold,backbone=str(R/'dinov2-vits14.pt')),scope='Untouched new recording groups only. Capture date must be independently established after prospective boundary. Fixed artifacts and settings. Crop classification, not end-to-end event recall.',minimum_support=dict(positive=50,negative=200,recordings=5),promotion='manual research decision only; no automatic activation',method='All available reserved images; paired recording-group bootstrap; report separate day/night/unknown strata. Never tune on this cohort.')
for m in protocol['models']:
 folder=R/'frozen-models'/m['version'];folder.mkdir(parents=True,exist_ok=True)
 if not (folder/'candidate.mlpackage').exists():shutil.copytree(Path(m['folder'])/'candidate.mlpackage',folder/'candidate.mlpackage')
 m['original_folder']=m['folder'];m['folder']=str(folder);m['package_sha256']=package_digest(folder/'candidate.mlpackage')
protocol['challenger']['backbone_sha256']=hashlib.sha256(Path(protocol['challenger']['backbone']).read_bytes()).hexdigest()
(R/'frozen-comparison.json').write_text(json.dumps(protocol,indent=2));print('frozen four production profiles and DINOv2 challenger',threshold)
