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
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--ok);margin-right:6px;vertical-align:baseline}
.dot.off{background:var(--line)}.dot.bad{background:var(--bad)}
h1{font-size:20px;margin:0 0 4px}
h2{font-size:16px;margin:0 0 8px}
.edtitle{display:flex;align-items:center;gap:8px}
.edtitle .clip{display:flex;gap:6px;margin-left:auto}
.edtitle .clip button{font-size:13px;background:transparent;color:var(--fg);
border:1px solid var(--line);border-radius:7px;padding:4px 8px;cursor:pointer}
.edtitle .clip button[disabled]{opacity:.5;cursor:not-allowed}
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
.sep{margin-top:16px;border-top:1px solid var(--line);padding-top:14px}
p.hd{color:var(--mut);font-size:12px;margin:0 0 8px;
text-transform:uppercase;letter-spacing:.06em}
.code .load{color:var(--mut);font-size:13px;margin:8px 0 0}
p.hd2,label.hd2{display:block;color:var(--mut);font-size:12px;margin:14px 0 6px;
text-transform:uppercase;letter-spacing:.06em}
h3{font-size:15px;margin:14px 0 8px}
h2>button.tog{background:none;border:0;padding:0;margin:0;width:100%;cursor:pointer;
display:flex;align-items:center;justify-content:space-between;gap:8px;text-align:left}
h2>button.tog span{color:var(--acc);font-size:13px;font-weight:400}
h2>button.tog span#cxz{color:var(--mut);margin:0 auto 0 12px}
select,input[type=text],input[type=search]{font:inherit;color:inherit;background:var(--card);
border:1px solid var(--line);border-radius:8px;padding:8px;width:100%;margin:2px 0}
input[type=search]::-webkit-search-cancel-button{cursor:pointer}
@media (prefers-color-scheme:dark){
input[type=search]::-webkit-search-cancel-button{filter:invert(1)}}
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
<section class="card full" id="cfg">
<h2><button type="button" class="tog" id="cxo" aria-expanded="false">Config<span
id="cxz"></span><span id="cxs">Show</span></button></h2>
<div id="cfgb" hidden><div id="z2m"></div><div class="sep" id="cfgio"></div></div>
</section>
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
// One press, one Zigbee command. a is the number the remote stores, c is the
// Zigbee2MQTT input cluster a target must carry to accept it, and p names the
// value the command needs. The numbers match the Action enum in
// zigbee_learning.h, so the two tables have to move together.
var ZA=[
{a:0,n:"Toggle",c:"genOnOff"},
{a:1,n:"On",c:"genOnOff"},
{a:2,n:"Off",c:"genOnOff"},
{a:3,n:"Brighter",c:"genLevelCtrl",p:"Step size",d:32,lo:1,hi:254},
{a:4,n:"Dimmer",c:"genLevelCtrl",p:"Step size",d:32,lo:1,hi:254},
{a:5,n:"Warmer white",c:"lightingColorCtrl",p:"Step in mireds",d:50,lo:1,hi:2000},
{a:6,n:"Cooler white",c:"lightingColorCtrl",p:"Step in mireds",d:50,lo:1,hi:2000},
{a:7,n:"Recall scene",c:"genScenes",p:"Scene ID",d:1,lo:0,hi:255},
{a:8,n:"Open",c:"closuresWindowCovering"},
{a:9,n:"Close",c:"closuresWindowCovering"},
{a:10,n:"Stop",c:"closuresWindowCovering"},
{a:11,n:"Warmer",c:"hvacThermostat",p:"Step in tenths of a degree",d:5,lo:1,hi:127},
{a:12,n:"Cooler",c:"hvacThermostat",p:"Step in tenths of a degree",d:5,lo:1,hi:127},
{a:13,n:"Lock",c:"closuresDoorLock"},
{a:14,n:"Unlock",c:"closuresDoorLock"},
{a:15,n:"Alarm",c:"ssIasWd",p:"Seconds",d:30,lo:1,hi:600},
{a:16,n:"Squawk",c:"ssIasWd"}];
var st=null,sel=null,mode="idle",rec=0,seen=false,timer=0,msg="",bad=false,keys={};
// tg holds the Zigbee2MQTT group snapshot this browser fetched, and zerr the
// reason it has none. The remote never sees either.
var tg=null,td=null,zerr="",ws=null,zbusy=false;
// The Home Assistant add-on address, because Ingress cannot carry a websocket.
var Z2MDEF="ws://homeassistant.local:8099/api";
// cd holds the editable code text for cdSlot. codeLoad rejects an old read
// after the user selects or pastes a newer code.
var cd="",cdSlot=null,codeLoad=0;
// act is the open action panel. The Zigbee field values live here too, because
// a late bridge/devices message repaints and would otherwise wipe them. A group
// and a device get one box each, and zkv says which kind is on screen, so only
// one target can ever be filled in.
// zav is the chosen action number and zvv the value it carries.
var act="ir",zkv="g",zsv="",zdv="",zgv="",zhv="",zpv="",zav=0,zvv="";
// The config card. cfgAll caches one code text per slot, so an export needs no
// second read of a code the editor already fetched.
var cfgMode="ex",cfgOut="",cfgIn="",cfgBusy=false,cfgMsg="",cfgBad=false,cfgAll={};
// Closed on arrival, because an export reads the code of every IR input and
// most visits change one input instead.
var cfgOpen=false;
// clip holds one selected IR or Zigbee assignment in this browser only. It
// cannot include Voice or Clear, because those are actions and not configs.
var clip=null,clipBusy=false;

function info(s){for(var i=0;i<S.length;i++)if(S[i].s===s)return S[i];return null}
function row(s){if(!st)return null;for(var i=0;i<st.slots.length;i++)
if(st.slots[i].slot===s)return st.slots[i];return null}
// The code block prints the same fallback, so a copy and a tile agree.
function codeName(r){return r.name?r.name:"Slot"+r.slot}
function words(s){var r=row(s);if(!r)return "Unknown";
if(r.action==="zigbee"){var A=za(r.act);
return "Zigbee "+(A?A.n:"action "+r.act)+": "+
(r.name?r.name:(r.ieee?r.ieee:"group "+r.group))}
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
// Only a stored address opens a socket by itself. The default fills the box so
// that one click connects, but a guess must not report itself as a failure.
var saved=!!u;
if(!u)u=Z2MDEF;
e.innerHTML="<p class=hd>Zigbee2MQTT</p>"+
"<p class=sub>This browser reads the group list from the bridge. The address "+
"and the token stay in this browser and never reach the remote.</p>"+
"<div class=fields>"+
"<input id=zu type=search autocomplete=off placeholder='"+Z2MDEF+"'>"+
"<input id=zk type=text autocomplete=off placeholder='Frontend token, if set'>"+
"<button type=button id=zc>Connect</button></div>"+
"<p class='sub st' id=zst></p>"+"<p class='sub st' id=zhp></p>";
document.getElementById("zu").value=u;
document.getElementById("zk").value=k;
document.getElementById("zc").onclick=z2mSave;
z2mStatus();
if(saved)z2mConnect(u,k)}

// A list in hand is the only proof the socket answered, so it also decides
// whether the button offers Connect or Disconnect.
function z2mUp(){return !!(tg||td)}

function z2mCounts(){return plural(tg?tg.length:0,"group")+", "+
plural(td?td.length:0,"device")}

function z2mTitle(){
var e=document.getElementById("cxz");
if(!e)return;
if(z2mUp()){e.innerHTML="<span class=dot></span>Zigbee2MQTT: "+z2mCounts();return}
e.innerHTML="<span class='dot "+(zerr?"bad":"off")+"'></span>Zigbee2MQTT "+
(zerr?"unreachable":"not connected")}

function z2mStatus(){
z2mTitle();
var b=document.getElementById("zc");
if(b)b.textContent=z2mUp()?"Disconnect":"Connect";
// The Home Assistant add-on serves the frontend through Ingress, which no
// other page can open a websocket to. The port has to be published first.
var h=document.getElementById("zhp");
if(h)h.textContent=z2mUp()?"":
"Home Assistant add-on: open Settings, Add-ons, Zigbee2MQTT, Configuration, "+
"Network, and set the host port for 8099/tcp to 8099. Then use "+
"ws://<home-assistant-host>:8099/api.";
var e=document.getElementById("zst");
if(!e)return;
e.className="sub st"+(zerr?" bad":"");
if(zerr){e.textContent=zerr;return}
if(!z2mUp()){e.textContent="Not connected. A group ID can still be typed by hand.";return}
e.innerHTML="<span class=dot></span>Connected. "+z2mCounts()+"."}

function plural(n,word){return n+" "+word+(n===1?"":"s")}

function byName(a,b){return a.name<b.name?-1:a.name>b.name?1:0}

function za(a){var i,n=Number(a)||0;
for(i=0;i<ZA.length;i++)if(ZA[i].a===n)return ZA[i];return null}

// Reduces the endpoint list Zigbee2MQTT publishes to {endpoint:[cluster]}. An
// older bridge that publishes no list gets endpoint 1 with no clusters, which
// reads as unknown rather than as a device that supports nothing.
function epMap(d){
var eps=d.endpoints,out={},k,n,cl;
if(!eps)return null;
for(k in eps){
if(!Object.prototype.hasOwnProperty.call(eps,k))continue;
n=parseInt(k,10);
if(!(n>=1&&n<=240))continue;
cl=eps[k]&&eps[k].clusters&&eps[k].clusters.input;
out[n]=Array.isArray(cl)?cl:[]}
return out}

// The lowest endpoint that carries the cluster wins, because a device that
// repeats a cluster gives the same command to every endpoint.
function epForCluster(eps,cluster){
var best=0,k,n;
if(!eps)return 0;
for(k in eps){
if(!Object.prototype.hasOwnProperty.call(eps,k))continue;
n=parseInt(k,10);
if(eps[k].indexOf(cluster)<0)continue;
if(!best||n<best)best=n}
return best}

// Every cluster the device carries on any endpoint. null means the bridge said
// nothing, so no action can be ruled out.
function devClusters(eps){
var out=null,k,i;
if(!eps)return null;
out={};
for(k in eps){
if(!Object.prototype.hasOwnProperty.call(eps,k))continue;
for(i=0;i<eps[k].length;i++)out[eps[k][i]]=true}
return out}

// A group only accepts what every member accepts, so this intersects them. A
// member the device list does not hold is skipped, and a group with no known
// member returns null, which offers every action.
function grpClusters(g){
var out=null,i,j,d,have,keep;
if(!td||!g||!g.members)return null;
for(i=0;i<g.members.length;i++){
d=null;
for(j=0;j<td.length;j++)if(td[j].ieee===g.members[i])d=td[j];
if(!d)continue;
have=devClusters(d.eps);
if(!have)continue;
if(!out){out=have;continue}
keep={};
for(j in out)if(Object.prototype.hasOwnProperty.call(have,j))keep[j]=true;
out=keep}
return out}

function commandable(eps){
var have=devClusters(eps),i;
if(!have)return true;
for(i=0;i<ZA.length;i++)if(have[ZA[i].c])return true;
return false}

// The cluster set of whatever the panel currently points at, or null when the
// bridge published nothing about it.
function targetClusters(){
var i,g;
if(zkv==="d"){
var a=String(zhv).replace(/^\s+|\s+$/g,"").replace(/^0[xX]/,"").toLowerCase();
if(!td||!a)return null;
for(i=0;i<td.length;i++)
if(td[i].ieee.replace(/^0[xX]/,"").toLowerCase()===a)return devClusters(td[i].eps);
return null}
var n=parseInt(zgv,String(zgv).slice(0,2).toLowerCase()==="0x"?16:10);
if(!tg||!(n>=1))return null;
for(i=0;i<tg.length;i++)if(tg[i].id===n)g=tg[i];
return g?grpClusters(g):null}

// A target the bridge never described offers everything, because a typed
// address is the one route left when this browser cannot reach Zigbee2MQTT.
function zActions(){
var have=targetClusters(),out=[],i;
if(!have)return ZA.slice(0);
for(i=0;i<ZA.length;i++)if(have[ZA[i].c])out.push(ZA[i]);
return out.length?out:ZA.slice(0)}

// The endpoint the action needs on the picked device, and 1 when the bridge
// named none.
function deviceEp(ieee,action){
var i,A=za(action),a=String(ieee).replace(/^0[xX]/,"").toLowerCase();
if(td)for(i=0;i<td.length;i++)
if(td[i].ieee.replace(/^0[xX]/,"").toLowerCase()===a)
return epForCluster(td[i].eps,A?A.c:"genOnOff")||1;
return 1}

function paint(){
z2mStatus();
for(var i=0;i<S.length;i++){var d=S[i],b=keys[d.s];
b.firstChild.textContent=d.l;
b.lastChild.textContent=words(d.s);
b.setAttribute("aria-pressed",sel===d.s?"true":"false")}
editor();cfgPaint()}

function esc(t){var e=document.createElement("div");e.textContent=t;return e.innerHTML}
// esc() escapes text nodes only, and a Zigbee2MQTT name can carry a quote.
function att(t){return esc(t).replace(/'/g,"&#39;").replace(/"/g,"&#34;")}

// The browser talks to Zigbee2MQTT, not the remote. The kind selector shows one
// target's fields at a time, so the panel cannot hold a group and a device at
// once and Assign never has to choose between two. A picker fills the fields of
// its own kind, and the fields also cover a target the bridge never published.
function zbForm(lock){
var h="",i,dis=(lock||zbusy)?" disabled":"";
if(zbusy)h+="<div class=note>Working with Zigbee2MQTT.</div>";
h+="<label class=hd2 for=zn>Target kind</label>"+
"<select id=zn"+dis+">"+
"<option value=g"+(zkv==="g"?" selected":"")+">Group</option>"+
"<option value=d"+(zkv==="d"?" selected":"")+">Device</option>"+
"</select>";
if(zkv==="d"){
if(td&&td.length){
h+="<p class=sub>Pick a device to fill the boxes below. The remote sends "+
"straight to it and Zigbee2MQTT keeps no group for it. A device that accepts "+
"none of the commands below is not listed.</p>"+
"<select id=zd"+dis+"><option value=''>Select a device</option>";
for(i=0;i<td.length;i++)h+="<option value='"+att(td[i].ieee)+"'"+
(zdv===td[i].ieee?" selected":"")+">"+esc(td[i].name)+"</option>";
h+="</select>"}
else h+="<p class=sub>No device list. Connect to Zigbee2MQTT in the Config card "+
"at the bottom of the page, or type an address below.</p>";
h+="<label class=hd2 for=zh>IEEE address</label>"+
"<input id=zh type=text autocomplete=off placeholder='0x94deb8fffe9db81e' "+
"value='"+att(zhv)+"'>"+
"<label class=hd2 for=zp>Endpoint</label>"+
"<input id=zp type=text autocomplete=off placeholder='1 when empty' "+
"value='"+att(zpv)+"'>"}
else{
if(tg&&tg.length){
h+="<p class=sub>Pick a group to fill the box below.</p>"+
"<select id=zs"+dis+"><option value=''>Select a group</option>";
for(i=0;i<tg.length;i++)h+="<option value='"+att(String(tg[i].id))+"'"+
(zsv===String(tg[i].id)?" selected":"")+">"+esc(tg[i].name)+"</option>";
h+="</select>"}
else h+="<p class=sub>No group list. Connect to Zigbee2MQTT in the Config card "+
"at the bottom of the page, or type an ID below.</p>";
h+="<label class=hd2 for=zg>Group ID</label>"+
"<input id=zg type=text autocomplete=off placeholder='0x1201 or 4609' "+
"value='"+att(zgv)+"'>"+
"<p class=sub>Membership lives in the "+
"light, so a group only works once the light has joined it.</p>"}
h+=actionForm(dis);
h+="<div class=act><button type=button id=zi"+dis+">Assign</button></div>";
return h}

// The target decides the list, so this runs after the picker above it. An
// action the target dropped cannot stay selected, or Assign would send it.
function actionForm(dis){
var list=zActions(),h="",i,found=false;
for(i=0;i<list.length;i++)if(list[i].a===Number(zav))found=true;
if(!found){zav=list[0].a;zvv=""}
h+="<label class=hd2 for=zt>Action</label>"+
"<select id=zt"+dis+">";
for(i=0;i<list.length;i++)h+="<option value="+list[i].a+
(Number(zav)===list[i].a?" selected":"")+">"+esc(list[i].n)+"</option>";
h+="</select>";
if(list.length<ZA.length)h+="<p class=sub>Zigbee2MQTT lists the clusters of "+
"this target, so only the commands it accepts are offered.</p>";
var A=za(zav);
if(A&&A.p)h+="<label class=hd2 for=zv>"+esc(A.p)+"</label>"+
"<input id=zv type=text autocomplete=off placeholder='"+A.d+" when empty' "+
"value='"+att(zvv)+"'>";
return h}

// IR owns the code box, because a pasted code and a captured one fill the same
// slot and reading one without the other tells you nothing.
function irPanel(lock){
var dis=lock?" disabled":"";
return "<p class=sub>Capture from a source remote, or paste a code.</p>"+
"<div class=act><button type=button id=b1"+dis+">Record IR</button></div>"+
codeBox(lock)}

function vaPanel(lock){
return "<p class=sub>The press starts Assist and the release ends it.</p>"+
"<div class=act><button type=button id=b2"+(lock?" disabled":"")+
">Assign voice assistant</button></div>"}

function clearPanel(lock){
return "<p class=sub>The input sends nothing until it is assigned again.</p>"+
"<div class=act><button type=button class=sec id=b3"+(lock?" disabled":"")+
">Clear this input</button></div>"}

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
// Only the addresses, because the member list is read to look each device up
// in the device list and intersect what they all accept.
var mem=[],j,list=Array.isArray(g.members)?g.members:[];
for(j=0;j<list.length;j++)if(list[j].ieee_address)mem.push(list[j].ieee_address);
out.push({id:g.id,name:String(g.friendly_name||g.id),members:mem})}
out.sort(byName);
done=true;tg=out;zerr="";
z2mStatus();if(act==="zb")paint();return}
if(m.topic==="bridge/devices"&&Array.isArray(m.payload)){
var devs=[];
for(i=0;i<m.payload.length;i++){
var d=m.payload[i];
if(!d.ieee_address||d.type==="Coordinator")continue;
var eps=epMap(d);
// A device the remote can send nothing to is not worth listing. A device
// the bridge published no endpoints for stays, because that says nothing
// about what it accepts.
if(eps&&!commandable(eps))continue;
devs.push({ieee:d.ieee_address,name:String(d.friendly_name||d.ieee_address),eps:eps})}
devs.sort(byName);
done=true;td=devs;zerr="";
z2mStatus();if(act==="zb")paint();return}};
ws.onerror=function(){if(!done){zerr="Could not reach Zigbee2MQTT at that address.";
z2mStatus();if(act==="zb")paint()}};
ws.onclose=function(){if(!done){zerr=zerr||"Zigbee2MQTT closed the connection. Check the token.";
z2mStatus();if(act==="zb")paint()}}}

// The close handlers go first, because an intentional close must not report
// itself as a broker that dropped the connection.
function z2mDisconnect(){
if(ws){try{ws.onmessage=null;ws.onerror=null;ws.onclose=null;ws.close()}catch(x){}ws=null}
tg=null;td=null;zerr="";
z2mStatus();if(act==="zb")paint()}

function z2mSave(){
if(z2mUp()){z2mDisconnect();return}
var u=document.getElementById("zu").value.replace(/^\s+|\s+$/g,"");
var k=document.getElementById("zk").value.replace(/^\s+|\s+$/g,"");
if(!u){zerr="Enter the Zigbee2MQTT websocket address.";z2mStatus();return}
try{localStorage.setItem("c6.z2m.url",u);localStorage.setItem("c6.z2m.token",k)}catch(x){}
z2mConnect(u,k);z2mStatus()}

// The box stays available on an empty slot, so a code can be pasted in without
// pointing a source remote at the board.
function hasCode(text){return !!String(text||"").replace(/\s+/g,"")}

function codeBox(lock){
var dis=lock?" disabled":"",codeDis=dis||(!hasCode(cd)?" disabled":"");
var h="<div class=code><p class=hd>IR code</p>"+
"<p class=sub><a href=https://github.com/Lucaslhm/Flipper-IRDB target=_blank "+
"rel=noreferrer>Flipper-IRDB</a></p>"+
"<textarea id=ct rows=7 spellcheck=false autocomplete=off>"+esc(cd)+"</textarea>";
h+="<div class=act><button type=button class=sec id=cc"+codeDis+">Copy</button>"+
"<button type=button id=ca"+codeDis+">Apply to this input</button></div>"+
(cdSlot!==sel?"<p class=load>Loading the stored code.</p>":"")+"</div>";
return h}

function loadCode(s){var loadId=++codeLoad;cdSlot=null;cd="";
return fetch("/buttons/api/code?slot="+s,{cache:"no-store"})
.then(function(r){return r.json()})
.then(function(j){if(loadId!==codeLoad||j.slot!==s)return;
cd=j.text||"";cfgAll[s]=cd;cdSlot=s;if(sel===s)paint()})
.catch(function(){})}

// The page is served over plain HTTP, so navigator.clipboard is undefined in
// most browsers. execCommand still works there.
function copyBox(t){
t.focus();t.select();
var ok=false;
try{ok=document.execCommand("copy")}catch(x){}
if(!ok&&navigator.clipboard){navigator.clipboard.writeText(t.value);ok=true}
return ok}

function copyCode(){var t=document.getElementById("ct");
if(!hasCode(t.value)){msg="This input has no code to copy.";bad=true;paint();return}
var ok=copyBox(t);
msg=ok?"Code copied.":"Copy is blocked. Select the text and copy it by hand.";
bad=!ok;paint()}

function clipConfig(r){
if(!r)return null;
if(r.action==="ir")return {kind:"ir",source:r.slot};
if(r.action!=="zigbee")return null;
return r.ieee?{kind:"zigbee",source:r.slot,device:true,ieee:r.ieee,ep:r.ep||1,
act:r.act||0,val:r.val||0,name:r.name||""}:
{kind:"zigbee",source:r.slot,device:false,group:r.group,act:r.act||0,
val:r.val||0,name:r.name||""}}

function clipName(c){var d=info(c.source);return d?d.l:"that input"}

function copyAssignment(){
var c=clipConfig(row(sel)),source=sel;
if(!c){msg="Only an IR code or Zigbee target can be copied.";bad=true;paint();return}
if(c.kind==="zigbee"){clip=c;msg="Copied Zigbee config from "+clipName(c)+".";bad=false;paint();return}
clipBusy=true;paint();
fetch("/buttons/api/code?slot="+source,{cache:"no-store"})
.then(function(r){return r.json()}).then(function(j){
if(j.slot!==source||!j.present||!j.text)throw new Error();
c.code=j.text;clip=c;cfgAll[source]=j.text;
msg="Copied IR config from "+clipName(c)+".";bad=false})
.catch(function(){msg="Could not read that IR code.";bad=true})
.then(function(){clipBusy=false;paint()})}

function pasteAssignment(){
var c=clip,target=sel;
if(!c){msg="Copy an IR code or Zigbee target first.";bad=true;paint();return}
if(c.kind==="ir"){act="ir";codeLoad++;cd=c.code;cdSlot=target}
else{
act="zb";zkv=c.device?"d":"g";
zsv=c.device?"":String(c.group);zdv=c.device?c.ieee:"";
zgv=c.device?"":String(c.group);zhv=c.device?c.ieee:"";
zpv=c.device?String(c.ep||1):"";zav=Number(c.act)||0;
zvv=za(zav)&&za(zav).p?String(c.val):""}
msg="Pasted "+(c.kind==="ir"?"IR":"Zigbee")+" config from "+clipName(c)+
". Select "+(c.kind==="ir"?"Apply to this input":"Assign")+" to save it.";
bad=false;paint()}

function applyCode(){
var text=document.getElementById("ct").value;
cd=text;
if(!hasCode(text)){msg="Paste a code first.";bad=true;paint();return}
go("set_ir_code",text)}

// One entry per input, in the render order of the page. label is for the reader,
// because an import applies the slot number.
function cfgBlob(){
var lines=[],i;
for(i=0;i<S.length;i++){
var s=S[i].s,r=row(s),e={slot:s,label:S[i].l,action:"none"};
if(r&&r.action==="zigbee"){e.action="zigbee";
if(r.ieee){e.kind="device";e.ieee=r.ieee;e.ep=r.ep||1}
else{e.kind="group";e.group=r.group}
e.act=r.act||0;
if(r.val)e.val=r.val;
if(r.name)e.name=r.name}
else if(r&&r.action==="voice")e.action="voice";
else if(r&&r.action==="ir"){e.action="ir";e.code=cfgAll[s]||""}
lines.push(JSON.stringify(e))}
// One line for each input, because an indented block runs past 100 lines and a
// single line hides which input an entry belongs to.
return '{"c6remote":1,"slots":[\n'+lines.join(",\n")+"\n]}"}

// Reads the code of every IR input, one request at a time, because a burst of 18
// would outrun the connection limit of the remote.
function cfgRefresh(){
var need=[],i,s,r;
for(i=0;i<S.length;i++){s=S[i].s;r=row(s);
if(r&&r.action==="ir"&&cfgAll[s]===undefined)need.push(s)}
if(!need.length){cfgOut=cfgBlob();cfgPaint();return Promise.resolve()}
cfgBusy=true;cfgPaint();
return need.reduce(function(p,slot){return p.then(function(){
return fetch("/buttons/api/code?slot="+slot,{cache:"no-store"})
.then(function(x){return x.json()})
.then(function(j){cfgAll[slot]=j.text||""})
.catch(function(){cfgAll[slot]=""})})},Promise.resolve())
.then(function(){cfgBusy=false;cfgOut=cfgBlob();cfgPaint()})}

function cfgNote(text,isBad){cfgMsg=text;cfgBad=!!isBad;cfgPaint()}

function cfgHex(v){return String(v===undefined?"":v)
.replace(/^\s+|\s+$/g,"").replace(/^0[xX]/,"")}

// Every entry is read before the first write, so a bad one cannot leave half of
// the inputs on the old config and half on the new one.
function cfgCheck(e){
if(!e||typeof e.slot!=="number"||!info(e.slot))
return "A slot number is missing or unknown.";
var a=e.action,ep,g;
if(a==="voice"&&!info(e.slot).v)return "Slot "+e.slot+" has no voice action.";
if(a==="ir"&&(typeof e.code!=="string"||!e.code.replace(/\s+/g,"")))
return "Slot "+e.slot+" carries no IR code.";
if(a==="zigbee"&&e.kind==="device"){
if(!/^[0-9a-fA-F]{16}$/.test(cfgHex(e.ieee)))
return "Slot "+e.slot+" needs an IEEE address of 16 hex digits.";
ep=e.ep===undefined?1:parseInt(e.ep,10);
if(!(ep>=1&&ep<=240))return "Slot "+e.slot+" has an endpoint outside 1 to 240."}
else if(a==="zigbee"){
g=parseInt(e.group,10);
if(!(g>=1&&g<=65527))return "Slot "+e.slot+" has a group outside 1 to 65527."}
else if(a!=="ir"&&a!=="voice"&&a!=="none")
return "Slot "+e.slot+" carries the unknown action "+a+".";
if(a==="zigbee"){
var A=za(e.act===undefined?0:e.act);
if(!A)return "Slot "+e.slot+" names the unknown Zigbee action "+e.act+".";
if(A.p){
var v=e.val===undefined?A.d:parseInt(e.val,10);
if(!(v>=A.lo&&v<=A.hi))
return "Slot "+e.slot+" needs "+A.p.toLowerCase()+" of "+A.lo+" to "+A.hi+"."}
else if(e.val!==undefined&&parseInt(e.val,10)!==0)
return "Slot "+e.slot+" gives a value to "+A.n+", which takes none."}
return ""}

// An action with no value sends 0, and one with a value falls back to its
// default, so a hand written block can leave the field out.
function cfgVal(e){var A=za(e.act===undefined?0:e.act);
if(!A||!A.p)return 0;
return e.val===undefined?A.d:parseInt(e.val,10)}

// A clear on an input that already holds nothing writes flash for no gain, so it
// is the one entry an import skips.
function cfgNeeded(e){if(e.action!=="none")return true;
var r=row(e.slot);return !!(r&&r.action!=="none")}

function cfgSend(e){
if(e.action==="voice")return post("set_voice",e.slot);
if(e.action==="ir")return post("set_ir_code",e.slot,e.code);
if(e.action==="zigbee"&&e.kind==="device")
return post("set_zigbee_device",e.slot,null,e.name||"",
"&ieee=0x"+cfgHex(e.ieee).toLowerCase()+
"&ep="+(e.ep===undefined?1:parseInt(e.ep,10))+
"&act="+(e.act===undefined?0:parseInt(e.act,10))+"&val="+cfgVal(e));
if(e.action==="zigbee")
return post("set_zigbee",e.slot,String(parseInt(e.group,10)),e.name||"",
"&act="+(e.act===undefined?0:parseInt(e.act,10))+"&val="+cfgVal(e));
return post("clear",e.slot)}

// One input at a time, because the remote reserves one action at a time and a
// second POST would take the 409.
function cfgRun(list,i){
if(i>=list.length)return Promise.resolve();
cfgMsg="Writing input "+(i+1)+" of "+list.length+".";cfgBad=false;cfgPaint();
return cfgSend(list[i]).then(function(r){
if(r.code!==200)throw new Error("Slot "+list[i].slot+": "+fail(r));
return waitAction(r.body.id)}).then(function(ok){
if(!ok)throw new Error("Slot "+list[i].slot+": the remote refused it.");
return cfgRun(list,i+1)})}

function cfgApply(){
var j,i,why,list=[];
try{j=JSON.parse(cfgIn)}catch(x){cfgNote("That text is not valid JSON.",true);return}
if(!j||!Array.isArray(j.slots)){cfgNote("A config holds a slots list.",true);return}
for(i=0;i<j.slots.length;i++){
why=cfgCheck(j.slots[i]);
if(why){cfgNote(why,true);return}
if(cfgNeeded(j.slots[i]))list.push(j.slots[i])}
if(!list.length){cfgNote("Every input already matches this config.",false);return}
cfgBusy=true;cfgBad=false;
var total=j.slots.length;
return cfgRun(list,0).then(function(){
cfgBusy=false;cfgAll={};cdSlot=null;
cfgNote("Applied "+list.length+" of "+total+" inputs.",false);
return load().then(function(){paint();cfgRefresh();
if(sel!==null)loadCode(sel)})})
.catch(function(err){cfgBusy=false;
cfgNote(err&&err.message?err.message:"The remote did not answer.",true);
return load().then(paint)})}

function cfgCopy(){var t=document.getElementById("cx");
if(!t.value){cfgNote("There is nothing to copy yet.",true);return}
var ok=copyBox(t);
cfgNote(ok?"Config copied.":"Copy is blocked. Select the text and copy it by hand.",!ok)}

// The box reads cfgOut or cfgIn, so a repaint during an import keeps the pasted
// text and never shows an export beside it.
// The heading is the toggle, so the card needs no control of its own.
function cfgToggle(){cfgOpen=!cfgOpen;cfgMsg="";cfgBad=false;cfgPaint();
if(cfgOpen&&cfgMode==="ex")cfgRefresh()}

function cfgPaint(){
var e=document.getElementById("cfgio"),b=document.getElementById("cfgb"),
s=document.getElementById("cxs"),o=document.getElementById("cxo");
if(!e||!b)return;
if(s)s.textContent=cfgOpen?"Hide":"Show";
if(o){o.setAttribute("aria-expanded",cfgOpen?"true":"false");o.onclick=cfgToggle}
b.hidden=!cfgOpen;
if(!cfgOpen){e.innerHTML="";return}
var rd=cfgBusy?" disabled":"",wr=(cfgBusy||(st&&st.busy))?" disabled":"";
var h="<p class=hd>Import and export</p>"+
"<p class=sub>Copy every assignment out as one block of text, or paste a saved "+
"block back in. An export holds the IR codes themselves, so it restores a "+
"remote without a source remote.</p>"+
"<label class=hd2 for=cs>Direction</label>"+
"<select id=cs"+rd+">"+
"<option value=ex"+(cfgMode==="ex"?" selected":"")+">Export</option>"+
"<option value=im"+(cfgMode==="im"?" selected":"")+">Import</option>"+
"</select>";
if(cfgMsg)h+="<div class='note "+(cfgBad?"bad":"ok")+"'>"+esc(cfgMsg)+"</div>";
if(cfgBusy)h+="<div class=bar><i></i></div>";
h+="<textarea id=cx rows=12 spellcheck=false autocomplete=off"+
(cfgMode==="ex"?" readonly":"")+">"+esc(cfgMode==="ex"?cfgOut:cfgIn)+"</textarea>";
h+="<div class=act>";
h+=cfgMode==="ex"
?"<button type=button class=sec id=cxc>Copy</button>"+
"<button type=button class=sec id=cxr"+rd+">Read the remote</button>"
:"<button type=button id=cxa"+wr+">Apply to the remote</button>";
h+="</div>";
if(cfgMode==="im")h+="<p class=sub>An import writes one input at a time. It "+
"stops on the first entry the remote refuses, and it leaves an input the block "+
"does not name alone.</p>";
e.innerHTML=h;
document.getElementById("cs").onchange=function(){cfgMode=this.value;
cfgMsg="";cfgBad=false;cfgPaint();if(cfgMode==="ex")cfgRefresh()};
if(cfgMode==="ex"){
document.getElementById("cxc").onclick=cfgCopy;
if(!cfgBusy)document.getElementById("cxr").onclick=function(){cfgAll={};cfgMsg="";
cfgBad=false;cfgRefresh()}}
else{
var box=document.getElementById("cx");
box.oninput=function(){cfgIn=box.value};
if(!cfgBusy&&!(st&&st.busy))document.getElementById("cxa").onclick=cfgApply}}

function editor(){
var e=document.getElementById("ed");
if(sel===null){e.innerHTML="<h2>No input selected</h2>"+
"<p class=sub>Select an input on the left to change what it does.</p>";return}
var d=info(sel);
var copied=clipConfig(row(sel)),locked=(st&&st.busy)||zbusy||clipBusy;
var h="<h2 class=edtitle><span>"+esc(d.l)+"</span><span class=clip>"+
"<button type=button id=bcopy"+(!copied||locked?" disabled":"")+">Copy</button>"+
"<button type=button id=bpaste"+(!clip||locked?" disabled":"")+
" title='Paste config from "+att(clip?clipName(clip):"")+"'>Paste</button>"+
"</span></h2><p class=sub>Now: "+esc(words(sel))+"</p>"+detail(sel);
if(mode==="rec"&&rec===sel){
h+="<p>Point the source remote at the front of the board and press its button.</p>"+
"<div class=bar><i></i></div><div class=act>"+
"<button type=button class=sec id=bc>Cancel</button></div>";
e.innerHTML=h;document.getElementById("bc").onclick=cancel;return}
if(msg)h+="<div class='note "+(bad?"bad":"ok")+"'>"+esc(msg)+"</div>";
var lock=locked;
if(mode==="cancel")h+="<div class=note>Cancelling.</div>";
else if(st&&st.busy&&st.owner==="device")
h+="<div class=note>Assignment in progress on the remote.</div>";
else if(st&&st.busy)h+="<div class=note>Another assignment is already running.</div>";

// One selector, because a slot holds one action. The panel below it carries
// everything that action needs, so nothing from another action is on screen.
var opts=[["ir","IR code"],["zb","Zigbee target"]];
if(d.v)opts.push(["va","Voice assistant"]);
opts.push(["cl","Clear"]);
if(!d.v&&act==="va")act="ir";
h+="<p class=hd2>Action</p><select id=as"+(lock?" disabled":"")+">";
var title="";
for(var i=0;i<opts.length;i++){h+="<option value="+opts[i][0]+
(act===opts[i][0]?" selected":"")+">"+opts[i][1]+"</option>";
if(act===opts[i][0])title=opts[i][1]}
h+="</select><h2>"+esc(title)+"</h2>";
h+=act==="zb"?zbForm(st&&st.busy):act==="va"?vaPanel(lock):
act==="cl"?clearPanel(lock):irPanel(lock);
e.innerHTML=h;

if(!locked&&copied)document.getElementById("bcopy").onclick=copyAssignment;
if(!locked&&clip)document.getElementById("bpaste").onclick=pasteAssignment;
document.getElementById("as").onchange=function(){act=this.value;msg="";bad=false;paint()};
if(act==="ir"){
var box=document.getElementById("ct");
box.oninput=function(){cd=box.value;
var disabled=lock||!hasCode(cd);
document.getElementById("cc").disabled=disabled;
document.getElementById("ca").disabled=disabled};
document.getElementById("cc").onclick=copyCode;
document.getElementById("ca").onclick=applyCode;
if(!lock)document.getElementById("b1").onclick=function(){go("record_ir")}}
if(act==="zb"){
var gs=document.getElementById("zs"),ds=document.getElementById("zd"),
gi=document.getElementById("zg"),hi=document.getElementById("zh"),
pi=document.getElementById("zp");
// Switching kind drops the other kind's values, so nothing the panel stopped
// showing can still be sent.
document.getElementById("zn").onchange=function(){zkv=this.value;
zsv="";zdv="";zgv="";zhv="";zpv="";msg="";bad=false;paint()};
if(gs)gs.onchange=function(){zsv=this.value;if(zsv)zgv=zsv;paint()};
if(ds)ds.onchange=function(){zdv=this.value;
if(zdv){zhv=zdv;zpv=String(deviceEp(zdv,zav))}paint()};
if(gi)gi.oninput=function(){zgv=gi.value};
if(hi)hi.oninput=function(){zhv=hi.value};
if(pi)pi.oninput=function(){zpv=pi.value};
if(gs)gs.onclick=null;
var ai=document.getElementById("zt"),vi=document.getElementById("zv");
// The value belongs to the action that asked for it, and the endpoint follows
// the cluster the new action needs.
if(ai)ai.onchange=function(){zav=parseInt(this.value,10);zvv="";
if(zkv==="d"&&zhv)zpv=String(deviceEp(zhv,zav));
msg="";bad=false;paint()};
if(vi)vi.oninput=function(){zvv=vi.value};
document.getElementById("zi").onclick=assignTarget}
if(act==="va"&&!lock)document.getElementById("b2").onclick=function(){go("set_voice")};
if(act==="cl"&&!lock)document.getElementById("b3").onclick=function(){go("clear")}}

function actFor(s){var r=row(s);
if(!r||r.action==="none")return "ir";
if(r.action==="zigbee")return "zb";
if(r.action==="voice")return "va";
return "ir"}

function pick(s){
// Clear the previous input's code before paint, so its text cannot show while
// the selected input's request is still in flight.
if(sel!==s){cdSlot=null;cd=""}
sel=s;
if(mode!=="rec"){msg="";bad=false}
// Every Zigbee field belongs to the slot that was open, so none of it may
// follow the selection to the next one.
act=actFor(s);zsv="";zdv="";zgv="";zhv="";zpv="";
var pr=row(s);zkv=(pr&&pr.action==="zigbee"&&pr.ieee)?"d":"g";
zav=(pr&&pr.action==="zigbee")?(pr.act||0):0;
zvv=(pr&&pr.action==="zigbee"&&pr.val)?String(pr.val):"";
// Only IR assignments have stored code. Empty and Clear slots show a ready
// code box, so they do not wait for a request that can only return empty text.
if(!pr||pr.action!=="ir")cdSlot=s;
paint();
if(pr&&pr.action==="ir"&&cdSlot!==s)loadCode(s)}

function load(){return fetch("/buttons/api/state",{cache:"no-store"})
.then(function(r){return r.json()}).then(function(j){st=j;return j})}

// A code block keeps its newlines, because the parser reads it a line at a time.
// ESPHome caps a POST body, and the sdkconfig raises that cap for a full length
// raw frame.
function post(a,s,v,n,x){var b="action="+a+(s?"&slot="+s:"")+
(v?(a==="set_zigbee"?"&group=":"&code=")+encodeURIComponent(v):"")+
(n===undefined?"":"&name="+encodeURIComponent(n))+(x===undefined?"":x);
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

// The kind selector already said which target this is, so nothing here has to
// infer it from the format. The name is looked up fresh rather than remembered,
// so an edited box cannot keep a label from the target it replaced.
// Empty means the placeholder, so the value the box shows is the value sent.
// The remote bounds it again, because an import never passes through here.
function actionValue(){
var A=za(zav);
if(!A)return null;
if(!A.p)return "0";
var raw=String(zvv).replace(/^\s+|\s+$/g,"");
var n=raw===""?A.d:parseInt(raw,10);
if(!(n>=A.lo&&n<=A.hi)){
msg=A.p+" is "+A.lo+" to "+A.hi+".";bad=true;paint();return null}
return String(n)}

function assignTarget(){
var name="",i,val=actionValue();
if(val===null)return;
if(zkv==="d"){
var a=zhv.replace(/^\s+|\s+$/g,""),hex=a.replace(/^0[xX]/,"");
if(!a){msg="Pick a device, or type an IEEE address.";bad=true;paint();return}
if(!/^[0-9a-fA-F]{16}$/.test(hex)){
msg="An IEEE address is 16 hex digits.";bad=true;paint();return}
var ieee="0x"+hex.toLowerCase(),ep=zpv.replace(/^\s+|\s+$/g,"");
if(td)for(i=0;i<td.length;i++)if(td[i].ieee.toLowerCase()===ieee){
name=td[i].name;if(!ep)ep=String(deviceEp(ieee,zav))}
sendDevice(ieee,ep||"1",name,val);
return}
var g=zgv.replace(/^\s+|\s+$/g,"");
if(!g){msg="Pick a group, or type a group ID.";bad=true;paint();return}
var n=parseInt(g,g.slice(0,2).toLowerCase()==="0x"?16:10);
if(tg)for(i=0;i<tg.length;i++)if(tg[i].id===n)name=tg[i].name;
sendGroup(g,name,val)}

// The picker and the typed box both land here, so one path builds the request.
function sendDevice(ieee,ep,name,val){
var s=sel;
zbusy=true;paint();
post("set_zigbee_device",s,null,name,
"&ieee="+encodeURIComponent(ieee)+"&ep="+encodeURIComponent(ep)+
"&act="+Number(zav)+"&val="+encodeURIComponent(val))
.then(function(r){
zbusy=false;
if(r.code!==200){msg=fail(r);bad=true;return load().then(paint)}
return waitAction(r.body.id).then(function(ok){
var A=za(zav);
if(ok){msg=(A?A.n:"That action")+" assigned to "+(name?name:ieee)+".";bad=false}
else{msg="The remote could not store that device.";bad=true}
return load().then(paint)})})
.catch(function(){zbusy=false;msg="The remote did not answer.";bad=true;paint()})}

function sendGroup(v,name,val){
var s=sel;
zbusy=true;paint();
post("set_zigbee",s,v,name,"&act="+Number(zav)+"&val="+encodeURIComponent(val))
.then(function(r){
zbusy=false;
if(r.code!==200){msg=fail(r);bad=true;return load().then(paint)}
return waitAction(r.body.id).then(function(ok){
var A=za(zav);
if(ok){msg=(A?A.n:"That action")+" assigned to the Zigbee group.";bad=false}
else{msg="The remote could not store that group.";bad=true}
return load().then(paint)})})
.catch(function(){zbusy=false;msg="The remote did not answer.";bad=true;paint()})}

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
