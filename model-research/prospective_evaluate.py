"""Score a frozen protocol; never optimize against the reserved cohort."""
import hashlib,io,json,sys,time
from pathlib import Path
import numpy as np
from PIL import Image
from research_metrics import counts,bootstrap_intervals

def package_digest(path):
 h=hashlib.sha256()
 for p in sorted(path.rglob('*')):
  if p.is_file():h.update(str(p.relative_to(path)).encode());h.update(p.read_bytes())
 return h.hexdigest()

def evaluate(root):
 root=Path(root);manifest=json.loads((root/'holdout/manifest.json').read_text());protocol=json.loads((root/'frozen-comparison.json').read_text());rows=[r for r in manifest['samples'] if r.get('prospective_eligible')];key=hashlib.sha256(json.dumps([protocol,rows],sort_keys=True).encode()).hexdigest();target=root/'confirmatory-results'/f'{key}.json'
 if target.exists():return json.loads(target.read_text())
 support=dict(positive=sum(r['label']=='anomalous' for r in rows),negative=sum(r['label']=='not_anomalous' for r in rows),recordings=len({r['group'] for r in rows}));enough=all(support[k]>=v for k,v in protocol['minimum_support'].items())
 result=dict(protocol=protocol['id'],fingerprint=key,support=support,minimum_support=protocol['minimum_support'],qualified_for_comparison=enough,eligible=len(rows),reserved=len(manifest['samples']),excluded_unknown_or_old_capture=len(manifest['samples'])-len(rows),state='collecting' if not enough else 'measured',automatic_activation=False,scope=protocol['scope'],models={})
 if not rows:return result
 sys.path[:0]=['/Volumes/UFO-Work/projects/field-station/uap-lab','/Volumes/UFO-Work/projects/field-station/uap-lab/recognition'];from crop_client import CropClassifier
 from live_decisions import classify,label
 tools=Path('/Volumes/UFO-Work/field/auto-training/tools')
 def image_bytes(r):
  path=root/'holdout'/r['image']
  if path.is_symlink() or not path.resolve().is_relative_to((root/'holdout').resolve()):raise ValueError('Unsafe holdout path')
  raw=path.read_bytes()
  with Image.open(io.BytesIO(raw)) as im:
   im=im.convert('RGB');digest=hashlib.sha256(f'{im.width}x{im.height}:RGB:'.encode()+im.tobytes()).hexdigest()
  if digest!=r['pixel_sha256']:raise ValueError('Holdout checksum mismatch')
  return raw
 predictions={}
 for m in protocol['models']:
  if package_digest(Path(m['folder'])/'candidate.mlpackage')!=m['package_sha256']:raise ValueError('Frozen native package changed')
  compiled=tools/(m['version']+'.mlmodelc')
  if not compiled.exists():
   import subprocess
   subprocess.run([str(tools/'compile_model'),str(Path(m['folder'])/'candidate.mlpackage'),str(compiled)],check=True,capture_output=True,timeout=300)
  values=[]
  with CropClassifier(tools/'crop_worker',compiled,m['version'],timeout=120) as worker:
   for start in range(0,len(rows),32):
    images=[image_bytes(r) for r in rows[start:start+32]];values.extend(classify(worker,images,images,[{}]*len(images),m['policy'],'prospective-'+m['lane']))
  predictions[m['lane']]=[dict(origin=r['origin'],group=r['group'],period=r.get('period','unknown'),truth=r['label'],prediction=label(v,m['policy']),score=v['scores']['anomalous']) for r,v in zip(rows,values)]
 import torch,joblib
 from torchvision import transforms
 torch.set_num_threads(2);c=protocol['challenger'];artifact=Path(c['artifact'])
 if hashlib.sha256(artifact.read_bytes()).hexdigest()!=c['sha256']:raise ValueError('Frozen challenger changed')
 if hashlib.sha256(Path(c['backbone']).read_bytes()).hexdigest()!=c['backbone_sha256']:raise ValueError('Frozen transformer changed')
 trained=joblib.load(artifact);net=torch.hub.load(str(root/'torch-hub/facebookresearch_dinov2_main'),'dinov2_vits14',source='local',pretrained=False);net.load_state_dict(torch.load(c['backbone'],weights_only=True));device='mps' if torch.backends.mps.is_available() else 'cpu';net.eval().to(device);transform=transforms.Compose([transforms.Resize((224,224),interpolation=transforms.InterpolationMode.BICUBIC),transforms.ToTensor(),transforms.Normalize((.485,.456,.406),(.229,.224,.225))]);probabilities=[]
 with torch.inference_mode():
  for start in range(0,len(rows),16):
   tensors=[]
   for raw in [image_bytes(r) for r in rows[start:start+16]]:
    with Image.open(io.BytesIO(raw)) as im:tensors.append(transform(im.convert('RGB')))
   features=net(torch.stack(tensors).to(device)).cpu().numpy();probabilities.extend(trained['model'].predict_proba(trained['scale'].transform(features))[:,1])
 predictions[c['name']]=[dict(origin=r['origin'],group=r['group'],period=r.get('period','unknown'),truth=r['label'],prediction='anomalous' if p>=c['threshold'] else 'not_anomalous',score=float(p)) for r,p in zip(rows,probabilities)]
 for name,p in predictions.items():result['models'][name]=dict(overall=counts(p),uncertainty=bootstrap_intervals(p),by_period={period:counts([r for r in p if r['period']==period]) for period in ['daytime','nighttime','unknown']},predictions=p)
 target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(result,indent=2,allow_nan=False));return result
