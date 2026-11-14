# Human model audit — November 14, 2026

The two human profiles retain shared learned weights and independent decision settings. The new artifact uses frozen native RGB MobileNetV3 Small features and a standardized 64-unit ReLU classifier, trained with dropout 0.25 and AdamW for 40 epochs. The human-only recipe uses square-root recording balancing, equal total class budgets, and duplicate-aware weights. Human labels and original images are preserved. Exact-pixel conflicting labels are excluded from fitting, not silently relabeled or deleted. Legacy non-human seed examples do not fit this head.

`human_nonlinear_v1` is selected in the HQ training configuration. Native extraction uses one original view, matching the complete review image. Stable threshold is 0.78; Experimental is 0.85, with the manual color bonus disabled for both. The learned model still processes RGB color. Scheduled training remains disabled.

## Evidence

Audited 105,608 unchanged reviewed images: 104,440 negatives and 1,168 positives. Four records with two contradictory pixel hashes were excluded from final fitting. The evaluated corpus is heavily correlated within recordings; frame counts do not imply independent observations.

| Profile | False-positive rate | Recall | Precision | Accuracy |
| --- | ---: | ---: | ---: | ---: |
| Previous Stable | 1.6287% | 83.3048% | 36.3874% | 98.2047% |
| New Stable (0.78) | 0.6894% | 95.2055% | 60.6987% | 99.2652% |
| New Experimental (0.85) | 0.4902% | 92.8082% | 67.9198% | 99.4356% |

These are full training-corpus replays, **not unseen-footage accuracy**. Native replay of the exported model differed from feature-space predictions by at most 0.000001133.

A separate recording-group split used 63,294 fitting, 21,249 calibration, and 21,065 test rows, with exact-pixel overlap purged from fitting. Architecture/epoch/threshold selection used calibration, not test. On that test partition, the nonlinear recipe achieved FP 0.7995%, recall 66.6667%, precision 41.4035%, accuracy 98.9271%. The original linear architecture fitted on the same human-only partition achieved FP 1.8671%, recall 63.2768%, precision 22.3108%, accuracy 97.8400%. This reference excludes legacy seed data and augmentation from both sides; it is an architecture/recipe experiment, not a reproduction of every incumbent training detail. Exploratory tests reused a finite historical corpus; fresh prospective review remains necessary.

The existing deployed classifier had already seen the test partition, so its test results cannot be used as an unseen-data comparison against the newly fitted experimental recipes.

## Machine-only lesson

On the paired full corpus, Machine-only rejected 1,286 negative examples that Stable incorrectly flagged, but also missed 488 positives Stable caught. Reviewed-live cohorts sometimes show 0% FP with no positive reviews (recall undefined). These measurements justify mining *human-confirmed* hard negatives, not replacing human labels with machine guesses or vetoing every disagreement.

## Operations

New artifact: `185750ddef1dd230761e83b84aaca5482cdcba0aa573f190634f154890650ebf`.

Full reproducible scripts, predictions, feature checksums, contact sheets, validation partitions, reports, and deployment receipts are on HQ external storage at `/Volumes/UFO-Work/field/model-audit-20261114/`. The prior live model is retained. Deployment requires native probability/latency checks and sustained advancing recognition before release publication.
