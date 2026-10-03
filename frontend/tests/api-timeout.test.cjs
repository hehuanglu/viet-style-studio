const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
const ids = new Set([...html.matchAll(/id="([^"]+)"/g)].map(m => m[1]));
for (const m of source.matchAll(/\$\("#([^" .]+)"\)/g)) {
  assert.ok(ids.has(m[1]), `Static element missing from HTML: ${m[1]}`);
}
const apiSource = source.slice(source.indexOf('async function api('), source.indexOf('function setKeyMessage'));
let callback, cleared, signal;
const context = vm.createContext({AbortController,
  setTimeout(fn, ms) { callback = fn; assert.equal(ms, 15000); return 7; },
  clearTimeout(id) { cleared = id; },
  fetch(_url, options) { signal = options.signal; return new Promise(() => {}); },
});
vm.runInContext(apiSource, context);
(async () => {
  const pending = vm.runInContext("api('/requests')", context);
  callback(); // Transport deliberately ignores abort; the deadline must still settle.
  await assert.rejects(pending, error => error.code === 'request_timeout');
  assert.equal(signal.aborted, true);
  assert.equal(cleared, 7);
  context.fetch = (_url, options) => {
    signal = options.signal;
    return Promise.resolve({ok:true, headers:{get:()=>'application/json'}, json:()=>new Promise(()=>{})});
  };
  const bodyPending = vm.runInContext("api('/requests/r')", context);
  await Promise.resolve(); await Promise.resolve();
  callback();
  await assert.rejects(bodyPending, error => error.code === 'request_timeout');
  assert.equal(cleared, 7);
  console.log('Passed: static DOM IDs and stalled transport/body timeouts.');
})().catch(error => {console.error(error); process.exitCode = 1;});
