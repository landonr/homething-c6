import { readFileSync, writeFileSync } from 'node:fs';
import vm from 'node:vm';
import { join } from 'node:path';

const [tuner, settingsPath, outputDir, presetName] = process.argv.slice(2);
const html = readFileSync(tuner, 'utf8');
const snapshot = JSON.parse(readFileSync(settingsPath, 'utf8'));
const settings = presetName ? snapshot.presets[presetName] : snapshot;
if (!settings?.front || !settings.back) {
  throw new Error(presetName ? 'Unknown preset: ' + presetName : 'Missing front or back settings.');
}

const geometry = JSON.parse(html.match(/id="c6ht-geometry">(.+)<\/script>/)[1]);
const labelBoxes = JSON.parse(html.match(/const labelBoxes = (.+);/)[1]);
const formula = html.slice(html.indexOf('function smoothstep'), html.indexOf('function paintDot'));
const radiiFor = vm.runInNewContext(formula + '\nradiiFor');

for (const [side, {dots}] of Object.entries(geometry)) {
  const preview = {dots, labelBoxes: labelBoxes[side], cloudOffset: side === 'back' ? 73 : 0};
  const {radii} = radiiFor(preview, settings[side]);
  const maxRadius = settings[side].maxDiameter / 200;
  const circles = [];
  for (const [index, [x, y]] of dots.entries()) {
    if (!radii[index]) continue;
    const radius = Math.min(Math.floor(radii[index] * 1e6 - 1) / 1e6, maxRadius);
    circles.push('<circle cx="' + x + '" cy="' + y + '" r="' + radius.toFixed(6) + '"/>');
  }
  const svg = '<svg xmlns="http://www.w3.org/2000/svg">' + circles.join('') + '</svg>';
  writeFileSync(join(outputDir, side + '.svg'), svg);
}
