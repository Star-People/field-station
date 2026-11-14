# Model research — 2026-11-14

## Decision

Keep the current deployed MobileNet nonlinear model. DINOv2 is a useful challenger, not an across-the-board upgrade. Do not promote on these historical results.

## Controlled experiment

6,175 selected reviewed RGB crops: all 1,168 positives and at most 40 negatives per recording. Both backbones see identical images. Five recording/pixel-linked folds rotate through three fitting folds, one threshold-selection fold, and one evaluation fold. Thresholds target 90% calibration recall. Three seeds per recipe; deterministic linear fits repeat identically and are not three independent observations.

These are historical development results on a sampled population. They are neither live error rates nor untouched test accuracy. Reusing old recordings and choosing a recipe after seeing this table limits inferential claims.

| Backbone | Head | Weighting | FP rate | Recall | Precision | Accuracy | AP |
|---|---|---|---:|---:|---:|---:|---:|
| mobilenet | linear | class | 13.10% | 82.71% | 59.56% | 86.11% | 85.75% |
| mobilenet | linear | recording | 12.54% | 82.71% | 60.60% | 86.56% | 85.96% |
| mobilenet | nonlinear | class | 10.96% | 83.28% | 63.94% | 87.95% | 88.81% |
| mobilenet | nonlinear | recording | 9.32% | 82.76% | 67.44% | 89.18% | 88.96% |
| dinov2 | linear | class | 11.00% | 85.79% | 64.52% | 88.39% | 87.26% |
| dinov2 | linear | recording | 10.41% | 84.85% | 65.54% | 88.70% | 87.80% |
| dinov2 | nonlinear | class | 9.19% | 80.74% | 67.21% | 88.90% | 84.83% |
| dinov2 | nonlinear | recording | 8.46% | 80.39% | 68.91% | 89.43% | 86.45% |

Lower FP alone is insufficient: DINOv2 nonlinear improves FP but loses recall against MobileNet nonlinear. Calibration thresholds also vary sharply by recording fold, indicating distribution shift. The published JSON includes raw confusion counts, Brier scores, calibration error, fold thresholds and group-bootstrap uncertainty.

## Prospective protocol

All historical manifests are registered as exposed. New recording groups are assigned label-blind: 20% reserved, 80% eligible for development. Exact-pixel and recording links connect partitions. A connection between already reserved and exposed evidence quarantines the connected component; it cannot be called an independent test. Missing provenance is withheld from fitting. Source images and human labels are preserved. All four trainers enforce the same registry.

A continuously running original generation remains development data. Truly new recording groups are required; renaming old data does not make it independent. Holdout scoring must also establish original capture time after the protocol boundary before being described as prospective. No such fresh reviewed cohort exists yet.

## Event and temporal evidence

The read-only observer measures contiguous processed-frame intervals and motion-track summaries. Gaps remain unobserved, not assumed healthy. It records no video and cannot suppress a detection or activate a model. Temporal features remain descriptive until qualified against independent event truth.

False alerts per camera-hour requires complete alert review over measured coverage. Event recall also needs an independent missed-event audit; reviewing only detections cannot measure objects never proposed. These values remain null until those conditions are met, rather than showing a fabricated zero.

## Remaining evidence requirements

1. Fresh independent recordings with positive and negative human-reviewed events, spanning day and night.
2. An independent audit of sampled continuous footage to establish missed events and proposal-stage recall.
3. Freeze each challenger artifact, preprocessing, decision settings and evaluation protocol before opening the confirmatory cohort.
4. Compare paired recording/event outcomes with uncertainty; retain runtime/export parity and sustained-load checks before any live replacement.

These are external evidence requirements, not claims that a more complex model has already solved detection. The current manual Train now activation rule remains unchanged.

## Operational verification

The four-profile full training replay completed on 105,604 images with no exclusions. The separate frozen-profile integration test scored eight historical fixture images through all four native profiles and the DINOv2 challenger; this smoke test is not independent evidence. The new research observer is installed as `app.ufo-files.model-research`, running once per minute on HQ. Its state and confirmatory report live under `/Volumes/UFO-Work/field/research-v1/`. Native package digests, decision settings, transformer digest and the linear challenger are frozen in `frozen-comparison.json`. Frozen artifacts and the holdout registry have a separate-drive backup under `/Volumes/UFO-Training/model-research-backup/`.

The standard CI environment tests data admission without requiring PyTorch. A separate GitHub-hosted Linux CPU job installs PyTorch and runs the neural learning test. The research collector is installation-specific: its paths refer to this HQ/field deployment; it is not a general installer.

Validation: 818 Python regression tests passed in the clean staged checkout (with environment-appropriate skips), along with the JavaScript checks invoked by the suite. The separate neural learning test passed. Three additional uncertainty/temporal tests passed after that run. Research inference runs in a separate low-priority 15-minute job, with 32-image native and 16-image transformer batches. Coverage collection runs every minute.
