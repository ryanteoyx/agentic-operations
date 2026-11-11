"""Offline video delivery checks; never runs the business scenario or publishes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
OUTPUT = SOURCE.parents[1] / "artifacts/video"


def read(path):
    return json.loads(path.read_text())


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def execute(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--project", type=Path, default=OUTPUT / "final/project")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    project = args.project.resolve()
    video = (args.video or OUTPUT / "final/agentic-operations-82s.mp4").resolve()
    plan = read(project / "production.json")
    if plan["draft"] != args.draft:
        raise ValueError("Draft/final verification mode mismatch")
    if args.smoke and not args.draft:
        raise ValueError("Short smoke files cannot be verified as final")
    captions = read(project / "captions.json")
    narration = (SOURCE / "narration.txt").read_text().strip()
    assert " ".join(c["text"] for c in captions) == " ".join(narration.split()), "Caption text changed"
    assert sha256(SOURCE / "narration.txt") == plan["narrationSha256"], "Narration source changed"
    assert (project / "narration.txt").read_bytes() == (SOURCE / "narration.txt").read_bytes()
    for index, caption in enumerate(captions):
        assert 0 <= caption["start"] < caption["end"] < 82
        if index:
            assert captions[index - 1]["end"] <= caption["start"], "Caption groups overlap"
    voice = plan["voice"]
    assert voice["voice"] == "en-US-EmmaMultilingualNeural"
    assert 0.75 <= voice["atempo"] <= 1.15
    assert voice["lastWordEndSeconds"] < 81
    assert abs(voice["normalizedDurationSeconds"] - 82) < 0.001
    if not args.draft:
        assert sha256(plan["checkedResult"]) == plan["resultSha256"], "Checked result changed"
        assert sha256(plan["captureManifest"]) == plan["captureManifestSha256"], "Capture changed"
        assert "DRAFT" not in (project / "index.html").read_text(), "Draft content in final HTML"
        assert (project / "assets/ui.mp4").is_file(), "Actual UI recording absent"
    probe = json.loads(execute(
        "ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(video)).stdout)
    picture = next(s for s in probe["streams"] if s["codec_type"] == "video")
    audio = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    target = 3 if args.smoke else 82
    duration = float(probe["format"]["duration"])
    assert duration < 90 and abs(duration - target) <= 0.08, f"Duration {duration} != {target}"
    assert (picture["width"], picture["height"]) == (1920, 1080)
    assert picture["codec_name"] == "h264" and picture["pix_fmt"] == "yuv420p"
    assert Fraction(picture["avg_frame_rate"]) == 30
    assert int(picture["nb_frames"]) == target * 30
    assert audio["codec_name"] == "aac" and int(audio["sample_rate"]) == 48000
    assert audio["channels"] == 2
    assert abs(float(audio["duration"]) - target) <= 0.08
    execute("ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-")
    # Inspect the delivered AAC, not just source WAV metadata.
    analysis = execute("ffmpeg", "-hide_banner", "-i", str(video), "-vn", "-af",
                       "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-").stderr
    loudness = json.loads(analysis[analysis.rfind("{"):analysis.rfind("}") + 1])
    if not args.smoke:
        assert -18 <= float(loudness["input_i"]) <= -14, "Review delivered speech loudness"
        assert float(loudness["input_tp"]) < 0, "Delivered audio clips"
    report = {
        "status": "technical_checks_passed_human_review_required",
        "draft": args.draft, "video": str(video), "sha256": sha256(video),
        "durationSeconds": duration, "frames": int(picture["nb_frames"]),
        "width": picture["width"], "height": picture["height"], "fps": 30,
        "videoCodec": picture["codec_name"], "pixelFormat": picture["pix_fmt"],
        "audioCodec": audio["codec_name"], "audioSampleRate": audio["sample_rate"],
        "exactNarrationAndCaptions": True, "voice": voice["voice"],
        "rawSpeechSeconds": voice["rawDurationSeconds"], "tempo": voice["atempo"],
        "lastSpokenWordEnds": voice["lastWordEndSeconds"], "loudness": loudness,
        "remainingHumanChecks": [
            "Listen to all narration; check pronunciation, sync, and uncut final words.",
            "Inspect all nine actual UI scenes and verify critical fields remain legible.",
            "Lead confirms every narrated measurement against the unchanged captured result.",
            "Do not upload a DRAFT or a smoke render.",
        ],
    }
    report_path = video.with_suffix(".verification.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
