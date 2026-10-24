'use strict';
// Test the real controller while stubbing only browser dialogs and its DOM boundary.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const C = require('../app/static/board-core.js');
const nodes = new Map();
const node = id => {
  if (!nodes.has(id)) nodes.set(id, {
    hidden: true, open: false, textContent: '', focus() {},
    close() { this.open = false; }, showModal() { this.open = true; }, replaceChildren() {},
  });
  return nodes.get(id);
};
const context = { window: { BoardCore: C }, document: { getElementById: node }, console, FormData, setTimeout, clearTimeout };
vm.createContext(context);
vm.runInContext(fs.readFileSync(require.resolve('../app/static/boards.js'), 'utf8').replace('window.boardWorkspace = new BoardWorkspace();', 'window.TestWorkspace = BoardWorkspace;'), context);
function workspace() {
  nodes.clear();
  const w = Object.create(context.window.TestWorkspace.prototype);
  Object.assign(w, {
    project: 1,
    board: { id: 1, name: 'Local', revision: 1, objects: [{ id: 'label', type: 'text', text: 'Unsaved', x: 1, y: 2, width: 30, height: 20 }], view: { x: 0, y: 0, zoom: 1 }, assets: [] },
    boards: [], selected: new Set(['label']), readOnly: false,
    history: new C.History(), saveState: new C.SaveState(1), saving: false,
  });
  w.saveState.edit(); w.saveState.conflict = true;
  w.render = () => {}; w.renderList = () => {};
  w.accept = board => { w.accepted = board; }; w.comparison = () => ({});
  // Async dialogs are UI boundaries. Awaited test functions make an accidentally
  // unresolved dialog fail node:test instead of silently exiting with code zero.
  w.askName = async () => 'Local copy';
  w.askConfirm = async () => true;
  node('conflict').open = true;
  return w;
}

test('failed copy retains the complete local board and conflict', async () => {
  const w = workspace(), local = JSON.stringify(w.board);
  let calls = 0;
  w.api = async () => { calls++; throw new Error('offline'); };
  await w.recover('copy');
  assert.equal(calls, 1);
  assert.equal(JSON.stringify(w.board), local);
  assert.equal(w.saveState.conflict, true);
  assert.match(node('recovery-error').textContent, /local edits are still here/);
});

test('canceling Open latest makes no request and preserves local edits', async () => {
  const w = workspace(), local = JSON.stringify(w.board);
  let calls = 0, confirmations = 0;
  w.askConfirm = async () => { confirmations++; return false; };
  w.api = async () => { calls++; };
  await w.recover('latest');
  assert.equal(confirmations, 1);
  assert.equal(calls, 0);
  assert.equal(JSON.stringify(w.board), local);
});

test('Replace latest is unavailable before comparison', async () => {
  const w = workspace();
  let calls = 0, confirmations = 0;
  w.askConfirm = async () => { confirmations++; return true; };
  w.api = async () => { calls++; };
  await w.recover('replace');
  assert.equal(calls, 0);
  assert.equal(confirmations, 0);
});

test('second conflict during confirmed replacement preserves edits and requires fresh comparison', async () => {
  const w = workspace(), local = JSON.stringify(w.board);
  w.api = async () => ({ ...w.board, name: 'Latest', revision: 4 });
  await w.recover('compare');
  assert.equal(node('comparison').hidden, false);
  assert.equal(node('replace').hidden, false);
  let calls = 0;
  w.api = async () => {
    calls++;
    const error = new Error('New conflict');
    error.status = 409; error.detail = { latest: { revision: 5 } }; throw error;
  };
  await w.recover('replace');
  assert.equal(calls, 1);
  assert.equal(JSON.stringify(w.board), local);
  assert.equal(w.saveState.conflict, true);
  assert.equal(node('replace').hidden, true);
});

test('read-only mutation calls do not change data or make requests', async () => {
  const w = workspace(); w.readOnly = true;
  const local = JSON.stringify(w.board);
  let calls = 0;
  w.api = async () => { calls++; };
  w.remove(); w.duplicate(); w.layer(true); w.undo(); w.edit('text');
  await w.recover('copy');
  assert.equal(JSON.stringify(w.board), local);
  assert.equal(calls, 0);
});

test('failed save retains dirty local edits and reports failure', async () => {
  const w = workspace(); w.saveState.conflict = false;
  w.api = async () => { throw new Error('offline'); };
  await w.save();
  assert.equal(w.saveState.dirty, true);
  assert.match(node('status').textContent, /Couldn't save/);
  assert.equal(w.board.objects[0].text, 'Unsaved');
});
