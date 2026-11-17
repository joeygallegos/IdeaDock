# Item-owned Visual Boards verification

Implemented November 17, 2026. Three implementation agents handled schema/migration, backend, and frontend; a fresh independent architect reviewed the integrated change.

| Requirement | Implementation and evidence |
| --- | --- |
| Board belongs to the focused item | Board/direct-upload `item_id` foreign keys; item-scoped API; tests cover no-Epic owners, same-Epic sibling isolation, and unchanged ownership after Epic edits. |
| Search dropdown uses board names on both pages | Global name search returns board ID and owner metadata; home/workspace controls use board names and owner titles. Tests cover duplicate names, literal wildcards, stale responses, errors/retry, and cross-owner navigation. |
| Existing boards remain usable | Explicit Epic-to-Item migration mapping preserves IDs, revisions, layouts, paths, references, and historical access. Populated SQLite upgrades and rollback failures tested. |
| Image workflow works | Owner-only deck; HTTP and browser checks cover upload, placement, save/reopen, and source deletion protection. |
| Recovery remains safe | Revision race/conflict tests, copy/latest/replace recovery, cancelled/failed navigation, and catalog refresh checks pass. |

Final automated checks: **41 Python tests passed**, **50 Node tests passed**. JavaScript syntax checks and `git diff --check` passed. No dependencies added or upgraded.

Browser verification used a disposable local database: created an item without Epics, created named boards, selected a board from home by name, saved text and reloaded it, uploaded an image through the empty-board button, placed it and confirmed persistence after reload. Empty-board text and swatch dialogs also opened successfully. Browser testing found and led to a fix for canvas pointer capture swallowing native control clicks; mouse/touch regression coverage was added.

Independent review caught null owner bindings and recovery catalog refresh omissions; both were corrected and reviewed again. No further blocking findings remained.

Deployment: stop the app, back up database/uploads, supply explicit ownership mapping for populated legacy boards/direct uploads, migrate, then restart. Automatic ownership downgrade is intentionally refused. Live MySQL migration was unavailable; native ALTER behavior was reviewed but not executed.

At the user's subsequent request, the configured SQLite database was backed up together with uploads under ignored `storage/backups/`, then migrated from `0003_visual_boards` to `0004_item_board_ownership`. No mapping was needed because legacy boards/direct uploads were empty. All 13 application tables retained their rows, including 16 items; integrity and foreign-key checks passed, and the new ownership constraints target Items. Read-only HTTP evaluation against that database returned 200 for health, items, board search, item boards, image deck, home, and workspace. The full 41 Python and 50 Node tests were rerun for commit validation. No evaluation records were added to the configured database.
