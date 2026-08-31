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
.full{grid-column:1/-1}
.fields{display:grid;gap:8px;align-items:center;
grid-template-columns:minmax(0,2fr) minmax(0,1fr) auto}
@media (max-width:720px){.fields{grid-template-columns:1fr}}
.fields button{background:var(--acc);color:#fff;border:1px solid var(--acc);
border-radius:8px;padding:8px 14px;cursor:pointer}
.st{margin:8px 0 0}.st.bad{color:var(--bad)}
h1{font-size:20px;margin:0 0 4px}
h2{font-size:16px;margin:0 0 8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.sub{color:var(--mut);font-size:13px;margin:0 0 12px}
a{color:var(--acc)}
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
.code{margin-top:12px;border-top:1px solid var(--line);padding-top:10px}
.code>p.hd{color:var(--mut);font-size:12px;margin:0 0 8px;
text-transform:uppercase;letter-spacing:.06em}
select,input[type=text]{font:inherit;color:inherit;background:var(--card);
border:1px solid var(--line);border-radius:8px;padding:8px;width:100%;margin:2px 0}
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
<section class="card full" id="z2m"></section>
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
// tg holds the Zigbee2MQTT group snapshot this browser fetched, and zerr the
// reason it has none. The remote never sees either.
var tg=null,td=null,zerr="",ws=null,zbusy=false;
// A Zigbee2MQTT request answers on a response topic that echoes its transaction.
var zreq={},zseq=0;
// cd holds the editable code text for cdSlot.
var cd="",cdSlot=null;

function info(s){for(var i=0;i<S.length;i++)if(S[i].s===s)return S[i];return null}
function row(s){if(!st)return null;for(var i=0;i<st.slots.length;i++)
if(st.slots[i].slot===s)return st.slots[i];return null}
// The code block prints the same fallback, so a copy and a tile agree.
function codeName(r){return r.name?r.name:"Slot"+r.slot}
function words(s){var r=row(s);if(!r)return "Unknown";
if(r.action==="zigbee")return "Zigbee: "+(r.name?r.name:"group "+r.group);
if(r.action==="voice")return "Voice assistant";
if(r.action==="ir")return "IR: "+codeName(r);return "Clear"}

function ms(u){return (u/1000).toFixed(1)+" ms"}

// Only what separates one code from another. The heading already names the
// action, and every frame goes out at 38 kHz with 50 percent duty.
function detail(s){var r=row(s);if(!r||r.action!=="ir")return "";var k=[],i;
if(r.fields){k.push(["Protocol","Samsung32"]);
k.push(["Address",r.fields.split(" ")[0]]);
k.push(["Command",r.fields.split(" ")[1]])}
else{k.push(["Protocol","Raw capture"]);
k.push(["Pulses",String(r.pulses)]);
if(r.us)k.push(["Frame",ms(r.us)])}
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

// Built once. A repaint only rewrites the status line, because rebuilding the
// inputs would discard an address that is still being typed.
function z2mBar(){
var e=document.getElementById("z2m");
var u="",k="";
try{u=localStorage.getItem("c6.z2m.url")||"";k=localStorage.getItem("c6.z2m.token")||""}catch(x){}
e.innerHTML="<h2>Zigbee2MQTT</h2>"+
"<p class=sub>This browser reads the group list from the bridge. The address "+
"and the token stay in this browser and never reach the remote.</p>"+
"<div class=fields>"+
"<input id=zu type=text autocomplete=off placeholder='ws://zigbee2mqtt.local:8080/api'>"+
"<input id=zk type=text autocomplete=off placeholder='Frontend token, if set'>"+
"<button type=button id=zc>Connect</button></div>"+
"<p class='sub st' id=zst></p>";
document.getElementById("zu").value=u;
document.getElementById("zk").value=k;
document.getElementById("zc").onclick=z2mSave;
z2mStatus();
if(u)z2mConnect(u,k)}

function z2mStatus(){
var e=document.getElementById("zst");
if(!e)return;
e.className="sub st"+(zerr?" bad":"");
if(zerr){e.textContent=zerr;return}
if(!tg&&!td){e.textContent="Not connected. A group ID can still be typed by hand.";return}
e.textContent="Connected. "+(tg?tg.length:0)+" groups, "+(td?td.length:0)+" devices."}

function byName(a,b){return a.name<b.name?-1:a.name>b.name?1:0}

// Sends one Zigbee2MQTT request and calls back with its response payload. The
// bridge answers on a response topic, so the transaction is the only link back.
function zpub(topic,payload,cb){
if(!ws||ws.readyState!==1){cb({status:"error",error:"Not connected to Zigbee2MQTT."});return}
var t="c6-"+(++zseq);
payload.transaction=t;zreq[t]=cb;
setTimeout(function(){if(zreq[t]){delete zreq[t];
cb({status:"error",error:"Zigbee2MQTT did not answer."})}},10000);
ws.send(JSON.stringify({topic:topic,payload:payload}))}

function paint(){
z2mStatus();
for(var i=0;i<S.length;i++){var d=S[i],b=keys[d.s];
b.firstChild.textContent=d.l;
b.lastChild.textContent=words(d.s);
b.setAttribute("aria-pressed",sel===d.s?"true":"false")}
editor()}

function esc(t){var e=document.createElement("div");e.textContent=t;return e.innerHTML}
// esc() escapes text nodes only, and a Zigbee2MQTT name can carry a quote.
function att(t){return esc(t).replace(/'/g,"&#39;").replace(/"/g,"&#34;")}

// The picker lists what the bridge published. The text field covers a target
// that the cache dropped, and any group ID that has no name.
// The browser talks to Zigbee2MQTT, not the remote. A group id is all the
// remote stores, so this form only has to resolve a name to that id.
function zbForm(){
var h="",i;
if(zbusy)h+="<div class=note>Working with Zigbee2MQTT.</div>";
if(tg&&tg.length){
h+="<p class=sub>Pick a group.</p>"+
"<select id=zs><option value=''>Select a group</option>";
for(i=0;i<tg.length;i++)h+="<option value='"+att(String(tg[i].id))+"'>"+
esc(tg[i].name)+"</option>";
h+="</select><div class=act><button type=button id=za"+(zbusy?" disabled":"")+
">Assign group</button></div>"}
if(td&&td.length){
h+="<p class=sub>Or pick one device. A groupcast is the only thing the remote "+
"can send, so this browser puts the device in a group of its own first.</p>"+
"<select id=zd><option value=''>Select a device</option>";
for(i=0;i<td.length;i++)h+="<option value='"+att(td[i].ieee)+"'>"+
esc(td[i].name)+"</option>";
h+="</select><div class=act><button type=button id=zw"+(zbusy?" disabled":"")+
">Assign device</button></div>"}
if(!tg&&!td)h+="<p class=sub>No lists. Connect to Zigbee2MQTT at the top of the "+
"page, or type a group ID below.</p>";
h+="<p class=sub>A typed ID wins over both pickers. Membership lives in the "+
"light, so a group only works once the light has joined it.</p>"+
"<input id=zt type=text autocomplete=off placeholder='0x1234 or 4609'>"+
"<div class=act><button type=button id=zi"+(zbusy?" disabled":"")+
">Assign typed ID</button>"+
"<button type=button class=sec id=zx>Back</button></div>";
return h}

// The frontend websocket relays every MQTT message as {topic,payload} with the
// base topic already stripped, so bridge/groups arrives without a subscribe.
// A websocket needs no CORS grant, which a fetch to the same host would.
function z2mConnect(url,token){
if(ws){try{ws.close()}catch(x){}ws=null}
zerr="";tg=null;td=null;
var full=url+(token?(url.indexOf("?")<0?"?":"&")+"token="+encodeURIComponent(token):"");
try{ws=new WebSocket(full)}catch(x){zerr="That address is not a websocket URL.";paint();return}
var done=false;
// The socket stays open, because a group request answers on it.
ws.onmessage=function(ev){
var m,i;try{m=JSON.parse(ev.data)}catch(x){return}
if(m.topic==="bridge/groups"&&Array.isArray(m.payload)){
var out=[];
for(i=0;i<m.payload.length;i++){
var g=m.payload[i];
if(typeof g.id!=="number"||g.id<1||g.id>65527)continue;
var mem=[],j,list=Array.isArray(g.members)?g.members:[];
for(j=0;j<list.length;j++)if(list[j].ieee_address)mem.push(list[j].ieee_address);
out.push({id:g.id,name:String(g.friendly_name||g.id),members:mem})}
out.sort(byName);
done=true;tg=out;zerr="";
z2mStatus();if(mode==="zb")paint();return}
if(m.topic==="bridge/devices"&&Array.isArray(m.payload)){
var devs=[];
for(i=0;i<m.payload.length;i++){
var d=m.payload[i];
if(!d.ieee_address||d.type==="Coordinator")continue;
devs.push({ieee:d.ieee_address,name:String(d.friendly_name||d.ieee_address)})}
devs.sort(byName);
done=true;td=devs;zerr="";
z2mStatus();if(mode==="zb")paint();return}
// A response echoes the transaction of the request that caused it.
if(m.topic&&m.topic.indexOf("bridge/response/")===0&&m.payload){
var t=m.payload.transaction,cb=t?zreq[t]:null;
if(cb){delete zreq[t];cb(m.payload)}}};
ws.onerror=function(){if(!done){zerr="Could not reach Zigbee2MQTT at that address.";
z2mStatus();if(mode==="zb")paint()}};
ws.onclose=function(){if(!done){zerr=zerr||"Zigbee2MQTT closed the connection. Check the token.";
z2mStatus();if(mode==="zb")paint()}}}

function z2mSave(){
var u=document.getElementById("zu").value.replace(/^\s+|\s+$/g,"");
var k=document.getElementById("zk").value.replace(/^\s+|\s+$/g,"");
if(!u){zerr="Enter the Zigbee2MQTT websocket address.";z2mStatus();return}
try{localStorage.setItem("c6.z2m.url",u);localStorage.setItem("c6.z2m.token",k)}catch(x){}
z2mConnect(u,k);z2mStatus()}

// The box stays available on an empty slot, so a code can be pasted in without
// pointing a source remote at the board.
function codeBox(){
var h="<div class=code><p class=hd>IR code</p>"+
"<p class=sub><a href=https://github.com/Lucaslhm/Flipper-IRDB target=_blank "+
"rel=noreferrer>Flipper-IRDB</a></p>"+
"<textarea id=ct rows=7 spellcheck=false autocomplete=off>"+esc(cd)+"</textarea>";
if(cdSlot!==sel)h+="<p class=sub>Loading the stored code.</p>";
h+="<div class=act><button type=button class=sec id=cc>Copy</button>"+
"<button type=button id=ca>Apply to this input</button></div></div>";
return h}

function loadCode(s){cdSlot=null;cd="";
return fetch("/buttons/api/code?slot="+s,{cache:"no-store"})
.then(function(r){return r.json()})
.then(function(j){if(j.slot!==s)return;
cd=j.text||"";cdSlot=s;if(sel===s)paint()})
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
if(mode==="zb"&&rec===sel){
if(msg)h+="<div class='note "+(bad?"bad":"ok")+"'>"+esc(msg)+"</div>";
h+=zbForm();e.innerHTML=h;
if(document.getElementById("za"))document.getElementById("za").onclick=assignGroup;
if(document.getElementById("zw"))document.getElementById("zw").onclick=assignDevice;
document.getElementById("zi").onclick=assignTyped;
document.getElementById("zx").onclick=function(){mode="idle";paint()};return}
if(msg)h+="<div class='note "+(bad?"bad":"ok")+"'>"+esc(msg)+"</div>";
var lock=st&&st.busy;
if(mode==="cancel")h+="<div class=note>Cancelling.</div>";
else if(lock&&st.owner==="device")
h+="<div class=note>Assignment in progress on the remote.</div>";
else if(lock)h+="<div class=note>Another assignment is already running.</div>";
h+="<div class=act>";
h+="<button type=button id=b1"+(lock?" disabled":"")+">Record IR</button>";
h+="<button type=button id=b4"+(lock?" disabled":"")+">Zigbee</button>";
if(d.v)h+="<button type=button id=b2"+(lock?" disabled":"")+">Voice assistant</button>";
h+="<button type=button class=sec id=b3"+(lock?" disabled":"")+">Clear</button></div>";
h+=codeBox();
e.innerHTML=h;
var box=document.getElementById("ct");
box.oninput=function(){cd=box.value};
document.getElementById("cc").onclick=copyCode;
document.getElementById("ca").onclick=applyCode;
if(lock)return;
document.getElementById("b1").onclick=function(){go("record_ir")};
document.getElementById("b4").onclick=openZigbee;
if(d.v)document.getElementById("b2").onclick=function(){go("set_voice")};
document.getElementById("b3").onclick=function(){go("clear")}}

function pick(s){sel=s;if(mode==="zb")mode="idle";
if(mode!=="rec"){msg="";bad=false}paint();
if(cdSlot!==s)loadCode(s)}

function load(){return fetch("/buttons/api/state",{cache:"no-store"})
.then(function(r){return r.json()}).then(function(j){st=j;return j})}

// A code block keeps its newlines, because the parser reads it a line at a time.
// ESPHome caps a POST body, and the sdkconfig raises that cap for a full length
// raw frame.
function post(a,s,v,n){var b="action="+a+(s?"&slot="+s:"")+
(v?(a==="set_zigbee"?"&group=":"&code=")+encodeURIComponent(v):"")+
(n===undefined?"":"&name="+encodeURIComponent(n));
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

function openZigbee(){mode="zb";rec=sel;msg="";bad=false;paint()}

function assignTyped(){
var v=document.getElementById("zt").value.replace(/^\s+|\s+$/g,"");
if(!v){msg="Type a group ID first.";bad=true;paint();return}
sendGroup(v,"")}

function assignGroup(){
var v=document.getElementById("zs").value,name="",i;
if(!v){msg="Select a group first.";bad=true;paint();return}
if(tg)for(i=0;i<tg.length;i++)if(String(tg[i].id)===v)name=tg[i].name;
sendGroup(v,name)}

// The remote can only send a groupcast, so a single device needs a group that
// holds only that device. An existing one is reused, because a repeat assign
// would otherwise leave a new group behind every time.
function assignDevice(){
var ieee=document.getElementById("zd").value,dev=null,i;
if(!ieee){msg="Select a device first.";bad=true;paint();return}
for(i=0;i<td.length;i++)if(td[i].ieee===ieee)dev=td[i];
if(!dev)return;
if(tg)for(i=0;i<tg.length;i++)
if(tg[i].members.length===1&&tg[i].members[0]===ieee){sendGroup(String(tg[i].id),dev.name);return}
zbusy=true;msg="Creating a group for "+dev.name+".";bad=false;paint();
zpub("bridge/request/group/add",{friendly_name:"c6 "+dev.name},function(r){
if(r.status!=="ok"||!r.data||typeof r.data.id!=="number"){
zbusy=false;msg="Zigbee2MQTT refused the group. "+(r.error||"");bad=true;paint();return}
var gid=r.data.id;
zpub("bridge/request/group/members/add",{group:String(gid),device:ieee},function(r2){
zbusy=false;
if(r2.status!=="ok"){
msg="Group "+gid+" was created, but the device was not added. "+(r2.error||"");
bad=true;paint();return}
sendGroup(String(gid),dev.name)})})}

function sendGroup(v,name){
var s=sel;
zbusy=true;paint();
post("set_zigbee",s,v,name).then(function(r){
zbusy=false;
if(r.code!==200){msg=fail(r);bad=true;mode="idle";return load().then(paint)}
return waitAction(r.body.id).then(function(ok){
mode="idle";
if(ok){msg="Assigned to the Zigbee group.";bad=false}
else{msg="The remote could not store that group.";bad=true}
return load().then(paint)})})
.catch(function(){zbusy=false;msg="The remote did not answer.";bad=true;mode="idle";paint()})}

function waitAction(id,ms){return load().then(function(j){
if(j.action_id>=id)return j.action_id===id&&j.action_ok;
return new Promise(function(done){setTimeout(done,ms||100)})
.then(function(){return waitAction(id,ms)})})}

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
z2mBar();
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
