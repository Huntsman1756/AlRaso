import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

import { assertProductWorktreeClean, classifyProductDrift } from '../../helpers/product-guard.mjs';

const clean = { diffExit: 0, status: '' };
const trackedDrift = { diffExit: 1, status: ' M webapp/static/app.js' };
const untrackedDrift = { diffExit: 0, status: '?? webapp/tmp.json' };

test('clean product roots pass', () => {
  assert.deepEqual(classifyProductDrift(clean), { clean: true, reasons: [] });
});

test('tracked product drift fails', () => {
  assert.equal(classifyProductDrift(trackedDrift).clean, false);
});

test('untracked product drift fails', () => {
  assert.equal(classifyProductDrift(untrackedDrift).clean, false);
});

test('baseline resolves the repository root from its tests directory', () => {
  const baselineFile = fileURLToPath(new URL('../baseline.spec.mjs', import.meta.url));
  const baselineSource = readFileSync(baselineFile, 'utf8');
  assert.match(baselineSource, /const root = path\.resolve\(here, '\.\.\/\.\.\/\.\.'\);/);

  const repositoryRoot = path.resolve(path.dirname(baselineFile), '../../..');
  for (const directory of ['webapp', 'alraso', 'qa']) {
    assert.equal(existsSync(path.join(repositoryRoot, directory)), true, directory);
  }
});

function makeCommittedProductRepo() {
  const root = mkdtempSync(path.join(tmpdir(), 'alraso-m92-product-guard-'));
  mkdirSync(path.join(root, 'webapp', 'static'), { recursive: true });
  mkdirSync(path.join(root, 'alraso'), { recursive: true });
  writeFileSync(path.join(root, 'webapp', 'static', 'app.js'), 'baseline\n');
  writeFileSync(path.join(root, 'alraso', 'resolver.py'), 'baseline\n');
  execFileSync('git', ['init', '-q'], { cwd: root });
  execFileSync('git', ['config', 'user.email', 'm92-guard@example.invalid'], { cwd: root });
  execFileSync('git', ['config', 'user.name', 'M9.2 guard test'], { cwd: root });
  execFileSync('git', ['add', '.'], { cwd: root });
  execFileSync('git', ['commit', '-qm', 'baseline'], { cwd: root });
  return root;
}

function withCommittedProductRepo(callback) {
  const root = makeCommittedProductRepo();
  try {
    return callback(root);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

test('committed product at HEAD passes and reports the current HEAD', () => {
  withCommittedProductRepo((root) => {
    const headSha = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
    assert.equal(assertProductWorktreeClean(root), headSha);
  });
});

test('tracked product modification fails the current-HEAD guard', () => {
  withCommittedProductRepo((root) => {
    writeFileSync(path.join(root, 'webapp', 'static', 'app.js'), 'changed\n');
    assert.throws(() => assertProductWorktreeClean(root), /tracked_product_diff/);
  });
});

test('untracked product file fails the current-HEAD guard', () => {
  withCommittedProductRepo((root) => {
    writeFileSync(path.join(root, 'webapp', 'untracked.json'), '{}\n');
    assert.throws(() => assertProductWorktreeClean(root), /product_worktree_not_clean/);
  });
});

test('the guard rejects a non-repository-root cwd', () => {
  const baselineFile = fileURLToPath(new URL('../baseline.spec.mjs', import.meta.url));
  const repositoryRoot = path.resolve(path.dirname(baselineFile), '../../..');
  assert.throws(() => assertProductWorktreeClean(path.join(repositoryRoot, 'qa')), /repository_root_mismatch/);
});

test('the historical M9.0 pin remains metadata and is absent from the active guard', () => {
  const guardFile = fileURLToPath(new URL('../../helpers/product-guard.mjs', import.meta.url));
  const historicalGuardFile = fileURLToPath(new URL('../../helpers/historical-product-guard.mjs', import.meta.url));
  const constantsFile = fileURLToPath(new URL('../../helpers/constants.mjs', import.meta.url));
  assert.doesNotMatch(readFileSync(guardFile, 'utf8'), /PRODUCT_COMMIT/);
  assert.match(readFileSync(historicalGuardFile, 'utf8'), /PRODUCT_COMMIT/);
  assert.match(readFileSync(constantsFile, 'utf8'), /PRODUCT_COMMIT = '2491d7d5e4e90d380b45c4baee3f2d023008b1a4'/);
});
