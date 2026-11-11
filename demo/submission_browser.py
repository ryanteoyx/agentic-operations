#!/usr/bin/env python3
"""Prepare the authorized Typeform in an isolated headed browser; NEVER submit.

One-time isolated setup (run from the repository root):
  python3 -m venv artifacts/submission/venv
  artifacts/submission/venv/bin/python -m pip install playwright==1.65.0
  PLAYWRIGHT_BROWSERS_PATH="$PWD/artifacts/submission/browsers" \
    artifacts/submission/venv/bin/python -m playwright install chromium

Usage:
  artifacts/submission/venv/bin/python demo/submission_browser.py prepare
  artifacts/submission/venv/bin/python demo/submission_browser.py resume \
    --catalog-pr-url REAL_PR_URL --x-post-url REAL_POST_URL

Only public UI controls are used. No submission APIs, cookies, credentials,
account actions, or X-limit workarounds. Typeform may autosave partial answers.
The browser remains running for the user and lead agent to inspect.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "submission"
PROFILE = ARTIFACTS / "browser-profile"
STATE = ARTIFACTS / "browser-state.json"
ENTRANT = ROOT / ".devin" / "submission.local.json"
FORM_URL = "https://form.typeform.com/to/FwJLvOln"
TITLE = "Agentic Operations"
DESCRIPTION = (
    "A Hermes plugin for durable manufacturing decisions: compare constrained "
    "shortage plans, reconcile interrupted simulated ERP actions, observe "
    "shipment outcomes, and activate evidence-backed estimate corrections."
)
LABELS = (
    "Plugin Title",
    "Plugin Description",
    "Email Address",
    "Discord Username",
    "X Demo Post Link",
    "GitHub Link to your Hermes Plugin Pull Request",
)
# Public schema IDs are recorded for reference only; Typeform's UI uses
# different DOM IDs. Interact by the actual accessible field labels instead.
FIELD_IDS = (
    "JLeqRn0QD1AC", "XASUlXDrI0Zn", "TeMPJ0hn8J40", "S64JXHHB6wm2",
    "ZmGHct8sYmhE", "l99CV8hLADvi",
)


class HandoffError(Exception):
    """A safe, non-PII explanation suitable for terminal output."""


def private_json(path: Path, data: dict) -> None:
    with open(path, "w", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
    path.chmod(0o600)


def entrant_values() -> tuple[str, str]:
    try:
        data = json.loads(ENTRANT.read_text())
        email, discord = data["email"], data["discord_username"]
        if not isinstance(email, str) or not re.fullmatch(r"\S+@\S+\.\S+", email):
            raise ValueError
        if not isinstance(discord, str) or not discord.strip():
            raise ValueError
        return email, discord
    except (OSError, ValueError, KeyError, TypeError):
        raise HandoffError("Entrant file is missing or its email/Discord fields are invalid.") from None


def validate_links(catalog: str, post: str) -> None:
    pr, x = urlparse(catalog), urlparse(post)
    if (
        pr.scheme != "https" or pr.netloc.lower() != "github.com"
        or not re.fullmatch(r"/NousResearch/hermes-agent/pull/[1-9][0-9]*/?", pr.path, re.I)
        or pr.query or pr.fragment
    ):
        raise HandoffError("Provide the actual HTTPS NousResearch/hermes-agent catalog PR URL.")
    if (
        x.scheme != "https" or x.netloc.lower() not in {"x.com", "www.x.com", "twitter.com"}
        or not re.fullmatch(r"/[A-Za-z0-9_]+/status/[1-9][0-9]*/?", x.path)
        or x.query or x.fragment
    ):
        raise HandoffError("Provide the actual HTTPS X demo status URL (without tracking parameters).")


def attach_or_launch(pw) -> dict:
    """Reuse only this helper's isolated process; never inspect a user profile."""
    ARTIFACTS.mkdir(parents=True, exist_ok=True, mode=0o700)
    ARTIFACTS.chmod(0o700)
    PROFILE.mkdir(exist_ok=True, mode=0o700)
    if STATE.exists():
        state = json.loads(STATE.read_text())
        pid = int(state["pid"])
        command = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True, text=True, timeout=5,
        ).stdout
        if command:
            if f"--user-data-dir={PROFILE}" not in command:
                raise HandoffError("Recorded PID is not the owned submission browser; refusing attachment.")
            port = int((PROFILE / "DevToolsActivePort").read_text().splitlines()[0])
            if port != int(state["port"]):
                raise HandoffError("Owned browser debugging port changed; inspect local state before retrying.")
            state["cdp_url"] = f"http://127.0.0.1:{port}"
            return state

    executable = pw.chromium.executable_path
    if not Path(executable).is_file():
        raise HandoffError("Isolated Chromium is missing; run the setup commands in this helper's docstring.")
    # Remove only the stale port marker in our own profile; leave saved progress.
    (PROFILE / "DevToolsActivePort").unlink(missing_ok=True)
    process = subprocess.Popen(
        [
            executable, f"--user-data-dir={PROFILE}",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
            "--no-first-run", "--no-default-browser-check", "--password-store=basic",
            "--use-mock-keychain", "--disable-save-password-bubble",
            "--window-size=1280,900", FORM_URL,
        ],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + 20
    while not (PROFILE / "DevToolsActivePort").exists():
        if process.poll() is not None or time.monotonic() > deadline:
            raise HandoffError("Headed Chromium did not become ready within 20 seconds.")
        time.sleep(0.1)
    port = int((PROFILE / "DevToolsActivePort").read_text().splitlines()[0])
    state = {
        "pid": process.pid, "port": port, "cdp_url": f"http://127.0.0.1:{port}",
        "console_url": f"http://127.0.0.1:{port}/json/list",
        "profile": str(PROFILE), "executable": executable, "form_url": FORM_URL,
        "status": "launched_not_filled",
    }
    private_json(STATE, state)
    return state


def focused(page):
    block = page.locator('[data-qa-block="true"][data-qa-focused="true"]')
    block.wait_for(state="visible")
    if block.count() != 1:
        raise HandoffError("Typeform no longer exposes one focused question; no further clicks made.")
    return block


def current_label(page) -> str | None:
    block = focused(page)
    for label in LABELS:
        if block.get_by_role("textbox", name=re.compile(re.escape(label), re.I)).count() == 1:
            return label
    return None


def expect_label(page, label: str):
    page.wait_for_function(
        """label => {
          const block = document.querySelector('[data-qa-block="true"][data-qa-focused="true"]');
          const title = block?.querySelector('[data-qa*="block-title"]');
          return title && title.textContent.toLowerCase().includes(label.toLowerCase());
        }""",
        arg=label, timeout=15000,
    )
    block = focused(page)
    field = block.get_by_role("textbox", name=re.compile(re.escape(label), re.I))
    if field.count() != 1:
        raise HandoffError("Expected field is missing or ambiguous; browser left open for inspection.")
    return block, field


def click_next_question(page, label: str, next_label: str) -> None:
    # Explicit allowlist: the final PR field can NEVER be advanced by this helper.
    if label not in LABELS[:5]:
        raise HandoffError("Refusing to advance a final or unknown question.")
    block, _ = expect_label(page, label)
    block.get_by_role("button", name="OK Next question", exact=True).click()
    if next_label:
        expect_label(page, next_label)


def go_to_first(page) -> None:
    start = page.get_by_role("button", name="Start Submission", exact=True)
    if start.count() == 1 and start.is_visible():
        start.click()
        expect_label(page, LABELS[0])
        return
    for _ in range(8):
        if current_label(page) == LABELS[0]:
            return
        previous = page.get_by_role("button", name="Navigate to previous question", exact=True)
        if previous.count() != 1 or not previous.is_enabled():
            break
        previous_ref = focused(page).get_attribute("data-qa-blockref")
        previous.click()
        page.wait_for_function(
            """previous => document.querySelector(
              '[data-qa-block="true"][data-qa-focused="true"]'
            )?.getAttribute('data-qa-blockref') !== previous""",
            arg=previous_ref, timeout=15000,
        )
    raise HandoffError("Cannot safely navigate back to Plugin Title; form UI may have changed.")


def fill_checked(page, label: str, value: str) -> None:
    _, field = expect_label(page, label)
    field.fill(value)
    if field.input_value() != value:
        raise HandoffError("A field did not retain its intended value; browser left open.")


def public_only_screenshot(page, email: str, discord: str) -> str | None:
    # Repeated runs might already contain PII in an adjacent mounted question.
    # Do not capture at all unless neither private value is rendered or entered.
    private_present = page.evaluate(
        """values => {
          const text = document.body.innerText;
          const fields = [...document.querySelectorAll('input,textarea')].map(e => e.value);
          return values.some(value => text.includes(value) || fields.some(v => v.includes(value)));
        }""",
        [email, discord],
    )
    if private_present:
        return None
    # Capture only the plugin-description question; never the email question.
    block, _ = expect_label(page, LABELS[1])
    path = ARTIFACTS / "public-fields-only.png"
    block.screenshot(path=str(path), animations="disabled")
    path.chmod(0o600)
    return str(path)


def advance_catalog_statement(page) -> None:
    # After the X field, wait for either the PR field or the catalog statement.
    page.wait_for_function(
        """() => {
          const block = document.querySelector('[data-qa-block="true"][data-qa-focused="true"]');
          const title = block?.querySelector('[data-qa*="block-title"]');
          return block && title && !title.textContent.includes('X Demo Post Link');
        }""", timeout=15000,
    )
    if current_label(page) == LABELS[5]:
        return
    block = focused(page)
    # Only known, text-only catalog instructions are eligible to advance.
    text = block.inner_text()
    if block.get_by_role("textbox").count() or not re.search(r"catalog|pull request", text, re.I):
        raise HandoffError("Unexpected statement after X link; manual inspection required.")
    next_button = block.get_by_role(
        "button", name=re.compile(r"^(?:Continue|OK)(?: Next question)?$", re.I),
    )
    if next_button.count() != 1:
        raise HandoffError("Catalog statement's safe Continue button was not found; stopped.")
    next_button.click()
    expect_label(page, LABELS[5])


def run(args) -> None:
    email, discord = entrant_values()
    if args.command == "resume":
        validate_links(args.catalog_pr_url, args.x_post_url)
    # Force browser binaries and all runtime data into ignored local artifacts.
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(ARTIFACTS / "browsers")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        state = attach_or_launch(pw)
        browser = pw.chromium.connect_over_cdp(state["cdp_url"], timeout=15000)
        pages = [p for ctx in browser.contexts for p in ctx.pages if p.url.split("?")[0] == FORM_URL]
        if len(pages) != 1:
            raise HandoffError("Expected exactly one owned Typeform tab; inspect the headed browser.")
        page = pages[0]
        page.set_default_timeout(15000)
        page.set_default_navigation_timeout(30000)
        page.bring_to_front()
        page.wait_for_load_state("domcontentloaded")
        go_to_first(page)
        # Verification and field entry are UI-only; private values never leave
        # memory except through the user-authorized Typeform and owned profile.
        for index, value in enumerate((TITLE, DESCRIPTION, email, discord)):
            fill_checked(page, LABELS[index], value)
            if index == 1:
                screenshot = public_only_screenshot(page, email, discord)
                if screenshot:
                    state["public_only_screenshot"] = screenshot
            click_next_question(page, LABELS[index], LABELS[index + 1])

        # Historical inspection flags must not describe a newly replayed form.
        for key in ("persisted_after_reload", "first_four_match", "paused_at_x",
                    "x_link_empty", "catalog_pr_link_present"):
            state.pop(key, None)
        state.update({
            "first_four_fields_verified": True,
            "final_submit_clicked": False,
            "submitted": False,
            "last_command": args.command,
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        if args.command == "prepare":
            # Never overwrite any link the user may already have entered.
            _, field = expect_label(page, LABELS[4])
            state.update({
                "status": "paused_at_x_demo_post_link",
                "paused_at_x": True,
                "x_link_present": bool(field.input_value()),
                "x_link_empty": not bool(field.input_value()),
                "remaining_inputs": ["Actual X demo post URL", "Actual Hermes catalog PR URL"],
            })
        else:
            fill_checked(page, LABELS[4], args.x_post_url)
            click_next_question(page, LABELS[4], "")
            advance_catalog_statement(page)
            fill_checked(page, LABELS[5], args.catalog_pr_url)
            # Stop directly after fill. No Enter, Tab, next, or submit click.
            state.update({
                "status": "ready_for_lead_inspection_not_submitted",
                "paused_at_x": False,
                "x_link_present": True,
                "x_link_empty": False,
                "catalog_pr_link_present": True,
                "remaining_inputs": [],
            })
        # Let ordinary Typeform autosave run; no API calls or storage extraction.
        page.wait_for_timeout(2000)
        private_json(STATE, state)
        # Disconnect only: do NOT call browser.close(), which would kill handoff.
    print(json.dumps({
        "status": state["status"], "browser_pid": state["pid"],
        "cdp_url": state["cdp_url"], "console_url": state["console_url"],
        "first_four_fields_verified": True, "submitted": False,
        "state_file": str(STATE), "remaining_inputs": state["remaining_inputs"],
    }, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare", help="Fill first four fields; pause at missing X demo link.")
    resume = commands.add_parser("resume", help="Fill actual published links; NEVER submit.")
    resume.add_argument("--catalog-pr-url", required=True)
    resume.add_argument("--x-post-url", required=True)
    args = parser.parse_args()
    try:
        run(args)
    except HandoffError as error:
        print(f"Stopped safely: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        # Playwright exception strings can contain locator values or page text.
        # Suppress them so email/Discord never leak to stdout, logs, or traces.
        print(
            f"Stopped safely ({type(error).__name__}); inspect the owned browser. "
            "No final submission action is implemented.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
