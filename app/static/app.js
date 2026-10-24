window.__ideaDockDebug = window.__ideaDockDebug || {
  seq: 0,
  instances: 0,
  events: [],
  pasteHandler: null,
  pasteListenerInstanceId: null,
  lastGlobalPasteFingerprint: "",
  lastGlobalPasteAt: 0,
};

window.ideaDockDebugDump = function ideaDockDebugDump() {
  return JSON.stringify(window.__ideaDockDebug.events.slice(-250), null, 2);
};

window.ideaDockDebugReset = function ideaDockDebugReset() {
  window.__ideaDockDebug.events = [];
  window.__ideaDockDebug.seq = 0;
  return "IdeaDock debug log cleared.";
};

window.ideaDockApp = function ideaDockApp() {
  return {
    instanceId: null,
    captureText: "",
    captureLineTemplate: "Title text #epic1 #epic2 -type @entity !priority due:YYYY-MM-DD",
    captureAssistantPrompt: `Summarize this idea in one line like this:

Title text #epic1 #epic2 -type @entity !priority due:YYYY-MM-DD

RULES:
- Put the plain-English title first.
- Use only tokens that clearly apply.
- Valid types: -task, -idea, -note, -someday.
- Valid priorities: !low, !med, !high.
- Use one or more #epic tokens when the life areas are obvious.
- Use @entity for a person, company, vendor, service, or other external actor when mentioned.
- Use due:YYYY-MM-DD only if there is a real explicit date.
- Return only the final one-line capture string and nothing else.

EXAMPLE:
Call bank about payoff #money #house -task @chase !high due:2026-04-20`,
    preview: null,
    review: {
      inbox_count: 0,
      waiting_count: 0,
      overdue_count: 0,
      unassigned_count: 0,
      stale_count: 0,
      mood_board_item_count: 0,
    },
    items: [],
    projectItems: [],
    projectBoards: [],
    projectBoardsLoading: false,
    projectBoardsError: "",
    projectBoardsRequest: 0,
    epics: [],
    entities: [],
    selectedItem: null,
    focusMode: false,
    moodBoardFocus: false,
    focusDraft: null,
    focusSaveError: "",
    lightboxAsset: null,
    isSaving: false,
    isFocusSaving: false,
    previewTimer: null,
    flashTimer: null,
    dragTargetItemId: null,
    uploadQueue: [],
    nextUploadId: 1,
    pasteHandler: null,
    recentPasteFingerprint: "",
    recentPasteAt: 0,
    statuses: ["inbox", "next", "doing", "waiting", "done"],
    itemTypes: ["task", "idea", "note", "someday"],
    priorities: ["low", "med", "high"],
    filters: {
      q: "",
      status_filter: "",
      item_type: "",
      priority: "",
      epic_id: "",
      entity_id: "",
      has_mood_board: "",
      due_state: "",
    },
    flash: {
      message: "",
      type: "success",
    },

    globalDebugState() {
      return window.__ideaDockDebug;
    },

    debugLog(label, payload = {}) {
      const debug = this.globalDebugState();
      const entry = {
        seq: ++debug.seq,
        at: new Date().toISOString(),
        label,
        instanceId: this.instanceId,
        payload,
      };
      debug.events.push(entry);
      if (debug.events.length > 400) {
        debug.events.shift();
      }
      console.debug("[IdeaDock]", label, entry);
      return entry;
    },

    async init() {
      this.filters.epic_id = new URLSearchParams(location.search).get("project") || "";
      const debug = this.globalDebugState();
      this.instanceId = ++debug.instances;
      this.debugLog("init:start", {
        readyState: document.readyState,
        existingPasteListenerInstanceId: debug.pasteListenerInstanceId,
      });

      if (debug.pasteHandler) {
        document.removeEventListener("paste", debug.pasteHandler);
        this.debugLog("init:paste-listener-removed", {
          previousInstanceId: debug.pasteListenerInstanceId,
        });
      }

      this.pasteHandler = this.handlePasteEvent.bind(this);
      document.addEventListener("paste", this.pasteHandler);
      debug.pasteHandler = this.pasteHandler;
      debug.pasteListenerInstanceId = this.instanceId;
      this.debugLog("init:paste-listener-attached", {
        currentInstanceId: this.instanceId,
      });

      await Promise.all([this.loadLookups(), this.loadSummary(), this.loadProjectOverview(), this.loadItems()]);
    },

    async fetchJson(url, options = {}) {
      const response = await fetch(url, options);
      if (!response.ok) {
        let detail = "Request failed.";
        try {
          const body = await response.json();
          // Source-image safeguards return structured board references; keep the
          // affected names visible rather than displaying "[object Object]".
          if (typeof body.detail === "string") detail = body.detail;
          else if (body.detail?.message) {
            detail = body.detail.message;
            if (body.detail.boards?.length) detail += ` Used by: ${body.detail.boards.map(board => board.name).join(", ")}.`;
          }
        } catch (_error) {
          detail = response.statusText || detail;
        }
        throw new Error(detail);
      }

      if (response.status === 204) {
        return null;
      }
      return response.json();
    },

    async loadLookups() {
      try {
        const [epics, entities] = await Promise.all([
          this.fetchJson("/api/epics"),
          this.fetchJson("/api/entities"),
        ]);
        this.epics = epics;
        this.entities = entities;
      } catch (error) {
        this.showFlash(error.message, "error");
      }
    },

    async loadSummary() {
      try {
        this.review = await this.fetchJson("/api/review-summary");
      } catch (error) {
        this.showFlash(error.message, "error");
      }
    },

    async loadProjectOverview() {
      try {
        this.projectItems = await this.fetchJson("/api/items");
      } catch (error) {
        this.showFlash(error.message, "error");
      }
    },

    selectProject(epicId) {
      this.filters.epic_id = epicId ? String(epicId) : "";
      this.filters.status_filter = "";
      this.filters.priority = "";
      this.filters.due_state = "";
      this.loadItems();
    },

    async loadProjectBoards(projectId) {
      // A late response must never show another project's boards after selection changes.
      const request = ++this.projectBoardsRequest;
      this.projectBoards = [];
      this.projectBoardsError = "";
      this.projectBoardsLoading = Boolean(projectId);
      if (!projectId) return;
      try {
        const boards = await this.fetchJson(`/api/projects/${encodeURIComponent(projectId)}/boards`);
        if (request === this.projectBoardsRequest) this.projectBoards = boards;
      } catch (error) {
        if (request === this.projectBoardsRequest) this.projectBoardsError = error.message;
      } finally {
        if (request === this.projectBoardsRequest) this.projectBoardsLoading = false;
      }
    },

    boardCreateUrl(projectId) {
      return `/static/boards.html?project=${encodeURIComponent(projectId)}&create=1`;
    },

    projectOpenCount(epicId) {
      return this.projectItems.filter((item) =>
        item.status !== "done" && this.itemEpics(item).some((epic) => epic.id === epicId)
      ).length;
    },

    activeEpics() {
      return this.epics.filter((epic) => this.projectOpenCount(epic.id) > 0);
    },

    projectOptionLabel(epic) {
      const openCount = this.projectOpenCount(epic.id);
      const highCount = this.projectHighCount(epic.id);
      return `${epic.name} — ${openCount} open${highCount ? `, ${highCount} high priority` : ""}`;
    },

    projectHighCount(epicId) {
      return this.projectItems.filter((item) =>
        item.status !== "done" && item.priority === "high" && this.itemEpics(item).some((epic) => epic.id === epicId)
      ).length;
    },

    async loadItems(preferredItemId = null, preserveSelectionWhenMissing = false) {
      try {
        const params = new URLSearchParams();
        Object.entries(this.filters).forEach(([key, value]) => {
          if (value !== "" && value !== null && value !== undefined) {
            params.set(key, value);
          }
        });
        // The default report is active work. Selecting a specific status, including
        // Done, intentionally switches to that status instead.
        if (!this.filters.status_filter) {
          params.set("active_only", "true");
        }

        const url = params.toString() ? `/api/items?${params}` : "/api/items";
        this.items = await this.fetchJson(url);

        const currentId = preferredItemId || this.selectedItem?.id;
        if (currentId) {
          const match = this.items.find((item) => item.id === currentId);
          if (match) {
            await this.loadItem(match.id);
            return;
          }
          if (preserveSelectionWhenMissing) {
            return;
          }
        }

        if (!this.items.length) {
          this.selectedItem = null;
          this.focusMode = false;
          this.focusDraft = null;
          return;
        }

        await this.loadItem(this.items[0].id);
      } catch (error) {
        this.showFlash(error.message, "error");
      }
    },

    async loadItem(itemId) {
      try {
        this.selectedItem = await this.fetchJson(`/api/items/${itemId}`);
        return this.selectedItem;
      } catch (error) {
        this.showFlash(error.message, "error");
        return null;
      }
    },

    queuePreview() {
      window.clearTimeout(this.previewTimer);
      if (!this.captureText.trim()) {
        this.preview = null;
        return;
      }

      this.previewTimer = window.setTimeout(() => {
        this.loadPreview();
      }, 160);
    },

    async loadPreview() {
      try {
        this.preview = await this.fetchJson("/api/parser/preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ raw_input: this.captureText }),
        });
      } catch (error) {
        this.showFlash(error.message, "error");
      }
    },

    async submitCapture() {
      if (!this.captureText.trim()) {
        return;
      }

      this.isSaving = true;
      try {
        const item = await this.fetchJson("/api/items", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ raw_input: this.captureText }),
        });
        this.captureText = "";
        this.preview = null;
        await Promise.all([this.loadLookups(), this.loadSummary(), this.loadProjectOverview()]);
        await this.loadItems(item.id);
        this.showFlash(`Saved item #${item.id}.`, "success");
      } catch (error) {
        this.showFlash(error.message, "error");
      } finally {
        this.isSaving = false;
      }
    },

    async copyCapturePrompt() {
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(this.captureAssistantPrompt);
        } else {
          this.copyTextFallback(this.captureAssistantPrompt);
        }
        this.showFlash("GPT capture prompt copied to clipboard.", "success");
      } catch (_error) {
        this.showFlash("Could not copy the GPT prompt.", "error");
      }
    },

    async setStatus(statusName) {
      if (!this.selectedItem || this.selectedItem.status === statusName) {
        return;
      }
      await this.patchSelectedItem({ status: statusName });
    },

    async completeItem(item) {
      if (!item || item.status === "done") {
        return;
      }

      this.selectedItem = item;
      const completed = await this.patchSelectedItem({ status: "done" });
      if (completed) {
        this.showFlash(`Marked “${item.title}” done.`, "success");
      }
    },

    async togglePinned() {
      if (!this.selectedItem) {
        return;
      }
      await this.patchSelectedItem({ is_pinned: !this.selectedItem.is_pinned });
    },

    async patchSelectedItem(payload) {
      if (!this.selectedItem) {
        return;
      }

      try {
        this.selectedItem = await this.fetchJson(`/api/items/${this.selectedItem.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        await Promise.all([
          this.loadSummary(),
          this.loadProjectOverview(),
          this.loadItems(this.selectedItem.id, payload.status === "done"),
        ]);
        if (this.focusMode && this.selectedItem) {
          this.focusDraft = this.createFocusDraft(this.selectedItem);
        }
        return true;
      } catch (error) {
        this.showFlash(error.message, "error");
        return false;
      }
    },

    openFocusMode() {
      if (!this.selectedItem) {
        return;
      }
      this.moodBoardFocus = false;
      this.focusDraft = this.createFocusDraft(this.selectedItem);
      this.focusSaveError = "";
      this.focusMode = true;
    },

    async openFocusModeForItem(itemId) {
      const item = await this.loadItem(itemId);
      if (!item) {
        return;
      }
      this.openFocusMode();
    },

    closeFocusMode() {
      this.focusMode = false;
      this.moodBoardFocus = false;
      this.focusDraft = null;
      this.focusSaveError = "";
    },

    createFocusDraft(item) {
      return {
        id: item.id,
        title: item.title || "",
        details: item.details || "",
        item_type: item.item_type || "idea",
        status: item.status || "inbox",
        priority: item.priority || "",
        due_date: item.due_date || "",
        epic_input: this.itemEpics(item).map((epic) => epic.name).join(", "),
        tag_input: (item.tags || []).map((tag) => tag.name).join(", "),
        is_pinned: Boolean(item.is_pinned),
      };
    },

    async saveFocusItem() {
      if (!this.focusDraft) {
        return;
      }

      const title = this.trimText(this.focusDraft.title);
      if (!title) {
        this.focusSaveError = "Title is required.";
        return;
      }

      this.isFocusSaving = true;
      this.focusSaveError = "";
      try {
        const updated = await this.fetchJson(`/api/items/${this.focusDraft.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title,
            details: this.trimMultiline(this.focusDraft.details),
            item_type: this.focusDraft.item_type,
            status: this.focusDraft.status,
            priority: this.focusDraft.priority || null,
            due_date: this.focusDraft.due_date || null,
            epic_names: this.parseEpicInput(this.focusDraft.epic_input),
            tag_names: this.parseNameList(this.focusDraft.tag_input),
            is_pinned: Boolean(this.focusDraft.is_pinned),
          }),
        });

        this.selectedItem = updated;
        this.focusDraft = this.createFocusDraft(updated);
        await Promise.all([this.loadSummary(), this.loadProjectOverview(), this.loadItems(updated.id), this.loadLookups()]);
        if (this.selectedItem) {
          this.focusDraft = this.createFocusDraft(this.selectedItem);
        }
        this.showFlash(`Updated item #${updated.id}.`, "success");
      } catch (error) {
        this.focusSaveError = error.message;
      } finally {
        this.isFocusSaving = false;
      }
    },

    async completeFocusItem() {
      if (!this.focusDraft || this.focusDraft.status === "done") {
        return;
      }
      this.focusDraft.status = "done";
      await this.saveFocusItem();
    },

    applyReviewPreset(preset) {
      if (preset === "inbox") {
        this.filters.status_filter = "inbox";
        this.filters.has_mood_board = "";
        this.filters.due_state = "";
      }
      if (preset === "waiting") {
        this.filters.status_filter = "waiting";
        this.filters.due_state = "";
      }
      if (preset === "overdue") {
        this.filters.status_filter = "";
        this.filters.due_state = "overdue";
      }
      this.loadItems();
    },

    resetFilters() {
      this.filters = {
        q: "",
        status_filter: "",
        item_type: "",
        priority: "",
        epic_id: "",
        entity_id: "",
        has_mood_board: "",
        due_state: "",
      };
      this.loadItems();
    },

    async uploadAsset(event) {
      if (!this.selectedItem) {
        return;
      }

      const files = Array.from(event.target.file.files || []);
      await this.uploadFiles(files, this.selectedItem.id);
      event.target.reset();
    },

    async uploadFilesFromInput(event, itemId) {
      const files = Array.from(event.target.files || []);
      await this.uploadFiles(files, itemId);
      event.target.value = "";
    },

    async uploadFiles(files, itemId) {
      const imageFiles = files.filter((file) => file && file.type && file.type.startsWith("image/"));
      this.debugLog("upload:batch", {
        itemId,
        inputCount: files.length,
        imageCount: imageFiles.length,
        files: imageFiles.map((file) => ({
          name: file.name || "",
          type: file.type || "",
          size: file.size || 0,
          lastModified: file.lastModified || 0,
        })),
      });
      if (!imageFiles.length) {
        return;
      }

      for (const rawFile of imageFiles) {
        const file = this.ensureNamedFile(rawFile);
        const upload = this.createUploadRecord(file, itemId);
        try {
          await this.uploadSingleFile(upload, file, itemId);
        } catch (_error) {
          // Error state is stored on the upload record.
        }
      }
    },

    createUploadRecord(file, itemId) {
      const upload = {
        id: this.nextUploadId++,
        itemId,
        name: file.name || `image-${Date.now()}.png`,
        progress: 0,
        status: "queued",
        error: "",
      };
      this.uploadQueue = [upload, ...this.uploadQueue];
      this.debugLog("upload:record-created", {
        itemId,
        uploadId: upload.id,
        name: upload.name,
      });
      return upload;
    },

    async uploadSingleFile(upload, file, itemId) {
      upload.status = "uploading";
      upload.progress = 2;
      this.debugLog("upload:xhr-start", {
        itemId,
        uploadId: upload.id,
        name: file.name || "",
        type: file.type || "",
        size: file.size || 0,
      });

      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `/api/items/${itemId}/assets`);
        xhr.responseType = "json";

        xhr.upload.addEventListener("progress", (event) => {
          if (event.lengthComputable) {
            upload.progress = Math.max(4, Math.round((event.loaded / event.total) * 100));
          } else {
            upload.progress = Math.max(upload.progress, 18);
          }
        });

        xhr.addEventListener("load", async () => {
          this.debugLog("upload:xhr-load", {
            itemId,
            uploadId: upload.id,
            status: xhr.status,
            responseDetail: xhr.response?.detail || null,
          });
          if (xhr.status >= 200 && xhr.status < 300) {
            upload.status = "done";
            upload.progress = 100;
            await this.refreshItemAfterAssetChange(itemId);
            window.setTimeout(() => {
              this.removeUploadRecord(upload.id);
            }, 2600);
            resolve();
            return;
          }

          upload.status = "error";
          upload.progress = 100;
          upload.error = xhr.response?.detail || "Upload failed.";
          this.showFlash(upload.error, "error");
          reject(new Error(upload.error));
        });

        xhr.addEventListener("error", () => {
          this.debugLog("upload:xhr-error", {
            itemId,
            uploadId: upload.id,
          });
          upload.status = "error";
          upload.progress = 100;
          upload.error = "Upload failed.";
          this.showFlash(upload.error, "error");
          reject(new Error(upload.error));
        });

        const formData = new FormData();
        formData.append("file", file, file.name);
        xhr.send(formData);
      });
    },

    async refreshItemAfterAssetChange(itemId) {
      await Promise.all([this.loadSummary(), this.loadItems(itemId)]);
      if (this.focusMode && this.selectedItem?.id === itemId) {
        this.focusDraft = this.createFocusDraft(this.selectedItem);
      }
    },

    removeUploadRecord(uploadId) {
      this.uploadQueue = this.uploadQueue.filter((upload) => upload.id !== uploadId);
    },

    uploadsForItem(itemId) {
      return this.uploadQueue.filter((upload) => upload.itemId === itemId);
    },

    uploadStatusLabel(upload) {
      if (upload.status === "queued") {
        return "Queued";
      }
      if (upload.status === "uploading") {
        return `${upload.progress}%`;
      }
      if (upload.status === "done") {
        return "Done";
      }
      return "Error";
    },

    uploadProgressStyle(upload) {
      const gradient = upload.status === "error"
        ? "linear-gradient(90deg, #fb7185 0%, #f43f5e 100%)"
        : "linear-gradient(90deg, #635bff 0%, #0ea5e9 100%)";
      return `width:${upload.progress}%; background:${gradient};`;
    },

    setDragTarget(itemId) {
      this.dragTargetItemId = itemId;
    },

    clearDragTarget(itemId) {
      if (this.dragTargetItemId === itemId) {
        this.dragTargetItemId = null;
      }
    },

    isDragTarget(itemId) {
      return this.dragTargetItemId === itemId;
    },

    async handleDrop(event, itemId) {
      this.clearDragTarget(itemId);
      const files = this.extractImageFiles(event.dataTransfer);
      await this.uploadFiles(files, itemId);
    },

    async handlePasteEvent(event) {
      const itemId = this.activeUploadItemId();
      const target = event.target;
      const targetSummary = {
        tagName: target?.tagName || null,
        type: target?.type || null,
        isContentEditable: Boolean(target?.isContentEditable),
        timeStamp: typeof event.timeStamp === "number" ? Math.round(event.timeStamp) : null,
        focusMode: Boolean(this.focusMode),
        focusDraftId: this.focusDraft?.id || null,
        selectedItemId: this.selectedItem?.id || null,
      };
      if (!itemId) {
        this.debugLog("paste:ignored-no-item", targetSummary);
        return;
      }

      const files = this.extractImageFiles(event.clipboardData);
      if (!files.length) {
        this.debugLog("paste:ignored-no-files", {
          itemId,
          ...targetSummary,
        });
        return;
      }

      const fingerprint = this.pasteFingerprint(files, itemId);
      const now = Date.now();
      const globalDebug = this.globalDebugState();
      const isGlobalDuplicate = globalDebug.lastGlobalPasteFingerprint === fingerprint
        && now - globalDebug.lastGlobalPasteAt < 1200;
      this.debugLog("paste:received", {
        itemId,
        fingerprint,
        fileCount: files.length,
        files: files.map((file) => ({
          name: file.name || "",
          type: file.type || "",
          size: file.size || 0,
          lastModified: file.lastModified || 0,
        })),
        ...targetSummary,
      });

      if (isGlobalDuplicate) {
        event.preventDefault();
        this.debugLog("paste:skipped-global-duplicate", {
          itemId,
          fingerprint,
        });
        return;
      }

      if (this.recentPasteFingerprint === fingerprint && now - this.recentPasteAt < 1200) {
        event.preventDefault();
        this.debugLog("paste:skipped-local-duplicate", {
          itemId,
          fingerprint,
        });
        return;
      }

      globalDebug.lastGlobalPasteFingerprint = fingerprint;
      globalDebug.lastGlobalPasteAt = now;
      this.recentPasteFingerprint = fingerprint;
      this.recentPasteAt = now;

      event.preventDefault();
      this.debugLog("paste:uploading", {
        itemId,
        fingerprint,
      });
      await this.uploadFiles(files, itemId);
      this.showFlash("Pasted image upload started.", "success");
    },

    activeUploadItemId() {
      if (this.focusMode && this.focusDraft?.id) {
        return this.focusDraft.id;
      }
      return this.selectedItem?.id || null;
    },

    extractImageFiles(dataSource) {
      if (!dataSource) {
        return [];
      }

      const files = [];
      const seen = new Set();

      const pushUniqueFile = (file) => {
        if (!file) {
          return;
        }
        const fingerprint = this.fileFingerprint(file);
        if (seen.has(fingerprint)) {
          return;
        }
        seen.add(fingerprint);
        files.push(this.ensureNamedFile(file));
      };

      if (dataSource.items) {
        Array.from(dataSource.items).forEach((item) => {
          if (item.kind === "file" && item.type.startsWith("image/")) {
            pushUniqueFile(item.getAsFile());
          }
        });
      }

      if (!files.length && dataSource.files) {
        Array.from(dataSource.files).forEach((file) => {
          if (file.type && file.type.startsWith("image/")) {
            pushUniqueFile(file);
          }
        });
      }

      return files;
    },

    pasteFingerprint(files, itemId) {
      return `${itemId}:${files.map((file) => this.fileFingerprint(file)).sort().join("|")}`;
    },

    fileFingerprint(file) {
      return [
        file.type || "",
        file.size || 0,
        file.lastModified || 0,
        this.isGeneratedPasteName(file.name) ? "" : (file.name || ""),
      ].join(":");
    },

    isGeneratedPasteName(name) {
      return typeof name === "string" && name.startsWith("pasted-image-");
    },

    ensureNamedFile(file) {
      if (file.name) {
        return file;
      }

      const extension = this.fileExtensionForType(file.type);
      const stableId = this.fileFingerprint(file)
        .replace(/[^a-zA-Z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        || "clipboard-image";
      return new File([file], `pasted-image-${stableId}${extension}`, {
        type: file.type || "image/png",
        lastModified: file.lastModified || 0,
      });
    },

    fileExtensionForType(type) {
      if (type === "image/jpeg") {
        return ".jpg";
      }
      if (type === "image/gif") {
        return ".gif";
      }
      if (type === "image/webp") {
        return ".webp";
      }
      return ".png";
    },

    async deleteAsset(assetId) {
      if (!this.selectedItem) {
        return;
      }

      try {
        await this.fetchJson(`/api/assets/${assetId}`, { method: "DELETE" });
        if (this.lightboxAsset && this.lightboxAsset.id === assetId) {
          this.lightboxAsset = null;
        }
        await this.refreshItemAfterAssetChange(this.selectedItem.id);
        this.showFlash("Image removed.", "success");
      } catch (error) {
        this.showFlash(error.message, "error");
      }
    },

    itemEpics(item) {
      if (!item) {
        return [];
      }

      if (Array.isArray(item.epics) && item.epics.length) {
        return item.epics;
      }

      if (item.epic) {
        return [item.epic];
      }

      return [];
    },

    parseEpicInput(value) {
      const raw = (value || "").trim();
      if (!raw) {
        return [];
      }

      const hashtagMatches = Array.from(raw.matchAll(/#([^\s#,]+)/g)).map((match) =>
        match[1].replaceAll("_", " ").trim()
      );
      if (hashtagMatches.length) {
        return this.dedupeNames(hashtagMatches);
      }

      return this.parseNameList(raw);
    },

    parseNameList(value) {
      const raw = (value || "").trim();
      if (!raw) {
        return [];
      }

      return this.dedupeNames(
        raw
          .split(/[\n,]+/)
          .map((part) => part.trim())
          .filter(Boolean)
          .map((part) => part.replace(/^#/, ""))
      );
    },

    dedupeNames(values) {
      const seen = new Map();
      values.forEach((value) => {
        const cleaned = this.trimText(value);
        if (!cleaned) {
          return;
        }
        const key = cleaned.toLowerCase();
        if (!seen.has(key)) {
          seen.set(key, cleaned);
        }
      });
      return Array.from(seen.values());
    },

    trimText(value) {
      if (value === null || value === undefined) {
        return "";
      }
      return String(value).replace(/\s+/g, " ").trim();
    },

    trimMultiline(value) {
      if (value === null || value === undefined) {
        return null;
      }
      const cleaned = String(value).trim();
      return cleaned || null;
    },

    labelize(value) {
      return value.replaceAll("_", " ");
    },

    formatDate(value) {
      if (!value) {
        return "";
      }
      return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    },

    relativeDate(value) {
      if (!value) {
        return "";
      }

      const timestamp = new Date(value);
      if (Number.isNaN(timestamp.getTime())) {
        return "";
      }

      return timestamp.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      });
    },

    copyTextFallback(value) {
      const input = document.createElement("textarea");
      input.value = value;
      input.setAttribute("readonly", "");
      input.style.position = "absolute";
      input.style.left = "-9999px";
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      document.body.removeChild(input);
    },

    statusClass(statusName) {
      if (statusName === "done") {
        return "status-pill status-pill--done";
      }
      if (statusName === "waiting") {
        return "status-pill status-pill--waiting";
      }
      if (statusName === "doing") {
        return "status-pill status-pill--doing";
      }
      if (statusName === "next") {
        return "status-pill status-pill--next";
      }
      return "status-pill status-pill--default";
    },

    showFlash(message, type = "success") {
      this.flash = { message, type };
      window.clearTimeout(this.flashTimer);
      this.flashTimer = window.setTimeout(() => {
        this.flash.message = "";
      }, 3400);
    },
  };
};
