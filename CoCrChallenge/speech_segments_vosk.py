#!/usr/bin/env python3
"""
speech_segments_vosk.py

Extracts audio from a video (.MOV supported), runs Vosk speech recognition,
and outputs speech and no-speech segments as timestamp intervals.

Requirements:
 - ffmpeg installed and available on PATH
 - pip install vosk
 - a Vosk model directory (set with --model or download a model from https://alphacephei.com/vosk/models)

Usage:
 python3 speech_segments_vosk.py input_video.MOV

Notes on using webrtcvad instead:
 - webrtcvad requires 16-bit PCM mono audio (S16LE) sampled at 8000, 16000, 32000 or 48000 Hz.
 - If you prefer webrtcvad, convert the audio from .MOV to a mono S16LE WAV (e.g. using ffmpeg with -ar 16000 -ac 1 -f wav) before running webrtcvad.

This script:
 - extracts audio to a temporary 16kHz mono WAV using ffmpeg
 - runs Vosk and collects word timestamps
 - merges words into speech segments (allowing short gaps)
 - computes complementary no-speech segments
 - writes a JSON file with both speech and no_speech segments
"""

import argparse
import json
import os
import subprocess
import tempfile
import wave
from pathlib import Path

try:
    from vosk import Model, KaldiRecognizer
except Exception as e:
    raise ImportError("Missing vosk package. Install with `pip install vosk`." ) from e


def extract_audio_to_wav(input_video: str, out_wav: str, sample_rate: int = 16000):
    # Use ffmpeg to extract and convert audio to mono 16-bit PCM WAV at desired sample_rate
    cmd = [
        "ffmpeg", "-y", "-i", input_video,
        "-ar", str(sample_rate),
        "-ac", "1",
        "-vn",
        out_wav
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def get_video_duration(input_video: str) -> float:
    # Use ffprobe to obtain duration in seconds
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", input_video
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return float(result.stdout.strip())


def recognize_with_vosk(wav_path: str, model_path: str, max_silence: float = 0.5):
    # Load Vosk model
    if not os.path.isdir(model_path):
        raise FileNotFoundError(f"Vosk model directory not found: {model_path}")

    model = Model(model_path)

    speech_segments = []
    with wave.open(wav_path, "rb") as wf:
        sample_rate = wf.getframerate()
        rec = KaldiRecognizer(model, sample_rate)
        # Enable word-level timestamps so results include 'result' with start/end times
        try:
            rec.SetWords(True)
        except Exception:
            # Some older bindings may not expose SetWords; continue but word timestamps may be missing
            pass

        current_seg = None

        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break

            if rec.AcceptWaveform(data):
                res = json.loads(rec.Result())
                if "result" in res:
                    for w in res["result"]:
                        start = float(w["start"])
                        end = float(w["end"])
                        if current_seg is None:
                            current_seg = {"start": start, "end": end}
                        else:
                            # If gap between last end and this start is small, merge
                            if start - current_seg["end"] <= max_silence:
                                current_seg["end"] = end
                            else:
                                speech_segments.append(current_seg)
                                current_seg = {"start": start, "end": end}

        # final
        final_res = json.loads(rec.FinalResult())
        if "result" in final_res:
            for w in final_res["result"]:
                start = float(w["start"])
                end = float(w["end"])
                if current_seg is None:
                    current_seg = {"start": start, "end": end}
                else:
                    if start - current_seg["end"] <= max_silence:
                        current_seg["end"] = end
                    else:
                        speech_segments.append(current_seg)
                        current_seg = {"start": start, "end": end}

        if current_seg is not None:
            speech_segments.append(current_seg)

    # Ensure segments are sorted and merged if overlapping
    speech_segments.sort(key=lambda s: s["start"])
    merged = []
    for seg in speech_segments:
        if not merged:
            merged.append(seg)
        else:
            last = merged[-1]
            if seg["start"] <= last["end"] + 1e-6:
                last["end"] = max(last["end"], seg["end"])
            else:
                merged.append(seg)

    return merged


def compute_no_speech_segments(speech_segs, duration: float):
    no_speech = []
    cursor = 0.0
    for seg in speech_segs:
        if seg["start"] > cursor:
            no_speech.append({"start": cursor, "end": seg["start"]})
        cursor = max(cursor, seg["end"])
    if cursor < duration:
        no_speech.append({"start": cursor, "end": duration})
    return no_speech


def format_timecode(seconds: float) -> str:
    # Simple formatting H:MM:SS.mmm
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:06.3f}"


def main():
    parser = argparse.ArgumentParser(description="Extract speech/no-speech segments from video using Vosk")
    parser.add_argument("input_video", help="Path to input video (e.g. .MOV)")
    parser.add_argument("--model", default="model", help="Path to Vosk model directory")
    parser.add_argument("--out", default=None, help="Path to output JSON file (defaults next to input video)")
    parser.add_argument("--max-gap", type=float, default=0.5, help="Max silence gap (s) to merge words into a speech segment")
    args = parser.parse_args()

    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(current_dir, args.input_video)
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")
    
    model_path = os.path.join(current_dir, args.model)

    duration = get_video_duration(input_path)

    # Prepare temporary WAV
    with tempfile.TemporaryDirectory() as tmpd:
        wav_path = os.path.join(tmpd, "extracted_audio.wav")
        print(f"Extracting audio to temporary WAV (16k mono)...")
        extract_audio_to_wav(input_path, wav_path, sample_rate=16000)

        print(f"Running Vosk recognition (model: {args.model})...")
        speech_segs = recognize_with_vosk(wav_path, model_path, max_silence=args.max_gap)

    no_speech_segs = compute_no_speech_segments(speech_segs, duration)

    # Prepare output
    base = Path(input_path).stem
    out_path = args.out if args.out else str(Path(input_path).with_name(base + "_speech_segments.json"))

    combined = []
    for s in speech_segs:
        combined.append({
            "type": "speech",
            "start": s["start"],
            "end": s["end"],
            "start_timecode": format_timecode(s["start"]),
            "end_timecode": format_timecode(s["end"]) 
        })
    for s in no_speech_segs:
        combined.append({
            "type": "no_speech",
            "start": s["start"],
            "end": s["end"],
            "start_timecode": format_timecode(s["start"]),
            "end_timecode": format_timecode(s["end"]) 
        })

    # Sort segments by start
    combined.sort(key=lambda x: x["start"])

    with open(out_path, "w") as f:
        json.dump({"video": input_path, "duration": duration, "segments": combined}, f, indent=2)

    print(f"Wrote segments to: {out_path}")
    print("Summary:")
    for seg in combined:
        print(f" - {seg['type']}: {seg['start_timecode']} -> {seg['end_timecode']}")


if __name__ == '__main__':
    main()
