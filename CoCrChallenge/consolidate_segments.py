#!/usr/bin/env python3
"""
consolidate_segments.py

Combine face/no-face segments and speech/no-speech segments into higher-level modes:
 - VOICEOVER_WITH_PICTURE = speech + face present
 - DIALOGUE_SCENE = speech + no face present
 - VISUAL_MONTAGE = no speech (face presence ignored)

The script can either run the detectors (by importing the existing modules) or read
precomputed JSONs using `--face-json` and/or `--speech-json`.

Usage examples:
 Run detectors then consolidate:
   python3 consolidate_segments.py videos/Mihir_clip.MOV --face-model yolov8s-face-lindevs.pt --vosk-model vosk-model-small-en-us-0.15

 Use existing detector JSONs:
   python3 consolidate_segments.py videos/Mihir_clip.MOV --face-json videos/Mihir_clip_face_segments.json --speech-json videos/Mihir_clip_speech_segments.json

Options include smoothing small fragments with `--min-duration` (default 1.0s).
"""

import argparse
import json
import os
import tempfile
from pathlib import Path


def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)


def run_face_detector(video_path, model_path, confidence):
    # Import at runtime so this script still works if user only wants to use JSONs
    import face_detect_video
    detector = face_detect_video.FaceDetector(video_path,
                                              confidence_threshold=confidence,
                                              face_class=0,
                                              model_path=model_path,
                                              show_class=0)
    stats = detector.detect_faces()
    return stats


def run_speech_detector(video_path, vosk_model, max_gap):
    import speech_segments_vosk as sv
    # re-use functions: extract audio, recognize, compute no-speech
    # create a temp wav and run recognizer
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, 'tmp.wav')
        sv.extract_audio_to_wav(video_path, wav, sample_rate=16000)
        speech_segs = sv.recognize_with_vosk(wav, vosk_model, max_silence=max_gap)
        duration = sv.get_video_duration(video_path)
        no_speech = sv.compute_no_speech_segments(speech_segs, duration)

        # build combined list like the JSON format created by speech_segments_vosk
        combined = []
        for s in speech_segs:
            combined.append({'type': 'speech', 'start': s['start'], 'end': s['end'],
                             'start_timecode': sv.format_timecode(s['start']), 'end_timecode': sv.format_timecode(s['end'])})
        for s in no_speech:
            combined.append({'type': 'no_speech', 'start': s['start'], 'end': s['end'],
                             'start_timecode': sv.format_timecode(s['start']), 'end_timecode': sv.format_timecode(s['end'])})
        combined.sort(key=lambda x: x['start'])
        return {'duration': duration, 'segments': combined}


def build_timeline(face_segments, speech_segments, duration):
    # Collect all unique boundaries
    bounds = set([0.0, float(duration)])
    for s in face_segments:
        bounds.add(float(s['start']))
        bounds.add(float(s['end']))
    for s in speech_segments:
        bounds.add(float(s['start']))
        bounds.add(float(s['end']))

    timeline = sorted(bounds)
    intervals = []
    for i in range(len(timeline) - 1):
        a = timeline[i]
        b = timeline[i+1]
        mid = (a + b) / 2.0

        # Determine speech presence at mid
        speech_present = any((float(s['start']) <= mid < float(s['end'])) and s.get('type', 'speech') == 'speech' for s in speech_segments)

        # Determine face presence at mid
        face_present = any((float(s['start']) <= mid < float(s['end'])) and s.get('type', 'face') == 'face' for s in face_segments)

        if speech_present:
            # NOTE: user prefers mapping where speech+face -> DIALOGUE_SCENE,
            # and speech+no_face -> VOICEOVER_WITH_PICTURE (reversed from earlier)
            if face_present:
                mode = 'DIALOGUE_SCENE'
            else:
                mode = 'VOICEOVER_WITH_PICTURE'
        else:
            mode = 'VISUAL_MONTAGE'

        intervals.append({'start': a, 'end': b, 'mode': mode})

    # Merge adjacent intervals with same mode
    merged = []
    for seg in intervals:
        if not merged:
            merged.append(seg.copy())
        else:
            last = merged[-1]
            if seg['mode'] == last['mode'] and abs(seg['start'] - last['end']) < 1e-6:
                last['end'] = seg['end']
            else:
                merged.append(seg.copy())
    return merged


def smooth_small_segments(segments, min_duration=1.0):
    # Merge segments shorter than min_duration into previous segment if possible, else next
    i = 0
    out = []
    while i < len(segments):
        seg = segments[i]
        dur = seg['end'] - seg['start']
        if dur >= min_duration or len(out) == 0 and i == len(segments) - 1:
            out.append(seg.copy())
            i += 1
            continue

        # Short segment
        if dur < min_duration:
            if len(out) > 0:
                # append to previous
                out[-1]['end'] = seg['end']
            elif i + 1 < len(segments):
                # merge into next
                segments[i+1]['start'] = seg['start']
            else:
                out.append(seg.copy())
        i += 1

    # After merging, also merge adjacent same-mode again
    merged = []
    for s in out:
        if not merged:
            merged.append(s.copy())
        else:
            last = merged[-1]
            if last['mode'] == s['mode'] and abs(last['end'] - s['start']) < 1e-6:
                last['end'] = s['end']
            else:
                merged.append(s.copy())
    return merged


def main():
    parser = argparse.ArgumentParser(description='Consolidate face and speech segments into scene modes')
    parser.add_argument('input_video', help='Path to input video (relative to script)')
    parser.add_argument('--face-model', default='yolov8s-face-lindevs.pt', help='Path to face YOLO model')
    parser.add_argument('--face-confidence', type=float, default=0.3, help='Face detection confidence threshold')
    parser.add_argument('--vosk-model', default='vosk-model-small-en-us-0.15', help='Path to Vosk model directory')
    parser.add_argument('--max-gap', type=float, default=0.5, help='Max gap to merge words into speech segment')
    parser.add_argument('--face-json', default=None, help='Use existing face JSON instead of running detector')
    parser.add_argument('--speech-json', default=None, help='Use existing speech JSON instead of running detector')
    parser.add_argument('--out', default=None, help='Output JSON path (defaults next to input video)')
    parser.add_argument('--min-duration', type=float, default=1.0, help='Minimum segment duration (s) to keep before smoothing')
    args = parser.parse_args()

    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(current_dir, args.input_video)
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")

    # Get face segments
    if args.face_json:
        face_stats = load_json(args.face_json)
    else:
        face_stats = run_face_detector(args.input_video, args.face_model, args.face_confidence)

    # Get speech segments
    if args.speech_json:
        speech_stats = load_json(args.speech_json)
    else:
        # speech runner expects full paths for model; let the speech module handle model path resolution
        speech_stats = run_speech_detector(input_path, args.vosk_model, args.max_gap)

    duration = float(face_stats.get('duration', speech_stats.get('duration')))

    # Normalize lists: face_stats['segments'] contains type 'face'/'no_face'; speech_stats['segments'] contains 'speech'/'no_speech'
    face_segments = face_stats['segments']
    speech_segments = speech_stats['segments']

    merged = build_timeline(face_segments, speech_segments, duration)
    smoothed = smooth_small_segments(merged, min_duration=args.min_duration)

    # Build output structure
    base = Path(input_path).stem
    out_path = args.out if args.out else str(Path(input_path).with_name(base + "_consolidated_segments.json"))

    payload = {'segments': [{'start': float(s['start']), 'end': float(s['end']), 'mode': s['mode']} for s in smoothed],
               'duration': duration}

    with open(out_path, 'w') as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote consolidated segments to: {out_path}")
    print("Summary:")
    for seg in payload['segments']:
        print(f" - {seg['mode']}: {seg['start']:.3f} -> {seg['end']:.3f}")


if __name__ == '__main__':
    import argparse
    main()
