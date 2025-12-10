from flask import Flask, request, jsonify
import os
import tempfile
from werkzeug.utils import secure_filename
from consolidate_segments import run_face_detector, run_speech_detector, build_timeline, smooth_small_segments

app = Flask(__name__)
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

@app.route('/analyze', methods=['POST'])
def process_video():
    payload = request.get_json(force=True)
    video = payload.get('video_path')
    if not video:
        return jsonify({'error': 'video_path required'}), 400
    if not os.path.isabs(video):
        video = os.path.join(REPO_ROOT, video)
    if not os.path.exists(video):
        return jsonify({'error': 'video not found'}), 404

    # Run detectors (blocking). You can optionally use existing JSON via payload fields.
    face_stats = run_face_detector(video, model_path='yolov8s-face-lindevs.pt', confidence=0.3)
    speech_stats = run_speech_detector(video, vosk_model='vosk-model-small-en-us-0.15', max_gap=0.5)

    duration = float(face_stats.get('duration', speech_stats.get('duration')))
    merged = build_timeline(face_stats['segments'], speech_stats['segments'], duration)
    smoothed = smooth_small_segments(merged, min_duration=1.0)

    payload = {'segments': [{'start': s['start'], 'end': s['end'], 'mode': s['mode']} for s in smoothed],
               'duration': duration}
    return jsonify(payload)

@app.route('/health', methods=['GET'])
def health():
    result = {
        'status': "ok"
    }
    return jsonify(result)
@app.route('/upload', methods=['POST'])
def upload_video():
    """Accept a multipart file upload (form field 'video'), save to a temp file,
    run the same detection pipeline, then remove the temp file and return JSON.
    """
    # Ensure a file was uploaded
    uploaded = request.files.get('video')
    if not uploaded:
        return jsonify({'error': 'no video file provided (field name: video)'}), 400

    # Sanitize filename and pick a sensible suffix
    filename = secure_filename(uploaded.filename or 'upload.mp4')
    _, ext = os.path.splitext(filename)
    if not ext:
        ext = '.mp4'

    tmp_file = None
    tmp_path = None
    try:
        # Create a persistent temp file under repo root so downstream code can open it
        tmp_file = tempfile.NamedTemporaryFile(prefix='upload_', suffix=ext, delete=False, dir=os.path.dirname(os.path.abspath(__file__)))
        tmp_path = tmp_file.name
        tmp_file.close()

        # Save uploaded content to disk
        uploaded.save(tmp_path)

        # Run detectors (blocking) on the saved file
        face_stats = run_face_detector(tmp_path, model_path='yolov8s-face-lindevs.pt', confidence=0.3)
        speech_stats = run_speech_detector(tmp_path, vosk_model='vosk-model-small-en-us-0.15', max_gap=0.5)

        duration = float(face_stats.get('duration', speech_stats.get('duration')))
        merged = build_timeline(face_stats['segments'], speech_stats['segments'], duration)
        smoothed = smooth_small_segments(merged, min_duration=1.0)

        payload = {'segments': [{'start': s['start'], 'end': s['end'], 'mode': s['mode']} for s in smoothed],
                   'duration': duration}
        return jsonify(payload)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
    finally:
        # cleanup
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)