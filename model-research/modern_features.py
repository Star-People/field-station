import os,json,pathlib,hashlib,time,collections
os.environ['PYTORCH_ENABLE_MPS_FALLBACK']='1'
import torch,numpy as np
from PIL import Image
from torchvision import transforms
root=pathlib.Path('/Volumes/UFO-Work/field/research-v1');audit=pathlib.Path('/Volumes/UFO-Work/field/model-audit-20261114');d=json.load((audit/'data.json').open());by={r['origin']:r for r in d['rows']};rows=[by[p['origin']] for p in d['predictions']];groups=collections.defaultdict(list)
for i,r in enumerate(rows):groups[(r['group'],r['label'])].append(i)
indices=[]
for (g,label),ix in sorted(groups.items()):indices+=sorted(ix,key=lambda i:hashlib.sha256(rows[i]['origin'].encode()).hexdigest())[:len(ix) if label=='anomalous' else 40]
indices=sorted(indices);plan=dict(indices=indices,samples=[rows[i] for i in indices],source=d['source'],scope='development only; all historical groups have previous experimental exposure',sampling='all reviewed positives; at most 40 negatives per recording group',created_epoch=time.time());plan['id']=hashlib.sha256(json.dumps(plan['samples'],sort_keys=True).encode()).hexdigest();(root/'development.json').write_text(json.dumps(plan));print('selected',len(indices),'positive',sum(rows[i]['label']=='anomalous' for i in indices),flush=True)
torch.set_num_threads(2);torch.hub.set_dir(str(root/'torch-hub'));m=torch.hub.load(str(root/'torch-hub/facebookresearch_dinov2_main'),'dinov2_vits14',source='local',pretrained=False);m.load_state_dict(torch.load(root/'dinov2-vits14.pt',weights_only=True));device='mps' if torch.backends.mps.is_available() else 'cpu';m.eval().to(device);transform=transforms.Compose([transforms.Resize((224,224),interpolation=transforms.InterpolationMode.BICUBIC),transforms.ToTensor(),transforms.Normalize((.485,.456,.406),(.229,.224,.225))]);out=np.lib.format.open_memmap(root/'dinov2-features.npy',mode='w+',dtype=np.float32,shape=(len(indices),384));t=time.time()
with torch.inference_mode():
 for start in range(0,len(indices),16):
  images=[]
  for i in indices[start:start+16]:
   r=rows[i]
   with Image.open(pathlib.Path(d['source'])/r['image']) as im:
    im=im.convert('RGB');assert hashlib.sha256(f'{im.width}x{im.height}:RGB:'.encode()+im.tobytes()).hexdigest()==r['pixel_sha256'];images.append(transform(im))
  features=m(torch.stack(images).to(device)).cpu().numpy();out[start:start+len(images)]=features
  if start%256==0:out.flush();(root/'modern-progress.json').write_text(json.dumps(dict(completed=start+len(images),total=len(indices),device=device,elapsed=time.time()-t)));print(start,len(indices),round(time.time()-t),flush=True)
out.flush();(root/'modern-progress.json').write_text(json.dumps(dict(completed=len(indices),total=len(indices),device=device,elapsed=time.time()-t,state='complete')));print('complete',flush=True)
