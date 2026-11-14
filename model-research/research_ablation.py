import json,hashlib,time,sys
from pathlib import Path
import numpy as np
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import average_precision_score,brier_score_loss
import torch
sys.path.insert(0,'/Volumes/UFO-Work/projects/field-station/uap-lab/auto_training')
from human_nonlinear import ReviewedHead,sample_weights
R=Path('/Volumes/UFO-Work/field/research-v1');d=json.loads((R/'development.json').read_text());rows=d['samples'];y=np.array([r['label']=='anomalous' for r in rows]);groups=np.array([r['group'] for r in rows]);pixels=np.array([r['pixel_sha256'] for r in rows]);torch.set_num_threads(2)
# Link recordings sharing exact pixels before splitting; omit contradictory pixels.
parent={g:g for g in groups}
def find(g):
 while parent[g]!=g:parent[g]=parent[parent[g]];g=parent[g]
 return g
seen={};labels={}
for g,p,t in zip(groups,pixels,y):
 labels.setdefault(p,set()).add(bool(t))
 if p in seen:parent[find(g)]=find(seen[p])
 else:seen[p]=g
linked=np.array([find(g) for g in groups]);valid=np.array([len(labels[p])==1 for p in pixels]);ix=np.flatnonzero(valid);fold=np.full(len(rows),-1)
for k,(_,test) in enumerate(StratifiedGroupKFold(5,shuffle=True,random_state=117).split(ix,y[ix],linked[ix])):fold[ix[test]]=k
np.save(R/'ablation-folds.npy',fold)
X={'mobilenet':np.load('/Volumes/UFO-Work/field/model-audit-20261114/features.npy',mmap_mode='r')[d['indices']], 'dinov2':np.load(R/'dinov2-features.npy')}
def metrics(truth,pred,prob=None):
 tp=int(np.sum(truth&pred));fp=int(np.sum(~truth&pred));tn=int(np.sum(~truth&~pred));fn=int(np.sum(truth&~pred));div=lambda a,b:float(a/b) if b else None
 z=dict(tp=tp,fp=fp,tn=tn,fn=fn,recall=div(tp,tp+fn),precision=div(tp,tp+fp),false_positive_rate=div(fp,fp+tn),accuracy=div(tp+tn,len(truth)))
 if prob is not None:
  z.update(average_precision=float(average_precision_score(truth,prob)),brier=float(brier_score_loss(truth,prob)))
  z['ece']=sum(abs(float(np.mean(truth[m]))-float(np.mean(prob[m])))*float(np.mean(m)) for b in range(10) if np.any(m:=(prob>=b/10)&(prob<(b+1)/10 if b<9 else prob<=1)))
 return z
results=[]
for backbone,x in X.items():
 for head in ['linear','nonlinear']:
  for balance in ['class','recording']:
   for seed in [731,947,1201]:
    prob=np.full(len(rows),np.nan);decision=np.zeros(len(rows),bool);thresholds=[]
    for k in range(5):
     te=fold==k;ca=fold==(k+1)%5;tr=(fold>=0)&~te&~ca;trainrows=[r for r,m in zip(rows,tr) if m]
     w=sample_weights(trainrows) if balance=='recording' else np.where(y[tr],len(trainrows)/(2*sum(y[tr])),len(trainrows)/(2*sum(~y[tr])))
     if head=='linear':
      scale=StandardScaler().fit(x[tr]);model=LogisticRegression(C=.5,max_iter=1000,random_state=seed).fit(scale.transform(x[tr]),y[tr],sample_weight=w);pc=model.predict_proba(scale.transform(x[ca]))[:,1];pt=model.predict_proba(scale.transform(x[te]))[:,1]
     else:
      torch.manual_seed(seed);model=ReviewedHead(x[tr].mean(0),np.maximum(x[tr].std(0),.1));a=torch.tensor(x[tr]);t=torch.tensor(y[tr],dtype=torch.float32);wt=torch.tensor(w,dtype=torch.float32);opt=torch.optim.AdamW(model.parameters(),lr=.0005,weight_decay=.01)
      for epoch in range(40):
       model.train();order=torch.randperm(len(a))
       for start in range(0,len(a),1024):
        ids=order[start:start+1024];out=model(a[ids]);loss=(torch.nn.functional.binary_cross_entropy_with_logits(out[:,0]-out[:,1],t[ids],reduction='none')*wt[ids]).mean();opt.zero_grad();loss.backward();opt.step()
      model.eval()
      with torch.inference_mode():pc=model(torch.tensor(x[ca])).softmax(1)[:,0].numpy();pt=model(torch.tensor(x[te])).softmax(1)[:,0].numpy()
     # Calibration fold alone selects highest threshold with >=90% recall.
     threshold=float(np.quantile(pc[y[ca]],.1,method='lower'));thresholds.append(threshold);prob[te]=pt;decision[te]=pt>=threshold
    name=f'{backbone}-{head}-{balance}-{seed}';np.savez_compressed(R/(name+'.npz'),prob=prob,decision=decision)
    result=dict(name=name,backbone=backbone,head=head,balance=balance,seed=seed,thresholds=thresholds,metrics=metrics(y[valid],decision[valid],prob[valid]));results.append(result)
    print(name,json.dumps(result['metrics']),flush=True)
    (R/'ablation-results.json').write_text(json.dumps(dict(scope='Historical development only; selected class/group-balanced cohort, not population or unseen accuracy',samples=int(sum(valid)),excluded_conflicting_pixels=int(sum(~valid)),protocol='five recording/pixel-linked folds; train 3, calibration 1, evaluation 1; threshold targets calibration recall >=90%; each factor varied independently',results=results),indent=2))
print('complete',flush=True)
