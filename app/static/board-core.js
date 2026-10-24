/* Pure canvas operations shared by the workspace and dependency-free tests. */
(function (root) {
  'use strict';
  const clone = value => JSON.parse(JSON.stringify(value));
  const point = (x, y, view) => ({
    x: (x - view.x) / view.zoom,
    y: (y - view.y) / view.zoom
  });
  const bounds = objects => objects.length ? {
    x: Math.min(...objects.map(o => o.x)),
    y: Math.min(...objects.map(o => o.y)),
    right: Math.max(...objects.map(o => o.x + o.width)),
    bottom: Math.max(...objects.map(o => o.y + o.height)),
  } : null;
  function fit(objects, width, height) {
    const b = bounds(objects);
    if (!b) return {
      x: width / 2, y: height / 2, zoom: 1
    };
    const zoom = Math.max(.05, Math.min(2, (width - 80) / Math.max(1, b.right - b.x), (height - 80) / Math.max(1, b.bottom - b.y)));
    return {
      x: (width - (b.right + b.x) * zoom) / 2, y: (height - (b.bottom + b.y) * zoom) / 2, zoom
    };
  }
  function zoomAt(view, factor, x, y) {
    const p = point(x, y, view), zoom = Math.max(.05, Math.min(5, view.zoom * factor));
    return {
      x: x - p.x * zoom, y: y - p.y * zoom, zoom
    };
  }
  function resize(object, delta) {
    const width = Math.max(16, Math.min(10000, object.width + delta));
    return {
      ...object, width, height: object.height * width / object.width
    };
  }
  function marquee(objects, a, b, previous = []) {
    const left = Math.min(a.x, b.x), right = Math.max(a.x, b.x), top = Math.min(a.y, b.y), bottom = Math.max(a.y, b.y);
    return [...new Set([
      ...previous,
      ...objects.filter(o =>
        o.x >= left && o.y >= top && o.x + o.width <= right && o.y + o.height <= bottom
      ).map(o => o.id)
    ])];
  }
  const hex = value => /^#[\da-f]{6}$/i.test(value) ? value.toUpperCase() : null;
  const typing = element => !!element?.closest('input, textarea, select, [contenteditable="true"]');
  class History {
    constructor() {
      this.past = [];
      this.future = [];
    }
    push(state) {
      this.past.push(clone(state));
      this.future = [];
    }
    undo(state) {
      if (!this.past.length) return state;
      this.future.push(clone(state));
      return this.past.pop();
    }
    redo(state) {
      if (!this.future.length) return state;
      this.past.push(clone(state));
      return this.future.pop();
    }
  }
  // Acknowledgements apply only to the exact snapshot sent. Edits made while a
  // request is in flight remain dirty, even when that older request succeeds.
  class SaveState {
    constructor(revision) {
      this.revision = revision;
      this.generation = 0;
      this.saved = 0;
      this.conflict = false;
    }
    edit() {
      this.generation++;
    }
    acknowledge(generation, revision) {
      this.saved = generation;
      this.revision = revision;
    }
    get dirty() {
      return this.generation !== this.saved;
    }
  }
  const api = {
    clone, point, bounds, fit, zoomAt, resize, marquee, hex, typing, History, SaveState
  };
  if (typeof module !== 'undefined') module.exports = api;
  else root.BoardCore = api;
})(typeof window !== 'undefined' ? window : globalThis);
