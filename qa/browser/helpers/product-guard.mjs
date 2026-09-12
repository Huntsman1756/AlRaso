import { execFileSync, spawnSync } from 'node:child_process';

import { PRODUCT_COMMIT } from './constants.mjs';

export function classifyProductDrift({ diffExit, status }) {
  const reasons = [];
  if (diffExit !== 0) reasons.push('tracked_product_diff');
  if (status.trim()) reasons.push('product_worktree_not_clean');
  return { clean: reasons.length === 0, reasons };
}

export function assertFrozenProductClean(root) {
  execFileSync('git', ['cat-file', '-e', `${PRODUCT_COMMIT}^{commit}`], {
    cwd: root,
    stdio: 'pipe'
  });

  const diff = spawnSync('git', ['diff', '--quiet', PRODUCT_COMMIT, '--', 'webapp', 'alraso'], {
    cwd: root,
    stdio: 'pipe'
  });
  const status = execFileSync(
    'git',
    ['status', '--porcelain=v1', '--untracked-files=all', '--', 'webapp', 'alraso'],
    { cwd: root, encoding: 'utf8' }
  );

  const result = classifyProductDrift({ diffExit: diff.status ?? 2, status });
  if (!result.clean) {
    throw new Error(`ENVIRONMENT_ERROR product drift: ${result.reasons.join(',')}`);
  }
}
