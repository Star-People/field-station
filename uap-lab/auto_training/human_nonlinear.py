"""Human-reviewed nonlinear classifier, qualified by the 2026-11-14 grouped audit.
All feature extraction uses the native Vision path. Human labels are never changed.
"""
from collections import Counter,defaultdict
import numpy as np
import torch
from torch import nn
ARCHITECTURE='MobileNetV3 Small frozen RGB features + normalized 64-unit nonlinear human-reviewed classifier'
THRESHOLD=.78

def select_rows(rows):
    human=[r for r in rows if r.get('human_confirmed') and r.get('split')=='train']
    labels=defaultdict(set)
    for r in human:labels[r['pixel_sha256']].add(r['label'])
    conflict={p for p,v in labels.items() if len(v)>1}
    return [r for r in human if r['pixel_sha256'] not in conflict],sorted(conflict)

def sample_weights(rows):
    groups=Counter((r['label'],r['group']) for r in rows)
    copies=Counter((r['label'],r['pixel_sha256']) for r in rows)
    weights=np.array([groups[(r['label'],r['group'])]**(-.5)/copies[(r['label'],r['pixel_sha256'])] for r in rows])
    for label in {r['label'] for r in rows}:
        mask=np.array([r['label']==label for r in rows]);weights[mask]*=len(rows)/2/weights[mask].sum()
    return weights

class ReviewedHead(nn.Module):
    def __init__(self,mean,std,width=64):
        super().__init__();self.register_buffer('mean',torch.as_tensor(mean,dtype=torch.float32));self.register_buffer('std',torch.as_tensor(std,dtype=torch.float32))
        self.layers=nn.Sequential(nn.Linear(len(mean),width),nn.ReLU(),nn.Dropout(.25),nn.Linear(width,1))
    def forward(self,x):
        z=self.layers((x-self.mean)/self.std)
        return torch.cat((z/2,-z/2),dim=1)

def fit_head(x,rows,classes,progress=None):
    if classes!=['anomalous','not_anomalous']:raise ValueError('Nonlinear human recipe requires the binary class order')
    if len(x)!=len(rows) or not all(r.get('human_confirmed') for r in rows):raise ValueError('Human-only native rows required')
    if {r['label'] for r in rows}!=set(classes):raise ValueError('Both reviewed classes required')
    torch.manual_seed(731);mean=np.mean(x,axis=0);std=np.maximum(np.std(x,axis=0),.1)
    head=ReviewedHead(mean,std);normalized=torch.tensor(x,dtype=torch.float32)
    target=torch.tensor([r['label']=='anomalous' for r in rows],dtype=torch.float32);weights=torch.tensor(sample_weights(rows),dtype=torch.float32)
    optimizer=torch.optim.AdamW(head.parameters(),lr=.0005,weight_decay=.01)
    for epoch in range(1,41):
        head.train();order=torch.randperm(len(rows))
        for start in range(0,len(rows),1024):
            ids=order[start:start+1024];out=head(normalized[ids]);loss=(nn.functional.binary_cross_entropy_with_logits(out[:,0]-out[:,1],target[ids],reduction='none')*weights[ids]).mean()
            optimizer.zero_grad();loss.backward();optimizer.step()
        if progress:progress(epoch,40)
    return head.eval()
