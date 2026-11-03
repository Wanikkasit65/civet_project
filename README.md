# civet_project

CMZ Phase 2: a pilot for civet behavior proposals from CCTV video.

The system uses pretrained MegaDetector for animal detection and a separately trained Random Forest for Walking/Eating proposals. Eating is called `Feeding` in the code. Resting and Sleeping are not trained behavior classes in this experiment.

## Open the local analysis website on your existing Windows setup

Use this route on the computer that already ran the project. It reuses the installed environment.

1. Open **Command Prompt** (`cmd`).
2. Run these commands:

```bat
cd /d "E:\mod stardewS\CMZ\CMZ_YOLO_Kit"
.allvideo_venv\Scripts\python.exe -m streamlit run all_video_app.py --server.address=127.0.0.1 --server.port=8504 --browser.gatherUsageStats=false
```

3. Open **http://127.0.0.1:8504** in Chrome or Edge. Keep Command Prompt open.
4. In **1. Existing workspace folder**, enter the real folder containing your old `phase2` annotations, review clips and `all_video_runs`:

```text
E:\mod stardewS\CMZ\CMZ_YOLO_Kit\workspace
```

5. Select an existing entry under **Current / previous run**, then press **Refresh progress** to show its recorded status. This selector lists `workspace\all_video_runs\full_*` folders.
6. Expand the available CSV sections to show saved per-video or per-camera results. **Download ALL_VIDEO_RESULTS.zip** appears when the selected run has that export.
7. To stop the web server, return to Command Prompt and press **Ctrl+C**. A running analysis worker is separate: use **Pause safely after the current window**, then refresh until it reports `paused` before stopping that analysis.

Opening the website does not start a new analysis. **3. Start a NEW full-folder analysis** starts a separate, potentially long processing run. You do not need that button to present existing results.

### Which results does this website show?

The existing all-video website shows its own `full_*` runs. The submitted 31-video experiment used `cmz_fast_sample.py` and saved results in a separate `fast_runs` folder. Those sampled results and the later **Assumed sleeping** reporting rule are not loaded by `all_video_app.py`.

For the submitted experiment, show the separately supplied presentation and `CMZ_Phase2_Results.xlsx`, starting with its **Summary** tab. The workbook contains 348 combined sample times: 53 Walking proposals, 9 Eating proposals, 198 Assumed sleeping points and 88 Unknown points. These are sample-point counts, not continuous behavior durations.

Do not present a different `full_*` run as the submitted sampled experiment. The exact saved Random Forest and raw videos are not included in the presentation/results pack, so that pack alone cannot reproduce live inference.

## Install and open the website on a new Windows setup

Prerequisites: **Python 3.12**, Git or GitHub's **Code > Download ZIP**, internet for the first dependency installation, and your separately retained workspace/videos if you want to process or review real data.

Keep the checkout path short. For example, open Command Prompt and run:

```bat
mkdir E:\CMZ
cd /d E:\CMZ
git clone https://github.com/Wanikkasit65/civet_project.git
cd civet_project\CMZ_YOLO_Kit
py -3.12 --version
py -3.12 all_video_launch.py
```

If `E:\CMZ` already exists, continue with the next command. If Git is unavailable, download the repository ZIP, extract it to a short path, open Command Prompt inside its `CMZ_YOLO_Kit` folder and run the last two commands.

`all_video_launch.py` creates a separate `.allvideo_venv`, installs the requirements and PyTorch, checks imports, then starts the website on **http://127.0.0.1:8504**. Its installer detects the CUDA version reported by `nvidia-smi` and chooses a PyTorch wheel, with CPU as the fallback. Actual GPU availability still depends on the installed driver/environment.

The repository does not contain your local workspace, raw CCTV videos or the exact saved behavior model from the submitted sampled run. A new checkout opens the app but will not automatically display your old results. Enter the path to your existing workspace. Keep the source videos and generated review-clip folders available for training or inference.

For a new analysis, enter one actual video-folder path per line in **2. Video folders**. Leave the camera-clock verification checkbox unchecked until you have checked the recording clocks. The app requires confirmed labels in the selected workspace. CPU processing is available under **Advanced settings** when CUDA is unavailable.

## Open the label-review and training website

This is the separate app for reviewing labels, training its behavior pilot and exporting annotation tables:

```bat
cd /d "E:\mod stardewS\CMZ\CMZ_YOLO_Kit"
py -3.12 phase2_launch.py
```

For a new checkout, change the first line to its actual `CMZ_YOLO_Kit` path. Then open **http://127.0.0.1:8503**.

In the sidebar, set **Existing workspace folder**, then choose the relevant step:

| App step | Purpose |
|---|---|
| 1 · Import confirmed labels | Import a human-confirmed JSON file |
| 2 · Review behavior clips | Replay clips, label intervals and review animal crops |
| 3 · Train behavior pilot | Train the app's motion-feature Random Forest |
| 4 · Tables & export | View confirmed-observation tables and create a results ZIP |
| 5 · Try a model proposal | Try a model trained in this app on a review clip |

This review app's crop-based pilot is separate from the submitted full-frame sampled pipeline. The submitted experiment uses `cmz_auto_pts.py` and `cmz_fast_sample.py`. Those historical scripts refer to specific local run folders. Inspect their configuration and retain the required workspace/model before attempting a reproduction on another machine.

## Quick troubleshooting

| Message or symptom | Action |
|---|---|
| Python version error | Run `py -3.12 --version`. Use Python 3.12 for `all_video_launch.py`. |
| `.allvideo_venv\Scripts\python.exe` not found | You are in a different folder or the environment has not been installed. Use `py -3.12 all_video_launch.py` in the correct kit folder. |
| `No module named streamlit` | Use the kit's `.allvideo_venv` command above or rerun its launcher. A different system Python may not have the dependencies. |
| Browser does not open automatically | Type `http://127.0.0.1:8504` into the browser after the server starts. |
| Port 8504 is in use | Use `--server.port=8505` in the direct Streamlit command and open `http://127.0.0.1:8505`. |
| No previous run appears | Check the workspace path. The selector reads only `all_video_runs\full_*`, not the sampled `fast_runs` results. |
| `No confirmed labels found` | Point to the old workspace with its annotations and review clips. A presentation ZIP is not a training workspace. |
| CUDA unavailable | Check the installer's import/CUDA output. The app's **Advanced settings** offers slower CPU processing. |

## Evidence and model references

- [Source code](CMZ_YOLO_Kit/)
- [Submitted sampling code](CMZ_YOLO_Kit/cmz_fast_sample.py)
- [Full-frame training implementation](CMZ_YOLO_Kit/cmz_auto_pts.py)
- [Training annotation register](submission/2026-11-01/ANNOTATION_REGISTER.csv) — retain its source-time verification caveats.
- [Original video folder](https://drive.google.com/drive/folders/1YKOcgZzu0evr6039I8rQhU7GNZ2nCJkB)
- [MegaDetector documentation](https://github.com/agentmorris/MegaDetector/blob/main/megadetector.md)
- [OpenCV Farneback optical flow](https://docs.opencv.org/3.4.8/dc/d6b/group__video__track.html)
- [scikit-learn RandomForestClassifier](https://scikit-learn.org/1.5/modules/generated/sklearn.ensemble.RandomForestClassifier.html)

Independent behavior accuracy, precision, recall and F1 have not been established for the submitted sampled experiment. The sleep label is a declared four-camera absence assumption, with incomplete camera-clock verification. It is not observed sleep or a trained sleep prediction.

The presentation and workbook are supplied separately as files. This README documents how to open the existing apps and trace the code.
