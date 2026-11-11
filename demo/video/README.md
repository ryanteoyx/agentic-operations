# Local product film — 82 seconds

This directory contains **video plumbing only**. The coordinator owns the real
measurement run and checks its evidence before final staging. Nothing here commits,
publishes, connects an account, or submits a form. All generated media and private
capture manifests live under the ignored `artifacts/video/` tree.

## Fixed production contract

- 1920 × 1080, 30 fps, exactly 82 seconds; H.264 / `yuv420p`, stereo AAC / 48 kHz.
- Hyperframes **0.9.34**, GSAP **3.14.2**, local fonts/assets, two render workers.
- Transcelestial-derived charcoal `#131211`, ice cyan `#64f5f8`, off-white
  `#f5f5f5`, muted `#b9c8c9`, and borders `#344040`; no gradients.
- Actual standalone control-room viewport is **1920×900**, recorded at
  **1920×1080** without scaling, leaving a 180 px lower caption band. The brand
  header appears only in the intro (0–5.3 s) and outro (77.9–82 s), never over the
  live UI. Footage remains full-size at (0, 0).
- Fictional company/supplier names come from the real fruit-named UI
  (Orange, Banana, Grapefruit, Plum); no video-side replacement of product data.
- `narration.txt` is the approved, unmodified narration. Do not paraphrase captions.
- Voice: **Microsoft `en-US-EmmaMultilingualNeural`**, verified in
  `artifacts/video/audio/voice.json`. The **edge-tts client is open source**; the
  Microsoft-hosted neural speech service/model is **not**. No paid API or signup.
- This is a deterministic synthetic scenario, not proof of real manufacturing ROI
  or a model-worker execution. Captured UI state comes from the real service only.
- Edited footage consists of chronological recorded stage clips, with original
  frames held when necessary to match narration. This is not real-time execution.

## Existing tools and audio

Run commands from the repository root. Existing dependencies are installed.
The standalone `artifacts/video/.venv/` is not the Hermes environment.

```sh
command -v ffmpeg
command -v ffprobe
artifacts/video/.venv/bin/python demo/video/scripts/voice.py --reuse-raw
```

`--reuse-raw` performs **no new speech request**. Preserve `narration-raw.mp3`,
`words-raw.json`, and `voice.json`. The raw voice is 73.968 s; the normalized tempo
is 0.9507455013× (slightly slower, below the 1.15× cap). The final spoken word ends
at approximately 77.813 s, followed by silence to 82 s. A separate post-loudnorm
padding pass avoids FFmpeg resampling/latency shortening the output.

Generated audio: `artifacts/video/audio/narration.wav`, `narration.m4a`,
`captions.{json,srt,vtt}`, `words.json`, `scene-timing.json`, `audio-production.json`.

If dependencies must be recreated, install **only** into this dedicated video
environment: `artifacts/video/.venv/bin/python -m pip install -r demo/video/requirements.txt`.
Do not install packages into Hermes. Do not download a browser when the supplied
binary/cache already exists.

## Lead-only: capture once, after release review

**The video worker must not run this command.** The lead runs it after reviewing the
driver and committing the release, with a fresh empty data root and a clean
installed `hermes_ops` package:

```sh
PYTHONDONTWRITEBYTECODE=1 artifacts/video/.venv/bin/python demo/video/scripts/capture.py \
  --data-dir /absolute/fresh/demo-data \
  --artifacts /Users/ryanteoyx/agentic-operations/artifacts/video/capture-release \
  --plugin-dir /absolute/clean-installed/plugin/hermes_ops
```

`--plugin-dir` must point **at `hermes_ops`**, not its parent.

The driver:

1. Requires fresh data and artifact directories; refuses overwrite/re-run.
2. Checks `.py`, `.html`, `.json`, `.sql`, and `.yaml` runtime bytes in the repository plugin against
   the clean installed package. `demo/serve.py` loads the repository-relative
   runtime; differing bytes are a hard error, never silently accepted. The lead
   should review the recorded hash map as well.
3. Imports **unchanged** `demo/run_demo.py` and `demo/serve.py`, hosts
   `create_server(data_dir, port=0)` on loopback in its own thread, and calls
   `run(data_dir, plugin_dir, artifact_dir, checkpoint=...)` once.
4. Launches a **fresh headless browser/context**, not CDP attachment, not a
   persistent profile. Reuses only the supplied Chrome and Playwright FFmpeg
   binaries under `artifacts/submission/browsers/`. Never reads/writes the form
   browser profile or its storage state. `VIDEO_BROWSER`/`--browser` can override
   the executable; `PLAYWRIGHT_BROWSERS_PATH` can override the recorder cache.
5. Before the harness runs, the driver requires `reload`, `setView`, and `#content`.
   Each checkpoint calls the real `reload(id)` and `setView(view)`, resets the
   internal `#content` scroll position, and verifies its full `dataset.caseId`.
   Views are overview / plan / activity / outcome; the correction stage scrolls
   `[data-section="correction"]` into view. It takes a **1920×900** viewport
   screenshot and holds 4.5 seconds
   (configurable only within 3–5 s). No product data injection, API interception,
   state-writing script, or mutating UI button. The manifest records the actual
   `#content` case ID, scroll position, dimensions, and bounds beside each stage.
6. Closes the recording context before resolving the raw WebM path. Saves console,
   HTTP, and request errors; freezes recording offsets and SHA-256 hashes of the
   raw recording, each screenshot, each measurement JSON, and final result.
   Shuts down only its own browser/server.

Output JSON on stdout contains `raw_video`, `screenshots`, `result_json`,
and `manifest`. Progress goes to stderr.

Expected artifacts:

```text
artifacts/video/capture-release/
  capture-manifest.json          # status recorded_pending_lead_review
  recordings/<playwright>.webm
  screenshots/01_open.png ... 09_v2_observed.png
  measurements/01_open.json ... 09_v2_observed.json
  measurements/result.json       # unchanged harness output
```

The lead checks the nine screenshots, stage JSONs, console errors, and result.
The driver does not approve or calculate business outcomes. It does not rerun or
rederive queries. Any runtime/hash/selector/interface mismatch must go to the lead;
do not modify the business harness or server to make capture pass.

## Draft plumbing check (no measured business data)

```sh
npm --prefix demo/video run stage -- --draft
npm --prefix demo/video run check -- --draft --json --budget 180s
node demo/video/scripts/hyperframes.mjs snapshot --draft \
  --at 0,8,30,80 --no-end \
  --output /Users/ryanteoyx/agentic-operations/artifacts/video/draft/snapshots
npm --prefix demo/video run render -- --draft --smoke
```

All such files say **DRAFT**, are under `artifacts/video/draft/`, and show a
capture-pending placeholder, **not a fake working product**. A smoke file is only
3 seconds and is never a deliverable. A full draft uses `--draft` without `--smoke`.

## Lead: stage checked captures, inspect, then render

`--checked-result` is the lead's explicit attestation that the supplied result has
been checked. It must hash-match the unchanged result from that exact capture.
The fixed narration's numeric claims are checked against this file; unsupported
claims cause failure. On-screen measured numbers are read only from that file.

```sh
npm --prefix demo/video run stage -- \
  --capture /Users/ryanteoyx/agentic-operations/artifacts/video/capture-release/capture-manifest.json \
  --checked-result /Users/ryanteoyx/agentic-operations/artifacts/video/capture-release/measurements/result.json
npm --prefix demo/video run check -- --json --budget 180s
node demo/video/scripts/hyperframes.mjs snapshot \
  --at 2,12,24,30,36,42,50,58,61,66,80 --no-end \
  --output /Users/ryanteoyx/agentic-operations/artifacts/video/final/snapshots
npm --prefix demo/video run preview
node demo/video/scripts/hyperframes.mjs preview --status
npm --prefix demo/video run render
```

Preview uses Hyperframes' owned background mode, opens no user browser by default,
and prints the local Studio URL. To stop **this** preview:
`node demo/video/scripts/hyperframes.mjs preview --stop`.

Final path: **`artifacts/video/final/agentic-operations-82s.mp4`**.
Also retained: the Hyperframes master, render provenance JSON, and technical
verification JSON. No final render is permitted before real checked capture.

The render wrapper runs the full Hyperframes check, uses two workers, caps its
Hyperframes render attempt at ten minutes, then performs an explicit delivery
encode. It never publishes or calls paid/cloud services; telemetry/update checks
and orphan-process cleanup are disabled. Chrome is always a new renderer process.

If Hyperframes is blocked for ten minutes, use the offline, explicitly disclosed
**FFmpeg actual-UI fallback** (not labelled as a Hyperframes render):

```sh
npm --prefix demo/video run render -- --fallback
```

It uses the **same checked actual footage**, exact caption text/timing and Emma
audio, with charcoal/ice-cyan labels and static title cards. The installed FFmpeg
does not include libass/drawtext, so a fresh headless browser rasterizes only the
offline editorial overlays to transparent PNGs; FFmpeg overlays them on the real
recording. It cannot run with missing captures or in draft mode. No
synthesized/reconstructed product UI.

## Verification and release boundary

```sh
artifacts/video/.venv/bin/python demo/video/scripts/verify.py \
  --project artifacts/video/final/project \
  --video artifacts/video/final/agentic-operations-82s.mp4
```

Verification checks exact narration/captions, provenance hashes, Emma voice,
tempo/last-word bounds, 82 s (<90), 2460 frames, 1920×1080, 30 fps, H.264/yuv420p,
AAC stereo/48 kHz, full decode, and delivered loudness/no clipping. It records
**technical checks passed; human review required**, not a public-release approval.

Before upload: watch all scenes, listen to every word, inspect speech sync and UI
legibility, confirm checked numbers, and ensure no DRAFT. X posting remains
blocked/unperformed until the lead has an authorized working upload surface.
No code in this directory commits or publishes.
