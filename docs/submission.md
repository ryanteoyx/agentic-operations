# Hermes Plugin Hackathon submission

Requirements checked on 12 November 2026, approximately 03:30 SGT.

## Deadline and delivery target

The [announcement](https://x.com/nousresearch/status/2118094256438936062)
states 11 November at 5 p.m. EST: **12 November at 6 a.m. Singapore time**.
Its accessible [mirror](https://nitter.gq/NousResearch/status/2118094256438936062)
contains the same requirements.

The live [entry form](https://form.typeform.com/to/FwJLvOln) was open when
checked. Its embedded scheduling data reported `formCloseTimestampLimit:
1794520800`, corresponding to 13 November at 6 a.m. SGT. This differs from
the announcement; it is not treated as a confirmed deadline extension.

Delivery target: release and video ready by **12 November, 05:15 SGT**,
leaving a **15-minute buffer before the requested 05:30 SGT delivery** for
posting, submission, and upload problems. The announcement's 06:00 SGT deadline
does not change that delivery target.

## Required deliverables

1. Open a PR adding the plugin to `NousResearch/hermes-agent`'s catalog.
2. Post a video **strictly under 90 seconds** on X and tag **@NousResearch**.
   Show the actual plugin working.
3. Submit the catalog PR URL and X post URL through the entry form.

The announcement explicitly permits submitting once the PR is open.
Maintainer review and catalog CI are separate from form submission.
Judging criteria are usefulness, reliability, polish, and creativity.
The entry is the plugin itself; functionality beyond a prompt or skill is favored.

## Form fields checked against the live form

| Field | Required | Draft or status |
| --- | --- | --- |
| Plugin Title | Yes | Agentic Operations |
| Plugin Description | Yes | A Hermes plugin for durable manufacturing decisions: compare constrained shortage plans, reconcile interrupted simulated ERP actions, observe shipment outcomes, and activate evidence-backed estimate corrections. |
| Email Address | Yes | Supplied and saved locally; intentionally omitted here |
| Discord Username | Yes | Supplied and saved locally; intentionally omitted here |
| X Demo Post Link | Yes | Video published; awaiting entrant review and X account availability |
| GitHub Link to your Hermes Plugin Pull Request | Yes | https://github.com/NousResearch/hermes-agent/pull/153990 — verified open at 05:19 SGT |

The form also has a statement directing entrants to submit the catalog PR.
The first four fields were filled, saved locally, and verified after reloading.
The form is paused at **X Demo Post Link**; nothing has been submitted.
Personal contact details are intentionally omitted from this public document.

The X account was reported temporarily limited; no bypass has been attempted.
No X post or final form submission has been made.

The [v0.1.0 release](https://github.com/ryanteoyx/agentic-operations/releases/tag/v0.1.0)
and [82-second MP4](https://github.com/ryanteoyx/agentic-operations/releases/download/v0.1.0/agentic-operations-82s.mp4)
were published at 05:19 SGT on 12 November. The catalog PR pins
`dd4a6cf563a03b65231e30f3b32338ab1fe5a113`; exact-revision installation,
Hermes validation, and hosted Python CI passed. See the
[verification record](devin-harness.md#published-release-verification--12-november-2026).

## Catalog release gate

Follow the [catalog submission guide](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission)
and the canonical `plugin-catalog/README.md` at the current Hermes source.

- Public repository: https://github.com/ryanteoyx/agentic-operations
- Plugin subdirectory: `plugin/hermes_ops`.
- Pin a full 40-character public commit SHA; quote the version.
- Validate that exact checkout with `hermes plugins validate <plugin-dir>
  --install-deps`, using an isolated Hermes home.
- Match manifest and catalog tool/hook/middleware/environment declarations.
- Use public plugin APIs, with no core overrides, credential-store access,
  runtime self-updates, or bundled executable payloads.
- Disclose optional host-model network requests, local storage, the optional
  loopback demo server, and the owned demo subprocess used to demonstrate recovery.
- Include screenshots for the UI.

## Video production brief

Target: 82 seconds, 1920×1080, H.264 video with AAC narration, below 90 seconds
after final encoding. Show real product captures and recovery evidence.
Hyperframes is the preferred composition tool; narration may use the
open-source `edge-tts` client with Microsoft's hosted Emma voice.
The hosted voice model itself is not open source. A local system voice is the fallback.

Show the synthetic-data label, shortage and obligations, feasible alternatives,
durable action intent, real child-process interruption, fresh-process
reconciliation to one PO, observed outcome, and a versioned correction affecting
a subsequent independent case.

Model-assisted investigation and deterministic execution must be labeled
accurately. Do not imply an actual model run if only stubbed tests ran.
Measurements and captures come from the verified scenario, with original
forecasts preserved. Synthetic results are not manufacturing ROI evidence.

## Draft X caption

> This is Ryan's Devin. We built Agentic Operations for @NousResearch's Hermes:
> durable manufacturing cases, constrained plans, crash recovery, and
> evidence-backed correction. Synthetic data. Watch the working demo.
>
> https://github.com/ryanteoyx/agentic-operations

Review the final caption, video, and entrant details before publication.
Record the actual post and submission confirmation once completed.
