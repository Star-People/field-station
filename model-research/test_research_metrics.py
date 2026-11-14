import unittest
from research_metrics import counts,event_metrics,temporal_evidence,bootstrap_intervals
class Metrics(unittest.TestCase):
 def test_absent_positives_not_perfect_recall(self):self.assertIsNone(counts([dict(truth='not_anomalous',prediction='not_anomalous')])['recall'])
 def test_incomplete_denominator_not_claimed(self):
  m=event_metrics([dict(event_id='1',truth='not_anomalous',prediction='anomalous')],3600)
  self.assertEqual(m['known_false_alerts_per_observed_hour'],1);self.assertIsNone(m['false_alerts_per_camera_hour']);self.assertIsNone(m['event_recall'])
 def test_unreviewed_alerts_block_complete_claim(self):self.assertIsNone(event_metrics([dict(event_id='1',prediction='anomalous')],3600,True)['false_alerts_per_camera_hour'])
 def test_duplicate_events_rejected(self):
  with self.assertRaises(ValueError):event_metrics([dict(event_id='1'),dict(event_id='1')],3600)
 def test_no_temporal_veto(self):self.assertFalse(temporal_evidence([dict(ambiguous_link=True,velocity_pixels_per_second=99)])['classification_control'])
 def test_vector_velocity(self):self.assertEqual(temporal_evidence([dict(velocity_pixels_per_second=[3,4])])['mean_speed_pixels_per_second'],5)
 def test_perfect_observations_do_not_prove_zero_risk(self):
  rows=[dict(group=g,truth='not_anomalous',prediction='not_anomalous') for g in ['one','two','three']]
  result=bootstrap_intervals(rows,100);self.assertIsNone(result['intervals']['false_positive_rate']);self.assertIsNone(result['intervals']['recall'])
 def test_one_recording_cannot_estimate_recording_variance(self):self.assertIsNone(bootstrap_intervals([dict(group='one',truth='anomalous',prediction='anomalous')])['intervals'])
if __name__=='__main__':unittest.main()
