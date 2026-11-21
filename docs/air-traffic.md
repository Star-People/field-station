# Air traffic context

The private camera feed shows a north-up ADS-B aircraft plot. Arrows indicate reported **ground track**, not the aircraft's nose orientation. Missing track data renders as a dot. Hover or tap for callsign, aircraft type, pressure altitude in feet, speed in knots, and track.

Settings → Radar center address defaults to the Stanford Dish (37.4083, -122.179). This is an operator-selected radar reference, not the automatic county-only station location. Address resolution uses OpenStreetMap Nominatim only on explicit Save; no autocomplete. The entered address and resolved point stay in the private station settings. The geocoder receives the entered address; the traffic provider receives the configured query point. The radar queries a 75 nautical-mile radius.

The collector polls https://opendata.adsb.fi/api/v3/lat/{lat}/lon/{lon}/dist/{distance} every 15 seconds, with exponential error backoff, Retry-After handling, and an hour pause for rejected configuration/authentication. See https://github.com/adsbfi/opendata for provider terms and limits. Data is attributed to adsb.fi and is for private, non-commercial analysis. It is not added to Internet Archive or public snapshots. Public redistribution would need a suitable provider license. Nominatim policy: https://operations.osmfoundation.org/policies/nominatim/.

Aircraft positions older than 30 seconds and known ground traffic are excluded. Feed timestamps are validated. Stale/unavailable data is explicitly shown and does not leave stale arrows on screen. Zero reports is not evidence that the airspace is empty: coverage depends on transponders and receiving stations. No automatic classification or training-label changes are made.

On detection creation, a bounded local database read records the latest preceding traffic sample within 30 seconds in `air-traffic.private.json`, next to that detection's event file. Review video → Air traffic at detection time shows that retained context. Historical detections without contemporaneous samples remain unavailable; current traffic is never substituted. This is regional context, not a geometrical match to the camera's field of view.

Storage is `<field-working-volume>/air-traffic`: private settings, current status, and compressed SQLite history, limited to 72 hours and 64 MiB of compressed payload (SQLite has additional overhead and reuses pages). Retained per-detection context is independent of the rolling history. Collection never participates in capture/video locks, and network calls never occur inside detection creation or review reads.

Install persistently with the station Python:

```
python scripts/install_air_traffic.py --root /Volumes/UFO-Field-Working-Files
```

Changes to `recognition_alerts.py` require reloading the recognition worker; the camera/recording worker need not restart. All new API routes require the private station token; public snapshot UI does not load the module.
