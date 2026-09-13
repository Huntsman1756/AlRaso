import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';

function normalizedPath(value) {
  return path.resolve(value).replace(/[\\/]+$/, '').toLowerCase();
}

export function classifyProductDrift({ diffExit, status, rootMismatch = false }) {
  const reasons = [];
  if (rootMismatch) reasons.push('repository_root_mismatch');
  if (diffExit !== 0) {
    reasons.push(diffExit === 1 ? 'tracked_product_diff' : 'product_worktree_check_failed');
  }
  if (status.trim()) reasons.push('product_worktree_not_clean');
  return { clean: reasons.length === 0, reasons };
}

export function assertProductWorktreeClean(root) {
  const requestedRoot = path.resolve(root);
  const repositoryRoot = execFileSync('git', ['rev-parse', '--show-toplevel'], {
    cwd: requestedRoot,
    encoding: 'utf8'
  }).trim();

  if (normalizedPath(repositoryRoot) !== normalizedPath(requestedRoot)) {
    throw new Error(
      `ENVIRONMENT_ERROR repository_root_mismatch: expected ${requestedRoot}, got ${repositoryRoot}`
    );
  }

  const headSha = execFileSync('git', ['rev-parse', 'HEAD'], {
    cwd: requestedRoot,
    encoding: 'utf8'
  }).trim();
  const diff = spawnSync('git', ['diff', '--quiet', 'HEAD', '--', 'webapp', 'alraso'], {
    cwd: requestedRoot,
    stdio: 'pipe'
  });
  const status = execFileSync(
    'git',
    ['status', '--porcelain=v1', '--untracked-files=all', '--', 'webapp', 'alraso'],
    { cwd: requestedRoot, encoding: 'utf8' }
  );

  const result = classifyProductDrift({ diffExit: diff.status ?? 2, status });
  if (!result.clean) {
    throw new Error(`ENVIRONMENT_ERROR product drift: ${result.reasons.join(',')}`);
  }
  return headSha;
}
