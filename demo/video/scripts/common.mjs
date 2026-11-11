import {fileURLToPath} from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';

export const SOURCE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const ROOT = path.resolve(SOURCE, '../..');
export const OUTPUT = path.join(ROOT, 'artifacts/video');
export const CLI = path.join(SOURCE, 'node_modules/hyperframes/dist/cli.js');
export const sha256 = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
export const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
export const write = (file, data) => fs.writeFileSync(file, JSON.stringify(data, null, 2) + '\n');
export const projectPath = draft => path.join(OUTPUT, draft ? 'draft' : 'final', 'project');

export function environment() {
  const browser = process.env.HYPERFRAMES_BROWSER_PATH || path.join(ROOT,
    'artifacts/submission/browsers/chromium-1254/chrome-mac-arm64/' +
    'Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing');
  if (!fs.existsSync(browser)) throw new Error(`Set HYPERFRAMES_BROWSER_PATH to an installed Chrome: ${browser}`);
  return {...process.env, HYPERFRAMES_BROWSER_PATH: browser,
    HYPERFRAMES_NO_TELEMETRY: '1', HYPERFRAMES_NO_UPDATE_CHECK: '1',
    HYPERFRAMES_NO_ORPHAN_CLEANUP: '1', DO_NOT_TRACK: '1'};
}

export function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: SOURCE, stdio: 'inherit', env: environment(), ...options,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} failed (${result.status ?? result.signal})`);
  return result.stdout;
}

export function hyperframes(command, project, args = [], options = {}) {
  return run(process.execPath, [CLI, command, project, ...args], {...options, cwd: project});
}

export function assertReady(project, draft) {
  const plan = read(path.join(project, 'production.json'));
  if (plan.draft !== draft) throw new Error('Draft/final mode mismatch');
  if (!draft) {
    if (!plan.checkedResult || sha256(plan.checkedResult) !== plan.resultSha256)
      throw new Error('Checked measurement result missing or changed. Stage again after lead review.');
    if (!plan.captureManifest || sha256(plan.captureManifest) !== plan.captureManifestSha256)
      throw new Error('Capture manifest changed. Stage again after lead review.');
    if (!fs.existsSync(path.join(project, 'assets/ui.mp4')))
      throw new Error('Real UI recording missing. Final output is forbidden.');
  }
  return plan;
}
