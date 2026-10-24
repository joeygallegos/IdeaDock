# Independent verification and requirement traceability

Status: automated, HTTP integration, and representative live-browser checks passed. User approval was received, the installer fix passed verification, and the PM completion audit accepted the implementation. No deployment-scope decision remains. No user database or uploads were used. Hardware and database limitations below remain explicit.

## Current evidence

- **Python: 34 passed** — `.venv/Scripts/python.exe -m unittest discover -s tests -v`. Includes 5 existing-workflow regressions, 5 independent integration tests, 3 real Alembic migration tests, 9 backend-owner tests, and 12 installer migration tests. Checks include capture, completed-item query/reopen, original uploads, project isolation/deduplication, retained moved-source placements, deletion guards, and truly concurrent revision claims with exactly one winner.
- **Node: 33 named tests passed** — `node --test tests/board_frontend.test.cjs tests/test_workspace_recovery.cjs` (latest PM run: 27 frontend plus 6 independent). Covers coordinate math, history, proportional resize, actual controller save/recovery races, failed-save retry, recovery library refresh/failure/identity, read-only guards, Space/middle pan, Shift-marquee, file-drop coordinates and typing-paste passthrough.
- **HTTP smoke passed**, reported by PM using `artifacts/implementation/http_smoke.py` against disposable preview service. Complements direct service tests with real route/response integration.
- **Live browser passed representative workflows**, recorded in [browser-verification.md](browser-verification.md): desktop 1280×900 and narrow 390×844, synthetic fixtures only. PM confirmed final Open latest library-refresh retest passed after the initial browser finding. Screenshot artifacts: `browser-preview.png`, `browser-view-only.png`.
- Fresh migration, populated 0002 upgrade, and known-unversioned-0002 stamp then upgrade preserved items, membership, and upload metadata with a clean SQLite foreign-key check. These are isolated temporary databases, not a live MySQL deployment.

Backend review: revision-qualified UPDATE and reference replacement commit together. Conflict rollback releases the previous transaction before returning latest state. Source locks plus FK RESTRICT protect current placements. Historical `board_asset_access` grants allow legitimate local recovery after a source item moves and a newer board removes its placement; they do not grant arbitrary cross-project access or block source deletion. Tests cover the recovery edge and unauthorized boards.

## PLAN functional rows

Evidence labels below refer to the executed suites above and the linked browser report. Code references are relative to repository root.

| Requirement | Code / executed evidence | Limits |
| --- | --- | --- |
| Navigation | `boards.js` start/open/renderList and main-page entry; browser completed-project entry and named board open | No outstanding functional gap observed |
| Boards | `services/boards.py` CRUD/copy; Python independent-board round trip; browser create/rename/local-copy/reopen and separate overflow | Destructive deletion is service-tested; not all management combinations exercised live |
| Workspace | `board-core.js` coordinates/fit/zoom; browser focused canvas, Hand/wheel/Fit and 120 placements | Physical trackpad hardware unavailable |
| Image deck | `project_assets`, renderDeck/place; Python completed/dedup/isolation; browser source preview and repeated Add | Scroll retention implemented; not every long-deck size profiled |
| Adding images | upload_project_asset/uploadOne/drop/paste handlers; browser mixed picker failure/retry, clipboard paste, deck drag; controller file-drop coordinates | Physical OS file-drop not exercised |
| Image ownership | ProjectAsset/reference keys; Python source bytes/lifecycle; browser shared uploads after switching boards | None observed |
| Arrangement | Ordered layout and pointer/key/layer methods; Python round trip; browser pointer move, keyboard movement/resize, group duplicate/remove/undo | Full layer ordering persisted in tests; not every overlap UI combination inspected |
| Other objects | BoardText/BoardSwatch, edit/commitEditor; Python round trip; browser text and swatch creation | None observed |
| Swatches | Strict hex validation/sample; browser valid hex, invalid value retains previous color, white-pixel sampling | Native picker variations across OS not tested |
| Intended use | VisualBoard persistence; browser reopen and confirmed latest composition/view | No export/sharing introduced |
| Input model | Default Select/tools; browser marquee, Hand/wheel; controller Space/middle and Shift-marquee at non-default zoom | Real trackpad and physical middle/Space gesture coverage limited |
| Non-drag access | key/place/change controls; browser Add, keyboard select/move/resize and remove/undo workflow | No physical assistive technology session |
| Smaller screens | mode/editable guards and responsive CSS; browser 390px View only, details, zoom, Arrow/Delete nonmutation; controller direct mutation guards | Physical touch unavailable |
| Recovery | CAS/copy plus recover/load latest; Python races; browser two-tab conflict, focused copy, comparison gate, cancel/confirmed latest and named copy; controller failure/dismissal/refresh races | Every failure branch not injected live; automated evidence identified explicitly |

## Acceptance criteria 1–23

| AC | Code / automated evidence | Live-browser evidence or remaining limit |
| --- | --- | --- |
| 1 | create_board/list_boards and independent-board test | Named creation, copy, reopen independently |
| 2 | project_assets; completed/dedup/isolation integration | Completed source image alongside direct upload |
| 3 | Ordered per-board layout; round trip and source-byte test | Repeated independent placements, pointer move and proportional keyboard resize; layer order tested in persistence |
| 4 | ProjectAsset and upload service; controller file-drop and paste | Picker/paste creates reusable project asset; second-board reuse and deck drag; physical file-drop untested |
| 5 | Text/swatch schema and edit/sample | Text label, valid/invalid hex retention, sampling synthetic image |
| 6 | change/duplicate/remove and marquee helpers | Shift selection exact count, group duplicate; 4 selected on 120-object board, remove to 116, undo to 120 |
| 7 | Source lifecycle and deletion-guard tests | Placement removal leaves reusable source and independent placements |
| 8 | Full objects/view round trip | Reopen and confirmed Open latest restore composition and view |
| 9 | History snapshots, undo/redo behavior tests | Group duplicate and removal undone live; not every edit type replayed live |
| 10 | Upload cleanup/save atomicity; failed save retry and dirty-generation tests | Mixed upload failure, explicit Retry, valid upload retained; save failures verified by controller |
| 11 | Stale two-session and true concurrent revision tests | Two tabs produced 409 conflict without overwrite |
| 12 | Board queries independent of active-item filter | Completed-project entry remained available |
| 13 | Fit/zoom coordinate invariants | Hand drag, wheel pan, Fit preserved geometry |
| 14 | Item/project source guard identifies affected boards | Service/HTTP evidence; complete affected-board dialog not exercised live |
| 15 | place/key/remove guarded non-drag controls | Add, keyboard selection, one-/ten-unit move, proportional resize and remove workflows |
| 16 | Space/middle controller pan tests; default Select and marquee | Hand/wheel pan and empty-canvas marquee at 57%; hardware-only alternatives not physically tested |
| 17 | Shift-marquee replacement/extension controller tests | Shift-click exact count and four-object marquee; hint implementation statically reviewed |
| 18 | renderDeck/place preserve asset/scroll state | Source preview and repeated Add retain selection/source; long-deck scroll not exhaustively tested |
| 19 | Independent failure/cancel/compare-gate tests; recovery history and latest-library refresh tests | Copy initially focused; replacement hidden before comparison; latest warning Cancel focused; cancel retains edits; named local copy and confirmed latest+library refresh passed |
| 20 | mode/editable and controller mutation guards | 390×844 View only, initial fit, readable details, zoom and Arrow/Delete nonmutation; no physical touch |
| 21 | boards.html Add object/edit flow | Text label and Color swatch distinct from Upload images |
| 22 | CSS focus/tooltips/disabled state and inverse-scale resize handle; proportional math tests | Keyboard movement/resize, 44×44 resize target at 83% zoom and overflow target measured; physical touch/assistive technology untested |
| 23 | renderList separate card and summary handlers | Open/reopen, rename, keyboard overflow distinct from card activation; target 44×44; physical touch untested |

## Existing requirements.md coverage and scope boundary

| Section | Preserved / extended / pre-existing gap |
| --- | --- |
| 1 Product summary | Preserved single-user Python/API/frontend architecture; visual boards extend inspiration use |
| 2 Goals | Capture regression tested; visual inspiration extended; filtering/review retained |
| 3 Non-goals | No auth, cloud, collaboration, mobile editing, Kanban or AI additions |
| 4 Principles | Existing shared items remain independent of board placements; no new dependency |
| 5 Core model | Epic = UI project; Item/Entity/Tag unchanged; independent board references extend assets |
| 6 Relationships | Existing item/epic many-to-many preserved and migration tested; new board/source relationships added |
| 7 Item types | Existing enum/default/change path retained; capture type/default tested |
| 8 Statuses | Completion/query/reopen regression tested; completed uploads explicitly in deck |
| 9 Quick syntax | Token extraction, raw input, normalized project/entity linkage, unknown tokens/date failure tested |
| 10 Entities | Existing model/link service retained; capture entity creation regression; no new entity UI |
| 11 Item mood boards | Original upload ownership/metadata/delete regression; project boards add arrangements without replacing item grid |
| 12 View system | Board layout separate from item data; pre-existing explicit list/card switch remains absent (README next steps) |
| 13 Filtering/search | Existing `list_items` retained; pre-existing tag filter is absent from route/service, not added in this scope |
| 14 Review | Existing review summary retained; no unrelated review workflow expansion |
| 15 Frontend | Static Alpine/vanilla REST architecture retained; focused workspace added |
| 16 Backend | FastAPI thin routes, SQLAlchemy services and Alembic retained; project board API added |
| 17 Storage | Local image files/DB metadata retained; source-key layouts and migration added |
| 18 Deployment | Existing environment/service approach retained; approved installer helper recognizes safe legacy baselines and applies real upgrades; 12 installer tests passed |
| 19 Security | Strict new board validation, project isolation, upload filename/path safeguards; existing item upload content checking was extension-only and remains a pre-existing limitation |
| 20 Backup/recovery | New board layout/references must join existing DB+uploads coordinated backup; no restore drill or live MySQL test performed |
| 21 Extensibility | Items retain identity and records; board-specific layout uses separate storage |
| 22 Suggested screens | Existing screens retained; board workspace is plan-authorized extension, not completion of every suggested screen |
| 23 Suggested order | Plan implementation sequence followed by separate owners; no unrelated base-product completion |
| 24 Success criteria | Capture/upload regression evidence plus board-specific evidence above; not a certification of all pre-existing product requirements |
| 25 Positioning | Preserved personal backlog/inspiration/local deployment scope |


## Review corrections and evidence integrity

Independent review identified stranded dirty edits behind a previous board's in-flight save and sub-threshold pointer changes without dirty/history tracking. Both were corrected and covered by controller tests. Overflow keyboard tooltip and small-screen guidance were corrected. PM browser review additionally corrected accessible naming/confirmation dialogs, menu stacking, zoom-compensated resize targets, responsive disclosure/guidance, and latest-recovery library refresh. The linked browser report records these findings and retests.

Two test-harness issues were resolved without application changes: SQLite connections needed explicit closing for Windows cleanup; the independent recovery harness needed six named async node:test cases after dialogs became asynchronous. The former standalone runner could exit on an unresolved dialog promise. Current evidence uses named async tests with explicit dialog stubs and request-count assertions; 33 named tests completed, not merely one test-file process exiting successfully.

## Remaining limitations and project gate

- The user approved the narrowly scoped installer migration fix. Scope review found only migration detection/execution changes, its helper, tests and documentation; no service-management redesign or dependency additions.
- No live MySQL migration, transaction race, backup/restore drill, physical touch, real trackpad hardware, or physical OS file-drop test was available.
- Automated controller event tests cover Space/middle pan, Shift-marquee, drop coordinates, paste typing preservation, failures, and recovery dismissal; these are not claims of physical-device validation.
- Representative responsiveness: 120 placements sharing one 240×160 PNG rendered with zero broken images; Open/Fit/inspection completed about one second and group selection/remove/undo responded. This is not a benchmark for 120 distinct high-resolution images or a supported-size promise.
- Browser file chooser latency once reflected slow tooling; upload outcomes were verified without inferring production latency.
- Existing unrelated requirements gaps remain catalogued above, including tag filtering, explicit list/card switching, and extension-only validation of original item uploads. They were not silently added to scope.

Earlier browser/Node evidence is unchanged; the newly approved installer scope was verified separately as recorded below. Verification edited tests and this report only.



## Approved installer migration gate — PLAN sequence 6; requirements §§18 and 20

The installer now invokes `python -m scripts.migrate_database` before service installation. Independent static review confirms the helper reads schema/tracking before mutation, compares unknown SQLite storage to exact historical migration shapes including constraints, rejects unsupported partial shapes, stamps the safe 0001 baseline only after recognition, and runs upgrade head. Replaying idempotent 0002 repairs absent legacy memberships even when the table already exists. It never blindly stamps head. Existing tracked databases use normal Alembic upgrade. No new dependency or systemd behavior was added.

`.venv/Scripts/python.exe -m unittest discover -s tests -p test_setup_migrations.py -v` — **12 passed** (28.982 seconds). Actual helper subprocess execution covers fresh; tracked 0001/0002; unversioned 0001/0002; empty version table; current schema idempotency; missing legacy table; malformed column; partial board table; missing 0002 membership; and both seven-/eight-table real ORM-bootstrap shapes. Successful cases assert all four new tables, head revision, preserved item/upload metadata and original upload bytes, many-to-many membership and clean foreign keys. Rejected cases assert the entire logical SQLite dump unchanged, including no inserted revision marker.

Comment pass complete for added tests. `.venv/Scripts/python.exe -m compileall -q tests/test_setup_migrations.py scripts/migrate_database.py` passed. `C:/Users/Joey/scoop/apps/git/current/bin/bash.exe -n scripts/setup-linux-service.sh` passed. No real sudo/systemctl execution, live database access, or Linux service installation was performed.


Final full Python regression gate after the comment pass: `.venv/Scripts/python.exe -m unittest discover -s tests -v` — **34 tests passed** in 39.225 seconds, comprising the unchanged 22 application/migration regressions plus 12 installer tests. Existing **33 named Node tests** and HTTP/browser evidence remain unchanged; no redundant Node rerun was needed for Python/shell-only changes. Installer verification and overall implementation traceability were accepted in the completed PM audit. Linux service installation and live MySQL remain unexecuted.


