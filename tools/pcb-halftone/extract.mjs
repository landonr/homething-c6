import { readFileSync, writeFileSync } from 'node:fs';
import vm from 'node:vm';
import { join } from 'node:path';
const [tuner, outputDir] = process.argv.slice(2);
const html = readFileSync(tuner,'utf8');
const data = JSON.parse(html.match(/id="c6ht-geometry">(.+)<\/script>/)[1]);
const settings = Object.fromEntries(Array.from(html.matchAll(/data-setting="(\w+)"[^\n]+?\bvalue="(\d+)"/g), ([,name,value])=>[name,Number(value)]));

const back = vm.runInNewContext('('+html.match(/const backSettings = Object.freeze\((\{[\s\S]+?\})\);/)[1]+')');
const prepare = html.slice(html.indexOf('    function prepare('),html.indexOf('    let queued'));
const radii = html.slice(html.indexOf('    function smoothstep('),html.indexOf('    function draw('));
const result = vm.runInNewContext(`const gap = .10;
const minRadius = .09;
function schedule() {}
${prepare}
${radii}
Object.entries(data).map(([side,item]) => {
  const preview = prepare(side,item);
  const {radii,shadowRadii} = radiiFor(preview,side === "back" ? back : settings);
  const primary = item.dots.map(([x,y],i)=>[x,y,radii[i]]);
  const shadow = preview.shadowField.map(({x,y},i)=>[x,y,shadowRadii[i]]);
  return [side,[...primary,...shadow].filter(dot=>dot[2]>0)];
})`,{data, settings, back, root:{querySelector:()=>null}, Image:class {}});
console.log(settings);
for (const [side,dots] of result) {
  const circles = dots.map(([x,y,r])=>'<circle cx="'+x+'" cy="'+y+'" r="'+(Math.floor(r*1e6-1)/1e6).toFixed(6)+'"/>').join('');
  writeFileSync(join(outputDir,side+'.svg'),'<svg xmlns="http://www.w3.org/2000/svg">'+circles+'</svg>');
}
