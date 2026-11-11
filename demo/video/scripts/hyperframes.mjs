import {hyperframes, projectPath, assertReady} from './common.mjs';

const args = process.argv.slice(2);
const command = args.shift() || 'check';
const draft = args.includes('--draft');
if (draft) args.splice(args.indexOf('--draft'), 1);
if (!['check', 'lint', 'snapshot', 'preview', 'info', 'timeline'].includes(command))
  throw new Error('Only local inspection/preview commands are enabled; publishing is not part of this pipeline');
const project = projectPath(draft);
assertReady(project, draft);
if (command === 'preview' && !args.some(a => ['--status', '--stop', '--context'].includes(a)))
  args.push('--background', '--no-open');
hyperframes(command, project, args);
