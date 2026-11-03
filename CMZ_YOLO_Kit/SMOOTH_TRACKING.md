# Make the smooth tracking video yourself

The demonstration uses the existing `all_video.AnimalDetector` (pretrained
MegaDetector V5A) and `cmz_auto_pts.ffmpeg_exe`. The new
`export_tracking_video.py` adds CSRT tracking, local crop re-detection, backward
refinement, foreground-motion correction and box smoothing. The original
`save_audit_sample()` exporter alone cannot produce this result.

This is animal detection/tracking, **not Walking/Eating classification**. The
final smooth video does not use the Random Forest behavior model. A visible
tracked box is not an independent detector confirmation or proof of accuracy.

## Get the version containing the script

The video and script are on the `video/civet-tracking-40s` branch, not `main`.

**If your existing website already works:** download
[`export_tracking_video.py`](export_tracking_video.py) using GitHub's **Download
raw file** button and save it inside your existing `CMZ_YOLO_Kit` folder, next to
`all_video.py` and `cmz_auto_pts.py`. Keep your existing `.allvideo_venv`. Continue
with **Install once** below; you only need the extra tracker installation.

**For a separate checkout:** on Windows, open **Command Prompt** and run:

```bat
git clone --branch video/civet-tracking-40s https://github.com/Wanikkasit65/civet_project.git civet_tracking
cd civet_tracking\CMZ_YOLO_Kit
```

Keep your existing project/workspace and original videos in place. This new
checkout does not contain the private source videos. Use their real local paths.

## Install once

Use **Python 3.12**. If this checkout already has a working `.allvideo_venv`, use
that environment; no separate PyTorch installation is needed. Add the tracker:

```bat
.allvideo_venv\Scripts\python.exe -m pip install --target "%USERPROFILE%\.cmz_tracking_cv2" --no-deps opencv-contrib-python-headless==4.14.0.94
```

The extra OpenCV installation is separate so it does not replace the project's
existing `cv2` package. The script selects it automatically. Use a fresh target
directory if you have installed a different OpenCV version there previously.

If you do **not** have a working environment, install a separate CPU environment:

```bat
py -3.12 -m venv .tracking_venv
.tracking_venv\Scripts\python.exe -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
.tracking_venv\Scripts\python.exe -m pip install -r requirements_all_video.txt megadetector==10.0.28 "setuptools<81"
.tracking_venv\Scripts\python.exe -m pip install --target "%USERPROFILE%\.cmz_tracking_cv2" --no-deps opencv-contrib-python-headless==4.14.0.94
```

For the following commands, replace `.allvideo_venv` with `.tracking_venv` if you
used this second route. Internet is needed for installation and the first model
download. A GPU and the old behavior-training workspace are not required.

## Reproduce the demonstrated interval

Use the **original** `A03_20260405000000.mp4` from the shared source folder.
Replace the example path below with its actual path on your computer:

```bat
.allvideo_venv\Scripts\python.exe export_tracking_video.py --input "E:\YOUR_VIDEO_FOLDER\camera 3\A03_20260405000000.mp4" --start 2490 --duration 40 --output "workspace\tracking_demo"
```

`--start 2490` means start **41 minutes 30 seconds into the file**. It is not
the recording's wall-clock time. `--duration 40` selects the following 40 seconds.
The script decodes with a preroll, converts the selected interval to 25 fps,
detects the animal once per second, tracks between detections, refines gaps,
renders the overlay and checks that every exported frame decodes.

When `DONE` appears, open:

```text
CMZ_YOLO_Kit\workspace\tracking_demo\civet_smooth_tracking.mp4
```

That is the actual H.264 MP4 to copy, send or upload. The output folder also
contains `SUMMARY.json`, `FRAME_RESULTS.csv`, `FINAL_TRACK.csv` and
`QA_contact_sheet.jpg`. Inspect the contact sheet and watch the video for drift.
`source_clip.mp4` and `render.mp4` are intermediate files.

Choose a new output folder for each run; the script refuses to overwrite a
nonempty folder. For a different interval, change `--start`, `--duration` and
`--output`. The source file remains unchanged.

The reusable command was rerun on this source interval: 1,000 decoded output
frames, 25 fps, 40 seconds, a track on all frames, and 28 detector confirmations
out of 40 scheduled queries. Its box positions reproduced those in the delivered
video. These are software/run checks, not independently measured accuracy.

## What to expect

- CPU processing is supported. Processing is slower than video playback.
- A 40-second clip at 960×540 uses about 1.6 GB for decoded frames, plus model
  and processing memory. Work on short clips, not an entire CCTV recording at once.
- Output is 25 fps with no audio. Converting to 25 fps does not invent motion
  detail missing from the source.
- The method was visually tuned on this single-animal, fixed-camera night clip.
  Other cameras, several animals, occlusion or moving backgrounds can cause
  missed detections, wrong associations or tracking drift. It does not guarantee
  detection on every frame. Missing tracks are marked as lost.
- Foreground refinement assumes a fixed scene and uses the first four seconds
  as background evidence. This can be unsuitable if the animal stays in the
  same place throughout that initial interval.
- Detector scores and track availability are not measured behavior accuracy.
  No species model or behavior classifier is trained by this command.
- The workflow was exercised in Linux/Python 3.12. The Windows commands use
  supported Python/OpenCV/FFmpeg interfaces but were not executed on Windows here.

## Linux command

Use an environment containing the repository dependencies. Install OpenCV contrib
in a separate directory and pass it explicitly, for example:

```sh
python -m pip install --target "$HOME/.cmz_tracking_cv2" --no-deps opencv-contrib-python-headless==4.14.0.94
python export_tracking_video.py --input /path/to/A03_20260405000000.mp4 --start 2490 --duration 40 --output workspace/tracking_demo
```
