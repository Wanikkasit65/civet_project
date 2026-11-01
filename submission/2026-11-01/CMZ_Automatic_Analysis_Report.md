# CMZ Phase 2: automatic analysis report

## Result and evidence scope

The historical run processed 1,319 two-second camera windows from all 31 discovered unique videos across A01-A04. These videos contain 109.841925 camera-hours, including overlapping views of one animal. Only 2,638 camera-seconds (43.97 camera-minutes, approximately 0.67%) were sampled. Shared filename-clock times produced 348 nominal fused sample points. Camera clocks have only been spot-checked.

| Historical model proposal | Fused sample points | Share of 348 |
|---|---:|---:|
| Walking | 53 | 15.23% |
| Feeding | 9 | 2.59% |
| Unknown | 286 | 82.18% |
| Total | 348 | 100.00% |

Active proposals total 62/348 (17.82%). Verified Inactive is unavailable, not zero. Of the Unknown points, 198 meet the conditional four-camera no-detection rule. This is a possible-shelter assumption, not observed sleeping. Per-camera counts are 53 Walking, 10 Feeding and 1,256 Unknown, with denominator 1,319. Counts across cameras and fused time points use different units.

## Workflow actually executed

1. Inventory original video filenames, camera IDs, duration and file identity. Preserve original bytes.
2. Decode using FFmpeg presentation timestamps to avoid known nominal-frame-rate timing problems.
3. Retain the nine existing reviewed clips. Extract 37 two-second training segments: 30 Feeding and 7 Walking. Preserve the original annotation register and its unresolved source-offset mapping.
4. Resize full frames to 96 x 96 grayscale. Calculate six motion/difference measures, then their mean, standard deviation and 90th percentile to obtain 18 features.
5. Train a Random Forest with 200 trees, maximum depth 8, minimum two samples per leaf, balanced class weights and random seed 42. MegaDetector V5A supplies animal-presence proposals separately.
6. Select one reproducible two-second nominal window per five-minute stratum in the historical run. Keep ambiguous cases as Unknown. Fuse matching nominal times conservatively across available cameras.
7. Export camera-window, per-video, fused-time and hourly tables. Recompute all four table families and verify their totals.
8. Run the additional automatic evidence pass, record frame boxes, detection coverage, image-plane movement proxies and source offsets. Preserve this separate cohort.
9. Compare raw images, detector input scale, CLAHE and gamma adjustment on the same deterministically selected saved images. Record every result, including failures to improve.
10. Produce the report, 15-slide presentation, requirement map and quick-access Markdown guide. Publish source and non-video evidence for review.

## Additional automatic pass

The completed additional pass processed 77/77 planned windows with 0 errors. It evaluated 548 detector frames and produced animal proposals in 10 frames at threshold 0.4. Cohort behavior counts: `{"additional_systematic_windows": {"Unknown": 24}, "saved_convenience_audit": {"Unknown": 53}}`. Movement-proxy counts: `{"Unknown": 76, "Moving proposal": 1}`.

This pass covers 53 previously saved convenience audit clips plus 24 eight-second systematic windows from the separately fetched original A03_20260405105417.mp4 (719.067 seconds). It does not reprocess all 31 original videos. Some saved audit clips already contain ROI outlines from the earlier export. Its reconstructed RF model uses the encoded reviewed clips and is distinct from the historical saved model. Short saved audit videos can end at 1.75 seconds. The classifier still uses two-second feature intervals, accepting at least five available temporal frames. Longer tracking windows require agreement across their feature intervals.

MegaDetector V5A uses a 640-pixel input in this additional pass. Bounding-box detection checks run at approximately 2 fps, while motion features use approximately 4 fps. No additional human labels were created. All new outputs remain machine proposals. The image-position density plot counts detected centroids and cannot establish room occupancy, dwell time or welfare.

## Image improvement experiment

Saved audit stills contain pre-existing red ROI outlines and compression. Here raw means no additional photometric transform of the saved image, not a clean original frame. This limits interpretation of detector sensitivity and prevents accuracy claims. Twelve images were selected before enhancement: four from each historical proposal stratum (Walking, Feeding, Unknown), ordered by SHA-256 of filename. The same images were processed in all variants. Threshold 0.4 matches the additional pass; 0.2 provides a sensitivity comparison.

| Variant | Detector input | Images with animal proposal at 0.4 | At 0.2 |
|---|---:|---:|---:|
| raw | 640 | 1/12 | 3/12 |
| raw | 1280 | 9/12 | 9/12 |
| clahe | 1280 | 8/12 | 9/12 |
| gamma_0.7 | 1280 | 9/12 | 9/12 |

Upscaling changes the detector's effective object scale without restoring lost details. CLAHE adjusts local luminance contrast with clip limit 2.0 and an 8 x 8 tile grid. Gamma 0.7 brightens the input. More detections or larger scores can include false positives, so these counts do not measure accuracy. On this exploratory set, larger input increased proposal counts while CLAHE and gamma did not exceed raw 1280. The historical run already uses the detector default of 1280. The automatic CLI now defaults to 1280 for future runs. The experiment does not replace historical results or label undetected animals as absent.

## Evaluation and correctness

Historical exported data passed arithmetic and fusion verification: 31 files, 1,319 camera windows, 348 fused times, 29 hourly bins and 198 conditional shelter points. The software suite passed 34 tests before the final reporting additions; the final test log is included separately. These are engineering checks.

The existing development Walking replays contain 30 seconds, with 18 seconds proposed Walking and 12 Unknown. The 60% ratio is development-check recovery on one previously exposed class. It is not overall accuracy. Leave-one-annotation-out development diagnostics report Feeding 29/30 and Walking 5/7 derived segments, but adjacent events and one source recording prevent interpreting these as independent accuracy.

Independent multi-class accuracy, precision, recall, F1 and verified Resting/Sleeping remain unavailable. Automatic detector outputs cannot supply independent ground truth for evaluating the same pipeline. Historical annotation source offsets remain unverified. Phase 1's 537 observations and 96.3% are not used as validated Phase 2 ground truth or results.

## Continuity with Phase 1 and requirement coverage

The project retains the Phase 1 problem, four-room/one-animal/four-camera setup, behavior definitions, behavior-versus-visibility distinction, pipeline structure and structured records. The implemented detector and classifier differ from the proposed classical background/Otsu/shape/zone rules. The trained behavior pilot supports Walking and Feeding, with Unknown for unsupported cases. Climb, visible Resting, a reliable Other classifier, calibrated room zones and continuous whole-period bouts are not established by this evidence set.

The requirement map distinguishes implemented deliverables from partially demonstrated outputs. Training, model explanation and source/annotation packaging are present. The Active/Inactive output requirement is only partly demonstrated because no validated Inactive model or labels are available. The package is suitable for presenting the actual pilot and its observed limits, not for claiming full validated behavior monitoring.

## Sources and reproducibility

- Source code: https://github.com/Wanikkasit65/civet_project
- Historical code revision: 1163e2091505f35026d71a53c8eb3b7ce454e469
- Original dataset: https://drive.google.com/drive/folders/1YKOcgZzu0evr6039I8rQhU7GNZ2nCJkB
- MegaDetector guide: https://megadetector.readthedocs.io/en/latest/userguide.html
- MegaDetector API: https://megadetector.readthedocs.io/en/latest/detection.html
- Input evidence: FAST_RESULTS.zip, CMZ_TIMING_CHECK.zip, PREFLIGHT_RESULTS.zip and the fetched original video.
- File identities, inference settings and package versions accompany the raw exports. No original video or annotation was modified.
