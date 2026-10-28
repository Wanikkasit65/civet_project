# Full-video inference and statistics

Training and inference are separate scopes. Course instructions allow a suitable training subset. This extension applies the resulting workflow to every readable original video discovered under the selected recursive roots. It does not treat training-label duration as full-recording statistics.

## Pipeline

1. Recursively discover video paths, exclude the chosen generated workspace, hash complete file contents, and deduplicate exact copies. Probe duration/FPS and preserve every failure in the inventory. Compare available names with previous review catalog names. This is not verification against the complete remote Drive collection.
2. Load pretrained MegaDetector V5A. Use its animal category as a presence proposal. Human proposals or ambiguous/multiple animal proposals remain Unknown. Species identity relies on the enclosure context, not an independently trained civet detector.
3. Refit a new Random Forest using the existing human labels and available local review clips. Split intervals into two-second segments and obtain crops through the same detector used for inference. This avoids silently applying the old human-ROI model to a different crop distribution. Preserve the old model and all labels.
4. Use the original 18 Farneback/frame-difference features and RF parameters (200 trees, depth 8, leaf minimum 2, class weights balanced, seed 42). Derived segments remain dependent on their source recording/event. Report actual recovered segment counts and unsupported classes. Never manufacture independent test metrics.
5. Replay the three previously exposed, chat-confirmed Walking clips using the new pipeline when the source video is available. Record per-segment predictions, detector outputs and crops. This is a one-class development check, not a fresh independent test. Do not reuse scores from the old human-ROI model.
6. Decode all readable videos sequentially. Retrieve approximately 4 fps. Analyze consecutive two-second windows, with animal checks at the first and last sampled frames. Use the padded union of detector boxes for features. Retain Unknown for failed/ambiguous presence, short windows, feature failures or low classifier scores. Confidence thresholds do not establish calibrated confidence or validated rejection of unseen behaviors.
7. Write each completed window to SQLite with content-hash identity and source time. Resume from the last committed interval. A process lock prevents concurrent workers writing the same run. Source modifications invalidate continuation. Decode errors remain explicit and the unprocessed tail is not treated as processed.
8. Export per-video and per-camera/hour model proposals separately from human confirmations. Active proposals equal Walking plus Feeding proposals. Inactive stays unavailable while either target Inactive class lacks support. The classifier is closed-set and may assign unseen behavior to a supported class; none of these totals constitutes verified animal behavior.
9. Only after the user verifies camera clocks, fuse absolute filename-time intervals using a sweep-line union. An agreeing behavior proposal from visible camera views contributes once. Disagreement becomes Unknown. This prevents multiplication by the camera count. Times with no recorded camera coverage remain gaps, rather than inferred Unknown duration.

## Evaluation boundary

This implementation enables full-data inference and model-output tables. It does not establish end-to-end accuracy. All-data inference includes the training footage and therefore is not held-out evaluation. The original nine intervals occupy one recording group. Independent Feeding performance, visible Resting/Sleeping performance, detector recall and whole-period behavior accuracy remain unmeasured until real validation supplies them. Results must be reviewed before presentation claims are finalized.

## Verification

Software tests cover exact-file deduplication, sequential window/tail accounting, resume boundaries, finite temporal features, conservative presence gating, unavailable class exports, hourly boundary splitting, camera conflict resolution, clock union without double counting and actual RF fitting on synthetic fixtures. Synthetic test outcomes are not project-model accuracy. Windows GPU installation, MegaDetector checkpoint loading and all-source video execution must be verified on the user's machine. No full-run result is bundled or claimed.

## Primary algorithm sources

- MegaDetector API and model loading: https://megadetector.readthedocs.io/en/latest/detection.html
- MegaDetector package and official example: https://github.com/agentmorris/MegaDetector/blob/main/README-package.md
- MegaDetector Windows/GPU setup guidance: https://github.com/agentmorris/MegaDetector/blob/main/skills/run-megadetector.md
- Random Forest: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html
- Farneback optical flow: https://docs.opencv.org/4.x/d4/dee/tutorial_optical_flow.html

Dependencies install into a new environment. The launcher chooses a PyTorch 2.6.0 / torchvision 0.21.0 CUDA wheel compatible with the CUDA support reported by nvidia-smi, or a CPU wheel. It does not update drivers. The run records installed package versions and actual CUDA availability. GPU support can still fail and requires checking the real environment.
