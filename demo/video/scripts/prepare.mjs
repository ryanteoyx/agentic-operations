import fs from 'node:fs';
import path from 'node:path';
import {parseArgs} from 'node:util';
import {SOURCE, OUTPUT, projectPath, read, write, run, sha256} from './common.mjs';

const {values} = parseArgs({options: {
  draft: {type: 'boolean', default: false},
  capture: {type: 'string'},
  'checked-result': {type: 'string'},
}});
const draft = values.draft;
if (!draft && (!values.capture || !values['checked-result'])) {
  throw new Error('Final staging requires --capture <manifest> --checked-result <lead-checked result.json>. Or explicitly use --draft.');
}
const project = projectPath(draft);
const assets = path.join(project, 'assets');
const audio = path.join(OUTPUT, 'audio');
const narration = fs.readFileSync(path.join(SOURCE, 'narration.txt'), 'utf8').trim();
const captions = read(path.join(audio, 'captions.json'));
const words = read(path.join(audio, 'words.json'));
const voice = read(path.join(audio, 'audio-production.json'));
if (captions.map(c => c.text).join(' ') !== narration.replace(/\s+/g, ' ')) {
  throw new Error('Caption text differs from exact approved narration');
}
if (Math.abs(voice.normalizedDurationSeconds - 82) > 0.001 || voice.atempo > 1.15 ||
    voice.lastWordEndSeconds >= 81) throw new Error('Audio duration/tempo/speech safety check failed');
const cue = phrase => {
  const character = narration.indexOf(phrase);
  const word = words.find(w => w.char === character);
  if (character < 0 || !word) throw new Error(`Missing exact narration cue: ${phrase}`);
  return Math.round(Math.max(0, word.start - 0.18) * 30) / 30;
};
const shots = [
  ['01_open', 0, 'A shortage. Two commitments.', 'Synthetic manufacturing scenario'],
  ['02_options', cue('Hermes tools and this control room'), 'One persistent case service', 'Approved suppliers · deadlines · capacity · authority'],
  ['03_selected', cue('The first estimate chooses economy supply.'), 'Choose within the boundaries', 'A durable intent exists before execution'],
  ['04_interrupted', cue('Now we interrupt the execution process'), 'Interrupted after the external commit', 'Owned process exits before local acknowledgement'],
  ['05_reconciled', cue('On restart, reconciliation finds'), 'Reconcile before retrying', 'Recover the same logical action'],
  ['06_observed', cue('We advance the simulated clock'), 'Observe what actually happened', 'Original forecast and observed outcome remain distinct'],
  ['07_corrected', cue('Supplier evidence supports'), 'Correct the estimate, not the history', 'Evidence-backed · versioned · bounded'],
  ['08_v2_options', cue('A fresh case chooses priority supply'), 'A fresh case uses the correction', 'The original case keeps its captured forecast'],
  ['09_v2_observed', cue('and ships at hour fifty-four.'), 'Durable execution. Observed correction.', 'Synthetic data · no manufacturing ROI claim'],
].map(([stage, start, title, subtitle], i, array) => ({
  stage, start, end: array[i + 1]?.[1] ?? 82, title, subtitle,
}));
let manifest, checkedResult, resultSha256, captureManifest;
if (!draft) {
  captureManifest = path.resolve(values.capture);
  manifest = read(captureManifest);
  checkedResult = path.resolve(values['checked-result']);
  resultSha256 = sha256(checkedResult);
  if (manifest.status !== 'recorded_pending_lead_review' ||
      manifest.result_sha256 !== resultSha256 ||
      sha256(manifest.result_json) !== resultSha256) {
    throw new Error('Capture is incomplete or checked result is not this capture’s unchanged harness result');
  }
  if (manifest.http_errors?.length || manifest.request_failures?.length)
    throw new Error('Capture has failed network requests; lead must inspect before staging');
  const errors = (manifest.console_errors || []).filter(e => !/favicon|404 \(Not Found\)/.test(e));
  if (errors.length) throw new Error(`Capture has browser errors: ${errors.join('; ')}`);
  const result = read(checkedResult);
  // These are gates against the already-approved narration, not new measurements.
  const claims = [
    [result.synthetic, true], [result.injected_child_exit, 73],
    [result.fresh_recovery_process_exit, 0], [result.recovered_purchase_orders_for_action, 1],
    [result.version_1?.evaluation?.actual_sales_ship_hour, 72],
    [result.version_1?.evaluation?.sales_forecast_error_hours, 24],
    [result.version_1?.evaluation?.sales_late_hours, 12],
    [result.version_2?.evaluation?.actual_sales_ship_hour, 54],
    [result.original_prediction_preserved, true],
  ];
  if (claims.some(([actual, expected]) => actual !== expected))
    throw new Error('Checked results do not support the fixed narration. Stop for lead review; never rewrite numbers silently.');
  if (manifest.stages?.map(s => s.stage).join() !== shots.map(s => s.stage).join())
    throw new Error('Missing or reordered real capture stages');
  if (sha256(manifest.raw_video) !== manifest.raw_video_sha256)
    throw new Error('Raw recording changed since capture');
  if (manifest.viewport?.width !== 1920 || manifest.viewport?.height !== 900 ||
      manifest.record_video_size?.width !== 1920 || manifest.record_video_size?.height !== 1080)
    throw new Error('Capture must preserve the 1920×900 UI in a 1920×1080 video frame');
  const rawProbe = JSON.parse(run('ffprobe', [
    '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
    '-of', 'json', manifest.raw_video], {stdio: 'pipe', encoding: 'utf8'}));
  if (rawProbe.streams[0]?.width !== 1920 || rawProbe.streams[0]?.height !== 1080)
    throw new Error('Raw recording dimensions differ; refusing to rescale the product UI');
  for (const stage of manifest.stages) {
    if (sha256(stage.measurement_json) !== stage.measurement_sha256 ||
        sha256(stage.screenshot) !== stage.screenshot_sha256)
      throw new Error(`Capture evidence changed for ${stage.stage}`);
  }
  shots[4].subtitle = `${result.recovered_purchase_orders_for_action} purchase order for the same action · fresh-process recovery`;
  shots[5].subtitle = `Sales h${result.version_1.evaluation.actual_sales_ship_hour} · forecast error +${result.version_1.evaluation.sales_forecast_error_hours} h · deadline miss ${result.version_1.evaluation.sales_late_hours} h`;
  shots[8].subtitle = `Sales h${result.version_2.evaluation.actual_sales_ship_hour} · original forecast preserved · synthetic scenario`;
}
fs.mkdirSync(assets, {recursive: true});
fs.copyFileSync(path.join(audio, 'narration.wav'), path.join(assets, 'narration.wav'));
fs.copyFileSync(path.join(SOURCE, 'node_modules/gsap/dist/gsap.min.js'), path.join(assets, 'gsap.min.js'));
const fontDir = path.join(SOURCE, 'node_modules/hyperframes/dist/skills/hyperframes/assets/frame-presets/code-editorial/fonts');
for (const weight of [400, 700])
  fs.copyFileSync(path.join(fontDir, `Inter-${weight}.woff2`), path.join(assets, `Inter-${weight}.woff2`));
for (const name of ['captions.srt', 'captions.vtt', 'captions.json', 'audio-production.json', 'scene-timing.json'])
  fs.copyFileSync(path.join(audio, name), path.join(project, name));
fs.copyFileSync(path.join(SOURCE, 'narration.txt'), path.join(project, 'narration.txt'));

if (!draft) {
  const clips = path.join(project, 'clips');
  fs.mkdirSync(clips, {recursive: true});
  for (const shot of shots) {
    const source = manifest.stages.find(s => s.stage === shot.stage);
    if (!(source.source_end_seconds > source.source_start_seconds))
      throw new Error(`No stable recorded window for ${shot.stage}`);
    const frames = Math.round((shot.end - shot.start) * 30);
    const output = path.join(clips, `${shot.stage}.mp4`);
    run('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y',
      '-ss', String(source.source_start_seconds),
      '-t', String(source.source_end_seconds - source.source_start_seconds),
      '-i', manifest.raw_video, '-an',
      '-vf', 'fps=30,setsar=1,tpad=stop_mode=clone:stop_duration=82',
      '-frames:v', String(frames), '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
      '-pix_fmt', 'yuv420p', '-threads', '2', '-video_track_timescale', '15360', output]);
    shot.source = {path: manifest.raw_video, start: source.source_start_seconds,
      end: source.source_end_seconds, heldFrameExtension: true, screenshot: source.screenshot};
  }
  const concat = path.join(clips, 'concat.txt');
  fs.writeFileSync(concat, shots.map(s => `file '${s.stage}.mp4'`).join('\n') + '\n');
  run('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0',
    '-i', concat, '-c', 'copy', '-movflags', '+faststart', path.join(assets, 'ui.mp4')]);
}
const escape = text => String(text).replace(/[&<>"']/g, c =>
  ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const timed = (start, end) => `data-start="${start}" data-duration="${(end - start).toFixed(6)}"`;
const bars = shots.map((shot, i) => `<div id="label-${i}" class="clip label" ${timed(shot.start, shot.end)} data-track-index="2" data-layout-allow-overlap>
  <span class="chapter">${String(i + 1).padStart(2, '0')} / ${String(shots.length).padStart(2, '0')}</span>
  <span class="shot-title">${escape(shot.title)}</span><span class="shot-subtitle">${escape(shot.subtitle)}</span></div>`).join('\n');
const subtitleHTML = captions.map((caption, i) => `<div id="caption-${i}" class="clip caption" ${timed(caption.start, caption.end)} data-track-index="3" data-track-kind="captions"><span>${escape(caption.text)}</span></div>`).join('\n');
const footage = draft
  ? '<div id="draft-placeholder" class="clip draft-placeholder" data-start="5.3" data-duration="72.6" data-track-index="0"><strong>DRAFT — CAPTURE PENDING</strong><p>No product data or measured results are shown.</p><p>Awaiting the lead-reviewed real UI recording.</p></div>'
  : '<video id="product" class="clip footage" src="assets/ui.mp4" data-start="0" data-duration="82" data-track-index="0" muted playsinline preload="auto"></video>';
const source = fs.readFileSync(path.join(SOURCE, 'index.html'), 'utf8');
const html = source.replace('<!-- FOOTAGE -->', footage).replace('<!-- LABELS -->', bars)
  .replace('<!-- CAPTIONS -->', subtitleHTML).replace('<!-- DRAFT -->',
    draft ? '<div class="draft-flag">DRAFT · NOT FOR RELEASE</div>' : '');
fs.writeFileSync(path.join(project, 'index.html'), html);
write(path.join(project, 'production.json'), {
  schema: 1, draft, duration: 82, width: 1920, height: 1080, fps: 30,
  checkedResult, resultSha256, captureManifest,
  captureManifestSha256: captureManifest ? sha256(captureManifest) : undefined,
  narrationSha256: sha256(path.join(SOURCE, 'narration.txt')), voice, shots,
  sourceTreatment: 'Real UI stage clips in chronological order; original frames held to match narration. No fake UI or speed-up.',
  disclosure: 'Microsoft-hosted Emma neural voice; open-source edge-tts client, not an open-source voice model. Deterministic harness; no model-worker execution implied.',
});
console.log(JSON.stringify({project, draft, readyFor: 'Hyperframes check and snapshot; final render only after lead review'}, null, 2));
