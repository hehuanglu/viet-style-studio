const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const drawn = [], text = [], writes = [];
const ctx = {clearRect(){},fillRect(){},measureText(value){return {width:value.length*9};},fillText(value){text.push(value);},drawImage(image){drawn.push(image.src);}};
const context = vm.createContext({
  Image: class {constructor(){this.naturalWidth=800;this.naturalHeight=1200;} async decode(){if(this.src.endsWith('broken'))throw new Error('Invalid image');}},
  Blob, window:{ClipboardItem:true}, ClipboardItem:class {constructor(formats){this.formats=formats;}},
  document:{createElement(name){assert.equal(name,'canvas');return {getContext(){return ctx;},toBlob(callback){callback(new Blob(['png-with-two-panels-and-prompt'],{type:'image/png'}));}};}},
  navigator:{clipboard:{async write(items){const resolved=await Promise.all(items.map(async item=>Object.fromEntries(await Promise.all(Object.entries(item.formats).map(async([type,value])=>[type,await value])))));writes.push(resolved);}}},
  escapeHtml(value){return String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');},
});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../image-editor.js'),'utf8'),context);
context.packet={prompt:'Giữ màu áo. <Không đổi nền>.',original:{mime_type:'image/jpeg',data:'before'},guide:{mime_type:'image/png',data:'after'}};
(async()=>{
  await vm.runInContext('copyArenaEditPacket(Promise.resolve(packet))',context);
  assert.equal(writes.length,1);assert.equal(writes[0].length,1);
  const formats=writes[0][0];assert.deepEqual(Object.keys(formats),['text/plain','text/html','image/png']);
  const html=await formats['text/html'].text();assert.equal((html.match(/<img /g)||[]).length,2);
  assert.ok(html.indexOf('base64,before') < html.indexOf('base64,after'));
  assert.ok(html.includes('&lt;Không đổi nền&gt;'));
  assert.ok((await formats['text/plain'].text()).endsWith(context.packet.prompt));
  assert.deepEqual(drawn,['data:image/jpeg;base64,before','data:image/png;base64,after']);
  assert.ok(text.includes(context.packet.prompt));
  context.packet.guide.data='broken';
  await assert.rejects(vm.runInContext('copyArenaEditPacket(packet)',context),/Invalid image/);
  assert.equal(writes.length,1,'An incomplete image packet must not be reported/copied as text only');
  console.log('Passed: one clipboard item contains prompt, ordered image pair and PNG fallback; missing images fail clearly.');
})().catch(error=>{console.error(error);process.exitCode=1;});
