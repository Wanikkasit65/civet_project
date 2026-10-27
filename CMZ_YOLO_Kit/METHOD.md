# CMZ video audit and YOLO detector stage

This is a staged implementation, not a finished animal activity experiment. No real behavior or detection score is claimed.

1. Decode local videos sequentially through bundled FFmpeg at 1 sampled frame/second; keep chronological thumbnails and compute grayscale frame-change scores for review ordering only. Approximate clip time is sample index + 0.5 seconds; verify on-screen timestamps and source playback. Sampling can miss brief appearances and image resizing can hide small animals. A lack of motion is not absence/rest. Inspect uniform and low-motion images as well as high-motion candidates.
2. A human verifies the animal in an original-resolution frame extracted near a selected time, annotates one visible civet bounding box, verifies background images explicitly, or marks uncertain. The tool is designed for one animal per image. Unreviewed/uncertain frames never become negatives. Labels retain reviewer, source name, approximate time and normalized box. An append-only history records label revisions.
3. Export one-class YOLO labels (class 0 = civet) with empty label files for verified backgrounds. Never infer true biological absence from a camera with occluded areas. Split by shared 30-minute recording-clock blocks across cameras, using a deterministic label-independent hash and 15-second block-edge exclusions. This reduces temporal leakage but does not establish independence between nearby blocks or days. Check clocks/animal identity manually. Same-animal, same-day results are a narrow pilot.
4. Optional real training script fine-tunes pretrained YOLO11n on custom boxes, with 640px training images, batch4, 50 epochs, patience10, seed42 and workers0. Select best checkpoint on validation. Evaluate detection on test once and keep all runs. Detecting the species is not guaranteed by COCO pretrained weights; civet is not a COCO class. Check tiny-object recall/occlusion/night IR errors and background false positives. GPU capability depends on PyTorch build and installed NVIDIA driver; diagnose before changing packages/drivers.
5. After measured detector results are reviewed, implement automatic candidate-video search and time-based Active/Inactive labeling/evaluation. Those stages are **pending**, not silently replaced by motion scores or object boxes. Test detection precision/recall/mAP separately from binary behavior precision/recall/F1/confusion matrix and visibility coverage. Not detected/occluded is Unknown, never automatically Inactive. Do not summarize sparse visible windows as a full-day activity budget.

The source links/repository, final presentation and measured outputs remain to be completed. No videos or annotation images are published automatically. Source originals are read only; new outputs go to this tool's own workspace. Contact-sheet ZIP export is a user-selected local action and may include enclosure images for ChatGPT review.

## Official references checked 27 October 2026

- https://docs.ultralytics.com/models/yolo11/
- https://docs.ultralytics.com/tasks/detect/
- https://docs.ultralytics.com/datasets/detect/
- https://docs.ultralytics.com/modes/val/
- https://pytorch.org/get-started/locally/

These document model APIs and formats, not performance on this project. YOLO dependencies and pretrained weights are downloaded only when the optional training launcher is invoked. A working detector and behavior outcomes still require real reviewed data.
