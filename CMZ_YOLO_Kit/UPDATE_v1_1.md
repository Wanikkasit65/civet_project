# Scout update v1.1

Fixes a Windows scan interruption caused by `WinError 5` when replacing status.json. Progress now writes immutable status snapshots first. The legacy status.json update is best-effort and cannot abort a scan just because that file is locked. The UI/export read the latest complete snapshot, with fallback support for old scans. Genuine video, image-storage or disk failures still stop the scan.

Adds a source/time jump in Step 2 and exports up to 40 reviewed box preview images when the user enables overview images. Existing scan images, index.csv and annotations are retained. This does not relabel data, restart an interrupted worker, or mark an interrupted scan as complete. No rescanning is needed simply to review existing frames.

## Apply to an existing Windows installation

1. Stop the app in its terminal with Ctrl+C. If a scan worker is active, let it finish first.
2. Copy the updated app.py and scout.py into a separate update folder first. Keep a backup of the previous two source files. Replace only those two files in the existing CMZ_YOLO_Kit folder after choosing to apply the update.
3. Keep the existing workspace folder and source videos in place. Open START_SCOUT_WINDOWS.bat again and select the existing scan.
4. Step 2: select Jump source, enter Jump directly to clip second, and click Open frame at this second.

A new scan uses the status fix; an old error remains honestly reported as an interrupted scan.

## Validation

Six unit tests cover existing grouping, label validation/history and YOLO export plus simulated Windows PermissionError during status replacement and legacy-state compatibility. No project-model accuracy is claimed.
