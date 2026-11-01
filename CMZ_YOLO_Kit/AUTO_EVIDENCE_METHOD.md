# Automatic evidence workflow

This workflow runs without new manual clip review. It reads video files and writes a new output directory. It never changes the input videos, historical annotations, or historical result tables.

## Models and units

MegaDetector V5A, a YOLOv5 animal/person/vehicle detector, proposes animal bounding boxes. It does not recognize a civet species or an animal's behavior. The completed additional control pass uses a 640-pixel detector input and an animal threshold of 0.4. The paired scale experiment supports retaining a 1280-pixel input, now the CLI default, because reducing it to 640 loses many proposals in the selected images. The historical run used the detector default of 1280. It runs the detector on approximately two decoded frames per second. The original historical run retains its own settings and results.

A Random Forest reconstructs the two-class pilot from the nine supplied, previously reviewed clips. Full frames become 96 x 96 grayscale images. Farneback optical flow and robust frame differences supply 18 features. The classifier has 200 trees, maximum depth 8, minimum two samples per leaf, balanced class weights, and random seed 42. It uses two-second segments. A longer tracking window uses successive two-second classifier segments and retains a behavior only when all segments agree above 0.7 and reliable animal proposals exist at both endpoints. These scores are not calibrated probabilities.

The reconstructed model is a new model trained on the compressed review clips. It is not the historical model file that produced the 1,319-window results. Both result sets remain separate.

## Position and movement proxies

Single-animal boxes supply image-plane centroids. Coordinates for distance calculations use frame width for both axes, preserving the frame's aspect ratio. Displacement is divided by median detected box size. At least 75% of sampled detector frames must show one animal without a person, and consecutive accepted frames must be no more than 1.1 seconds apart.

* Moving proposal: displacement at least half a box-length and average displacement at least 0.25 box-lengths per second.
* Stationary proposal: at least six seconds between accepted endpoints, displacement below 0.25 box-lengths, and average displacement below 0.04 box-lengths per second.
* Otherwise: Unknown.

These thresholds are engineering assumptions, not fitted ethological boundaries. Perspective, occlusion, detector jitter, out-and-back movement, and changes in box size can distort them. A stationary box cannot establish resting, feeding or sleep. Heatmaps count detected image-plane centroids, not room occupancy or dwell time. Camera identity is not a validated room assignment, since adjacent rooms may be visible through mesh.

## Time and sampling

FFmpeg decodes by presentation timestamps through `cmz_auto_pts.py`. Duration comes from demuxed metadata, not frame-count divided by nominal frame rate. The short audit clips carry source filename/start mappings from the historical sampled table. Original offsets of the nine historical training annotations remain unverified and are not silently repaired.

Saved audit clips form a convenience cohort. Additional original-video windows form a separate systematic cohort. Neither cohort is added to the historical random-sample denominator. No behavior is interpolated across gaps, and intervals from multiple cameras are never added as if they represented different animals.

## Running

Install the project requirements and `requirements_auto_evidence.txt` in an isolated environment. Download the official MegaDetector V5A checkpoint. Use only trusted model files.

```bash
python auto_evidence.py --timing PATH_TO_CMZ_TIMING_CHECK --audit PATH_TO_FAST_RESULTS/review_samples --sampled PATH_TO_FAST_RESULTS/SAMPLED_WINDOWS.csv --detector PATH_TO_md_v5a.0.0.pt --originals PATH_TO_ORIGINAL_FOLDER --output PATH_TO_NEW_OUTPUT
```

Omit `--originals` to process only the supplied saved audit clips. `--interval 30 --window 8` selects eight-second windows at starts 0, 30, 60, ... in additional original videos. This is systematic sampling, not exhaustive analysis. The output directory must not exist.

```bash
python verify_submission.py PATH_TO_HISTORICAL_RESULTS
python -m unittest discover -p 'test_*.py'
```

The first command checks exported data arithmetic. The tests check software behavior. Neither command measures behavior-classification accuracy.

## Evaluation boundary

Automatic detection and automatic agreement checks do not create independent ground truth. Without independent labels, accuracy, precision, recall, F1 and verified Inactive duration remain unavailable. Existing development replays are reported as development evidence only. No manual review is required to run or export this workflow.

## References

* MegaDetector documentation: https://megadetector.readthedocs.io/en/latest/userguide.html
* MegaDetector detector API: https://megadetector.readthedocs.io/en/latest/detection.html
* Official V5A checkpoint: https://github.com/agentmorris/MegaDetector/releases/download/v5.0/md_v5a.0.0.pt
* Project source: https://github.com/Wanikkasit65/civet_project

## Saved audit-image qualification

The earlier `save_audit_sample` function draws red ROI outlines into both its JPEG stills and MP4 previews. Consequently the additional saved-audit cohort and the enhancement experiment include existing overlays as well as compression. In the experiment, `raw` means no further photometric change to that saved image. It does not mean a clean original frame. Paired proposal counts are exploratory and do not prove improved accuracy on original footage. The extra original-video cohort is decoded directly and has no added ROI outline.
