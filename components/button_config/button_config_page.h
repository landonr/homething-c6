#pragma once

namespace esphome::button_config {

static const char PAGE_HTML[] = R"=====(<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Remote buttons</title>
<style>
:root{--bg:#f3f4f7;--fg:#16181d;--card:#fff;--line:#c6cad3;--mut:#565b66;
--acc:#14428f;--sel:#dae5fb;--ok:#0f5c31;--bad:#9c2114}
@media (prefers-color-scheme:dark){:root{--bg:#15171c;--fg:#e7eaef;--card:#1e2128;
--line:#3b404b;--mut:#a3a9b5;--acc:#7aa9ff;--sel:#26324a;--ok:#5cc98c;--bad:#ff8c7c}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:16px;display:grid;gap:16px;
grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
@media (max-width:720px){.wrap{grid-template-columns:1fr}}
h1{font-size:20px;margin:0 0 4px}
h2{font-size:16px;margin:0 0 8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.sub{color:var(--mut);font-size:13px;margin:0 0 12px}
.grp{margin:0 0 14px}
.grp>p{color:var(--mut);font-size:12px;margin:0 0 6px;text-transform:uppercase;
letter-spacing:.06em}
.row{display:grid;gap:8px;grid-template-columns:1fr 1fr}
.pad{display:grid;gap:8px;grid-template-columns:repeat(3,1fr)}
.plus{display:grid;gap:8px;grid-template-columns:repeat(3,1fr)}
.plus .tl{grid-area:1/1}.plus .u{grid-area:1/2}.plus .tr{grid-area:1/3}
.plus .l{grid-area:2/1}.plus .c{grid-area:2/2}.plus .r{grid-area:2/3}
.plus .d{grid-area:3/2}
button{font:inherit;color:inherit}
textarea{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;
color:inherit;background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:8px;width:100%;margin:2px 0;resize:vertical}
details.code{margin-top:12px;border-top:1px solid var(--line);padding-top:10px}
details.code summary{cursor:pointer;color:var(--mut);font-size:12px;
text-transform:uppercase;letter-spacing:.06em}
.k{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px;
text-align:left;cursor:pointer;display:block;width:100%}
.k:hover{border-color:var(--acc)}
.k[aria-pressed=true]{background:var(--sel);border-color:var(--acc)}
.k b{display:block;font-weight:600;font-size:14px}
.k span{display:block;color:var(--mut);font-size:12px;margin-top:2px}
:focus-visible{outline:3px solid var(--acc);outline-offset:2px}
.act{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.act button{background:var(--acc);color:#fff;border:1px solid var(--acc);
border-radius:8px;padding:8px 14px;cursor:pointer}
.act button.sec{background:transparent;color:var(--fg);border-color:var(--line)}
.act button[disabled]{opacity:.5;cursor:not-allowed}
dl.info{display:grid;grid-template-columns:auto minmax(0,1fr);gap:4px 12px;
margin:0 0 12px;font-size:13px}
dl.info dt{color:var(--mut);text-transform:uppercase;letter-spacing:.06em;
font-size:11px;padding-top:2px}
dl.info dd{margin:0;overflow-wrap:anywhere}
.note{border-left:4px solid var(--line);padding:8px 12px;margin:12px 0;
background:var(--bg);border-radius:0 6px 6px 0}
.note.ok{border-color:var(--ok)}.note.bad{border-color:var(--bad)}
.bar{height:6px;border-radius:3px;background:var(--line);overflow:hidden;margin:12px 0}
.bar i{display:block;height:100%;width:36%;background:var(--acc);
animation:sweep 1.4s ease-in-out infinite}
@keyframes sweep{0%{margin-left:-36%}100%{margin-left:100%}}
</style>
</head>
<body>
<div class="wrap">
<section class="card">
<h1>Remote buttons</h1>
<p class="sub">Select an input to see or change what it does.</p>
<div class="grp"><p>Top</p><div class="row" id="top"></div></div>
<div class="grp"><p>Wheel</p><div class="plus" id="plus"></div></div>
<div class="grp"><p>Keypad</p><div class="pad" id="pad"></div></div>
</section>
<section class="card" id="ed" aria-live="polite"></section>
</div>
<script>
var S=[
{s:19,l:"SW2",v:0,g:"top"},{s:20,l:"SW1",v:1,g:"top"},
// Rotation flanks Up on the top row: anticlockwise (18) left, clockwise (17) right.
{s:18,l:"Turn left",v:0,g:"plus",c:"tl"},{s:13,l:"Up",v:1,g:"plus",c:"u"},
{s:17,l:"Turn right",v:0,g:"plus",c:"tr"},
{s:16,l:"Left",v:1,g:"plus",c:"l"},{s:14,l:"Press",v:1,g:"plus",c:"c"},
{s:12,l:"Right",v:1,g:"plus",c:"r"},{s:15,l:"Down",v:1,g:"plus",c:"d"},
// Keypad fills column by column on the board, so the rows read 3 6 11, 4 7 10,
// 5 8 9. The array order is the render order, not the slot order.
{s:3,l:"SW3",v:1,g:"pad"},{s:6,l:"SW6",v:1,g:"pad"},{s:11,l:"SW11",v:1,g:"pad"},
{s:4,l:"SW4",v:1,g:"pad"},{s:7,l:"SW7",v:1,g:"pad"},{s:10,l:"SW10",v:1,g:"pad"},
{s:5,l:"SW5",v:1,g:"pad"},{s:8,l:"SW8",v:1,g:"pad"},{s:9,l:"SW9",v:1,g:"pad"}];
var st=null,sel=null,mode="idle",rec=0,seen=false,timer=0,msg="",bad=false,keys={};
// cd holds the editable code text for cdSlot. cdOpen keeps the box unfolded
// across the repaints that every action triggers.
var cd="",cdSlot=null,cdOpen=false;

function info(s){for(var i=0;i<S.length;i++)if(S[i].s===s)return S[i];return null}
function row(s){if(!st)return null;for(var i=0;i<st.slots.length;i++)
if(st.slots[i].slot===s)return st.slots[i];return null}
function words(s){var r=row(s);if(!r)return "Unknown";
if(r.action==="voice")return "Voice assistant";
if(r.action==="ir")return r.code?"IR "+r.code:"IR ("+r.pulses+" pulses)";return "Clear"}

function ms(u){return (u/1000).toFixed(1)+" ms"}

// The tile holds one line only, so the editor carries the transport, the
// command, and the identifier that the remote actually sends.
function detail(s){var r=row(s);if(!r)return "";var k=[],i;
if(r.action==="ir"){
k.push(["Type","IR"]);
k.push(["Action","Transmit the stored code"]);
k.push(["Protocol",r.code?"Samsung 32-bit":"Raw capture"]);
if(r.code)k.push(["Target",r.code]);
k.push(["Pulses",String(r.pulses)]);
if(r.us)k.push(["Frame",ms(r.us)]);
k.push(["Carrier","38 kHz at 50% duty"])}
else if(r.action==="voice"){
k.push(["Type","Voice"]);
k.push(["Action","Start the voice assistant"]);
k.push(["Target","Home Assistant over the native API"])}
else{k.push(["Type","Unassigned"]);k.push(["Action","None"])}
var h="<dl class=info>";
for(i=0;i<k.length;i++)h+="<dt>"+esc(k[i][0])+"</dt><dd>"+esc(k[i][1])+"</dd>";
return h+"</dl>"}

function build(){
for(var i=0;i<S.length;i++){var d=S[i];
var b=document.createElement("button");
b.type="button";b.className="k"+(d.c?" "+d.c:"");b.setAttribute("aria-pressed","false");
b.innerHTML="<b></b><span></span>";
b.onclick=(function(n){return function(){pick(n)}})(d.s);
keys[d.s]=b;document.getElementById(d.g).appendChild(b)}}

function paint(){
for(var i=0;i<S.length;i++){var d=S[i],b=keys[d.s];
b.firstChild.textContent=d.l;
b.lastChild.textContent=words(d.s);
b.setAttribute("aria-pressed",sel===d.s?"true":"false")}
editor()}

function esc(t){var e=document.createElement("div");e.textContent=t;return e.innerHTML}

// The box stays available on an empty slot, so a code can be pasted in without
// pointing a source remote at the board.
function codeBox(){
var h="<details class=code"+(cdOpen?" open":"")+" id=cx>"+
"<summary>Raw code</summary>"+
"<p class=sub>Timings in microseconds, mark first. A positive value is a mark "+
"and a negative value is a space. Copy it to another board, or paste one in.</p>"+
"<textarea id=ct rows=6 spellcheck=false autocomplete=off>"+esc(cd)+"</textarea>";
if(cdSlot!==sel)h+="<p class=sub>Loading the stored code.</p>";
h+="<div class=act><button type=button class=sec id=cc>Copy</button>"+
"<button type=button id=ca>Apply to this input</button></div></details>";
return h}

function loadCode(s){cdSlot=null;cd="";
return fetch("/buttons/api/code?slot="+s,{cache:"no-store"})
.then(function(r){return r.json()})
.then(function(j){if(j.slot!==s)return;
cd=(j.timings||[]).join(", ");cdSlot=s;if(sel===s)paint()})
.catch(function(){})}

// The page is served over plain HTTP, so navigator.clipboard is undefined in
// most browsers. execCommand still works there.
function copyCode(){var t=document.getElementById("ct");
if(!t.value){msg="This input has no code to copy.";bad=true;paint();return}
t.focus();t.select();
var ok=false;
try{ok=document.execCommand("copy")}catch(x){}
if(!ok&&navigator.clipboard){navigator.clipboard.writeText(t.value);ok=true}
msg=ok?"Code copied.":"Copy is blocked. Select the text and copy it by hand.";
bad=!ok;paint()}

function applyCode(){
var text=document.getElementById("ct").value;
cd=text;
if(!text.replace(/\s+/g,"")){msg="Paste a code first.";bad=true;paint();return}
go("set_ir_code",text)}

function editor(){
var e=document.getElementById("ed");
if(sel===null){e.innerHTML="<h2>No input selected</h2>"+
"<p class=sub>Select an input on the left to change what it does.</p>";return}
var d=info(sel);
var h="<h2>"+esc(d.l)+"</h2><p class=sub>Now: "+esc(words(sel))+"</p>"+detail(sel);
if(mode==="rec"&&rec===sel){
h+="<p>Point the source remote at the front of the board and press its button.</p>"+
"<div class=bar><i></i></div><div class=act>"+
"<button type=button class=sec id=bc>Cancel</button></div>";
e.innerHTML=h;document.getElementById("bc").onclick=cancel;return}
if(msg)h+="<div class='note "+(bad?"bad":"ok")+"'>"+esc(msg)+"</div>";
var lock=st&&st.busy;
if(mode==="cancel")h+="<div class=note>Cancelling.</div>";
else if(lock&&st.owner==="device")
h+="<div class=note>Assignment in progress on the remote.</div>";
else if(lock)h+="<div class=note>Another assignment is already running.</div>";
h+="<div class=act>";
h+="<button type=button id=b1"+(lock?" disabled":"")+">Record IR</button>";
if(d.v)h+="<button type=button id=b2"+(lock?" disabled":"")+">Voice assistant</button>";
h+="<button type=button class=sec id=b3"+(lock?" disabled":"")+">Clear</button></div>";
h+=codeBox();
e.innerHTML=h;
var box=document.getElementById("ct");
box.oninput=function(){cd=box.value};
document.getElementById("cx").ontoggle=function(){
cdOpen=document.getElementById("cx").open};
document.getElementById("cc").onclick=copyCode;
document.getElementById("ca").onclick=applyCode;
if(lock)return;
document.getElementById("b1").onclick=function(){go("record_ir")};
if(d.v)document.getElementById("b2").onclick=function(){go("set_voice")};
document.getElementById("b3").onclick=function(){go("clear")}}

function pick(s){sel=s;if(mode!=="rec"){msg="";bad=false}paint();
if(cdSlot!==s)loadCode(s)}

function load(){return fetch("/buttons/api/state",{cache:"no-store"})
.then(function(r){return r.json()}).then(function(j){st=j;return j})}

// A pasted code can carry newlines and a bracket, so the separators collapse to
// commas before the body is built. ESPHome caps a POST body, and the sdkconfig
// raises that cap for a full length frame.
function post(a,s,c){var b="action="+a+(s?"&slot="+s:"")+
(c?"&code="+encodeURIComponent(c.replace(/[^0-9+\-]+/g,",")):"");
return fetch("/buttons/api/action",{method:"POST",
headers:{"Content-Type":"application/x-www-form-urlencoded"},body:b})
.then(function(r){return r.text().then(function(t){
var j={};try{j=JSON.parse(t)}catch(x){}return{code:r.status,body:j}})})}

function fail(r){
if(r.code===409)return "Another assignment is already running";
if(r.body&&r.body.error)return r.body.error;
return "Request failed ("+r.code+")"}

function go(a,c){
var s=sel;
post(a,s,c).then(function(r){
if(r.code!==200){msg=fail(r);bad=true;return load().then(paint)}
if(a==="record_ir"){mode="rec";rec=s;seen=false;msg="";bad=false;
return load().then(function(){paint();watch()})}
return waitAction(r.body.id).then(function(ok){
if(ok){msg=a==="set_voice"?"Assigned to the voice assistant.":
a==="set_ir_code"?"Code applied.":"Cleared.";bad=false}
else{msg=a==="set_ir_code"?"The remote refused that code.":
"Flash write failed. The assignment was not saved.";bad=true}
return load().then(function(){paint();return loadCode(s)})})})
.catch(function(){msg="The remote did not answer.";bad=true;paint()})}

function waitAction(id){return load().then(function(j){
if(j.action_id>=id)return j.action_id===id&&j.action_ok;
return new Promise(function(done){setTimeout(done,100)}).then(function(){return waitAction(id)})})}

// The close runs on the main loop, so the watcher keeps polling until it lands.
function cancel(){mode="cancel";paint();
post("cancel",0).catch(function(){
msg="The remote did not answer.";bad=true;paint()})}

// A repaint during a recording restarts the progress bar and rebuilds Cancel,
// which drops keyboard focus. Nothing in that panel changes, so skip it.
function watch(){if(timer)return;timer=setInterval(function(){
load().then(function(j){if(j.result==="saved"&&j.result_slot===rec)seen=true;
if(j.busy){
if(mode!=="rec")paint();return}stop();finish()})
.catch(function(){})},700)}

function stop(){if(timer){clearInterval(timer);timer=0}}

function finish(){
var was=mode;mode="idle";
if(was==="cancel"){msg="Recording cancelled.";bad=true}
else if(seen){msg="Code saved.";bad=false}
else{msg="No code received.";bad=true}
paint();if(sel!==null)loadCode(sel)}

build();
load().then(function(j){
if(j.busy&&j.owner==="web"&&j.op_slot){mode="rec";rec=j.op_slot;sel=j.op_slot;
seen=j.result==="saved"&&j.result_slot===rec;watch()}
paint();if(sel!==null)loadCode(sel)}).catch(function(){
document.getElementById("ed").textContent="The remote did not answer."});
</script>
</body>
</html>
)=====";

}  // namespace esphome::button_config
