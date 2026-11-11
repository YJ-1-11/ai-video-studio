const {Config} = require('@remotion/cli/config');
const path = require('node:path');

const modules = process.env.AI_VIDEO_STUDIO_REMOTION_MODULES;
if (!modules || !path.isAbsolute(modules)) {
  throw new Error('Launch this configuration via the AI Video Studio Python command.');
}
Config.overrideWebpackConfig((config) => ({
  ...config,
  resolve: {...config.resolve, modules: [modules, ...(config.resolve?.modules || ['node_modules'])]},
  resolveLoader: {...config.resolveLoader, modules: [modules, ...(config.resolveLoader?.modules || ['node_modules'])]},
}));
