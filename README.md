# IdeaDock

IdeaDock is a single-user, self-hosted backlog app for fast capture, filtering, and later review.

This first pass stays intentionally small:

- FastAPI backend with a simple service layer
- SQLAlchemy models for the core object graph
- Alembic baseline migration
- Quick-entry parser for one or more `#epic` tokens, plus `-type`, `@entity`, `!priority`, and `due:YYYY-MM-DD`
- A single HTML page served by the backend for quick capture, filtering, focused item editing, and mood board uploads
- A focused project visual-board workspace with reusable images and independently saved arrangements

## KISS decisions

- The frontend is one static page instead of a full SPA build pipeline.
- Tailwind and Alpine are loaded from CDNs for now so there is no Node build step yet.
- The app defaults to SQLite for local bootstrapping, but the schema and configuration are ready for MySQL via `DATABASE_URL`.
- The first API slice focuses on items, parser preview, review summary, and simple lookup lists.

## Install

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -m alembic upgrade head
```

If you want to activate the virtual environment in PowerShell, use:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks that script, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Generic Python

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
```

You can still install the project in editable mode with `pip install -e .`, but `requirements.txt` is the simplest path to get running quickly.

## Run

Start the app with:

```powershell
.\.venv\Scripts\python -m app.main
```

Then open `http://127.0.0.1:8017`.

`APP_HOST` and `APP_PORT` are read from `.env`; the default port is `8017`. For local development with automatic reload, run:

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8017
```

The main entrypoint is `app/main.py`, and the ASGI app object is `app`.

If you already activated the virtual environment, this shorter command also works:

```powershell
python -m app.main
```

By default, the app expects migrations to create the schema. `AUTO_BOOTSTRAP_DB` is off by default and should usually stay off once Alembic is part of the workflow.

If you want temporary local bootstrap behavior for an empty SQLite database, you can explicitly set:

```env
AUTO_BOOTSTRAP_DB=true
```

Do not leave that enabled for a `systemd` deployment that already runs `alembic upgrade head`.

## Linux service

For a quick `systemd` setup on Linux, use:

```bash
chmod +x scripts/setup-linux-service.sh
./scripts/setup-linux-service.sh
```

The script will:

- create `.venv` if needed
- install `requirements.txt`
- copy `.env.example` to `.env` if missing
- run `alembic upgrade head`
- install `/etc/systemd/system/<service-name>.service`
- enable and start the service

The generated service explicitly sets `AUTO_BOOTSTRAP_DB=false` so startup does not race with schema creation.

For an older SQLite database without Alembic version tracking, setup validates the recognized legacy schema, records its baseline revision, then runs the remaining migrations. It never marks a legacy database as current without applying those migrations. An unrecognized or incomplete schema stops setup before service installation; back up the database and uploads and inspect the schema before attempting manual recovery.

Useful overrides:

```bash
SERVICE_NAME=ideadock APP_PORT=8017 APP_HOST=0.0.0.0 ./scripts/setup-linux-service.sh
```

By default, the service name is the app directory name lowercased. For `/opt/joey/IdeaDock`, that becomes `ideadock`.

After install:

```bash
sudo systemctl status ideadock --no-pager
sudo journalctl -u ideadock -n 100 --no-pager
```

## MySQL example

```env
DATABASE_URL=mysql+pymysql://ideadock:password@127.0.0.1:3306/ideadock
```

## Environment notes

`CORS_ORIGINS` can be set either as a comma-separated string:

```env
CORS_ORIGINS=http://localhost:8017,http://127.0.0.1:8017
```

or as a JSON array:

```env
CORS_ORIGINS=["http://localhost:8017","http://127.0.0.1:8017"]
```

If you are using SQLite and the repo lives inside Dropbox, OneDrive, or another synced folder, SQLite file locking can be flaky. In that case, point `DATABASE_URL` at a path outside the synced folder or switch to MySQL.

Items can belong to more than one epic. In quick capture, that means you can write input like:

```text
Plan backyard party #house #family -idea
```

## UI Notes

- The home screen keeps project filtering compact: use the single Project selector to narrow the working list; each option includes its open-item count and any high-priority work.
- The default report shows active work only, so a project drops out of the active selector when all of its items are marked Done. Select the `Done` status under More filters to review completed work.
- Selecting a note or task opens the focused editor directly, keeping project notes and metadata out of the dashboard until they are needed.
- Close work explicitly with **Mark done** beside an open list item or in the focused editor. The editor's Status field also explains that `Done` closes an item.
- Marking an item Done removes it from the active report but keeps that item open as the current context; the app does not automatically jump to another project or item.
- The capture box is intentionally plain. Add `#project`, `!high`, or `-task` only when that context will help with later review; search and secondary filters are available without dominating the default view.
- `Focus mode` opens a distraction-reduced editor for the currently selected item so you can change title, details, type, status, priority, due date, epics, tags, and pin state in one place.
- Item image attachments support file picker, drag-and-drop, and image paste when an item is selected or open in focus mode.
- The upload UI shows per-file status so you can see queued, active, completed, and failed image uploads without leaving the page.

## Current API surface

- `GET /api/health`
- `GET /api/items`
- `POST /api/items`
- `GET /api/items/{item_id}`
- `PATCH /api/items/{item_id}`
- `POST /api/parser/preview`
- `GET /api/review-summary`
- `GET /api/epics`
- `GET /api/entities`
- `GET /api/tags`
- `POST /api/items/{item_id}/assets`
- `DELETE /api/assets/{asset_id}`

## Project visual boards

Choose a project on the home screen, then use **Create board** in **Project boards**. Name the board to create it, then upload, drop, or paste images inside the workspace. Existing named boards appear under their project. Selecting a project never creates a board; cancelling the name dialog creates nothing. The project chooser includes completed projects. Projects use the existing Epic records; boards do not create copies of notes or tasks.

The focused item editor also offers **Project boards** links for each project currently attached to the item. Save project changes first; each link opens that project's board naming step in a new tab so the editor stays open.

The image deck combines uploads from all project items (including completed items) with images uploaded directly to the project. Select an image and choose **Add to board**, or drag it onto the canvas. Uploading into the deck adds a reusable source image; dropping or pasting an image onto a board also places it there. Multiple boards and placements share source files without changing them.

Use **Select** for objects and marquee selection, Shift to extend selection, and **Hand**, Space-drag, middle-mouse drag, or trackpad scrolling to pan. Arrow keys move selected objects by one canvas unit; Shift+Arrow moves by ten. Image size controls preserve proportions. **Add object** creates text labels or color swatches; swatches accept a picker, hex value, or a color sampled from an image. Undo/redo applies during the current editing session. Smaller screens show an explicit **View only** workspace with browsing, pan, and zoom.

Completed edits save automatically. **Saved** means the server confirmed persistence. Failed saves retain local work and offer retry; do not close the tab until work is saved or copied. When another tab saves first, autosave pauses. **Keep my changes as a copy** preserves the complete local composition in a separate board. **Open latest** requires confirmation; replacing the latest version requires comparison and explicit confirmation. This is conflict detection, not real-time collaboration.

Removing a placement or deleting a board preserves source images. Permanent source-image deletion is blocked while any board uses it, with the affected boards identified. Moving a source item to another project removes it from the old project's deck but preserves existing board placements. Missing image files display placeholders so layout remains recoverable.

### Storage and upgrades

Run `python -m alembic upgrade head` using the application's virtual environment before running the updated application. The board migration adds separate board, project-image, and image-reference tables while preserving existing item-upload records. Do not use `alembic stamp head` as a substitute for running migrations.

For an unversioned legacy SQLite installation, run `python -m scripts.migrate_database` from the repository root instead; the Linux setup script uses this same helper. It recognizes the complete original or many-to-many legacy schema, records the original baseline, and runs all subsequent migrations, including membership backfill. It also handles fresh and already-tracked databases. Unknown schemas require manual inspection and are not automatically stamped or repaired.

Back up the database and the entire configured `UPLOAD_DIR` together before upgrading and as part of regular backups. Board layouts and source references live in the database; image bytes remain in the upload directory. Restore both to the same backup point, then run required migrations. Repeated image placements do not create additional image files. MySQL remains the primary deployment database; SQLite is supported for local development.

### Board API

All board routes are under `/api/projects/{project_id}`:

- `GET/POST /boards` lists or creates boards.
- `GET/PUT/DELETE /boards/{board_id}` loads, saves, or deletes a board. Saves and deletes require the last confirmed revision; stale revisions return HTTP 409.
- `POST /boards/{board_id}/copy` creates a board from the supplied complete local state.
- `GET/POST /assets` lists the combined image deck or uploads a project-owned image.
- `DELETE /assets/{asset_id}` deletes an unused project-owned source image.

Boards store image references, text, swatches, geometry, back-to-front object order, and the last canvas view. View changes do not change object geometry. API clients must retain local work on HTTP 409 and obtain user confirmation before replacing a newer version. Source-deletion conflicts also return HTTP 409 with affected board names.

### Verification

Run the isolated Python checks with `python -m unittest discover -s tests -p "test_*.py" -v` using the virtual environment. They cover migrations, board persistence, source ownership, revision conflicts, and existing capture/upload behavior without modifying the live database.

Frontend checks use Node's built-in test runner: `node --test tests/board_frontend.test.cjs tests/test_workspace_recovery.cjs`. Node is only needed for these development checks; the application frontend has no build step. Controller tests do not replace browser checks for gestures, touch targets, responsive layout, and uploads.

## Next sensible steps

- Add real item detail editing for notes, tags, and linked entity roles in the UI
- Add explicit list/card view switching
- Replace CDN frontend assets with vendored local assets
- Add tests around parser behavior and filter combinations
