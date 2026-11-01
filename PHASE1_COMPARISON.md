# Phase 1 compared with the current Phase 2

This comparison treats the old slides as the earlier presentation, not as newly verified experimental evidence. The current 15-slide deck uses the latest raw tables.

| Topic | Earlier Phase 1 slides | Current Phase 2 evidence | Current slide |
|---|---|---|---|
| Problem and setting | Background and 4 rooms / 1 animal / 4 cameras, slides 2–4 | Same problem and setting | 2 |
| Behavior definitions | Walk, Climb, Eat, Rest, Other, Not identifiable, slides 6–7 | Target definitions retained. Trained pilot supports Walking and Feeding, with Unknown | 3 |
| Dataset | Slides 5/8 describe 22 clips, 537 observations and May 2026 recordings | Current run samples 31 long videos with April 2026 filename times. These are different data and units | 4, 9 |
| Observation conditions | Visibility, lighting, camera, zone and occluder, slides 7–8 | Camera, source, offset and uncertainty are retained. Calibrated zones / complete occluder labels are not established | 3, 9, 14 |
| Detector | Background subtraction, Otsu, morphology and last-seen design, slides 11/15 | Pretrained MegaDetector V5A animal proposals | 5, 7 |
| Behavior features | Motion, centroid displacement, zone, shape, slide 12 | 18 full-frame Farneback / frame-difference features for RF. Additional bbox motion is a separate proxy | 5–6, 12 |
| Classifier | Ordered rules and 6-second median design, slide 13 | Random Forest with 200 trees. No validated Resting / Climbing model | 6 |
| Multiple cameras | Proposed room-aware selection and synchronization, slides 16–17 | Nominal-time fusion with spot-checked clocks. Full room assignment is not validated | 9 |
| Main results | Old figures are not transferred into the current results | 53 Walking, 9 Feeding, 286 Unknown over 348 fused sampled times | 10 |
| Accuracy | Slide 14 reports 96.3% Rest-vs-Active | No independently verified current multi-class accuracy. The 96.3% is not reused | 13 |
| Visual output | Proposed / shown timeline, position heatmap, budget and room use, slides 16–18 | Sampled hourly results and additional detected-position density. No whole-day time budget or validated room-use duration | 11–12 |
| Review access | Earlier checklist / pipeline description | Code, annotation register, raw tables, workflow report and question-to-evidence links | 14 |

The current deck has **15 slides**. It includes the earlier project context, definitions and pipeline continuity without repeating unsupported old result figures. It has no separate “Next evidence needed” slide. Material limits appear alongside the results they qualify.
