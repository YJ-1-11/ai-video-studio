'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const remotion = path.join(__dirname, '..', 'tools', 'remotion');
const modules = path.join(remotion, 'node_modules');

async function check() {
  process.env.AI_VIDEO_STUDIO_REMOTION_MODULES = modules;
  const cfg = require(path.join(modules, '@remotion', 'cli', 'dist', 'config', 'index.js'));
  const {loadConfigFile} = require(path.join(modules, '@remotion', 'cli', 'dist', 'load-config.js'));
  await loadConfigFile(path.join(__dirname, '..'), path.join(remotion, 'studio.config.js'), true);
  const overrides = await cfg.ConfigInternals.getWebpackOverrideFn()({resolve: {modules: ['node_modules']}});
  assert.equal(overrides.resolve.modules[0], modules);
  const {BundlerInternals} = require(path.join(modules, '@remotion', 'bundler'));
  const source = fs.readFileSync(path.join(__dirname, '..', 'templates', 'video', 'timeline-composition.jsx'), 'utf8');
  await BundlerInternals.esbuild.transform(source, {loader: 'jsx'});
  const chromium = process.env.AI_VIDEO_STUDIO_BROWSER || path.join(modules, '.remotion', 'chrome-headless-shell', 'win64',
    'chrome-headless-shell-win64', 'chrome-headless-shell.exe');
  assert.equal(fs.statSync(chromium).isFile(), true);
  console.log('Installed Remotion configuration, JSX syntax and Chromium file verified (no render or browser launch)');
}
check().catch((err) => { console.error(err); process.exitCode = 1; });
