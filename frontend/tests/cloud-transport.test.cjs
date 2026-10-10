const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
const transport = source.slice(source.indexOf('let cloudApiKey'), source.indexOf('function setKeyMessage'));
const calls = [];
const assets = new Map();
let next = 0;
const context = vm.createContext({
  window: {ARENA_CLOUD: true}, sessionId: 'browser-session', AbortController,
  setTimeout, clearTimeout, Blob, URL,
  fetch: async (url, options) => {
    calls.push({url, options});
    const body = options.body ? JSON.parse(options.body) : null;
    let value;
    if (url === '/uploads') {
      const id = String(++next); assets.set(id, body.data); value = {asset_id: id};
    } else if (url === '/uploads/assemble') {
      const id = String(++next); assets.set(id, body.chunks.map(c => assets.get(c)).join('')); value = {asset_id: id};
    } else value = body || {status: 'ok'};
    return {ok: true, headers: {get: () => 'application/json'}, json: async () => value};
  },
});
vm.runInContext(transport, context);
vm.runInContext('cloudApiKey = "fixture-key"', context);
(async () => {
  const original = 'A'.repeat(1048576 * 5 + 4);
  const result = await vm.runInContext(`api('/requests/r/images', {method:'POST',body:JSON.stringify({image:{mime_type:'image/png',data:${JSON.stringify(original)}}})})`, context);
  assert.equal(assets.get(result.image.asset_id), original);
  assert.equal(calls.filter(c => c.url === '/uploads').length, 6);
  assert.ok(calls.filter(c => c.url === '/uploads').every(c => c.options.body.length < 1400000));
  const final = calls.at(-1);
  assert.equal(final.options.headers['X-Arena-Session'], 'browser-session');
  assert.equal(final.options.headers['X-Gemini-Key'], 'fixture-key');
  assert.equal(JSON.parse(final.options.body).image.data, undefined);
  assert.equal(final.options.body.includes('fixture-key'), false);
  assert.equal(final.options.body.includes('browser-session'), false);
  console.log('Passed: lossless chunk staging, small payloads, scoped session and memory-only key header.');
})().catch(error => {console.error(error); process.exitCode = 1;});
