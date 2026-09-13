import { execFileSync, spawnSync } from 'node:child_process';

import { PRODUCT_COMMIT } from './constants.mjs';
import { classifyProductDrift } from './product-guard.mjs';

// M9.0 historical workflow only. M9.2 uses product-guard.mjs against HEAD.
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
