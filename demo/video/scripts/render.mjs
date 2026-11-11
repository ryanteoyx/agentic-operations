import path from 'node:path';
import {parseArgs} from 'node:util';
import {SOURCE, OUTPUT, projectPath, assertReady, hyperframes, run, write, sha256} from './common.mjs';

const {values} = parseArgs({options: {
  draft: {type: 'boolean', default: false},
  smoke: {type: 'boolean', default: false},
  fallback: {type: 'boolean', default: false},
}});
const draft = values.draft;
if (values.smoke && !draft) throw new Error('A smoke render must be marked --draft');
if (values.fallback && draft) throw new Error('The FFmpeg fallback requires actual checked UI footage');
const project = projectPath(draft);
const plan = assertReady(project, draft);
const directory = path.dirname(project);
const name = draft ? (values.smoke ? 'DRAFT-smoke' : 'DRAFT-preview') : 'agentic-operations-82s';
const master = path.join(directory, `${name}-hyperframes.mp4`);
const final = path.join(directory, `${name}.mp4`);
const seconds = values.smoke ? 3 : 82;
if (values.fallback) {
  // Offline deadline fallback: compose the actual recorded UI with exact caption overlays.
  // This is explicitly identified as FFmpeg, never passed off as a Hyperframes render.
  run(path.join(OUTPUT, '.venv/bin/python'), [
    path.join(SOURCE, 'scripts/fallback.py'), '--project', project]);
  run('ffmpeg', ['-hide_banner', '-y', '-i', path.join(project, 'assets/ui.mp4'),
    '-f', 'concat', '-safe', '0', '-i', path.join(project, 'fallback-overlays/concat.txt'),
    '-i', path.join(project, 'assets/narration.wav'),
    '-filter_complex', '[0:v][1:v]overlay=0:0:eof_action=repeat:format=auto[v]',
    '-map', '[v]', '-map', '2:a:0', '-t', '82', '-r', '30',
    '-c:v', 'libx264', '-crf', '18', '-preset', 'fast', '-pix_fmt', 'yuv420p',
    '-threads', '2', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
    '-movflags', '+faststart', final], {cwd: project});
} else {
  hyperframes('check', project, ['--budget', '180s']);
  hyperframes('render', project, ['--output', master, '--fps', '30', '--workers', '2',
    '--quality', draft ? 'draft' : 'delivery', '--format', 'mp4',
    '--video-frame-format', 'png', '--chroma-subsampling', '420',
    '--no-best-effort', '--strict', ...(values.smoke ? ['--end', String(seconds)] : [])],
    {timeout: 600000});
  // Explicit delivery codec/pixel format and known normalized narration.
  run('ffmpeg', ['-hide_banner', '-y', '-i', master, '-i', path.join(project, 'assets/narration.wav'),
    '-map', '0:v:0', '-map', '1:a:0', '-t', String(seconds), '-r', '30',
    '-c:v', 'libx264', '-crf', '18', '-preset', 'fast', '-pix_fmt', 'yuv420p',
    '-threads', '2', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
    '-movflags', '+faststart', final]);
}
write(path.join(directory, `${name}-render.json`), {
  draft, smoke: values.smoke, renderer: values.fallback ? 'FFmpeg actual-UI fallback' : 'Hyperframes 0.9.34',
  video: final, sha256: sha256(final), project, plan, expectedDuration: seconds,
});
run(path.join(OUTPUT, '.venv/bin/python'), [
  path.join(SOURCE, 'scripts/verify.py'), '--video', final, '--project', project,
  ...(values.smoke ? ['--smoke'] : []), ...(draft ? ['--draft'] : [])]);
console.log(`Local video ready for human review (not published): ${final}`);
