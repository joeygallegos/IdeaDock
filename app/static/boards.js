'use strict';

// This page owns only board presentation. Source uploads and item records stay
// on their existing API paths; placements carry asset keys, never file copies.
const C = window.BoardCore;
const $ = id => document.getElementById(id);
const el = (tag, text, className) => {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (className) n.className = className;
  return n;
};
const action = (text, fn, className) => {
  const n = el('button', text, className);
  n.type = 'button';
  n.addEventListener('click', fn);
  return n;
};
const uid = () => window.crypto?.randomUUID?.() || `o-${Date.now()}-${Math.random().toString(36).slice(2)}`;

class BoardWorkspace {
  constructor() {
    this.project = null;
    this.board = null;
    this.boards = [];
    this.assets = [];
    this.selected = new Set();
    this.asset = null;
    this.history = new C.History();
    this.saveState = null;
    this.saving = false;
    this.timer = null;
    this.tool = 'select';
    this.space = false;
    this.readOnly = matchMedia('(max-width: 899px)').matches;
    this.uploads = [];
    this.gesture = null;
    this.pointers = new Map();
    this.loadVersion = 0;
    this.bind();
    this.mode();
    this.start();
  }

  async api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        ...(options.body && !(options.body instanceof FormData)
          ? { 'Content-Type': 'application/json' }
          : {}),
        ...options.headers
      }
    });
    const data = response.status === 204 ? null : await response.json();
    if (!response.ok) {
      const error = new Error(typeof data?.detail === 'string' ? data.detail : data?.detail?.message || 'The request could not be completed.');
      error.status = response.status;
      error.detail = data?.detail;
      throw error;
    }
    return data;
  }

  path(suffix = '') {
    return `/api/projects/${this.project}${suffix}`;
  }

  notice(text) {
    $('message').textContent = text;
    $('message').hidden = !text;
  }

  askName(title, initial = '') {
    $('name-title').textContent = title;
    $('name-value').value = initial;
    $('name-dialog').showModal();
    $('name-value').focus();
    $('name-value').select();
    return new Promise(resolve => {
      const finish = value => {
        $('name-form').onsubmit = null;
        $('name-cancel').onclick = null;
        $('name-dialog').oncancel = null;
        $('name-dialog').close();
        resolve(value);
      };
      $('name-form').onsubmit = event => {
        event.preventDefault();
        const value = $('name-value').value.trim();
        if (value) finish(value);
      };
      $('name-cancel').onclick = () => finish(null);
      $('name-dialog').oncancel = event => {
        event.preventDefault();
        finish(null);
      };
    });
  }

  askConfirm(message, label = 'Continue') {
    $('confirm-message').textContent = message;
    $('confirm-proceed').textContent = label;
    $('confirm-dialog').showModal();
    $('confirm-cancel').focus();
    return new Promise(resolve => {
      const finish = confirmed => {
        $('confirm-cancel').onclick = null;
        $('confirm-proceed').onclick = null;
        $('confirm-dialog').oncancel = null;
        $('confirm-dialog').close();
        resolve(confirmed);
      };
      $('confirm-cancel').onclick = () => finish(false);
      $('confirm-proceed').onclick = () => finish(true);
      $('confirm-dialog').oncancel = event => {
        event.preventDefault();
        finish(false);
      };
    });
  }

  editable() {
    return !!this.board && !this.readOnly;
  }

  payload(board = this.board) {
    return {
      name: board.name, objects: C.clone(board.objects), view: C.clone(board.view)
    };
  }

  async start() {
    try {
      const projects = await this.api('/api/epics');
      projects.forEach(p => {
        const o = el('option', p.name);
        o.value = p.id;
        $('projects').append(o);
      });
      if (!projects.length) {
        this.notice('Create a project in IdeaDock before adding visual boards.');
        $('new-board').disabled = true;
        return;
      }
      const params = new URLSearchParams(location.search), requested = params.get('project');
      // Unscoped navigation must not silently choose a different project.
      this.project = projects.some(p => String(p.id) === requested) ? requested : '';
      $('projects').value = this.project;
      const loaded = await this.loadProject();
      if (!loaded) return;
      if (params.get('create') === '1') await this.create();
      else if (params.get('board')) await this.open(params.get('board'));
    } catch {
      this.notice('Could not load projects. Reload this page to retry.');
    }
  }

  async loadProject() {
    const version = ++this.loadVersion, path = this.path();
    this.board = null;
    this.saveState = null;
    this.selected.clear();
    this.asset = null;
    this.uploads = [];
    $('workspace').hidden = true;
    $('list').hidden = false;
    this.boards = [];
    this.assets = [];
    this.renderList();
    $('new-board').disabled = !this.project || this.readOnly;
    $('project-back').href = this.project ? `/?project=${this.project}` : '/';
    if (!this.project) {
      this.status('');
      this.notice('Choose a project before creating or opening a board.');
      return;
    }
    this.status('Loading…');
    try {
      const [boards, assets] = await Promise.all([this.api(`${path}/boards`), this.api(`${path}/assets`)]);
      if (version !== this.loadVersion) return;
      this.boards = boards;
      this.assets = assets;
      this.renderList();
      this.status('');
      if (!this.readOnly) this.notice('');
      history.replaceState(null, '', `?project=${this.project}`);
      return true;
    } catch (error) {
      this.status('Could not load boards');
      this.notice(error.message + ' Reload to retry.');
    }
  }

  status(text) {
    $('status').textContent = text;
    $('retry').hidden = !(text.startsWith("Couldn't save"));
    $('recovery').hidden = !this.saveState?.conflict;
  }

  async canLeave() {
    return !(this.saveState?.dirty || this.uploads.some(u => u.state === 'uploading'))
      || await this.askConfirm(
        'Unsaved changes or uploads are still here. Leave this board anyway?',
        'Leave board'
      );
  }

  renderList() {
    $('boards').replaceChildren();
    $('switcher').replaceChildren();
    if (!this.boards.length && this.project) $('boards').append(el('p', 'No boards created for this project. Choose Create board, then upload images inside it.'));
    this.boards.forEach(board => {
      const option = el('option', board.name);
      option.value = board.id;
      $('switcher').append(option);
      const card = el('article', undefined, 'board-card');
      const open = action('', () => this.open(board.id), 'board-open');
      open.setAttribute('aria-label', `Open ${board.name}`);
      const preview = el('div', undefined, 'board-preview');
      for (const o of board.objects.slice(-3)) {
        if (o.type === 'image') {
          const a = board.assets.find(a => a.key === o.asset_key);
          if (a) {
            const img = el('img');
            img.src = a.file_url;
            img.alt = '';
            preview.append(img);
          }
        } else {
          const sample = el('span', o.type === 'text' ? o.text : o.color);
          if (o.type === 'swatch') {
            sample.style.backgroundColor = o.color;
            sample.style.padding = '24px';
          }
          preview.append(sample);
        }
      }
      open.append(preview, el('h2', board.name), el('p', `${board.objects.length} objects · ${new Date(board.updated_at).toLocaleDateString()}`));
      card.append(open);
      const menu = el('details', undefined, 'board-menu edit'), summary = el('summary', '•••');
      summary.setAttribute('aria-label', `Manage ${board.name}`);
      summary.dataset.tip = `Manage ${board.name}`;
      const choices = el('div', undefined, 'popover');
      for (const verb of ['Rename', 'Duplicate', 'Delete']) choices.append(action(verb, () => {
        menu.open = false;
        this.manage(board, verb);
      }));
      menu.append(summary, choices);
      card.append(menu);
      $('boards').append(card);
    });
  }

  async manage(board, verb) {
    if (this.readOnly) return;
    try {
      if (verb === 'Delete') {
        if (!(await this.askConfirm(`Delete “${board.name}”? Source images will be kept.`, 'Delete board')) || this.readOnly) return;
        await this.api(this.path(`/boards/${board.id}?revision=${board.revision}`), {
          method: 'DELETE'
        });
      } else {
        const name = await this.askName(verb === 'Rename' ? 'Board name' : 'Name for the board copy', verb === 'Rename' ? board.name : `${board.name} copy`);
        if (!name?.trim() || this.readOnly) return;
        const payload = {
          ...this.payload(board), name: name.trim()
        };
        if (verb === 'Rename') payload.revision = board.revision;
        await this.api(this.path(`/boards/${board.id}${verb === 'Duplicate' ? '/copy' : ''}`), {
          method: verb === 'Duplicate' ? 'POST' : 'PUT', body: JSON.stringify(payload)
        });
      }
      await this.loadProject();
    } catch (error) {
      this.notice(error.status === 409 ? 'This board changed elsewhere. Reload the list before managing it; no changes were overwritten.' : error.message);
    }
  }

  async create() {
    if (this.readOnly || !this.project || !(await this.canLeave())) return;
    const name = await this.askName('Name your visual board');
    if (!name?.trim() || this.readOnly) return;
    try {
      const board = await this.api(this.path('/boards'), {
        method: 'POST', body: JSON.stringify({
          name: name.trim()
        })
      });
      this.boards.push(board);
      this.renderList();
      this.accept(board);
    }
    catch (error) {
      this.notice(error.message);
    }
  }

  async open(id) {
    if (!(await this.canLeave())) {
      $('switcher').value = this.board?.id;
      return;
    }
    clearTimeout(this.timer);
    const version = ++this.loadVersion;
    try {
      const [board, assets] = await Promise.all([this.api(this.path(`/boards/${id}`)), this.api(this.path('/assets'))]);
      if (version === this.loadVersion) {
        this.assets = assets;
        this.accept(board);
      }
    }
    catch (error) {
      this.notice(error.message);
    }
  }

  accept(board) {
    this.board = board;
    this.saveState = new C.SaveState(board.revision);
    this.history = new C.History();
    this.selected.clear();
    this.latest = null;
    this.tool = 'select';
    this.sampling = false;
    this.space = false;
    this.gesture = null;
    $('list').hidden = true;
    $('workspace').hidden = false;
    $('switcher').value = board.id;
    this.status('Saved');
    this.renderDeck();
    this.render();
    this.tools();
    if (this.readOnly) {
      this.editView = C.clone(board.view);
      this.fit(false);
    }
  }

  mode() {
    const viewOnlyNotice = 'View only. Use a larger screen to edit. Pan and zoom to inspect this board.';
    document.body.classList.toggle('view-only', this.readOnly);
    $('view-only').hidden = !this.readOnly;
    $('new-board').disabled = !this.project || this.readOnly;
    if (this.readOnly) {
      // Browsing uses a temporary camera. Shrinking the window must not save
      // a fit/pan/zoom operation over the last editable canvas view.
      if (this.board) this.editView = C.clone(this.board.view);
      if (this.gesture?.objects) this.board.objects = this.gesture.objects;
      if ($('name-dialog').open) $('name-cancel').click();
      if ($('confirm-dialog').open) $('confirm-cancel').click();
      this.sampling = false;
      this.gesture = null;
      $('deck').hidden = true;
      $('editor').close();
      this.notice(viewOnlyNotice);
      if (this.board) this.fit(false);
    } else if (this.board && this.editView) {
      this.board.view = this.editView;
      this.editView = null;
      this.view();
      if (this.saveState?.dirty) this.schedule();
    }
    if (!this.readOnly && $('message').textContent === viewOnlyNotice) this.notice('');
    $('deck-toggle').setAttribute('aria-expanded', String(!$('deck').hidden));
    $('canvas').setAttribute('aria-label', this.readOnly
      ? 'Canvas. View only. Drag to pan; use zoom controls to inspect.'
      : 'Canvas. Arrow keys move selected objects; Space-drag pans.');
    this.tools();
  }

  mark() {
    this.saveState.edit();
    this.status('Unsaved changes');
    this.schedule();
  }

  schedule() {
    clearTimeout(this.timer);
    if (!this.saveState.conflict) this.timer = setTimeout(() => this.save(), 650);
    else this.status('Changed in another tab — local edits retained');
  }

  change(fn) {
    if (!this.editable()) return;
    this.history.push(this.board.objects);
    fn();
    this.mark();
    this.render();
  }

  async save() {
    if (!this.board || this.readOnly || !this.saveState?.dirty || this.saveState.conflict || this.saving) return;
    // Capture identity and generation: late responses from a previous board
    // must never overwrite the current workspace or acknowledge newer edits.
    const board = this.board, state = this.saveState, generation = state.generation;
    this.saving = true;
    this.status('Saving…');
    try {
      const saved = await this.api(this.path(`/boards/${board.id}`), {
        method: 'PUT', body: JSON.stringify({
          ...this.payload(board), revision: state.revision
        })
      });
      if (this.board !== board) return;
      state.acknowledge(generation, saved.revision);
      board.revision = saved.revision;
      const index = this.boards.findIndex(b => b.id === board.id);
      if (index >= 0) this.boards[index] = saved;
      this.status(state.dirty ? 'Unsaved changes' : 'Saved');
    } catch (error) {
      if (this.board !== board) return;
      if (error.status === 409) {
        state.conflict = true;
        this.latest = error.detail.latest;
        this.status('Changed in another tab — local edits retained');
        this.showRecovery();
      } else this.status("Couldn't save — your changes are still here");
    } finally {
      this.saving = false;
      // A different board may have become dirty while this request held the
      // single save slot; its expired timer must not strand those edits.
      if (this.saveState?.dirty && !this.saveState.conflict && (this.board !== board || $('status').textContent === 'Unsaved changes')) this.schedule();
    }
  }

  showRecovery() {
    if (!this.saveState?.conflict) return;
    $('comparison').hidden = true;
    $('replace').hidden = true;
    $('recovery-error').textContent = '';
    if (!$('conflict').open) $('conflict').showModal();
    $('keep-copy').focus();
  }

  async recover(choice) {
    if (!this.saveState?.conflict || (this.readOnly && !['latest', 'compare'].includes(choice))) return;
    const local = this.board, generation = this.saveState.generation, wasOpen = $('conflict').open;
    // A recovery request may finish after its dialog was dismissed. Preserve
    // the workspace if the user has resumed editing or left that recovery UI.
    const stillCurrent = () => this.board === local && this.saveState.generation === generation && (!wasOpen || $('conflict').open);
    try {
      if (choice === 'copy') {
        const name = await this.askName('Name for your local board copy', `${local.name} copy`);
        if (!name?.trim() || this.readOnly) return;
        const copied = await this.api(this.path(`/boards/${local.id}/copy`), {
          method: 'POST', body: JSON.stringify({
            ...this.payload(), name: name.trim()
          })
        });
        if (!stillCurrent()) {
          this.notice('Your copy was saved. Local edits remain here; reopen recovery when ready.');
          return;
        }
        this.boards.push(copied);
        this.renderList();
        $('conflict').close();
        this.accept(copied);
      } else if (choice === 'latest') {
        if (!(await this.askConfirm('Open the latest saved board? Your current local edits will be left behind.', 'Open latest'))) return;
        // Refresh the reusable library with the recovered composition. Commit
        // neither result until both reads succeed and recovery is still active.
        const [latest, assets] = await Promise.all([
          this.api(this.path(`/boards/${local.id}`)),
          this.api(this.path('/assets'))
        ]);
        if (!stillCurrent()) return;
        this.assets = assets;
        this.boards = this.boards.map(board => board.id === latest.id ? latest : board);
        this.renderList();
        $('conflict').close();
        this.accept(latest);
      } else if (choice === 'compare') {
        this.latest = await this.api(this.path(`/boards/${local.id}`));
        $('comparison').replaceChildren(
          this.comparison(local, 'Your local version'),
          this.comparison(this.latest, `Latest saved · revision ${this.latest.revision}`)
        );
        $('comparison').hidden = false;
        $('replace').hidden = this.readOnly;
      } else if (choice === 'replace' && !$('comparison').hidden) {
        if (!(await this.askConfirm(
          `Replace saved revision ${this.latest.revision} of “${this.latest.name}” with your local version?`,
          'Replace latest'
        )) || this.readOnly) return;
        const saved = await this.api(this.path(`/boards/${local.id}`), {
          method: 'PUT', body: JSON.stringify({
            ...this.payload(), revision: this.latest.revision
          })
        });
        if (!stillCurrent()) {
          this.notice('The confirmed version was saved. Your current local edits remain here. Compare again before replacing.');
          return;
        }
        $('conflict').close();
        this.accept(saved);
      }
    } catch (error) {
      // Failed recovery retains the entire local board and conflict pause. A
      // further concurrent edit requires a fresh comparison before replacement.
      $('recovery-error').textContent = `${error.message} Your local edits are still here. Try again.`;
      if (error.status === 409) {
        this.latest = error.detail.latest;
        $('replace').hidden = true;
        $('comparison').hidden = true;
      }
    }
  }

  comparison(board, title) {
    const section = el('section');
    section.append(el('h3', title), el('p', board.name));
    const preview = el('div', undefined, 'compare-preview'), view = C.fit(board.objects, 250, 160);
    board.objects.forEach(o => {
      const n = this.objectNode(o, board.assets, false);
      n.style.transformOrigin = '0 0';
      n.style.left = `${o.x * view.zoom + view.x}px`;
      n.style.top = `${o.y * view.zoom + view.y}px`;
      n.style.transform = `scale(${view.zoom})`;
      n.removeAttribute('tabindex');
      preview.append(n);
    });
    section.append(preview, el('p', `${board.objects.length} objects · view ${Math.round(board.view.zoom * 100)}%`));
    const details = el('details'), summary = el('summary', 'Inspect object positions and content');
    details.append(summary);
    board.objects.forEach(o => details.append(el(
      'p',
      `${o.type}: ${o.text || o.color || o.asset_key} · x ${o.x.toFixed(1)}, y ${o.y.toFixed(1)} · ${o.width.toFixed(1)} × ${o.height.toFixed(1)}`
    )));
    section.append(details);
    return section;
  }

  renderDeck() {
    const focusedAsset = document.activeElement?.closest('[data-asset-key]')?.dataset.assetKey;
    const scroll = $('deck').scrollTop, query = $('search').value.toLowerCase();
    $('asset-grid').replaceChildren();
    this.assets.filter(a => `${a.original_filename} ${a.caption || ''} ${a.source_name}`.toLowerCase().includes(query)).forEach(a => {
      const button = action('', () => {
        this.asset = a;
        this.renderDeck();
      });
      button.setAttribute('aria-pressed', String(a.key === this.asset?.key));
      button.dataset.assetKey = a.key;
      const img = el('img');
      img.src = a.file_url;
      img.alt = a.caption || a.original_filename;
      button.append(img, el('span', a.source_name));
      button.draggable = !this.readOnly;
      button.addEventListener('dragstart', event => {
        if (this.readOnly) {
          event.preventDefault();
          return;
        }
        event.dataTransfer.setData('application/x-ideadock-asset', a.key);
      });
      $('asset-grid').append(button);
    });
    if (!this.assets.length) $('asset-grid').append(el('p', 'No project images yet. Upload an image, drop one on the canvas, or paste from your clipboard.'));
    $('asset-preview').replaceChildren();
    if (this.asset) {
      const img = el('img');
      img.src = this.asset.file_url;
      img.alt = this.asset.caption || this.asset.original_filename;
      $('asset-preview').append(
        img,
        el('p', this.asset.caption || this.asset.original_filename),
        el('p', this.asset.source_name),
        action('Add to board', () => this.place(this.asset), 'primary edit')
      );
    }
    if (focusedAsset) [...$('asset-grid').children].find(n => n.dataset.assetKey === focusedAsset)?.focus({
      preventScroll: true
    });
    $('deck').scrollTop = scroll;
  }

  center() {
    const r = $('canvas').getBoundingClientRect();
    return C.point(r.width / 2, r.height / 2, this.board.view);
  }

  async place(asset, position = null) {
    if (!this.editable()) return;
    const board = this.board, p = position || this.center();
    const img = new Image();
    try {
      img.src = asset.file_url;
      await img.decode();
    } catch {
      /* Missing images keep a useful placement and can recover on reload. */
    }
    if (!this.editable() || this.board !== board) return;
    const ratio = img.naturalWidth && img.naturalHeight ? img.naturalHeight / img.naturalWidth : .75;
    const width = Math.min(280, 400 / ratio), height = width * ratio;
    const object = {
      id: uid(), type: 'image', asset_key: asset.key, x: p.x - width / 2, y: p.y - height / 2, width, height
    };
    if (!board.assets.some(a => a.key === asset.key)) board.assets.push(asset);
    this.change(() => {
      board.objects.push(object);
      this.selected = new Set([object.id]);
    });
  }

  objectNode(o, assets = this.board.assets, interactive = true) {
    const n = el('div', undefined, `object ${o.type}${this.selected.has(o.id) && interactive ? ' selected' : ''}`);
    n.dataset.id = o.id;
    Object.assign(n.style, {
      left: `${o.x}px`, top: `${o.y}px`, width: `${o.width}px`, height: `${o.height}px`
    });
    if (interactive) {
      n.tabIndex = 0;
      n.setAttribute('role', 'button');
      n.setAttribute('aria-pressed', String(this.selected.has(o.id)));
      n.setAttribute('aria-label', `${o.type}: ${o.text || o.color || assets.find(a => a.key === o.asset_key)?.original_filename || 'Missing image'}`);
    }
    if (o.type === 'image') {
      const asset = assets.find(a => a.key === o.asset_key), img = el('img');
      img.alt = asset?.caption || asset?.original_filename || 'Missing source image';
      const missing = () => {
        img.remove();
        n.prepend(el('span', 'Image unavailable — placement preserved', 'missing'));
      };
      img.addEventListener('error', missing);
      if (asset) {
        img.src = asset.file_url;
        n.append(img);
      } else missing();
    } else if (o.type === 'text') n.textContent = o.text;
    else {
      n.style.backgroundColor = o.color;
      n.title = o.color;
    }
    return n;
  }

  render() {
    if (!this.board) return;
    const activeId = document.activeElement?.closest('.object')?.dataset.id, handleActive = document.activeElement?.classList.contains('resize');
    $('world').replaceChildren();
    this.board.objects.forEach(o => {
      const n = this.objectNode(o);
      if (!this.readOnly && this.selected.size === 1 && this.selected.has(o.id)) {
        const handle = action('↘', () => {}, 'resize');
        handle.setAttribute('aria-label', 'Resize proportionally with arrow keys or drag');
        handle.dataset.tip = 'Resize proportionally (Arrow keys; Shift for 10)';
        // Handles are compensated for zoom so their hit area remains 44 CSS px.
        handle.style.transform = `scale(${1 / this.board.view.zoom})`;
        n.append(handle);
      }
      $('world').append(n);
    });
    if (this.selected.size > 1) {
      const b = C.bounds(this.board.objects.filter(o => this.selected.has(o.id)));
      if (b) {
        const boundary = el('div', undefined, 'group-boundary');
        Object.assign(boundary.style, {
          left: `${b.x - 4}px`, top: `${b.y - 4}px`, width: `${b.right - b.x + 8}px`, height: `${b.bottom - b.y + 8}px`
        });
        $('world').append(boundary);
      }
      if (!this.hintDismissed) $('hint').hidden = false;
    }
    this.view();
    $('empty').hidden = !!this.board.objects.length;
    $('selection-tools').hidden = !this.selected.size;
    $('selection-count').textContent = `${this.selected.size} selected`;
    $('edit-object').disabled = this.selected.size !== 1 || this.board.objects.find(o => this.selected.has(o.id))?.type === 'image';
    $('undo').disabled = !this.history.past.length;
    $('redo').disabled = !this.history.future.length;
    this.renderDetails();
    if (activeId) {
      const n = [...$('world').children].find(n => n.dataset.id === activeId);
      (handleActive ? n?.querySelector('.resize') : n)?.focus({
        preventScroll: true
      });
    }
  }

  renderDetails() {
    $('object-list').replaceChildren();
    if (!this.board) return;
    this.board.objects.forEach(o => {
      const asset = this.board.assets.find(a => a.key === o.asset_key);
      const b = action(`${o.type}: ${o.text || o.color || asset?.original_filename || 'Unavailable image'}`, () => {
        this.selected = new Set([o.id]);
        this.render();
      });
      b.setAttribute('aria-pressed', String(this.selected.has(o.id)));
      $('object-list').append(b);
      if (this.selected.has(o.id)) {
        $('object-list').append(el(
          'p',
          `${Math.round(o.width)} × ${Math.round(o.height)} · ${asset?.source_name || 'Board object'}`
        ));
      }
    });
  }

  view() {
    if (!this.board) return;
    const v = this.board.view;
    $('world').style.transform = `translate(${v.x}px, ${v.y}px) scale(${v.zoom})`;
    $('zoom').textContent = `${Math.round(v.zoom * 100)}%`;
    $('world').querySelectorAll('.resize').forEach(h => h.style.transform = `scale(${1 / v.zoom})`);
  }

  tools() {
    $('select').setAttribute('aria-pressed', String(this.tool === 'select'));
    $('hand').setAttribute('aria-pressed', String(this.tool === 'hand'));
    $('canvas').classList.toggle('hand', this.readOnly || this.space || this.tool === 'hand');
    $('sampling').hidden = !this.sampling;
  }

  fit(save = true) {
    if (!this.board) return;
    const r = $('canvas').getBoundingClientRect();
    this.board.view = C.fit(this.board.objects, r.width, r.height);
    this.view();
    if (save && !this.readOnly) this.mark();
  }

  zoom(factor, x, y) {
    if (!this.board) return;
    const r = $('canvas').getBoundingClientRect();
    this.board.view = C.zoomAt(this.board.view, factor, x ?? r.width / 2, y ?? r.height / 2);
    this.view();
    if (!this.readOnly) this.mark();
  }

  select(id, shift) {
    if (shift) {
      this.selected.has(id) ? this.selected.delete(id) : this.selected.add(id);
    } else this.selected = new Set([id]);
    this.render();
  }

  remove() {
    this.change(() => {
      this.board.objects = this.board.objects.filter(o => !this.selected.has(o.id));
      this.selected.clear();
    });
  }

  duplicate() {
    this.change(() => {
      const copies = this.board.objects.filter(o => this.selected.has(o.id)).map(o => ({
        ...C.clone(o), id: uid(), x: o.x + 24, y: o.y + 24
      }));
      this.board.objects.push(...copies);
      this.selected = new Set(copies.map(o => o.id));
    });
  }

  layer(front) {
    this.change(() => {
      const yes = this.board.objects.filter(o => this.selected.has(o.id)), no = this.board.objects.filter(o => !this.selected.has(o.id));
      this.board.objects = front ? [...no, ...yes] : [...yes, ...no];
    });
  }

  undo(redo = false) {
    if (!this.editable()) return;
    this.board.objects = redo ? this.history.redo(this.board.objects) : this.history.undo(this.board.objects);
    this.selected.clear();
    this.mark();
    this.render();
  }

  edit(type) {
    if (!this.editable()) return;
    this.editing = type ? null : this.board.objects.find(o => this.selected.has(o.id));
    this.editType = type || this.editing?.type;
    if (!['text', 'swatch'].includes(this.editType)) return;
    $('canvas-shell').querySelectorAll('details').forEach(menu => {
      menu.open = false;
    });
    $('editor-title').textContent = this.editType === 'text' ? 'Text label' : 'Color swatch';
    $('text-field').hidden = this.editType !== 'text';
    $('color-field').hidden = this.editType !== 'swatch';
    $('text-value').value = this.editing?.text || '';
    $('hex-value').value = this.editing?.color || '#635BFF';
    $('color-value').value = $('hex-value').value;
    $('color-error').textContent = '';
    $('editor').showModal();
    (this.editType === 'text' ? $('text-value') : $('hex-value')).focus();
  }

  commitEditor() {
    if (!this.editable()) return;
    const color = C.hex($('hex-value').value.trim());
    if (this.editType === 'swatch' && !color) {
      $('color-error').textContent = 'Enter a valid six-digit hex color, such as #635BFF. Previous color kept.';
      return;
    }
    const p = this.center(), object = this.editing || {
      id: uid(), type: this.editType, x: p.x - 100, y: p.y - 50, width: this.editType === 'text' ? 280 : 140, height: this.editType === 'text' ? 100 : 140
    };
    this.change(() => {
      if (this.editType === 'text') object.text = $('text-value').value;
      else object.color = color;
      if (!this.editing) this.board.objects.push(object);
      this.selected = new Set([object.id]);
    });
    $('editor').close();
  }

  sample(event, node) {
    if (!this.editable()) return;
    const image = node?.querySelector('img');
    if (!image?.naturalWidth) {
      this.notice('Choose a loaded image to sample a color.');
      return;
    }
    try {
      const r = image.getBoundingClientRect(), canvas = document.createElement('canvas');
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(image, 0, 0);
      const pixel = ctx.getImageData(
        Math.min(canvas.width - 1, Math.max(0, Math.floor((event.clientX - r.left) / r.width * canvas.width))),
        Math.min(canvas.height - 1, Math.max(0, Math.floor((event.clientY - r.top) / r.height * canvas.height))),
        1,
        1
      ).data;
      const color = '#' + [...pixel].slice(0, 3).map(n => n.toString(16).padStart(2, '0')).join('').toUpperCase();
      const p = this.center();
      this.change(() => this.board.objects.push({
        id: uid(), type: 'swatch', color, x: p.x, y: p.y, width: 140, height: 140
      }));
      this.sampling = false;
      this.tools();
    }
    catch {
      this.notice('Could not sample this image. You can enter a color manually.');
    }
  }

  pointerDown(event) {
    if (!this.board) return;
    if (event.pointerType === 'touch') {
      this.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
      // Keep two-finger navigation available on iPads in both responsive
      // modes. Their CSS viewport can exceed the small-screen breakpoint, but
      // pinch and two-finger pan remain navigation rather than board edits.
      if (this.pointers.size >= 2) {
        if (this.gesture?.objects) this.board.objects = this.gesture.objects;
        const points = [...this.pointers.values()].slice(0, 2);
        this.gesture = {
          kind: 'touch-navigation',
          midpoint: this.midpoint(points[0], points[1]),
          distance: this.distance(points[0], points[1]),
          view: C.clone(this.board.view)
        };
        event.preventDefault();
        return;
      }
      // On touch screens the first finger pans in browse mode. A second finger
      // upgrades that gesture to pinch navigation without ever editing objects.
      if (this.readOnly && this.pointers.size === 1) {
        this.gesture = {
          kind: 'pan',
          start: { x: event.clientX - $('canvas').getBoundingClientRect().left, y: event.clientY - $('canvas').getBoundingClientRect().top },
          view: C.clone(this.board.view)
        };
        event.preventDefault();
        return;
      }
      if (this.gesture?.kind === 'touch-navigation') this.gesture = null;
      if (this.readOnly) return;
    }
    if (![0, 1].includes(event.button)) return;
    const node = event.target.closest('.object'), r = $('canvas').getBoundingClientRect(), start = {
      x: event.clientX - r.left, y: event.clientY - r.top
    };
    if (this.sampling && !this.readOnly) {
      this.sample(event, node);
      return;
    }
    const pan = this.readOnly || event.button === 1 || this.space || this.tool === 'hand';
    if (pan) this.gesture = {
      kind: 'pan', start, view: C.clone(this.board.view)
    };
    else if (node) {
      const id = node.dataset.id;
      if (event.shiftKey) {
        this.select(id, true);
        return;
      }
      if (!this.selected.has(id)) this.select(id, false);
      this.gesture = {
        kind: event.target.closest('.resize') ? 'resize' : 'move', id, start, objects: C.clone(this.board.objects)
      };
    } else {
      this.gesture = {
        kind: 'marquee', start, previous: event.shiftKey ? [...this.selected] : []
      };
      if (!event.shiftKey) {
        this.selected.clear();
        this.render();
      }
    }
    event.preventDefault();
    $('canvas').setPointerCapture(event.pointerId);
    $('canvas').focus({
      preventScroll: true
    });
  }

  pointerMove(event) {
    const g = this.gesture;
    if (!g || !this.board) return;
    if (event.pointerType === 'touch' && this.pointers.has(event.pointerId)) {
      this.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (g.kind === 'touch-navigation' && this.pointers.size >= 2) {
        const points = [...this.pointers.values()].slice(0, 2), r = $('canvas').getBoundingClientRect();
        const midpoint = this.midpoint(points[0], points[1]);
        const localMidpoint = { x: midpoint.x - r.left, y: midpoint.y - r.top };
        const startMidpoint = { x: g.midpoint.x - r.left, y: g.midpoint.y - r.top };
        const scale = Math.max(.05, Math.min(5, g.view.zoom * this.distance(points[0], points[1]) / g.distance)) / g.view.zoom;
        const anchored = C.zoomAt(g.view, scale, startMidpoint.x, startMidpoint.y);
        this.board.view = {
          ...anchored,
          x: anchored.x + localMidpoint.x - startMidpoint.x,
          y: anchored.y + localMidpoint.y - startMidpoint.y
        };
        this.view();
        return;
      }
      if (g.kind === 'pan' && this.readOnly && this.pointers.size === 1) {
        const r = $('canvas').getBoundingClientRect();
        this.board.view = {
          ...g.view,
          x: g.view.x + event.clientX - r.left - g.start.x,
          y: g.view.y + event.clientY - r.top - g.start.y
        };
        this.view();
        return;
      }
    }
    const r = $('canvas').getBoundingClientRect(), now = {
      x: event.clientX - r.left, y: event.clientY - r.top
    }, dx = now.x - g.start.x, dy = now.y - g.start.y;
    g.moved = g.moved || Math.abs(dx) + Math.abs(dy) > 2;
    if (!g.moved) return;
    if (g.kind === 'pan') {
      this.board.view = {
        ...g.view, x: g.view.x + dx, y: g.view.y + dy
      };
      this.view();
    } else if (!this.editable()) return;
    else if (g.kind === 'marquee') {
      Object.assign($('marquee').style, {
        left: `${Math.min(g.start.x, now.x)}px`, top: `${Math.min(g.start.y, now.y)}px`, width: `${Math.abs(dx)}px`, height: `${Math.abs(dy)}px`
      });
      $('marquee').hidden = false;
      this.selected = new Set(C.marquee(
        this.board.objects,
        C.point(g.start.x, g.start.y, this.board.view),
        C.point(now.x, now.y, this.board.view),
        g.previous
      ));
      this.render();
    } else {
      this.board.objects = g.objects.map(o =>
        g.kind === 'resize' && o.id === g.id
          ? C.resize(o, dx / this.board.view.zoom)
          : g.kind === 'move' && this.selected.has(o.id)
            ? {
              ...o,
              x: o.x + dx / this.board.view.zoom,
              y: o.y + dy / this.board.view.zoom
            }
            : o
      );
      this.render();
    }
  }

  midpoint(a, b) {
    return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  }

  distance(a, b) {
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  pointerUp(event) {
    if (event?.pointerType === 'touch') {
      if (event.type === 'pointercancel') {
        this.pointers.clear();
        this.gesture = null;
        $('marquee').hidden = true;
        return;
      }
      this.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (this.gesture?.kind === 'touch-navigation' && this.pointers.size >= 2) {
        const points = [...this.pointers.values()].slice(0, 2), r = $('canvas').getBoundingClientRect();
        const midpoint = this.midpoint(points[0], points[1]);
        const localMidpoint = { x: midpoint.x - r.left, y: midpoint.y - r.top };
        const startMidpoint = { x: this.gesture.midpoint.x - r.left, y: this.gesture.midpoint.y - r.top };
        const end = this.gesture;
        const pinchZoom = Math.max(.05, Math.min(5, end.view.zoom * this.distance(points[0], points[1]) / end.distance));
        const view = C.zoomAt(end.view, pinchZoom / end.view.zoom, startMidpoint.x, startMidpoint.y);
        this.board.view = {
          ...view,
          x: view.x + localMidpoint.x - startMidpoint.x,
          y: view.y + localMidpoint.y - startMidpoint.y
        };
        this.view();
      }
      this.pointers.delete(event.pointerId);
      if (this.gesture?.kind === 'touch-navigation') {
        if (this.readOnly && this.pointers.size === 1) {
          const [pointer] = this.pointers.values();
          const r = $('canvas').getBoundingClientRect();
          this.gesture = {
            kind: 'pan', start: { x: pointer.x - r.left, y: pointer.y - r.top },
            view: C.clone(this.board.view)
          };
        } else this.gesture = null;
        $('marquee').hidden = true;
        return;
      }
    }
    const g = this.gesture;
    if (!g) return;
    this.gesture = null;
    $('marquee').hidden = true;
    if (g.moved && !this.readOnly && g.kind !== 'marquee') {
      if (g.objects) this.history.push(g.objects);
      this.mark();
      this.render();
    }
  }

  key(event) {
    if (event.key === 'Escape') {
      this.sampling = false;
      this.space = false;
      this.tools();
      return;
    }
    if (C.typing(event.target) || $('conflict').open || $('editor').open || $('confirm-dialog').open || $('name-dialog').open || !this.board) return;
    if (event.code === 'Space' && (
      event.target === $('canvas')
      || event.target === document.body
      || (event.target.closest('.object') && !event.target.closest('.resize'))
    )) {
      event.preventDefault();
      this.space = true;
      this.tools();
      return;
    }
    const object = event.target.closest('.object');
    if ((event.key === 'Enter' || event.key === ' ') && object && !event.target.closest('.resize')) {
      event.preventDefault();
      this.select(object.dataset.id, event.shiftKey);
      return;
    }
    if (!this.editable()) return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
      event.preventDefault();
      this.undo(event.shiftKey);
      return;
    }
    if (!this.selected.size) return;
    if (event.key === 'Delete' || event.key === 'Backspace') {
      event.preventDefault();
      this.remove();
    }
    if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
      event.preventDefault();
      const step = event.shiftKey ? 10 : 1, delta = ['ArrowLeft', 'ArrowUp'].includes(event.key) ? -step : step;
      this.change(() => {
        this.board.objects = this.board.objects.map(o => !this.selected.has(o.id) ? o : event.target.closest('.resize') ? C.resize(o, delta) : {
          ...o,
          x: o.x + (event.key.includes('Left') || event.key.includes('Right') ? delta : 0),
          y: o.y + (event.key.includes('Up') || event.key.includes('Down') ? delta : 0)
        });
      });
    }
  }

  async upload(files, position = null) {
    if (!this.editable()) return;
    const board = this.board, project = this.project;
    for (const file of files) {
      if (!this.editable() || this.board !== board) break;
      const record = {
        file, position, name: file.name, state: 'uploading', progress: 0, project, board
      };
      this.uploads.push(record);
      this.renderUploads();
      await this.uploadOne(record);
    }
  }

  async uploadOne(record) {
    if (!this.editable() || this.board !== record.board || this.project !== record.project) return;
    record.state = 'uploading';
    record.progress = 0;
    this.renderUploads();
    try {
      const asset = await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest(), body = new FormData();
        body.append('file', record.file);
        xhr.open('POST', `/api/projects/${record.project}/assets`);
        xhr.responseType = 'json';
        xhr.timeout = 120000;
        xhr.upload.onprogress = event => {
          if (event.lengthComputable) record.progress = Math.round(event.loaded / event.total * 100);
          this.renderUploads();
        };
        xhr.onload = () => xhr.status >= 200 && xhr.status < 300
          ? resolve(xhr.response)
          : reject(new Error(typeof xhr.response?.detail === 'string' ? xhr.response.detail : 'Upload failed.'));
        xhr.onerror = xhr.ontimeout = () => reject(new Error('Upload failed. Check your connection and retry.'));
        xhr.send(body);
      });
      record.state = 'done';
      record.progress = 100;
      if (this.project === record.project) {
        if (!this.assets.some(a => a.key === asset.key)) this.assets.push(asset);
        this.renderDeck();
      }
      if (record.position && this.board === record.board) await this.place(asset, record.position);
    } catch (error) {
      record.state = 'error';
      record.error = error.message;
    }
    this.renderUploads();
  }

  renderUploads() {
    $('uploads').replaceChildren();
    this.uploads.forEach(record => {
      const n = el('div', undefined, 'upload-row');
      n.append(el('span', `${record.name}: ${
        record.state === 'done'
          ? 'Uploaded'
          : record.state === 'error'
            ? record.error
            : record.progress === 100
              ? 'Processing…'
              : `${record.progress}%`
      }`));
      if (record.state === 'uploading') {
        const progress = el('progress');
        progress.max = 100;
        progress.value = record.progress;
        progress.setAttribute('aria-label', `Uploading ${record.name}`);
        n.append(progress);
      }
      if (record.state === 'error') n.append(action('Retry upload', () => this.uploadOne(record), 'edit'));
      $('uploads').append(n);
    });
  }

  bind() {
    const bind = (id, fn) => $(id).addEventListener('click', fn);
    bind('new-board', () => this.create());
    bind('workspace-new', () => this.create());
    bind('retry', () => this.save());
    bind('recovery', () => this.showRecovery());
    $('projects').addEventListener('change', async () => {
      if (!(await this.canLeave())) {
        $('projects').value = this.project;
        return;
      }
      this.project = $('projects').value;
      await this.loadProject();
    });
    $('switcher').addEventListener('change', () => this.open($('switcher').value));
    bind('back', async () => {
      if (!(await this.canLeave())) return;
      clearTimeout(this.timer);
      await this.loadProject();
    });
    bind('deck-toggle', () => {
      $('deck').hidden = !$('deck').hidden;
      $('deck-toggle').setAttribute('aria-expanded', String(!$('deck').hidden));
    });
    bind('objects-toggle', () => {
      $('details').hidden = !$('details').hidden;
    });
    bind('details-close', () => {
      $('details').hidden = true;
    });
    $('search').addEventListener('input', () => this.renderDeck());
    ['upload', 'empty-upload'].forEach(id => bind(id, () => {
      if (this.editable()) $('files').click();
    }));
    $('files').addEventListener('change', () => {
      this.upload([...$('files').files]);
      $('files').value = '';
    });
    ['text', 'empty-text'].forEach(id => bind(id, () => this.edit('text')));
    ['swatch', 'empty-swatch'].forEach(id => bind(id, () => this.edit('swatch')));
    bind('edit-object', () => this.edit());
    bind('editor-save', () => this.commitEditor());
    $('color-value').addEventListener('input', () => {
      $('hex-value').value = $('color-value').value;
    });
    bind('select', () => {
      this.tool = 'select';
      this.tools();
    });
    bind('hand', () => {
      this.tool = 'hand';
      this.tools();
    });
    bind('sample', () => {
      if (this.editable()) {
        this.sampling = true;
        this.tools();
        $('canvas').focus();
      }
    });
    bind('remove', () => this.remove());
    bind('duplicate', () => this.duplicate());
    bind('front-layer', () => this.layer(true));
    bind('back-layer', () => this.layer(false));
    bind('undo', () => this.undo());
    bind('redo', () => this.undo(true));
    bind('dismiss-hint', () => {
      this.hintDismissed = true;
      $('hint').hidden = true;
    });
    bind('zoom-in', () => this.zoom(1.2));
    bind('zoom-out', () => this.zoom(1 / 1.2));
    bind('fit', () => this.fit());
    bind('keep-copy', () => this.recover('copy'));
    bind('open-latest', () => this.recover('latest'));
    bind('compare', () => this.recover('compare'));
    bind('replace', () => this.recover('replace'));
    bind('dismiss-conflict', () => $('conflict').close());
    $('canvas').addEventListener('pointerdown', e => this.pointerDown(e));
    $('canvas').addEventListener('pointermove', e => this.pointerMove(e));
    $('canvas').addEventListener('pointerup', e => this.pointerUp(e));
    $('canvas').addEventListener('pointercancel', e => this.pointerUp(e));
    $('canvas').addEventListener('wheel', event => {
      if (!this.board) return;
      event.preventDefault();
      const r = $('canvas').getBoundingClientRect();
      if (event.ctrlKey || event.metaKey) this.zoom(Math.exp(-event.deltaY * .01), event.clientX - r.left, event.clientY - r.top);
      else {
        this.board.view.x -= event.deltaX;
        this.board.view.y -= event.deltaY;
        this.view();
        if (!this.readOnly) this.mark();
      }
    }, {
      passive: false
    });
    $('canvas').addEventListener('dragover', e => {
      if (this.editable()) e.preventDefault();
    });
    $('canvas').addEventListener('drop', e => {
      e.preventDefault();
      if (!this.editable()) return;
      const r = $('canvas').getBoundingClientRect(),
        p = C.point(e.clientX - r.left, e.clientY - r.top, this.board.view),
        key = e.dataTransfer.getData('application/x-ideadock-asset');
      if (key) {
        const asset = this.assets.find(a => a.key === key);
        if (asset) this.place(asset, p);
      } else this.upload([...e.dataTransfer.files], p);
    });
    document.addEventListener('paste', e => {
      // Dialog input and ordinary text editing retain their native paste path.
      if (!this.editable() || C.typing(e.target) || document.querySelector('dialog[open]')) return;
      const files = [...(e.clipboardData?.items || [])]
      .filter(i => i.kind === 'file' && i.type.startsWith('image/'))
      .map(i => i.getAsFile()).filter(Boolean);
      if (files.length) {
        e.preventDefault();
        this.upload(files, this.center());
      }
    });
    document.addEventListener('keydown', e => this.key(e));
    document.addEventListener('keyup', e => {
      if (e.code === 'Space') {
        this.space = false;
        this.tools();
      }
    });
    window.addEventListener('blur', () => {
      this.space = false;
      this.pointers.clear();
      this.pointerUp();
      this.tools();
    });
    window.addEventListener('beforeunload', e => {
      if (this.saveState?.dirty || this.uploads.some(u => u.state === 'uploading')) {
        e.preventDefault();
        e.returnValue = '';
      }
    });
    matchMedia('(max-width: 899px)').addEventListener('change', e => {
      this.readOnly = e.matches;
      this.mode();
      this.render();
      this.renderDeck();
    });
  }
}
window.boardWorkspace = new BoardWorkspace();
