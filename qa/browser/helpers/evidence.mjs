import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';

export function manifestHashCandidates(files) {
  return [...new Set(files)].filter((file) => path.basename(file) !== 'manifest.json');
}

export function sha256File(filePath) {
  return createHash('sha256').update(readFileSync(filePath)).digest('hex');
}

export function ensureParent(filePath) {
  mkdirSync(path.dirname(filePath), { recursive: true });
}

export function writeJson(filePath, value) {
  ensureParent(filePath);
  writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

export function writeText(filePath, value) {
  ensureParent(filePath);
  writeFileSync(filePath, value, 'utf8');
}

export async function writeScreenshot(page, filePath, options = {}) {
  ensureParent(filePath);
  await page.screenshot({ path: filePath, ...options });
}
