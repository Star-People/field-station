"""Evidence metrics with explicit support; missing evidence is never a perfect score."""
import math

def ratio(a,b):return a/b if b else None

def counts(rows):
 out=dict(tp=0,fp=0,tn=0,fn=0,unreviewed=0)
 for r in rows:
  truth=r.get('truth');pred=r.get('prediction')
  if truth not in ('anomalous','not_anomalous') or pred not in ('anomalous','not_anomalous'):out['unreviewed']+=1;continue
  positive=pred=='anomalous';out[('t' if truth==pred else 'f')+('p' if positive else 'n')]+=1
 tp,fp,tn,fn=[out[k] for k in ('tp','fp','tn','fn')]
 return dict(out,recall=ratio(tp,tp+fn),precision=ratio(tp,tp+fp),false_positive_rate=ratio(fp,fp+tn),accuracy=ratio(tp+tn,tp+fp+tn+fn))

def event_metrics(events,coverage_seconds,coverage_complete=False,positive_event_audit_complete=False):
 """One independently identified event per row, not one crop per event.
 Event IDs must come from audited tracking/session identity, not guessed similarity.
 """
 ids=[r.get('event_id') for r in events]
 if None in ids or len(set(ids))!=len(ids):raise ValueError('Unique audited event IDs required')
 if not math.isfinite(coverage_seconds) or coverage_seconds<0:raise ValueError('Invalid coverage')
 m=counts(events);hours=coverage_seconds/3600
 complete=coverage_complete and not m['unreviewed']
 return dict(counts=m,observed_camera_hours=hours,known_false_alerts_per_observed_hour=ratio(m['fp'],hours),false_alerts_per_camera_hour=ratio(m['fp'],hours) if complete else None,event_recall=m['recall'] if positive_event_audit_complete else None,complete_alert_review=complete,missed_event_audit_complete=positive_event_audit_complete)

def temporal_evidence(observations):
 """Descriptive track evidence only. Never suppress or relabel an alert."""
 usable=[r for r in observations if not r.get('ambiguous_link') and not r.get('source_discontinuity')]
 usable=[dict(r,velocity_pixels_per_second=math.hypot(*r['velocity_pixels_per_second'])) if isinstance(r.get('velocity_pixels_per_second'),(list,tuple)) and len(r['velocity_pixels_per_second'])==2 else r for r in usable]
 speeds=[float(r['velocity_pixels_per_second']) for r in usable if isinstance(r.get('velocity_pixels_per_second'),(int,float)) and math.isfinite(r['velocity_pixels_per_second'])]
 return dict(observations=len(observations),usable_observations=len(usable),mean_speed_pixels_per_second=sum(speeds)/len(speeds) if speeds else None,max_speed_pixels_per_second=max(speeds) if speeds else None,ambiguous=any(r.get('ambiguous_link') for r in observations),capture_control=False,classification_control=False,qualification='descriptive_only')

def bootstrap_intervals(rows,replicates=2000):
 import numpy as np
 grouped={}
 for r in rows:
  if not r.get('group'):raise ValueError('Recording groups required for uncertainty')
  m=counts([r]);v=grouped.setdefault(r['group'],np.zeros(4))
  v+=np.array([m[k] for k in ['tp','fp','tn','fn']])
 if len(grouped)<2:return dict(recordings=len(grouped),intervals=None,reason='At least two independent recordings required')
 values=np.array([grouped[g] for g in sorted(grouped)]);rng=np.random.default_rng(411);samples=values[rng.integers(0,len(values),size=(replicates,len(values)))].sum(1);tp,fp,tn,fn=samples.T;result={};unresolved={}
 for name,num,den in [('recall',tp,tp+fn),('precision',tp,tp+fp),('false_positive_rate',fp,fp+tn),('accuracy',tp+tn,tp+fp+tn+fn)]:
  valid=den>0;result[name]=[float(v) for v in np.quantile(num[valid]/den[valid],[.025,.975])] if valid.any() else None
  if result[name] and result[name][0]==result[name][1]:result[name]=None;unresolved[name]='Degenerate cluster resamples cannot establish a confidence bound; no claim of zero unseen error risk'
 return dict(recordings=len(grouped),replicates=replicates,method='recording-cluster percentile bootstrap',intervals=result,unresolved=unresolved)
