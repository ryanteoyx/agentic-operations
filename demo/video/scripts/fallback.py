"""Rasterize offline editorial overlays for FFmpeg; never touches the live product UI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / "artifacts/submission/browsers"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--draft", action="store_true")
    args = parser.parse_args()
    project = args.project.resolve()
    plan = json.loads((project / "production.json").read_text())
    if plan["draft"] != args.draft:
        raise ValueError("Draft/final mode mismatch")
    output = project / "fallback-overlays"
    output.mkdir(exist_ok=True)
    from playwright.sync_api import sync_playwright

    browser_path = os.environ.get("HYPERFRAMES_BROWSER_PATH") or str(ROOT / (
        "artifacts/submission/browsers/chromium-1254/chrome-mac-arm64/"
        "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=browser_path, headless=True)
        try:
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.goto((project / "index.html").as_uri(), wait_until="load")
            page.evaluate("async () => { await document.fonts.ready; }")
            # Only the offline film composition is changed, never a service page.
            # PNG overlays replace unavailable libass/drawtext in the installed FFmpeg.
            page.evaluate("""() => {
                document.querySelectorAll('video,audio,#progress').forEach(el => el.remove());
                for (const el of [document.documentElement, document.body, document.querySelector('#main')])
                    el.style.background = 'transparent';
                for (const el of document.querySelectorAll('.title-inner')) {
                    el.style.opacity = '1'; el.style.transform = 'none';
                }
            }""")
            boundaries = page.evaluate("""() => [...document.querySelectorAll('.clip')].flatMap(el => {
                const start = Number(el.dataset.start), duration = Number(el.dataset.duration);
                return [start, start + duration];
            })""")
            frames = sorted({0, 2460} | {max(0, min(2460, round(t * 30))) for t in boundaries})
            lines = []
            for index, (start, end) in enumerate(zip(frames, frames[1:])):
                if end <= start:
                    continue
                # Seek one half-frame into the quantized interval to avoid float seams.
                seconds = (start + 0.5) / 30
                page.evaluate("""t => {
                    for (const el of document.querySelectorAll('.clip')) {
                        const start = Math.round(Number(el.dataset.start) * 30) / 30;
                        const end = Math.round((Number(el.dataset.start) + Number(el.dataset.duration)) * 30) / 30;
                        el.style.visibility = t >= start && t < end ? 'visible' : 'hidden';
                    }
                }""", seconds)
                name = f"overlay-{index:03d}.png"
                page.screenshot(path=str(output / name), omit_background=True)
                lines.extend([f"file '{name}'", "option framerate 30",
                              f"duration {(end - start) / 30:.9f}"])
            lines.extend([f"file '{name}'", "option framerate 30"])
            (output / "concat.txt").write_text("\n".join(lines) + "\n")
        finally:
            browser.close()
    print(output / "concat.txt")


if __name__ == "__main__":
    main()
