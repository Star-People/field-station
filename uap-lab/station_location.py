"""Capture-time county/state only. Never accept or persist coordinates or addresses."""
import math
import sqlite3
import time
from pathlib import Path


def unknown():
    return {'status': 'unknown', 'precision': 'county'}


def display_label(location):
    if location.get('status') != 'known':
        return ''
    county = location['county']
    if location.get('country') == 'US' and county.endswith(' County'):
        county = county[:-7]
    return ', '.join((county, location['state'], 'USA' if location['country'] == 'US' else location['country']))


_NOW = object()


def location_at(root, epoch=_NOW):
    """No forward/back filling: use only a fresh fix preceding this capture."""
    epoch = time.time() if epoch is _NOW else epoch
    if type(epoch) not in (int, float) or not math.isfinite(epoch) or epoch <= 0:
        return unknown()
    path = Path(root) / 'station-location/history.sqlite'
    db = None
    try:
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=.05)
        row = db.execute('SELECT sampled_epoch,valid_until,status,county,state,country '
                         'FROM fixes WHERE sampled_epoch<=? ORDER BY sampled_epoch DESC LIMIT 1',
                         (epoch,)).fetchone()
        if not row or row[2] != 'known' or not row[0] <= epoch < min(row[1], row[0]+180):
            return unknown()
        if not all(isinstance(v, str) and 0 < len(v.strip()) <= 120 and not any(ord(c)<32 for c in v) for v in row[3:]):
            return unknown()
        # Deliberate allowlist. Never return database records wholesale.
        return dict(status='known', precision='county', county=row[3], state=row[4], country=row[5],
                    source='macos_location_services')
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return unknown()
    finally:
        if db is not None:
            db.close()
