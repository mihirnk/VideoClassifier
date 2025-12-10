import cv2
from ultralytics import YOLO
import os
import argparse
from datetime import timedelta
import json
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))


def _format_timecode(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:06.3f}"


class FaceDetector:
    def __init__(self, video_path, confidence_threshold=0.3, face_class=5, model_path='yolov8s-face-lindevs.pt', display=True, show_class=0):
        # Load a face-specialized model. Default: yolov8s-face-lindevs.pt (balanced speed/accuracy)
        self.model = YOLO(model_path)
        self.input_path = os.path.join(current_dir, video_path)
        self.cap = cv2.VideoCapture(self.input_path)

        # Some videos or capture devices may report 0 FPS; fall back to 30 FPS
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if not self.fps or self.fps <= 0:
            self.fps = 30.0

        self.confidence_threshold = confidence_threshold
        self.face_class = int(face_class)
        # Which class id to treat as "face" (defaults to --face-class)
        self.show_class = int(show_class)

    def detect_faces(self):
        frame_count = 0
        face_segments = []
        current_seg = None

        while self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                break

            timestamp = frame_count / self.fps

            # Run standard YOLO inference (no tracking)
            results = self.model(frame)

            # default: no target detected
            target_detected = False

            # Robustly extract confidences and class IDs from Ultrayltics Results
            try:
                r0 = results[0]
            except Exception:
                r0 = None

            if r0 is not None and hasattr(r0, 'boxes') and r0.boxes is not None:
                # Try boxes.data first (numpy array), fallback to .conf and .cls attributes
                boxes_data = None
                try:
                    boxes_data = r0.boxes.data
                except Exception:
                    boxes_data = None

                if boxes_data is not None and getattr(boxes_data, 'shape', (0,))[0] > 0:
                    for box in boxes_data:
                        if len(box) >= 6:
                            conf = float(box[4])
                            class_id = int(box[5])
                            if class_id == self.show_class and conf >= self.confidence_threshold:
                                target_detected = True
                                break
                else:
                    # Try tensor attributes (.conf / .cls)
                    try:
                        confs = list(r0.boxes.conf.cpu().numpy()) if hasattr(r0.boxes.conf, 'cpu') else list(r0.boxes.conf.numpy())
                        classes = list(r0.boxes.cls.cpu().numpy()) if hasattr(r0.boxes.cls, 'cpu') else list(r0.boxes.cls.numpy())
                        for conf, class_id in zip(confs, classes):
                            if int(class_id) == self.show_class and float(conf) >= self.confidence_threshold:
                                target_detected = True
                                break
                    except Exception:
                        # Last resort: try string parsing of results
                        try:
                            text = r0.boxes.__repr__()
                            if text and str(self.show_class) in text:
                                target_detected = True
                        except Exception:
                            target_detected = False

            # Handle segment creation/ending
            if target_detected:
                if current_seg is None:
                    current_seg = {
                        'start_frame': frame_count,
                        'start_time': timestamp,
                        'start_timecode': _format_timecode(timestamp)
                    }
            else:
                if current_seg is not None:
                    current_seg.update({
                        'end_frame': frame_count,
                        'end_time': timestamp,
                        'end_timecode': _format_timecode(timestamp),
                        'duration': timestamp - current_seg['start_time']
                    })
                    face_segments.append(current_seg)
                    current_seg = None

            frame_count += 1

        # Close any open segment at the end of video
        if current_seg is not None:
            timestamp = frame_count / self.fps
            current_seg.update({
                'end_frame': frame_count,
                'end_time': timestamp,
                'end_timecode': _format_timecode(timestamp),
                'duration': timestamp - current_seg['start_time']
            })
            face_segments.append(current_seg)

        self.cap.release()

        # Compute complementary no-face segments
        duration = frame_count / self.fps
        no_face = []
        cursor = 0.0
        for seg in face_segments:
            if seg['start_time'] > cursor:
                no_face.append({'start': cursor, 'end': seg['start_time'], 'start_timecode': _format_timecode(cursor), 'end_timecode': _format_timecode(seg['start_time'])})
            cursor = max(cursor, seg['end_time'])
        if cursor < duration:
            no_face.append({'start': cursor, 'end': duration, 'start_timecode': _format_timecode(cursor), 'end_timecode': _format_timecode(duration)})

        # Merge and order segments: alternate no_face and face where appropriate
        combined = []
        # Build a combined timeline by merging both lists
        i, j = 0, 0
        # We'll simply create a list of all segments (face and no_face) and sort by start
        for s in face_segments:
            combined.append({'type': 'face', 'start': s['start_time'], 'end': s['end_time'], 'start_timecode': s['start_timecode'], 'end_timecode': s['end_timecode']})
        for s in no_face:
            combined.append({'type': 'no_face', 'start': s['start'], 'end': s['end'], 'start_timecode': s['start_timecode'], 'end_timecode': s['end_timecode']})
        combined.sort(key=lambda x: x['start'])

        return {'duration': duration, 'segments': combined, 'total_frames': frame_count}


def main():
    parser = argparse.ArgumentParser(description='Face Detection -> produce face/no-face timestamp segments')
    parser.add_argument('input_video', help='Path to input video file (relative to script)')
    parser.add_argument('output_json', nargs='?', default=None, help='Path to output JSON file (defaults next to input video)')
    parser.add_argument('--confidence', type=float, default=0.3,
                        help='Confidence threshold for face detection (default: 0.3)')
    parser.add_argument('--model', type=str, default='yolov8s-face-lindevs.pt',
                        help='Path or name of the YOLO face model to use (default: yolov8s-face-lindevs.pt)')
    parser.add_argument('--face-class', type=int, default=0,
                        help='Class id corresponding to "face" in your model (default: 0)')

    args = parser.parse_args()

    print(f"Processing video: {args.input_video}")
    print(f"Model: {args.model}")
    print(f"Confidence threshold: {args.confidence}")

    detector = FaceDetector(args.input_video,
                            confidence_threshold=args.confidence,
                            face_class=args.face_class,
                            model_path=args.model,
                            show_class=args.face_class,
                            )

    stats = detector.detect_faces()

    # Prepare output path
    input_path = os.path.join(current_dir, args.input_video)
    base = Path(input_path).stem
    out_path = args.output_json if args.output_json else str(Path(input_path).with_name(base + "_face_segments.json"))

    payload = {
        'video': input_path,
        'duration': stats['duration'],
        'segments': stats['segments']
    }

    with open(out_path, 'w') as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote segments to: {out_path}")
    print("Summary:")
    for seg in stats['segments']:
        print(f" - {seg['type']}: {seg['start_timecode']} -> {seg['end_timecode']}")


if __name__ == "__main__":
    main()
