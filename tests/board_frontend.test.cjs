const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const C = require('../app/static/board-core.js');

test('screen coordinates and zoom keep the pointer over the same canvas point', () => {
  const view = { x: -130, y: 240, zoom: .4 };
  const before = C.point(200, 350, view);
  assert.deepEqual(C.point(200, 350, C.zoomAt(view, 2.5, 200, 350)), before);
});
test('fit contains negative-position objects without changing arrangements', () => {
  const objects = [{ x: -500, y: 20, width: 200, height: 100 }, { x: 600, y: 300, width: 100, height: 400 }];
  const original = C.clone(objects), view = C.fit(objects, 800, 600);
  for (const o of objects) { assert.ok(o.x * view.zoom + view.x >= 0); assert.ok((o.y + o.height) * view.zoom + view.y <= 600); }
  assert.deepEqual(objects, original);
});
test('resize preserves aspect ratio and never produces a zero dimension', () => {
  const object = { width: 100, height: 300 };
  for (const delta of [1, 10, -1, -1000, 100000]) { const resized = C.resize(object, delta); assert.equal(resized.height / resized.width, 3); assert.ok(resized.width > 0); }
});
test('marquee replacement and Shift extension deduplicate selection', () => {
  const objects = [{ id: 'one', x: 10, y: 10, width: 10, height: 10 }, { id: 'two', x: 100, y: 100, width: 5, height: 5 }];
  assert.deepEqual(C.marquee(objects, { x: 30, y: 30 }, { x: 0, y: 0 }), ['one']);
  assert.deepEqual(C.marquee(objects, { x: 0, y: 0 }, { x: 30, y: 30 }, ['two', 'one']), ['two', 'one']);
});
test('history snapshots do not alias later edits and a new edit clears redo', () => {
  const history = new C.History(), objects = [{ x: 0 }]; history.push(objects); objects[0].x = 100;
  assert.deepEqual(history.undo(objects), [{ x: 0 }]); assert.deepEqual(history.redo([{ x: 0 }]), objects);
  history.undo(objects); history.push([{ x: 5 }]); assert.equal(history.future.length, 0);
});
test('save acknowledgement leaves edits made in flight dirty', () => {
  const state = new C.SaveState(1); state.edit(); const sent = state.generation; state.edit(); state.acknowledge(sent, 2);
  assert.equal(state.dirty, true); assert.equal(state.revision, 2);
});
test('invalid hex does not become a valid color', () => { assert.equal(C.hex('#abc123'), '#ABC123'); assert.equal(C.hex('red'), null); assert.equal(C.hex('#123'), null); });

// Exercise the real controller without a browser dependency. Only DOM surfaces
// used by the tested methods are stubbed; API completion remains asynchronous.
function workspace() {
  const nodes = new Map();
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, {
      textContent: '', hidden: true, open: false, style: {}, listeners: {},
      close() { this.open = false; },
      showModal() { this.open = true; },
      focus() {},
      setPointerCapture() {},
      closest() { return null; },
      addEventListener(type, listener) { this.listeners[type] = listener; },
    });
    return nodes.get(id);
  };
  const context = { window: { BoardCore: C }, document: { getElementById: node }, console, history: { replaceState() {} }, setTimeout, clearTimeout, confirm: () => true };
  vm.createContext(context);
  const source = fs.readFileSync(require.resolve('../app/static/boards.js'), 'utf8').replace('window.boardWorkspace = new BoardWorkspace();', 'window.BoardWorkspace = BoardWorkspace;');
  vm.runInContext(source, context);
  const app = Object.create(context.window.BoardWorkspace.prototype);
  app.itemId = 1; app.board = { id: 1, name: 'Local', revision: 1, objects: [{ id: 'text', type: 'text', text: 'local', x: 0, y: 0, width: 100, height: 40 }], view: { x: 0, y: 0, zoom: 1 }, assets: [] };
  app.boards = [app.board]; app.saveState = new C.SaveState(1); app.saveState.edit(); app.saving = false; app.readOnly = false; app.selected = new Set(['text']); app.history = new C.History(); app.uploads = [];
  app.pointers = new Map(); app.loadVersion = 0;
  app.render = () => {}; app.schedule = () => { app.scheduled = (app.scheduled || 0) + 1; };
  app.askConfirm = async () => true;
  app.loadCatalog = async () => {};
  return { app, node, context };
}
test('controller preserves in-flight edits and schedules the next save', async () => {
  const { app } = workspace(); let resolve; app.api = () => new Promise(r => { resolve = r; });
  const saving = app.save(); app.saveState.edit(); resolve({ ...app.board, revision: 2 }); await saving;
  assert.equal(app.saveState.dirty, true); assert.equal(app.saveState.revision, 2); assert.equal(app.scheduled, 1);
});
test('old board response cannot acknowledge a new board and restarts its save', async () => {
  const { app } = workspace(); let resolve; app.api = () => new Promise(r => { resolve = r; });
  const old = app.board, saving = app.save(); app.board = { ...old, id: 2 }; app.saveState = new C.SaveState(5); app.saveState.edit();
  await app.save(); resolve({ ...old, revision: 2 }); await saving;
  assert.equal(app.saveState.revision, 5); assert.equal(app.saveState.dirty, true); assert.equal(app.scheduled, 1);
});
test('save conflict retains local state and pauses automatic writes', async () => {
  const { app } = workspace(), local = C.clone(app.board); app.api = async () => { throw { status: 409, detail: { latest: { id: 1, revision: 2 } } }; };
  await app.save(); assert.equal(app.saveState.conflict, true); assert.deepEqual(app.board, local); assert.equal(app.scheduled, undefined);
});
test('failed save keeps changes available for a successful explicit retry', async () => {
  const { app, node } = workspace(), local = C.clone(app.board);
  app.api = async () => { throw new Error('Offline'); }; await app.save();
  assert.equal(app.saveState.dirty, true); assert.deepEqual(app.board, local); assert.match(node('status').textContent, /Couldn't save/);
  app.api = async () => ({ ...local, revision: 2 }); await app.save(); assert.equal(app.saveState.dirty, false); assert.equal(node('status').textContent, 'Saved');
});
test('failed latest recovery and dismissal retain complete local work', async () => {
  const { app, node } = workspace(), local = C.clone(app.board); app.saveState.conflict = true; app.api = async () => { throw new Error('Offline'); };
  await app.recover('latest'); assert.deepEqual(app.board, local); assert.equal(app.saveState.conflict, true); assert.match(node('recovery-error').textContent, /local edits are still here/);
  node('conflict').close(); assert.deepEqual(app.board, local); assert.equal(app.saveState.dirty, true);
});
test('dismissing recovery during a successful request retains local edits', async () => {
  const { app, node } = workspace(), local = C.clone(app.board); app.saveState.conflict = true; node('conflict').open = true;
  const originalAssets = [{ key: 'project:1' }]; app.assets = originalAssets;
  let resolve;
  app.api = path => path.endsWith('/board-assets')
    ? Promise.resolve([{ key: 'project:1' }, { key: 'project:2' }])
    : new Promise(r => { resolve = r; });
  const recovery = app.recover('latest'); await new Promise(setImmediate); node('conflict').close(); resolve({ ...local, revision: 2, objects: [] }); await recovery;
  assert.deepEqual(app.board, local); assert.equal(app.saveState.conflict, true);
  assert.equal(app.assets, originalAssets);
});

test('opening latest refreshes the combined library and switcher before accepting the board', async () => {
  const { app, node } = workspace();
  app.saveState.conflict = true;
  node('conflict').open = true;
  const latest = { ...app.board, name: 'Updated name', revision: 2 };
  const assets = [{ key: 'project:1' }, { key: 'project:2' }, { key: 'item:3' }];
  app.assets = [assets[0]];
  app.api = async path => path.endsWith('/board-assets') ? assets : latest;
  let rendered = false, accepted = false;
  app.renderList = () => {
    rendered = true;
    assert.equal(app.boards[0].name, 'Updated name');
  };
  app.accept = board => {
    accepted = true;
    assert.equal(board, latest);
    assert.equal(app.assets, assets);
    assert.equal(rendered, true);
  };
  await app.recover('latest');
  assert.equal(accepted, true);
  assert.equal(node('conflict').open, false);
});

test('library refresh failure preserves the local composition, old deck, and conflict', async () => {
  const { app, node } = workspace();
  app.saveState.conflict = true;
  node('conflict').open = true;
  const local = app.board, originalAssets = [{ key: 'project:1' }];
  app.assets = originalAssets;
  app.api = async path => {
    if (path.endsWith('/board-assets')) throw new Error('Library unavailable');
    return { ...local, revision: 2, objects: [] };
  };
  app.accept = () => assert.fail('Recovery must not discard local work after a failed library refresh');
  await app.recover('latest');
  assert.equal(app.board, local);
  assert.equal(app.assets, originalAssets);
  assert.equal(app.saveState.conflict, true);
  assert.equal(node('conflict').open, true);
  assert.match(node('recovery-error').textContent, /Library unavailable/);
});

test('late recovery results never refresh a different active workspace', async () => {
  const { app, node } = workspace();
  app.saveState.conflict = true;
  node('conflict').open = true;
  const local = app.board, originalAssets = [{ key: 'project:1' }];
  app.assets = originalAssets;
  let finish;
  app.api = path => path.endsWith('/board-assets')
    ? Promise.resolve([{ key: 'project:2' }])
    : new Promise(resolve => { finish = resolve; });
  app.accept = () => assert.fail('Superseded recovery must not change the active workspace');
  const recovering = app.recover('latest');
  await new Promise(setImmediate);
  const current = { ...local, id: 2 };
  app.board = current;
  finish({ ...local, revision: 2 });
  await recovering;
  assert.equal(app.board, current);
  assert.equal(app.assets, originalAssets);
});
test('replace requires comparison and a fresh conflict hides replacement again', async () => {
  const { app, node } = workspace(); app.saveState.conflict = true; let calls = 0; app.latest = { revision: 2, name: 'Latest' };
  app.api = async () => { calls++; throw { status: 409, message: 'Changed again', detail: { latest: { revision: 3 } } }; };
  await app.recover('replace'); assert.equal(calls, 0);
  node('comparison').hidden = false; await app.recover('replace'); assert.equal(calls, 1); assert.equal(node('comparison').hidden, true); assert.equal(node('replace').hidden, true); assert.equal(app.board.objects[0].text, 'local');
});
test('cancelling confirmation never opens latest or replaces the saved version', async () => {
  const { app, node } = workspace(), local = C.clone(app.board); app.saveState.conflict = true; app.latest = { revision: 2, name: 'Latest' };
  node('comparison').hidden = false; app.askConfirm = async () => false; let calls = 0; app.api = async () => { calls++; };
  await app.recover('latest'); await app.recover('replace'); assert.equal(calls, 0); assert.deepEqual(app.board, local); assert.equal(app.saveState.conflict, true);
});
test('View only rejects mutation methods even when invoked directly', async () => {
  const { app } = workspace(); app.readOnly = true; app.saveState.conflict = true; const local = C.clone(app.board); let requests = 0; app.api = async () => { requests++; };
  app.change(() => { throw new Error('mutation invoked'); }); app.remove(); app.duplicate(); app.layer(true); app.undo(); app.commitEditor(); app.edit('text');
  await app.place({ key: 'project:1' }); await app.upload([]); await app.create(); await app.manage(app.board, 'Delete'); await app.recover('copy'); await app.recover('replace'); await app.save();
  assert.deepEqual(app.board, local); assert.equal(requests, 0);
});
test('sub-threshold pointer motion does not mutate or silently become unsaved', () => {
  const { app, node } = workspace(); node('canvas').getBoundingClientRect = () => ({ left: 0, top: 0 });
  const before = C.clone(app.board.objects); app.gesture = { kind: 'move', start: { x: 0, y: 0 }, objects: C.clone(before) };
  app.pointerMove({ clientX: 1, clientY: 0 }); app.pointerUp(); assert.deepEqual(app.board.objects, before); assert.equal(app.history.past.length, 0);
});

test('responsive mode keeps deck disclosure and canvas instructions accurate', () => {
  const { app, node, context } = workspace();
  context.document.body = { classList: { toggle() {} } };
  for (const id of ['deck-toggle', 'canvas']) {
    node(id).attributes = {};
    node(id).setAttribute = (key, value) => { node(id).attributes[key] = value; };
  }
  app.fit = () => {};
  app.view = () => {};
  app.tools = () => {};
  node('deck').hidden = false;
  app.readOnly = true;
  app.mode();
  assert.equal(node('deck').hidden, true);
  assert.equal(node('deck-toggle').attributes['aria-expanded'], 'false');
  assert.match(node('canvas').attributes['aria-label'], /View only/);
  assert.doesNotMatch(node('canvas').attributes['aria-label'], /move selected/);

  app.readOnly = false;
  app.mode();
  assert.equal(node('deck-toggle').attributes['aria-expanded'], 'false');
  assert.match(node('canvas').attributes['aria-label'], /Arrow keys move/);
  assert.equal(node('message').hidden, true);
  app.notice('Upload failed. Please retry.');
  node('deck').hidden = false;
  app.mode();
  assert.equal(node('deck-toggle').attributes['aria-expanded'], 'true');
  assert.equal(node('message').textContent, 'Upload failed. Please retry.');
  assert.equal(node('message').hidden, false);
});

function interactionWorkspace() {
  // Register the production event wiring, then dispatch through its listeners.
  // This catches missing gesture guards and coordinate conversion at entry,
  // rather than only retesting the pure geometry helpers in isolation.
  const harness = workspace();
  const { app, node, context } = harness;
  node('canvas').getBoundingClientRect = () => ({ left: 20, top: 30, width: 600, height: 400 });
  context.document.addEventListener = (type, handler) => node('document').addEventListener(type, handler);
  context.document.querySelector = () => null;
  context.window.addEventListener = () => {};
  context.matchMedia = () => ({ addEventListener() {} });
  app.tool = 'select';
  app.view = () => {};
  app.tools = () => {};
  app.bind();
  return harness;
}

test('Space-drag pans the camera without moving or changing selected objects', () => {
  const { app, node } = interactionWorkspace();
  app.board.view = { x: 10, y: 20, zoom: 2 };
  const geometry = C.clone(app.board.objects);
  node('document').listeners.keydown({
    key: ' ', code: 'Space', target: node('canvas'), preventDefault() {},
  });
  node('canvas').listeners.pointerdown({
    button: 0, clientX: 50, clientY: 60, pointerId: 1,
    target: node('canvas'), preventDefault() {},
  });
  node('canvas').listeners.pointermove({ clientX: 95, clientY: 100 });
  node('canvas').listeners.pointerup();
  node('document').listeners.keyup({ code: 'Space' });
  assert.deepEqual(C.clone(app.board.view), { x: 55, y: 60, zoom: 2 });
  assert.deepEqual(app.board.objects, geometry);
  assert.deepEqual([...app.selected], ['text']);
  assert.equal(app.history.past.length, 0);
  assert.equal(app.space, false);
  assert.equal(app.tool, 'select');
});

test('middle-button drag pans even over an object without selecting or moving it', () => {
  const { app, node } = interactionWorkspace();
  app.selected.clear();
  const geometry = C.clone(app.board.objects);
  const object = { dataset: { id: 'text' } };
  node('canvas').listeners.pointerdown({
    button: 1, clientX: 50, clientY: 60, pointerId: 1,
    target: { closest: selector => selector === '.object' ? object : null },
    preventDefault() {},
  });
  node('canvas').listeners.pointermove({ clientX: 95, clientY: 100 });
  node('canvas').listeners.pointerup();
  assert.deepEqual(C.clone(app.board.view), { x: 45, y: 40, zoom: 1 });
  assert.deepEqual(app.board.objects, geometry);
  assert.equal(app.selected.size, 0);
  assert.equal(app.history.past.length, 0);
});

test('View only touch pans with one finger and pinches around the moving midpoint without editing objects', () => {
  const { app, node } = interactionWorkspace();
  app.readOnly = true;
  const wasDirty = app.saveState.dirty;
  app.board.view = { x: 0, y: 0, zoom: 1 };
  const geometry = C.clone(app.board.objects), canvas = node('canvas');
  const touch = (pointerId, x, y) => ({ pointerType: 'touch', pointerId, button: 0, clientX: x, clientY: y, target: canvas, preventDefault() {} });

  canvas.listeners.pointerdown(touch(1, 120, 130));
  canvas.listeners.pointermove(touch(1, 150, 160));
  canvas.listeners.pointerup({ ...touch(1, 150, 160), type: 'pointerup' });
  assert.deepEqual(C.clone(app.board.view), { x: 30, y: 30, zoom: 1 });

  // An iPad in landscape can be past the responsive breakpoint and still need
  // native two-finger camera navigation while its editing controls are shown.
  app.readOnly = false;
  canvas.listeners.pointerdown(touch(2, 100, 100));
  canvas.listeners.pointerdown(touch(3, 200, 100));
  canvas.listeners.pointermove(touch(2, 80, 80));
  canvas.listeners.pointermove(touch(3, 240, 120));
  canvas.listeners.pointerup({ ...touch(3, 240, 120), type: 'pointerup' });

  assert.ok(app.board.view.zoom > 1);
  assert.ok(Number.isFinite(app.board.view.x));
  assert.ok(Number.isFinite(app.board.view.y));
  assert.deepEqual(app.board.objects, geometry);
  assert.equal(app.history.past.length, 0);
  assert.equal(app.saveState.dirty, wasDirty);
});

for (const shiftKey of [false, true]) {
  test(`Select marquee ${shiftKey ? 'extends selection with Shift' : 'replaces selection'} at non-default zoom`, () => {
    const { app, node } = interactionWorkspace();
    app.board.objects.push({ id: 'outside', type: 'swatch', color: '#000000', x: 200, y: 0, width: 30, height: 30 });
    app.board.view = { x: 10, y: 20, zoom: 2 };
    app.selected = new Set(['outside']);
    const geometry = C.clone(app.board.objects), camera = C.clone(app.board.view);
    node('canvas').listeners.pointerdown({
      button: 0, clientX: 10, clientY: 30, pointerId: 1, shiftKey,
      target: node('canvas'), preventDefault() {},
    });
    node('canvas').listeners.pointermove({ clientX: 270, clientY: 170 });
    node('canvas').listeners.pointerup();
    assert.deepEqual([...app.selected].sort(), shiftKey ? ['outside', 'text'] : ['text']);
    assert.deepEqual(app.board.objects, geometry);
    assert.deepEqual(app.board.view, camera);
    assert.equal(app.history.past.length, 0);
    assert.equal(node('marquee').hidden, true);
  });
}

test('file drop converts viewport location into canvas coordinates and View only rejects it', () => {
  const { app, node } = interactionWorkspace();
  app.board.view = { x: 100, y: 40, zoom: 2 };
  const file = { name: 'reference.png' }, uploads = [];
  app.upload = (files, position) => uploads.push({ files, position });
  const event = {
    clientX: 220, clientY: 190, preventDefault() {},
    dataTransfer: { getData: () => '', files: [file] },
  };
  node('canvas').listeners.drop(event);
  assert.equal(uploads.length, 1);
  assert.equal(uploads[0].files[0], file);
  assert.deepEqual(uploads[0].position, { x: 50, y: 60 });
  app.readOnly = true;
  node('canvas').listeners.drop(event);
  assert.equal(uploads.length, 1);
});

test('image paste preserves typing and dialog input, then places outside typing in the visible canvas', () => {
  const { app, node, context } = interactionWorkspace();
  app.board.view = { x: 100, y: 40, zoom: 2 };
  const file = { name: 'clipboard.png' }, uploads = [];
  let prevented = 0;
  app.upload = (files, position) => uploads.push({ files, position });
  const event = {
    target: { closest: () => ({ tagName: 'TEXTAREA' }) },
    preventDefault: () => { prevented++; },
    clipboardData: { items: [{ kind: 'file', type: 'image/png', getAsFile: () => file }] },
  };
  node('document').listeners.paste(event);
  assert.equal(uploads.length, 0);
  assert.equal(prevented, 0);
  event.target = node('canvas');
  context.document.querySelector = () => ({ open: true });
  node('document').listeners.paste(event);
  assert.equal(uploads.length, 0);
  assert.equal(prevented, 0);
  context.document.querySelector = () => null;
  node('document').listeners.paste(event);
  assert.equal(uploads.length, 1);
  assert.equal(uploads[0].files[0], file);
  assert.deepEqual(uploads[0].position, { x: 100, y: 80 });
  assert.equal(prevented, 1);
  app.readOnly = true;
  node('document').listeners.paste(event);
  assert.equal(uploads.length, 1);
});

// Project entry is read-only until the explicit naming step succeeds.
function entryWorkspace(search) {
  const state = workspace();
  state.context.location = { search };
  state.context.URLSearchParams = URLSearchParams;
  state.context.document.createElement = () => ({});
  state.app.loadCatalog = async () => {};
  state.app.itemId = '';
  return state;
}

test('unscoped or invalid board links never select the first project or create a board', async () => {
  for (const search of ['', '?project=999&create=1']) {
    const { app } = entryWorkspace(search);
    app.api = async () => [{ id: 2, name: 'Project' }];
    app.loadItemBoards = async () => false;
    app.create = async () => assert.fail('Unexpected board creation');
    await app.start();
    assert.equal(app.itemId, '');
  }
});

test('item entry only requests creation for explicit create intent after successful load', async () => {
  for (const [query, loaded, expected] of [['?item=2', true, 0], ['?item=2&create=1', true, 1], ['?item=2&create=1', false, 0]]) {
    const { app } = entryWorkspace(query);
    app.api = async () => [{ id: 2, name: 'Project' }];
    app.loadItemBoards = async () => loaded;
    let created = 0;
    app.create = async () => { created++; };
    await app.start();
    assert.equal(app.itemId, '2');
    assert.equal(created, expected);
  }
});

test('named board link opens its board without creating another', async () => {
  const { app } = entryWorkspace('?item=2&board=7');
  app.api = async () => [{ id: 2, name: 'Project' }];
  app.loadItemBoards = async () => true;
  app.open = async id => { assert.equal(id, '7'); app.opened = true; };
  app.create = async () => assert.fail('Unexpected board creation');
  await app.start();
  assert.equal(app.opened, true);
});

test('cancelling board naming performs no writes and confirmed creation opens the board', async () => {
  const { app } = workspace();
  app.canLeave = async () => true;
  app.askName = async () => null;
  app.api = async () => assert.fail('Cancelled creation must not write');
  await app.create();
  app.askName = async () => 'My board';
  app.api = async (path, options) => {
    assert.equal(path, '/api/items/1/boards');
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), { name: 'My board' });
    return { id: 8, name: 'My board' };
  };
  app.renderList = () => {};
  app.loadCatalog = async () => {};
  app.accept = board => { app.board = board; };
  await app.create();
  assert.equal(app.board.id, 8);
});

test('uploads before a board is open do not enter the upload queue', async () => {
  const { app } = workspace();
  app.board = null;
  app.uploadOne = async () => assert.fail('No board is open');
  await app.upload([{ name: 'test.png' }]);
  assert.equal(app.uploads.length, 0);
});


function dashboard() {
  const context = { window: {}, console };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(require.resolve('../app/static/app.js'), 'utf8'), context);
  return context.window.ideaDockApp();
}

test('item board listings ignore stale responses and clear when no item is selected', async () => {
  const app = dashboard(), pending = [];
  app.fetchJson = () => new Promise(resolve => pending.push(resolve));
  const first = app.loadItemBoards('1');
  const second = app.loadItemBoards('2');
  pending[1]([{ id: 20 }]); await second;
  pending[0]([{ id: 10 }]); await first;
  assert.equal(app.itemBoards[0].id, 20);
  await app.loadItemBoards('');
  assert.equal(app.itemBoards.length, 0);
  assert.equal(app.itemBoardsLoading, false);
});

test('failed item board listing reports failure instead of claiming the item is empty', async () => {
  const app = dashboard();
  app.fetchJson = async () => { throw new Error('Offline'); };
  await app.loadItemBoards('1');
  assert.equal(app.itemBoardsError, 'Offline');
  assert.equal(app.itemBoardsLoading, false);
  app.fetchJson = async () => [{ id: 10 }];
  await app.loadItemBoards('1');
  assert.equal(app.itemBoardsError, '');
  assert.equal(app.itemBoards.length, 1);
});


test('home board search ignores stale results and searches board names', async () => {
  const app = dashboard(), pending = [];
  app.fetchJson = url => new Promise(resolve => pending.push({ url, resolve }));
  app.boardQuery = 'First'; const first = app.searchBoards();
  app.boardQuery = 'Second & plan'; const second = app.searchBoards();
  assert.equal(pending[1].url, '/api/boards?q=Second%20%26%20plan');
  pending[1].resolve([{ id: 2, name: 'Second & plan', item_id: 4 }]); await second;
  pending[0].resolve([{ id: 1 }]); await first;
  assert.equal(app.boardResults[0].id, 2);
  assert.equal(app.boardSearchLoading, false);
  assert.equal(app.boardCreateUrl(4), '/static/boards.html?item=4&create=1');
  assert.equal(app.boardUrl(4, 2), '/static/boards.html?item=4&board=2');
});

test('home board search errors clear results and retry recovers', async () => {
  const app = dashboard();
  app.fetchJson = async () => { throw new Error('Offline'); };
  await app.searchBoards();
  assert.equal(app.boardSearchError, 'Offline');
  assert.equal(app.boardResults.length, 0);
  app.fetchJson = async () => [{ id: 1, name: 'Board' }];
  await app.searchBoards();
  assert.equal(app.boardSearchError, '');
  assert.equal(app.boardResults[0].name, 'Board');
});

function catalogWorkspace() {
  const state = workspace();
  delete state.app.loadCatalog;
  state.context.document.createElement = tag => ({ tag, textContent: '', value: '' });
  const select = state.node('board-results');
  select.children = [];
  select.replaceChildren = child => { select.children = [child]; select.firstChild = child; };
  select.append = child => select.children.push(child);
  return state;
}

test('workspace search labels duplicate boards with their owners and ignores stale results', async () => {
  const { app, node } = catalogWorkspace(), pending = [];
  app.api = url => new Promise(resolve => pending.push({ url, resolve }));
  node('board-search').value = 'Old'; const first = app.loadCatalog();
  node('board-search').value = 'Plan'; const second = app.loadCatalog();
  assert.equal(pending[1].url, '/api/boards?q=Plan');
  pending[1].resolve([{ id: 2, name: 'Plan', item_id: 3, item_title: 'Kitchen' }, { id: 4, name: 'Plan', item_id: 5, item_title: 'Garden' }]);
  await second; pending[0].resolve([]); await first;
  assert.equal(app.catalog.length, 2);
  assert.equal(node('board-results').children[1].textContent, 'Plan — Kitchen');
  assert.equal(node('board-results').children[2].value, 4);
  assert.equal(node('board-results').disabled, false);
});

test('workspace search reports errors, disables stale choices, and can retry', async () => {
  const { app, node } = catalogWorkspace();
  app.api = async () => { throw new Error('Offline'); };
  await app.loadCatalog();
  assert.equal(node('board-results').disabled, true);
  assert.equal(node('board-search-retry').hidden, false);
  app.api = async () => [];
  await app.loadCatalog();
  assert.equal(node('board-search-status').textContent, 'No matching visual boards.');
  assert.equal(node('board-search-retry').hidden, true);
});

test('cross-owner board selection commits owner and deck together after successful load', async () => {
  const { app } = workspace(), calls = [], board = { id: 9, item_id: 7, name: 'Destination' };
  app.canLeave = async () => true;
  app.renderList = () => {};
  app.accept = value => { app.board = value; };
  app.api = async path => {
    calls.push(path);
    if (path.endsWith('/boards/9')) return board;
    if (path.endsWith('/board-assets')) return [{ key: 'project:8' }];
    if (path.endsWith('/boards')) return [board];
    return { id: 7, title: 'Owner' };
  };
  await app.open(9, 7);
  assert.equal(app.itemId, '7');
  assert.equal(app.board.id, 9);
  assert.equal(app.assets[0].key, 'project:8');
  assert.ok(calls.every(path => path.startsWith('/api/items/7')));
});

test('cancelled or failed cross-owner selection preserves local board and owner', async () => {
  const { app } = workspace(), original = app.board;
  app.canLeave = async () => false;
  app.api = async () => assert.fail('Cancelled switch made a request');
  await app.open(9, 7);
  assert.equal(app.itemId, 1);
  app.canLeave = async () => true;
  app.api = async () => { throw new Error('Offline'); };
  await app.open(9, 7);
  assert.equal(app.itemId, 1);
  assert.equal(app.board, original);
  assert.equal(app.saveState.dirty, true);
  assert.equal(app.scheduled, 1);
});


test('empty editor board links do not invent an owner ID', () => {
  const app = dashboard();
  assert.equal(app.boardCreateUrl(null), '#');
  assert.equal(app.boardCreateUrl(undefined), '#');
  assert.equal(app.boardUrl(undefined, 2), '#');
  assert.equal(app.boardUrl(2, undefined), '#');
});


test('successful copy, latest, and replace recovery refresh the global board-name chooser', async () => {
  for (const choice of ['copy', 'latest', 'replace']) {
    const { app, node } = catalogWorkspace();
    app.saveState.conflict = true;
    node('conflict').open = true;
    node('comparison').hidden = false;
    app.latest = { revision: 2 };
    app.askName = async () => 'Recovered copy';
    app.renderList = () => {};
    app.accept = board => { app.board = board; };
    const saved = { ...app.board, id: choice === 'copy' ? 8 : 1, name: 'Recovered name', revision: 3 };
    const paths = [];
    app.api = async path => {
      paths.push(path);
      if (path.startsWith('/api/boards?')) return [{ ...saved, item_id: 1, item_title: 'Owner' }];
      if (path.endsWith('/board-assets')) return [];
      return saved;
    };
    await app.recover(choice);
    assert.equal(app.board.id, saved.id);
    assert.equal(app.catalog[0].name, 'Recovered name');
    assert.equal(node('board-results').children[1].textContent, 'Recovered name — Owner');
    assert.equal(node('board-results').value, saved.id);
    assert.equal(paths.filter(path => path.startsWith('/api/boards?')).length, 1);
  }
});


test('empty-canvas controls keep native mouse and touch clicks without pointer capture', () => {
  for (const pointerType of ['mouse', 'touch']) {
    const { app, node } = interactionWorkspace();
    app.board.objects = [];
    let captured = 0, prevented = 0;
    node('canvas').setPointerCapture = () => { captured++; };
    const edits = [];
    app.edit = type => edits.push(type);
    node('files').click = () => edits.push('upload');
    for (const [id, expected] of [['empty-text', 'text'], ['empty-swatch', 'swatch'], ['empty-upload', 'upload']]) {
      const target = { closest: selector => selector.includes('button:not(.resize)') ? {} : null };
      node('canvas').listeners.pointerdown({ pointerType, pointerId: 1, button: 0, target, preventDefault() { prevented++; } });
      node(id).listeners.click();
      assert.equal(edits.at(-1), expected);
    }
    assert.equal(captured, 0);
    assert.equal(prevented, 0);
    assert.equal(app.gesture, undefined);
    assert.equal(app.pointers.size, 0);
  }
});
