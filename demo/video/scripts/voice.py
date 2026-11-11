"""Generate only the approved public narration; no credentials or product data."""

import argparse
import asyncio
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
OUTPUT = SOURCE.parents[1] / "artifacts" / "video" / "audio"
VOICE = "en-US-EmmaMultilingualNeural"
DURATION = 82.0
LEAD_IN = 0.4
SCENE_PHRASES = [
    "I'm Ryan's Devin.",
    "This is a synthetic manufacturer.",
    "Hermes tools and this control room",
    "Now we interrupt the execution process",
    "We advance the simulated clock",
    "Supplier evidence supports",
    "This is durable execution",
]


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def duration(path):
    return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(path)))


def timestamp(seconds, separator=","):
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{milliseconds:03d}"


async def synthesize(text):
    import edge_tts

    voices = await edge_tts.list_voices()
    matching = [voice for voice in voices if voice["ShortName"] == VOICE]
    if not matching:
        candidates = [voice["ShortName"] for voice in voices if "Emma" in voice["ShortName"]]
        raise RuntimeError(f"Requested Emma voice unavailable; available Emma voices: {candidates}")
    (OUTPUT / "voice.json").write_text(json.dumps(matching[0], indent=2) + "\n")
    words = []
    communicate = edge_tts.Communicate(text, VOICE, rate="+0%", boundary="WordBoundary")
    with (OUTPUT / "narration-raw.mp3").open("wb") as audio:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 10000000,
                    "end": (chunk["offset"] + chunk["duration"]) / 10000000,
                })
    if not words:
        raise RuntimeError("No word timings returned; do not invent caption alignment.")
    (OUTPUT / "words-raw.json").write_text(json.dumps(words, indent=2) + "\n")


def align_original_text(text, words):
    """Attach original punctuation to timed words, preserving authored captions."""
    def key(value):
        return re.sub(r"[^a-z0-9]", "", value.lower())

    original = list(re.finditer(r"\S+", text))
    position = 0
    aligned = []
    for token in original:
        target = key(token.group())
        begin = position
        collected = ""
        while position < len(words) and len(collected) < len(target):
            collected += key(words[position]["text"])
            position += 1
        if collected != target:
            raise RuntimeError(f"Cannot align original token {token.group()!r}: {collected!r}")
        aligned.append({
            "text": token.group(), "char": token.start(),
            "start": words[begin]["start"], "end": words[position - 1]["end"],
        })
    if position != len(words):
        raise RuntimeError("Unused spoken words; review exact narration.")
    return aligned


def make_captions(words):
    captions, group = [], []
    for index, word in enumerate(words):
        group.append(word)
        next_text = words[index + 1]["text"] if index + 1 < len(words) else ""
        length = len(" ".join(item["text"] for item in group))
        if (word["text"].endswith((".", ":", "?")) or len(group) >= 9
                or length + len(next_text) + 1 > 69 or index == len(words) - 1):
            captions.append({
                "start": round(group[0]["start"], 3),
                "end": round(min(group[-1]["end"] + 0.09,
                                 words[index + 1]["start"] - 0.02
                                 if index + 1 < len(words) else DURATION), 3),
                "text": " ".join(item["text"] for item in group),
            })
            group = []
    return captions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-raw", action="store_true", help="No further network/TTS request")
    parser.add_argument("--speech-seconds", type=float, default=77.8,
                        help="Natural narration window; padding makes total exactly 82 s")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    text = (SOURCE / "narration.txt").read_text().strip()
    if not args.reuse_raw:
        asyncio.run(synthesize(text))
    words = align_original_text(text, json.loads((OUTPUT / "words-raw.json").read_text()))
    raw_duration = duration(OUTPUT / "narration-raw.mp3")
    tempo = raw_duration / args.speech_seconds
    if not 0.75 <= tempo <= 1.15:
        raise RuntimeError(f"Required tempo {tempo:.4f} outside allowed range 0.75–1.15; adjust pauses/rate.")
    if args.speech_seconds + LEAD_IN > 81:
        raise RuntimeError("Narration must finish before 81 s; never truncate speech.")
    audio_filter = f"atempo={tempo:.8f},adelay={round(LEAD_IN * 1000)}:all=1,apad,atrim=duration=82"
    analysis = subprocess.run([
        "ffmpeg", "-hide_banner", "-i", str(OUTPUT / "narration-raw.mp3"),
        "-af", f"{audio_filter},loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-",
    ], check=True, capture_output=True, text=True).stderr
    measurements = json.loads(analysis[analysis.rfind("{"):analysis.rfind("}") + 1])
    normalize = (
        "loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:"
        f"measured_I={measurements['input_i']}:measured_TP={measurements['input_tp']}:"
        f"measured_LRA={measurements['input_lra']}:measured_thresh={measurements['input_thresh']}:"
        f"offset={measurements['target_offset']}"
    )
    run("ffmpeg", "-hide_banner", "-y", "-i", str(OUTPUT / "narration-raw.mp3"),
        "-af", f"{audio_filter},{normalize}", "-ar", "48000", "-ac", "2",
        "-c:a", "pcm_s16le", str(OUTPUT / "narration-normalized.wav"))
    # Pad after loudnorm's resampling/latency, in a separate 48 kHz pass.
    run("ffmpeg", "-hide_banner", "-y", "-i", str(OUTPUT / "narration-normalized.wav"),
        "-af", "apad", "-t", str(DURATION), "-ar", "48000", "-ac", "2",
        "-c:a", "pcm_s16le", str(OUTPUT / "narration.wav"))
    run("ffmpeg", "-hide_banner", "-y", "-i", str(OUTPUT / "narration.wav"),
        "-c:a", "aac", "-b:a", "192k", str(OUTPUT / "narration.m4a"))
    for word in words:
        word["start"] = word["start"] / tempo + LEAD_IN
        word["end"] = word["end"] / tempo + LEAD_IN
    if words[-1]["end"] >= 81:
        raise RuntimeError("Aligned speech exceeds the safe narration window; do not truncate.")
    captions = make_captions(words)
    (OUTPUT / "captions.json").write_text(json.dumps(captions, indent=2) + "\n")
    (OUTPUT / "words.json").write_text(json.dumps(words, indent=2) + "\n")
    (OUTPUT / "captions.srt").write_text("\n\n".join(
        f"{i + 1}\n{timestamp(c['start'])} --> {timestamp(c['end'])}\n{c['text']}"
        for i, c in enumerate(captions)) + "\n")
    (OUTPUT / "captions.vtt").write_text("WEBVTT\n\n" + "\n\n".join(
        f"{timestamp(c['start'], '.')} --> {timestamp(c['end'], '.')}\n{c['text']}"
        for c in captions) + "\n")
    starts = []
    for phrase in SCENE_PHRASES:
        char = text.index(phrase)
        start = next(word["start"] for word in words if word["char"] == char)
        starts.append(round(max(0, start - 0.18), 3))
    starts[0] = 0
    scenes = [{
        "id": f"scene-{i + 1:02d}", "start": start,
        "end": starts[i + 1] if i + 1 < len(starts) else DURATION,
        "narrationStartsWith": SCENE_PHRASES[i],
    } for i, start in enumerate(starts)]
    (OUTPUT / "scene-timing.json").write_text(json.dumps(scenes, indent=2) + "\n")
    shutil.copyfile(SOURCE / "narration.txt", OUTPUT / "narration.txt")
    metadata = {
        "voice": VOICE, "client": "edge-tts==7.3.1",
        "speechService": "Microsoft hosted Edge neural speech (not open source)",
        "textSha256": hashlib.sha256(text.encode()).hexdigest(),
        "rawDurationSeconds": raw_duration, "atempo": tempo,
        "leadInSeconds": LEAD_IN, "normalizedDurationSeconds": duration(OUTPUT / "narration.wav"),
        "lastWordEndSeconds": words[-1]["end"],
        "wordCount": len(text.split()), "normalization": measurements,
    }
    (OUTPUT / "audio-production.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({"audio": str(OUTPUT / "narration.wav"), **metadata, "scenes": scenes}, indent=2))


if __name__ == "__main__":
    main()
