import unittest,tempfile,json
from pathlib import Path
from decision_tuning import fresh,split,tune,measure,safe,training_filter
class TuningTests(unittest.TestCase):
 def row(self,group,label,score):return dict(generation=group,label=label,score=score,native_size=20,human_confirmed=True,id=group+label+str(score))
 def test_group_aliases_and_pixels_exclude_training_leaks(self):
  rows=[dict(self.row('run-a','anomalous',.9),pixel_sha256='p1'),dict(self.row('run-b','not_anomalous',.1),pixel_sha256='p2'),dict(self.row('run-c','anomalous',.9),pixel_sha256='p3')]
  dataset={'samples':[{'group_aliases':['machine:run-a'],'pixel_sha256':'p2'}]}
  self.assertEqual([r['generation'] for r in fresh(rows,dataset,'hybrid')],['run-c'])
 def test_machine_rejects_human_labels(self):
  with self.assertRaises(ValueError):fresh([self.row('run-a','anomalous',.9)],{},'machine')
 def test_split_never_shares_a_recording(self):
  rows=[self.row('run-'+str(i//10),'anomalous',.9) for i in range(200)];a,b=split(rows);self.assertFalse({r['generation'] for r in a}&{r['generation'] for r in b})
 def test_all_negative_policy_fails_recall_guard(self):
  rows=[self.row('a','anomalous',.9),self.row('b','not_anomalous',.85)];baseline=measure(rows,dict(anomaly_threshold=.8,minimum_native_size=8));candidate=measure(rows,dict(anomaly_threshold=.99,minimum_native_size=8));self.assertFalse(safe(candidate,baseline))
 def test_insufficient_data_retains_settings(self):
  self.assertEqual(tune([self.row('a','not_anomalous',.9)],dict(anomaly_threshold=.8,minimum_native_size=8))['state'],'collecting')
 def test_independent_validation_can_accept_improvement(self):
  rows=[]
  for i in range(20):
   for j in range(20):rows.append(self.row('run-'+str(i),'anomalous' if j<5 else 'not_anomalous',.99 if j<5 else .85))
  result=tune(rows,dict(anomaly_threshold=.8,minimum_native_size=8));self.assertTrue(result['accepted']);self.assertEqual(result['validation']['recall'],1);self.assertEqual(result['validation']['false_positive_rate'],0)
 def test_reserved_groups_never_enter_future_training(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'decision-tuning';p.mkdir();(p/'reservations.json').write_text(json.dumps(dict(groups=['run-a'],pixels=['p1'])));allowed=training_filter(d);self.assertFalse(allowed({'group':'machine:run-a'}));self.assertFalse(allowed({'generation':'run-b','pixel_sha256':'p1'}));self.assertTrue(allowed({'generation':'run-b','pixel_sha256':'p2'}))
