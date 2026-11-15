import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from station_location import location_at,display_label

class LocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'station-location').mkdir()
        self.db = sqlite3.connect(self.root/'station-location/history.sqlite')
        self.addCleanup(self.db.close)
        self.db.execute('CREATE TABLE fixes(sampled_epoch REAL PRIMARY KEY,valid_until REAL,status TEXT,county TEXT,state TEXT,country TEXT)')
    def fix(self, epoch=1000, status='known', county='Example County', until=None):
        self.db.execute('INSERT INTO fixes VALUES(?,?,?,?,?,?)',(epoch,until or epoch+180,status,county,'CA','US'))
        self.db.commit()
    def test_only_county_fields_leave_provider(self):
        self.fix()
        self.assertEqual(location_at(self.root,1001),dict(status='known',precision='county',county='Example County',state='CA',country='US',source='macos_location_services'))
    def test_no_backfill_or_unbounded_stale_fix(self):
        self.fix(until=100000)
        for epoch in (999,1180,100000):self.assertEqual(location_at(self.root,epoch)['status'],'unknown')
    def test_moving_station_does_not_relabel_history(self):
        self.fix();self.fix(1100,county='Second County')
        self.assertEqual(location_at(self.root,1050)['county'],'Example County')
        self.assertEqual(location_at(self.root,1150)['county'],'Second County')
    def test_failure_invalidates_previous_location(self):
        self.fix();self.fix(1050,status='unknown')
        self.assertEqual(location_at(self.root,1060)['status'],'unknown')
    def test_missing_or_corrupt_store_never_stops_capture(self):
        self.assertEqual(location_at(self.root/'missing',1001)['status'],'unknown')
        self.db.execute('DROP TABLE fixes');self.db.commit()
        self.assertEqual(location_at(self.root,1001)['status'],'unknown')
    def test_invalid_epochs_do_not_mean_current_location(self):
        for epoch in (None,0,-1,float('nan'),float('inf'),'1000',True):self.assertEqual(location_at(self.root,epoch)['status'],'unknown')
    def test_malformed_geographic_name_is_not_exported(self):
        self.fix(county='County\nStreet address')
        self.assertEqual(location_at(self.root,1001)['status'],'unknown')
    def test_display_format_and_unknown(self):
        self.assertEqual(display_label(dict(status='known',county='San Mateo County',state='CA',country='US')),'San Mateo, CA, USA')
        self.assertEqual(display_label(dict(status='unknown')),'')

if __name__=='__main__':unittest.main()
