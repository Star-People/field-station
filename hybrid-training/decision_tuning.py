"""Conservative tuning on recording-disjoint data never used to fit this model."""
import hashlib,json,math
from pathlib import Path
LABELS={'anomalous','not_anomalous'}

def groups(row):
 values=row.get('group_aliases') or [row.get('generation') or row.get('group','')]
 return {str(v).removeprefix('generation:').removeprefix('machine:') for v in values if v}

def reservations(root):
 path=Path(root)/'decision-tuning/reservations.json'
 return json.loads(path.read_text()) if path.exists() else dict(groups=[],pixels=[])

def allowed_for_training(root,row):
 reserved=reservations(root)
 return not (groups(row)&set(reserved['groups']) or row.get('pixel_sha256') in set(reserved['pixels']))

def fresh(rows,dataset,lane):
 trained_groups=set().union(*(groups(r) for r in dataset.get('samples',[])));pixels={r.get('pixel_sha256') for r in dataset.get('samples',[])};seen=set();result=[]
 for row in rows:
  if row.get('label') not in LABELS or not groups(row) or len(groups(row))!=1:continue
  if lane=='machine' and (row.get('human_confirmed') or row.get('label_source')!='machine'):raise ValueError('Human labels cannot tune Machine-only')
  if lane=='hybrid' and not row.get('human_confirmed'):continue
  if groups(row)&trained_groups or row.get('pixel_sha256') and row['pixel_sha256'] in pixels:continue
  key=row.get('pixel_sha256') or row.get('native_crop_sha256') or row.get('id')
  if key in seen:continue
  seen.add(key);result.append(row)
 return result

def split(rows):
 fit=[];guard=[]
 for row in rows:
  group=next(iter(groups(row)));target=guard if int(hashlib.sha256(group.encode()).hexdigest()[:8],16)%2 else fit;target.append(row)
 return fit,guard

def sufficient(rows):
 return all(sum(r['label']==label for r in rows)>=minimum and len(set().union(*(groups(r) for r in rows if r['label']==label)))>=2 for label,minimum in [('anomalous',10),('not_anomalous',30)])

def measure(rows,settings):
 counts=dict(tp=0,fp=0,tn=0,fn=0)
 for r in rows:
  positive=r['score']>=settings['anomaly_threshold'] and r['native_size']>=settings['minimum_native_size'] and not r.get('suppressed',False)
  truth=r['label']=='anomalous';counts[('t' if positive==truth else 'f')+('p' if positive else 'n')]+=1
 tp,fp,tn,fn=[counts[k] for k in ('tp','fp','tn','fn')];recall=tp/(tp+fn) if tp+fn else 0;fpr=fp/(fp+tn) if fp+tn else 0
 return dict(counts,recall=recall,false_positive_rate=fpr,balanced_accuracy=(recall+1-fpr)/2)

def safe(candidate,baseline):
 return candidate['recall']>=max(.9,baseline['recall']) and candidate['false_positive_rate']<=baseline['false_positive_rate'] and candidate['balanced_accuracy']>=baseline['balanced_accuracy']

def tune(rows,baseline):
 fit,guard=split(rows)
 coverage={name:dict(total=len(part),positive=sum(r['label']=='anomalous' for r in part),negative=sum(r['label']=='not_anomalous' for r in part),recordings=len(set().union(*(groups(r) for r in part))) if part else 0) for name,part in [('tuning',fit),('validation',guard)]}
 if not sufficient(fit) or not sufficient(guard):return dict(accepted=False,state='collecting',coverage=coverage,message='Collecting independent positive and negative examples across recordings.')
 baseline_fit=measure(fit,baseline);best=dict(baseline);best_score=baseline_fit
 # Never relax an unmeasured nighttime context requirement. This first tuner
 # searches threshold and size; qualified context/color policy stays fixed.
 for threshold in sorted({baseline['anomaly_threshold'],.8,.85,.9,.95,.98}):
  if threshold<baseline['anomaly_threshold']:continue
  for size in sorted({baseline['minimum_native_size'],8,10,12,16,24,32}):
   candidate=dict(baseline,anomaly_threshold=threshold,minimum_native_size=size);result=measure(fit,candidate)
   if safe(result,baseline_fit) and result['balanced_accuracy']>best_score['balanced_accuracy']:
    best=candidate;best_score=result
 baseline_guard=measure(guard,baseline);candidate_guard=measure(guard,best)
 accepted=best!=baseline and safe(candidate_guard,baseline_guard)
 return dict(accepted=accepted,state='tuned' if accepted else 'retained',values=best if accepted else baseline,coverage=coverage,baseline_tuning=baseline_fit,tuning=best_score,baseline_validation=baseline_guard,validation=candidate_guard,independent_groups=True,message='Validated automatic settings applied.' if accepted else 'Current settings retained; no validated improvement without losing anomaly recall.')

def training_filter(root):
 value=reservations(root);reserved_groups=set(value['groups']);reserved_pixels=set(value['pixels'])
 return lambda row:not (groups(row)&reserved_groups or row.get('pixel_sha256') in reserved_pixels)
