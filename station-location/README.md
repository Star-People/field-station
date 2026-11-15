# Automatic county-only observation location

The station Mac—not the reviewing browser—uses macOS Location Services and
Apple reverse geocoding to resolve county, state/region, and country. The helper
retains no coordinates, street addresses, postcodes, raw placemarks, or error
descriptions. Coordinates are transient in the OS/location/geocoder path;
Apple supplies the location and geocoding services. This does not change Apple's
own operating-system privacy behavior or imply that coordinates never reach Apple.

Every minute the helper requests a fresh fix. Fixes older than 60 seconds,
accuracy worse than 1 km, or reported travel speed of 3 m/s or more are rejected.
Failed lookups invalidate the last known result. A previously successful result
expires after at most three minutes if the helper stops. County resolution is
approximate; near a boundary it may be uncertain. No IP/VPN geolocation fallback
is used, and no precise location appears in the web API or public bundles.

Coarse fixes live in `STATION_ROOT/station-location/history.sqlite` on the data
drive. Indexed capture-time queries never use a later fix for an earlier event.
Detections carry their capture-time county; recording/bundle metadata explicitly
uses `location_scope: session_start` (not a claim that a long mobile recording
stayed in one county). Training exports include location only where known,
preserving fingerprints of historical unknown-location data. Existing captures
are not assigned the current location retrospectively.

Settings displays the coarse location read-only. Permission is controlled by
macOS Privacy & Security → Location Services → Field Station Location. Revoking
access makes location unknown; camera operation does not depend on it. Day/night
scheduling is unchanged; this feature does not replace its sunrise reference.

Install on the station's logged-in macOS account (Xcode command-line tools needed):

```sh
python3 station-location/install.py --station-root /Volumes/UFO-Field
```

Approve the macOS location prompt once. The signed helper runs at login and is
restarted by launchd if it exits; it does not run before the account logs in.
Reload the web/capture/recognition services after installing the accompanying
Python changes, waiting for any active manual recording to finish first.

Validation: `python3 -m unittest discover -s uap-lab -p test_station_location.py`.

The camera viewer and YouTube broadcast display `San Mateo, CA, USA` (for example)
in the lower-left corner. Labels share the existing RF adaptive palette, refresh
automatically, and disappear when location is unknown. `/api/location` is a
read-only, coarse-field allowlisted endpoint, also available in the public viewer.
