# CMZ Phase 2: open evidence quickly

**Presentation:** [15-slide PPTX](submission/2026-11-01/CMZ_Phase2_Automatic_15slides_v2.pptx) · [PDF](submission/2026-11-01/CMZ_Phase2_Automatic_15slides_v2.pdf)

**Report:** [Full workflow and results](submission/2026-11-01/CMZ_Automatic_Analysis_Report.md) · [Printable report](submission/2026-11-01/CMZ_Automatic_Analysis_Report.pdf)

**Compare with Phase 1:** [Earlier plan versus current evidence](PHASE1_COMPARISON.md)

**Speaking:** [English answers with Thai explanations](PRESENTATION_QA.md) · [Requirement-to-slide map](submission/2026-11-01/REQUIREMENTS_TRACE.csv)

## Fast question-to-evidence map

| If asked… | Open this evidence | What it establishes |
|---|---|---|
| What did you train? | [Training settings](submission/2026-11-01/historical_results/BATCH_TRAINING_REPORT.json) | RF settings, 37 segments and supported classes |
| Where are your annotations? | [Annotation register](submission/2026-11-01/ANNOTATION_REGISTER.csv) | Nine retained reviewed labels, provenance and timing limitations |
| Show me the training samples | [Derived segment register](submission/2026-11-01/auto_evidence/RECONSTRUCTED_TRAINING_SEGMENTS.csv) | Review-clip IDs, offsets, labels and hashes |
| Where does 53 / 9 / 286 come from? | [348 fused time points](submission/2026-11-01/historical_results/FUSED_SAMPLED_TIMES.csv) | One historical proposal per nominal fused time |
| Show the raw per-camera outputs | [1,319 camera windows](submission/2026-11-01/historical_results/SAMPLED_WINDOWS.csv) | Source, camera, offset, proposal, score and status |
| Did you cover all 31 files? | [Per-video results](submission/2026-11-01/historical_results/PER_VIDEO_SAMPLING_TABLE.csv) | Sample coverage of each original file |
| Show hourly results | [29 hourly bins](submission/2026-11-01/historical_results/HOURLY_SAMPLED_TIME_TABLE.csv) | Counts per sampled nominal hour |
| Are these whole-day durations? | [Result scope](submission/2026-11-01/historical_results/RESULT_SCOPE.json) | Sampling fraction, unsupported classes and clock limits |
| Show software tests | [Test log](submission/2026-11-01/SOFTWARE_TESTS.txt) · [Test source](CMZ_YOLO_Kit/test_auto_evidence.py) | Engineering correctness, not animal-behavior accuracy |
| Show that the tables agree | [Recomputed integrity result](submission/2026-11-01/INTEGRITY_CHECK.json) · [Verifier source](CMZ_YOLO_Kit/verify_submission.py) | Arithmetic and fusion match the exported raw tables |
| Show behavior evaluation | [Development replay segments](submission/2026-11-01/preflight_evidence/REPLAY_WALKING_CHECKS.json) | 18/30 s Walking recovery on exposed development clips, not independent accuracy |
| Where is independent accuracy / F1? | [Evaluation explanation](submission/2026-11-01/CMZ_Automatic_Analysis_Report.md#evaluation-and-correctness) | Unavailable. Automatic predictions are not independent ground truth |
| Show new automatic detections | [Frame-level boxes](submission/2026-11-01/auto_evidence/AUTO_DETECTIONS.csv) · [Window proposals](submission/2026-11-01/auto_evidence/AUTO_WINDOWS.csv) | Separate additional evidence cohort |
| Did image enhancement help? | [Paired summary](submission/2026-11-01/enhancement/ENHANCEMENT_SUMMARY.csv) · [All paired calls](submission/2026-11-01/enhancement/ENHANCEMENT_RESULTS.csv) | Proposal-count changes under identical image selection, not accuracy gains |
| Show the detector / classifier code | [Automatic method](CMZ_YOLO_Kit/AUTO_EVIDENCE_METHOD.md) · [Implementation](CMZ_YOLO_Kit/auto_evidence.py) | Exact preprocessing, thresholds, RF and geometry rules |
| What changed from Phase 1? | [Coverage map](submission/2026-11-01/REQUIREMENTS_TRACE.csv) | Current implementation versus earlier planned features |

## Three tabs to open before presenting

1. This guide, kept as the main navigation tab.
2. The [15-slide PDF](submission/2026-11-01/CMZ_Phase2_Automatic_15slides_v2.pdf).
3. The [raw camera-window CSV](submission/2026-11-01/historical_results/SAMPLED_WINDOWS.csv).

Use **Ctrl+F** on this page for `train`, `test`, `hourly`, `annotation`, `accuracy`, or `enhancement`. Click the relevant evidence. If asked about a source filename, open the raw CSV and search that filename. `source` plus `start` / `end` identifies the corresponding source-video window. Some historical training annotation offsets remain unverified; use the saved review-clip identifiers and hashes for those labels.

## Important distinctions

* Historical totals use 348 fused points or 1,319 camera windows. Never mix these denominators.
* Additional automatic evidence is a separate cohort and is not added to historical totals.
* Unknown is not Inactive. Missing detections do not confirm sleep.
* Software tests, development recovery and independent behavior accuracy answer different questions.
* The Phase 1 figure 96.3% is not used as a Phase 2 accuracy result.

Original videos remain at the [source dataset](https://drive.google.com/drive/folders/1YKOcgZzu0evr6039I8rQhU7GNZ2nCJkB). The repository contains source and non-video evidence. Access to original Drive videos follows their existing permissions.
