const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Deliberately return older HTTP responses after the new manual checkpoint.
// No browser, backend, or provider is contacted by this regression test.
const elements = new Map();
const pending = [];
const timers = new Map();
let timerId = 0;
const context = vm.createContext({
  document: {
    querySelector(selector) {
      if (!elements.has(selector)) elements.set(selector, {
        hidden: false, value: '', textContent: '', innerHTML: '', style: {setProperty() {}}, getAttribute() {return 'false';}, setAttribute() {}, querySelector() {return {textContent:''};},
        addEventListener() {}, classList: {add() {}, remove() {}, toggle() {}},
        replaceChildren() {},
      });
      return elements.get(selector);
    },
    querySelectorAll() { return []; },
  },
  localStorage: {getItem(key) { return key === 'arena-session-id' ? 'test' : null; }, setItem() {}},
  location: {search: ''}, URLSearchParams, AbortController, crypto: {randomUUID() { return 'test'; }},
  setTimeout() { return 0; }, clearTimeout() {},
  setInterval(fn) { timers.set(++timerId, fn); return timerId; },
  clearInterval(id) { timers.delete(id); },
  fetch(url) {
    if (url === '/health') return new Promise(() => {});
    return new Promise(resolve => pending.push(job => resolve({
      ok: true, headers: {get() { return 'application/json'; }},
      async json() { return job; },
    })));
  },
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8'), context);
vm.runInContext(`
  renderCards = renderQuestion = renderWarnings = renderImage = renderManual = renderReport = () => {};
  activeId = 'r';
  activeJob = {request_id:'r', revision:1, status:'awaiting_image', events:[{sequence:8}]};
`, context);

function job(revision, sequence, status) {
  return {request_id: 'r', revision, status, events: [{sequence}], turns: [], brief: null};
}

(async () => {
  const older = vm.runInContext('refreshJob()', context);
  const newer = vm.runInContext('refreshJob()', context);
  pending[1](job(2, 10, 'awaiting_manual_audit'));
  await newer;
  assert.equal(elements.get('#next-action').hidden, false);
  assert.match(elements.get('#result-title').textContent, /Chờ kết quả kiểm tra/);
  assert.equal(timers.size, 0);
  pending[0](job(2, 9, 'queued'));
  await older;
  assert.equal(vm.runInContext('activeJob.status', context), 'awaiting_manual_audit');
  assert.equal(elements.get('#next-action').hidden, false);
  assert.equal(timers.size, 0);

  pending.length = 0;
  const oldRevision = vm.runInContext('refreshJob()', context);
  const nextRevision = vm.runInContext('refreshJob()', context);
  pending[1](job(3, 11, 'queued'));
  await nextRevision;
  assert.equal(timers.size, 1);
  pending[0](job(2, 10, 'awaiting_manual_audit'));
  await oldRevision;
  assert.equal(vm.runInContext('activeJob.revision', context), 3);
  assert.equal(timers.size, 1); // stale waiting state must not stop active polling
  vm.runInContext('syncPolling(); syncPolling()', context);
  assert.equal(timers.size, 1); // only one polling timer

  pending.length = 0;
  const completed = vm.runInContext('refreshJob()', context);
  pending[0](job(3, 12, 'awaiting_image_repair'));
  await completed;
  assert.equal(timers.size, 0);
  assert.equal(elements.get('#next-action').hidden, true);
  console.log('Passed: stale responses, revision ordering, audit action, and polling lifecycle.');
})().catch(error => { console.error(error); process.exitCode = 1; });
