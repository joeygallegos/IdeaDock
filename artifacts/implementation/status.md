# Visual boards implementation status

Status: complete. PM accepted the implementation, independent verification, and the user-approved legacy installer fix. No pending scope decisions or browser blockers remain. No live database migration or service installation was performed.

## Scope and readiness

Authority: PLAN.md (all sections and acceptance criteria 1–23), with requirements.md as the existing product contract. Both read in full before delegation. PROJECT.md is absent. Project in the UI maps to Epic in the existing database. Preserve existing items, uploads, filters, and capture. No dependency changes authorized. No Git metadata exists here; baseline file hashes are recorded alongside this log. Do not migrate the user's live database during development.

Architecture: static Alpine/vanilla frontend → FastAPI thin routes → SQLAlchemy service layer → SQLite development/MySQL primary database. Alembic owns migration; uploads use local files with DB metadata. Board arrangements must remain separate from items and source files.

## Work packages and ownership

| Package / owner | Scope and plan trace | Files allowed | Dependencies | Acceptance gate |
| --- | --- | --- | --- | --- |
| A / backend agent | Sequence 1, backend portions of 2/4/5; ownership, boards, combined deck, revision conflicts, deletion safeguards. requirements.md §§6,11,12,16–21. | app/models.py, app/schemas.py, app/api/*, app/services/*, new alembic/versions/0003*, tests/test_boards_backend.py | Publish API contract before UI integration | AC 1–4,7–8,10–12,14,19 server behavior; isolated persistence/migration/failure tests |
| B / frontend agent | Sequence 2–5; complete focused workspace, board management, interactions, content, recovery, accessibility. requirements.md §§11,12,15,21. | app/static/*; tests/board_frontend* | Read A's frozen API contract before integration | AC 1–23 UI behavior; keyboard and browse-only mutation guards; syntax and behavioral checks |
| C / verification agent | Sequence 6 independent requirements audit and tests | tests except A/B-owned paths; artifacts/implementation/verification.md | Inspect initially; execute integration checks after A/B | Trace every PLAN functional requirement and AC; report unverified evidence candidly, test migration and regressions |
| PM / root | Contracts, scope review, integration, milestone traceability, documentation | artifacts/implementation/* except verification.md, README.md; minimal app/main.py integration if needed | Reviews A/B/C before acceptance | Tests and comment pass; documented operational workflow and limitations |

Agents must not edit outside ownership, add dependencies, or implement untraced features. Escalate genuine scope gaps/conflicts to PM; PM asks user with options and recommendation before scope changes. Other contributors are active: never revert others' work.

## Milestones and acceptance

1. Readiness / contract: complete. PLAN.md and requirements.md read in full before delegation; architecture mapped, baseline hashes recorded, API contract reviewed and released to frontend.
2. Persistence: accepted. Board ownership, layout persistence, asset lifecycle, atomic revision claims and complete-local-copy recovery verified by service, migration and HTTP tests. MySQL DDL compiles offline.
3. Workspace: accepted. Desktop and narrow browser workflows, controller tests, accessibility corrections, source readability and comment pass completed.
4. Recovery / integration: accepted. Two-tab conflicts, comparison prerequisite, safe initial focus, cancellation, complete local copy, confirmed latest and refreshed asset library verified. Earlier native-dialog browser blocker resolved.
5. Approved deployment extension: accepted. User explicitly approved the setup-script fix and legacy upgrade tests. Backend owned scripts/setup-linux-service.sh and scripts/migrate_database.py; verification owned tests/test_setup_migrations.py; PM owned README and final scope review. Known legacy schemas upgrade with data preserved; unknown/partial schemas stop without falsely recording a revision. Fresh and tracked installations remain covered. Trace: PLAN sequence 6 and requirements sections 18/20.
6. Final gate: accepted. 34 Python tests and 33 named Node tests passed; HTTP smoke, JavaScript syntax, Python compilation and Git Bash syntax checks passed. Comment pass completed before final checks. README and full requirement traceability are current.

## Decision and review history

- Existing UI project maps to Epic; no replacement project abstraction or new dependencies introduced.
- Historical board-specific asset access was separated from current references so legitimate local recovery survives moved sources and newer remote removal, without authorizing unrelated assets or blocking unused-source deletion. Trace: AC 7, 14 and 19.
- Review corrected save/navigation races, sub-threshold drag dirty tracking, dialog accessibility, menu stacking, zoom-independent 44px resize targets, responsive guidance and latest-recovery library refresh. Each correction stayed within board requirements.
- An obsolete asynchronous recovery test harness could exit before executing assertions. It was replaced by six named node:test cases; final evidence records 33 completed named tests.
- Installer scope was paused pending explicit approval under AGENTS.md. The user subsequently approved the narrow fix and tests, superseding the earlier blocked checkpoint. No service-management redesign was introduced.
- The installer recognizes complete historical SQLite schemas, replays the idempotent membership migration, then runs pending migrations. It rejects unknown or partial unversioned schemas without alteration. Twelve installer regressions include real ORM-bootstrap shapes and preserved upload bytes.
- Baseline review found changes confined to assigned feature files, documentation and the approved installer extension. Original migrations, plan, dependency files and live data were preserved.
- Existing unrelated product gaps, including tag filtering and legacy extension-only upload validation, remain catalogued in verification.md rather than silently added to scope.

## Verification limits and operational handoff

- Live MySQL execution, actual Linux service installation, backup/restore drills, physical touch, trackpad and assistive technology sessions were not performed. Offline MySQL DDL and Git Bash syntax checks do not substitute for those environments.
- Browser evidence uses disposable data at desktop 1280x900 and narrow 390x844. The 120-placement responsiveness check reused one small image and is not a benchmark for large distinct images.
- The disposable preview server was stopped and viewport overrides reset. No user database or uploads were used or migrated.
- README documents board workflows, coordinated database/upload backups and the safe legacy migration helper. No dependency changes required security advisory checks.
- No outstanding implementation work or user decisions remain within the approved scope.

## Requirement traceability

See verification.md for every PLAN functional row, acceptance criteria 1–23, and requirements.md sections 1–25 mapped to code, executed tests and explicit limits. Browser evidence is recorded in browser-verification.md. Existing unrelated gaps are distinguished from this implementation's acceptance. PM accepts the final traceability and installer verification gates.

## Follow-up: explicit project-to-board workflow (2026-10-24)

User clarification: boards belong to projects and exist only after explicit creation; desired flow is project -> board creation -> resources uploaded inside the board. PM implemented a focused navigation correction, traced to PLAN Navigation / Board Management / Adding Images, AC 1, 4 and 12.

Completed: home project selection now shows only that project's saved boards and Create board. All projects, including completed/empty ones, are selectable. Creation intent opens a naming dialog and cancellation writes nothing. Unscoped/invalid links do not silently pick a project. Existing board links open directly; Back to project retains selection. Item galleries are labeled Image attachments to distinguish them from named project boards. Upload controls require an open board; existing project-shared image ownership remains unchanged.

Files: app/static/index.html, app.js, boards.html, boards.js; tests/board_frontend.test.cjs; README.md. No backend/schema/dependency changes. Reviewed modified-code comments and reran syntax and tests: 40 named Node tests and all 34 Python tests passed. Browser verified empty project, cancelled creation, named creation, workspace upload controls, project return and direct reopening. Created test board only in disposable preview storage; no user board was created. Screenshot: project-board-flow.png. Main app remains running on port 8017.
