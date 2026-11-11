'use strict';

const assert = require('node:assert/strict');
assert.equal(require('@remotion/cli/package.json').version, '4.0.484',
  'Review the loopback-only preview launcher before upgrading Remotion.');
const {RenderInternals} = require('@remotion/renderer');
assert.equal(typeof RenderInternals.getPortConfig, 'function');
RenderInternals.getPortConfig = () => ({host: '127.0.0.1', hostsToTry: ['127.0.0.1']});
if (process.argv[2] === '--check-loopback') {
  assert.equal(RenderInternals.getPortConfig().host, '127.0.0.1');
  console.log('Remotion Studio loopback guard OK (no server started)');
} else {
  assert.equal(process.argv[2], 'studio');
  require('./node_modules/@remotion/cli/remotion-cli.js');
}
