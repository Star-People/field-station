# Public Field Station snapshot

`https://data.starpeople.ai` serves the Field Station's public, read-only interface from GitHub Pages. HQ exports the latest UI, detection records, existing model classifications, model inspection data, metrics, RF snapshot, and a saved camera frame. All views explicitly show their snapshot timestamp; no capture, radio transmission, review mutation, training, or administration endpoint is deployed.

The exporter removes credentials, private filesystem paths, reviewer links and precise coordinates. Images are derived from the verified HQ training-frame mirror, resized to at most 320×320 and written without EXIF. Missing frames are fetched individually from the field station, never video files. Internet Archive links stay attached to verified public observations.

Runtime files and generated data live on the HQ external SSD at `/Volumes/UFO-Work/services/public-data-snapshot`. The launchd job `ai.starpeople.public-data-snapshot` runs `worker.py` every 15 minutes and at login. Overlapping refreshes are prevented by an advisory lock. An incomplete/offline cycle leaves the last published site available. The status JSON records the last success and retry state.

The generated branch contains only the newest snapshot, with a lease-protected replacement so it cannot overwrite another publisher’s work. Old generated Git objects are reclaimed locally. Only the generated `public-snapshot` branch is published; application source remains on `main`. A complete site must remain below 800 MiB with zero missing thumbnail files before publication. The static adapter supports the same review/classification/starred filters and 100-item pagination without calling the private station from visitors' browsers. Manual video content remains on its existing field/Archive storage.

Tests: `python -m unittest discover -s public-access -v` and `python -m unittest discover -s public-snapshot -v`, plus browser checks of all four views, filters, pagination, image loading, disabled write controls, and direct POST rejection.
