"""Lead-operated recording plumbing. The unchanged measurement harness owns all mutations."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
# Reuse only installed browser/recorder binaries, never a browser profile.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / "artifacts/submission/browsers"))
sys.dont_write_bytecode = True
DEFAULT_BROWSER = ROOT / (
    "artifacts/submission/browsers/chromium-1254/chrome-mac-arm64/"
    "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
)
VIEWPORT = {"width": 1920, "height": 900}
VIDEO_SIZE = {"width": 1920, "height": 1080}
STAGES = {
    "01_open": "overview",
    "02_options": "plan",
    "03_selected": "activity",
    "04_interrupted": "activity",
    "05_reconciled": "activity",
    "06_observed": "outcome",
    "07_corrected": "outcome",
    "08_v2_options": "plan",
    "09_v2_observed": "outcome",
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def runtime_files(root):
    """Compare actual imported core and UI bytes, not Git state or version labels."""
    return {
        str(path.relative_to(root)): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
        and path.suffix in {".py", ".js", ".html", ".json", ".sql", ".yaml"}
    }


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--plugin-dir", required=True, type=Path,
                        help="Clean installed hermes_ops directory (not its parent)")
    parser.add_argument("--browser", type=Path, default=Path(
        os.environ.get("VIDEO_BROWSER", str(DEFAULT_BROWSER))))
    parser.add_argument("--hold-seconds", type=float, default=4.5)
    args = parser.parse_args()
    if not 3 <= args.hold_seconds <= 5:
        parser.error("--hold-seconds must be between 3 and 5")
    data_dir, output, plugin = (p.expanduser().resolve() for p in
                                (args.data_dir, args.artifacts, args.plugin_dir))
    if data_dir.exists() and any(data_dir.iterdir()):
        parser.error("Use a fresh, empty --data-dir; never reuse a completed measurement")
    if output.exists() and any(output.iterdir()):
        parser.error("Use a fresh --artifacts directory; never overwrite capture evidence")
    if not args.browser.is_file():
        parser.error(f"Browser executable not found: {args.browser}")
    repo_plugin = ROOT / "plugin/hermes_ops"
    expected, installed = runtime_files(repo_plugin), runtime_files(plugin)
    if not installed or expected != installed:
        changed = sorted(key for key in expected.keys() | installed.keys()
                         if expected.get(key) != installed.get(key))
        parser.error(f"Server/release runtime bytes differ: {changed}. Lead must resolve; no fallback.")
    # Import before any authoritative work: a missing recorder must not consume the fresh run.
    from playwright.sync_api import sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    (output / "screenshots").mkdir()
    (output / "recordings").mkdir()
    measurements = output / "measurements"
    harness = load(ROOT / "demo/run_demo.py", "_video_measurement_harness")
    serve = load(ROOT / "demo/serve.py", "_video_loopback_server")
    server = serve.create_server(data_dir, port=0)
    thread = threading.Thread(target=server.serve_forever, name="video-loopback", daemon=True)
    thread.start()
    manifest = {
        "schema": 1, "status": "capturing", "synthetic": True,
        "data_dir": str(data_dir), "plugin_dir": str(plugin),
        "server_plugin_dir": str(repo_plugin), "runtime_files_sha256": installed,
        "harness_sha256": sha256(ROOT / "demo/run_demo.py"),
        "server_sha256": sha256(ROOT / "demo/serve.py"),
        "viewport": VIEWPORT, "record_video_size": VIDEO_SIZE,
        "browser": str(args.browser), "stages": [], "screenshots": {},
        "result_json": str(measurements / "result.json"),
        "console_errors": [], "http_errors": [], "request_failures": [],
        "note": "Actual UI recording; harness alone advances state. No API interception or data injection.",
    }
    manifest_path = output / "capture-manifest.json"
    browser = context = video = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=str(args.browser), headless=True,
                args=["--disable-background-networking", "--no-first-run"])
            try:
                context = browser.new_context(
                    viewport=manifest["viewport"], device_scale_factor=1,
                    record_video_dir=str(output / "recordings"),
                    record_video_size=manifest["record_video_size"],
                    locale="en-SG", timezone_id="Asia/Singapore",
                    reduced_motion="reduce",
                )
                epoch = time.monotonic()
                page = context.new_page()
                video = page.video
                page.on("pageerror", lambda error: manifest["console_errors"].append(str(error)))
                page.on("console", lambda message: manifest["console_errors"].append(message.text)
                        if message.type == "error" else None)
                page.on("response", lambda response: manifest["http_errors"].append(
                    {"url": response.url, "status": response.status})
                    if response.status >= 400 and not response.url.endswith("/favicon.ico") else None)
                page.on("requestfailed", lambda request: manifest["request_failures"].append(
                    {"url": request.url, "failure": request.failure}))
                page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="networkidle")
                page.wait_for_function(
                    "typeof reload === 'function' && typeof setView === 'function'")
                page.locator("#content").wait_for(state="attached")
                page.mouse.move(1850, 55)

                def checkpoint(stage, captured):
                    if stage not in STAGES:
                        raise ValueError(f"Unrecognized capture checkpoint: {stage}")
                    # This is the real UI's read-only reload, never an injected state/render.
                    page.evaluate(
                        "async ({id,view}) => { await reload(id); setView(view);"
                        " document.querySelector('#content').scrollTop=0; }",
                        {"id": captured["case"]["id"], "view": STAGES[stage]})
                    page.wait_for_function(
                        "id => document.querySelector('#content').dataset.caseId === id",
                        arg=captured["case"]["id"])
                    if stage == "07_corrected":
                        page.locator('[data-section="correction"]').scroll_into_view_if_needed()
                    page.wait_for_timeout(250)
                    content = page.locator("#content").evaluate("""el => ({
                        case_id: el.dataset.caseId, scroll_top: el.scrollTop,
                        client_width: el.clientWidth, client_height: el.clientHeight,
                        bounds: el.getBoundingClientRect().toJSON()
                    })""")
                    screenshot = output / "screenshots" / f"{stage}.png"
                    page.screenshot(path=str(screenshot), full_page=False)
                    start = time.monotonic() - epoch
                    page.wait_for_timeout(args.hold_seconds * 1000)
                    end = time.monotonic() - epoch
                    manifest["screenshots"][stage] = str(screenshot)
                    manifest["stages"].append({
                        "stage": stage, "case_id": captured["case"]["id"],
                        "view": STAGES[stage], "content": content,
                        "stable_start_wall_seconds": start,
                        "stable_end_wall_seconds": end,
                        "screenshot": str(screenshot),
                        "measurement_json": str(measurements / f"{stage}.json"),
                    })
                    write(manifest_path, manifest)
                    print(f"Captured {stage}", file=sys.stderr, flush=True)

                harness.run(data_dir, plugin, measurements, checkpoint=checkpoint)
                if [item["stage"] for item in manifest["stages"]] != list(STAGES):
                    raise RuntimeError("Harness did not produce the complete ordered checkpoint set")
                page.wait_for_timeout(500)
                manifest["recording_wall_seconds"] = time.monotonic() - epoch
            finally:
                if context:
                    context.close()
                    if video:
                        manifest["raw_video"] = str(Path(video.path()).resolve())
                if browser:
                    browser.close()
        manifest["result_sha256"] = sha256(measurements / "result.json")
        manifest["raw_video_sha256"] = sha256(manifest["raw_video"])
        raw_seconds = float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
            "default=noprint_wrappers=1:nokey=1", manifest["raw_video"]], text=True))
        manifest["raw_video_seconds"] = raw_seconds
        # Playwright's recording epoch precedes navigation. Align its end to the
        # measured wall interval; edit points retain >0.6 s margins on both ends.
        offset = raw_seconds - manifest["recording_wall_seconds"]
        manifest["video_wall_offset_seconds"] = offset
        for stage in manifest["stages"]:
            stage["source_start_seconds"] = max(0, stage["stable_start_wall_seconds"] + offset + 0.8)
            stage["source_end_seconds"] = stage["stable_end_wall_seconds"] + offset - 0.6
            stage["measurement_sha256"] = sha256(stage["measurement_json"])
            stage["screenshot_sha256"] = sha256(stage["screenshot"])
        manifest["status"] = "recorded_pending_lead_review"
        write(manifest_path, manifest)
        print(json.dumps({key: manifest[key] for key in
                          ("raw_video", "screenshots", "result_json") } |
                         {"manifest": str(manifest_path)}, indent=2))
    except BaseException as error:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(error).__name__}: {error}"
        write(manifest_path, manifest)
        raise
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
