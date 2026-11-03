"""Export a short CCTV clip with MegaDetector + CSRT tracking.

Uses the project's AnimalDetector and FFmpeg helper. Tracking, cropped
re-detection and offline refinement are additions to the original exporter.
See SMOOTH_TRACKING.md. A tracked box is not an independent detection.
"""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys


def arguments():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True, type=Path, help='Original local video')
    p.add_argument('--start', type=float, default=2490, help='Source-relative seconds')
    p.add_argument('--duration', type=float, default=40, help='5–120 source seconds')
    p.add_argument('--output', type=Path, required=True, help='New/empty output folder')
    p.add_argument('--tracker-deps', type=Path,
                   default=Path.home() / '.cmz_tracking_cv2',
                   help='Directory containing the separate OpenCV contrib installation')
    return p.parse_args()


def write_rows(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    args = arguments()
    if not args.input.is_file():
        raise ValueError('Input video not found: ' + str(args.input))
    if args.start < 0 or not 5 <= args.duration <= 120:
        raise ValueError('Start must be nonnegative; duration must be 5–120 seconds.')
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError('Output folder is not empty. Choose a new --output folder.')
    if args.tracker_deps.is_dir():
        sys.path.insert(0, str(args.tracker_deps.resolve()))

    import cv2
    import numpy as np
    import torch
    from PIL import Image
    from scipy.signal import savgol_filter
    from all_video import AnimalDetector
    from cmz_auto_pts import ffmpeg_exe

    if not hasattr(cv2, 'TrackerCSRT_create'):
        raise RuntimeError('CSRT is missing. Install OpenCV contrib as described in SMOOTH_TRACKING.md.')
    cv2.setNumThreads(2)
    torch.set_num_threads(4)
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_exe()
    source = root / 'source_clip.mp4'
    seek = max(0., args.start - 2.)
    # Preroll allows the original HEVC CCTV inter-frames to decode before trim.
    subprocess.run([
        ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(seek),
        '-i', str(args.input.resolve()), '-ss', str(args.start - seek),
        '-t', str(args.duration), '-an', '-vf', 'scale=960:540,fps=25',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-threads', '4',
        '-movflags', '+faststart', str(source),
    ], check=True)
    cap = cv2.VideoCapture(str(source))
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    if not frames:
        raise RuntimeError('The selected source interval did not decode any frames.')
    height, width = frames[0].shape[:2]
    fps = 25
    print(f'Decoded {len(frames)} frames / {len(frames) / fps:.2f}s. Loading detector.', flush=True)
    detector = AnimalDetector(cpu=True)

    def make_tracker(frame, box):
        tracker = cv2.TrackerCSRT_create()
        tracker.init(frame, tuple(int(round(v)) for v in box))
        return tracker

    def distance(a, b):
        return float(np.linalg.norm(
            np.array([a[0] + a[2]/2, a[1] + a[3]/2]) -
            np.array([b[0] + b[2]/2, b[1] + b[3]/2])))

    def detect(frame, region):
        if region is None:
            x0, y0, x1, y1 = 0, 0, width, height
        else:
            x, y, w, h = region
            cx, cy = x + w/2, y + h/2
            x0, x1 = max(0, int(cx-max(130, w*1.6))), min(width, int(cx+max(130, w*1.6)))
            y0, y1 = max(0, int(cy-max(100, h*1.6))), min(height, int(cy+max(100, h*1.6)))
        if x1 <= x0 or y1 <= y0:
            return []
        result = detector.model.generate_detections_one_image(
            Image.fromarray(cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2RGB)),
            image_id='frame', image_size=1280 if region is None else 640,
            detection_threshold=.05)
        if result.get('failure'):
            raise RuntimeError(result['failure'])
        candidates = []
        for d in result.get('detections', []):
            if str(d['category']) != '1' or d['conf'] < (.35 if region is None else .15):
                continue
            x, y, w, h = d['bbox']
            box = (x0+x*(x1-x0), y0+y*(y1-y0), w*(x1-x0), h*(y1-y0))
            if all(np.isfinite(box)) and box[2] > 8 and box[3] > 8:
                candidates.append((box, float(d['conf'])))
        return candidates

    rows = []
    tracker = box = None
    last_detection, last_score = -999, None
    for i, frame in enumerate(frames):
        good = confirmed = False
        if tracker is not None:
            good, candidate = tracker.update(frame)
            good = bool(good and candidate[2] > 8 and candidate[3] > 8)
            if good:
                box = tuple(map(float, candidate))
        if i % fps == 0 or box is None:
            candidates = detect(frame, box if good else None)
            if box is None:
                choice = max(candidates, key=lambda c: c[1], default=None)
            else:
                matching = [c for c in candidates if distance(c[0], box) <
                            max(75, np.hypot(box[2], box[3])*.8)]
                choice = min(matching, key=lambda c: distance(c[0], box) /
                             max(20, np.hypot(box[2], box[3])) - .25*c[1], default=None)
            if choice:
                box, last_score = choice
                last_detection = i
                good = confirmed = True
                tracker = make_tracker(frame, box)
            elif not good:
                tracker = None
        rows.append(dict(
            frame=i, clip_second=i/fps, source_second=args.start+i/fps,
            track_ok=good, detector_confirmed=confirmed, last_detector_score=last_score,
            x=box[0] if good else None, y=box[1] if good else None,
            width=box[2] if good else None, height=box[3] if good else None,
            frames_since_detection=i-last_detection))
        if i % fps == 0:
            print(f'Tracking {i/fps:.0f}s / {len(frames)/fps:.0f}s; '
                  f'tracked={good}, detector_confirmed={confirmed}', flush=True)
    write_rows(root / 'FRAME_RESULTS.csv', rows)

    boxes = np.array([[r[k] if r[k] is not None else np.nan
                       for k in ('x', 'y', 'width', 'height')] for r in rows], dtype=float)
    anchors = [i for i, r in enumerate(rows) if r['detector_confirmed']]
    background = np.median([cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
                            for i in range(0, min(100, len(frames)), 5)], axis=0).astype('uint8')
    corrections = []
    for left, right in zip(anchors, anchors[1:]):
        if right-left <= 37:
            continue
        reverse = make_tracker(frames[right], boxes[right])
        for i in range(right-1, left, -1):
            ok, candidate = reverse.update(frames[i])
            if not ok or not np.isfinite(boxes[i]).all():
                continue
            candidate = np.array(candidate, float)
            # Motion evidence helps prevent reverse tracking from sticking to a fence.
            x0 = max(0, int(min(boxes[i, 0], candidate[0])-25))
            y0 = max(60, int(min(boxes[i, 1], candidate[1])-25))
            x1 = min(width, int(max(boxes[i, 0]+boxes[i, 2], candidate[0]+candidate[2])+25))
            y1 = min(500, int(max(boxes[i, 1]+boxes[i, 3], candidate[1]+candidate[3])+25))
            difference = cv2.absdiff(cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY), background)
            mask = np.zeros_like(difference)
            mask[y0:y1, x0:x1] = (difference[y0:y1, x0:x1] > 22)*255
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            choices = [c for c in contours if cv2.contourArea(c) > 150]
            if choices:
                x, y, w, h = cv2.boundingRect(max(choices, key=cv2.contourArea))
                shift = np.linalg.norm(np.array([x+w/2, y+h/2]) -
                                       (candidate[:2]+candidate[2:]/2))
                if w > candidate[2]*1.3 or shift > .6*np.hypot(candidate[2], candidate[3]):
                    candidate = np.array([x-8, y-8, w+16, h+16], float)
            weight = min(1., (i-left)/fps)
            boxes[i] = (1-weight)*boxes[i] + weight*candidate
        corrections.append((left, right))
        print(f'Refined detector gap {left/fps:.1f}–{right/fps:.1f}s', flush=True)

    # Smooth only contiguous valid tracks; do not invent boxes across lost intervals.
    valid = np.isfinite(boxes).all(axis=1)
    for run in np.split(np.flatnonzero(valid), np.flatnonzero(np.diff(np.flatnonzero(valid)) > 1)+1):
        if len(run) < 3:
            continue
        data = boxes[run]
        center, size = data[:, :2]+data[:, 2:]/2, data[:, 2:]
        def smooth(values, window):
            window = min(window, len(run) if len(run) % 2 else len(run)-1)
            return savgol_filter(values, window, 2, axis=0)
        center, size = smooth(center, 9), np.maximum(smooth(size, 13), 8)
        boxes[run] = np.column_stack([center-size/2, size])

    raw = root / 'render.mp4'
    writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError('OpenCV could not open the intermediate MP4 writer.')
    final_rows, previews = [], []
    last_detection = -999
    for i, (original, b, r) in enumerate(zip(frames, boxes, rows)):
        frame = original.copy()
        if r['detector_confirmed']:
            last_detection = i
        if valid[i]:
            x, y, w, h = b
            x1, y1 = max(0, int(x)), max(30, int(y))
            x2, y2 = min(width-1, int(x+w)), min(height-35, int(y+h))
            color = (70, 235, 110)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
            label = 'Animal track'
            tw = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, .55, 1)[0][0]
            cv2.rectangle(frame, (x1, y1-25), (min(width-1, x1+tw+12), y1), (15, 15, 15), -1)
            cv2.putText(frame, label, (x1+5, y1-7), cv2.FONT_HERSHEY_SIMPLEX, .55, color, 1, cv2.LINE_AA)
            status = 'Detector + tracking' if i-last_detection < fps else 'Tracking between detections'
        else:
            status = 'Track lost / not detected'
        cv2.rectangle(frame, (0, height-34), (width, height), (18, 18, 18), -1)
        cv2.putText(frame, f'{i/fps:05.2f} / {len(frames)/fps:.2f} s  |  25 fps  |  {status}',
                    (12, height-12), cv2.FONT_HERSHEY_SIMPLEX, .54, (245, 245, 245), 1, cv2.LINE_AA)
        writer.write(frame)
        final_rows.append(dict(frame=i, second=i/fps, track_ok=bool(valid[i]),
                               x=float(b[0]) if valid[i] else None,
                               y=float(b[1]) if valid[i] else None,
                               width=float(b[2]) if valid[i] else None,
                               height=float(b[3]) if valid[i] else None,
                               detector_confirmed=r['detector_confirmed'],
                               tracking_refined=any(a < i < z for a, z in corrections)))
        if i % 50 == 0:
            previews.append(cv2.resize(frame, (480, 270)))
    writer.release()
    write_rows(root / 'FINAL_TRACK.csv', final_rows)
    while len(previews) % 4:
        previews.append(np.zeros_like(previews[0]))
    cv2.imwrite(str(root / 'QA_contact_sheet.jpg'), np.vstack([
        np.hstack(previews[i:i+4]) for i in range(0, len(previews), 4)]))
    output = root / 'civet_smooth_tracking.mp4'
    subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(raw),
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p',
                    '-movflags', '+faststart', '-an', str(output)], check=True)
    cap = cv2.VideoCapture(str(output))
    output_fps, decoded = cap.get(cv2.CAP_PROP_FPS), 0
    while True:
        ok, _ = cap.read()
        if not ok:
            break
        decoded += 1
    cap.release()
    if decoded != len(frames) or output_fps != fps:
        raise RuntimeError(f'Output validation failed: {decoded} frames at {output_fps} fps.')
    subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(output),
                    '-f', 'null', '-'], check=True)
    summary = dict(source=str(args.input.resolve()), source_start_second=args.start,
                   requested_source_duration=args.duration, video=output.name,
                   frames=decoded, fps=output_fps, duration=decoded/output_fps,
                   frames_with_track=int(valid.sum()), detector_confirmations=len(anchors),
                   detector='Existing all_video.AnimalDetector / MegaDetector V5A',
                   full_frame_threshold=.35, associated_crop_threshold=.15,
                   tracking='CSRT, crop re-detection once per second, backward/motion refinement, smoothing',
                   behavior_classifier_used=False,
                   limitations='Track coverage is not accuracy. Animal detection is not species classification. '
                               'This single-animal, fixed-camera workflow was visually tuned on the demonstration clip.')
    (root / 'SUMMARY.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print('DONE: ' + str(output), flush=True)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
