import { execFileSync, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';

import { BASELINE_NOW } from './constants.mjs';

function commandVersion(command, args) {
  const result = spawnSync(command, args, { encoding: 'utf8' });
  if (result.error || result.status !== 0) {
    throw new Error(`HARNESS_ERROR unable to read ${command} version`);
  }
  return `${result.stdout || ''}${result.stderr || ''}`.trim();
}

function rasterioStatus() {
  const result = spawnSync('python', ['-c', 'import rasterio'], { encoding: 'utf8' });
  return {
    installed: !result.error && result.status === 0
  };
}

export async function installBaselineClock(page) {
  if (!page?.clock?.install) {
    throw new Error('HARNESS_ERROR Playwright page clock API is unavailable');
  }
  await page.clock.install({ time: new Date(BASELINE_NOW) });
}

export function captureEnvironment(browser, root = path.resolve(new URL('../..', import.meta.url).pathname)) {
  const demDir = path.join(root, 'webapp', 'data', 'dem');
  const rasterio = rasterioStatus();
  const tilePresent = existsSync(path.join(demDir, 'picos_mdt.tif'));
  const metadataPresent = existsSync(path.join(demDir, 'picos_mdt.meta.json'));

  return {
    node_version: process.version,
    python_version: commandVersion('python', ['--version']),
    playwright_version: '1.63.0',
    chromium_version: browser.version(),
    platform: {
      os: process.platform,
      arch: process.arch
    },
    dem: {
      available: rasterio.installed && tilePresent && metadataPresent,
      rasterio_installed: rasterio.installed,
      tile_present: tilePresent,
      metadata_present: metadataPresent
    }
  };
}

export function assertCanonicalEnvironment(environment) {
  if (environment.dem.rasterio_installed) {
    throw new Error('ENVIRONMENT_ERROR rasterio unexpectedly installed');
  }
  if (environment.dem.available) {
    throw new Error('ENVIRONMENT_ERROR DEM unexpectedly available');
  }
}

export { execFileSync };
