# Requirements.md

## 1. Product Summary

A single-user, self-hosted personal backlog app for quickly capturing ideas, tasks, notes, and someday items, organizing them by epic, linking them to people or entities, and reviewing them later through multiple presentation views.

The app is intended to run on a small server on the local network only. It will use a Python backend, a MySQL database, and a lightweight frontend built with Alpine.js, Tailwind CSS, and vanilla JavaScript.

The product must optimize for fast capture, clean filtering, flexible organization, and future support for alternate view modes such as Kanban.

---

## 2. Primary Goals

1. Capture thoughts and todos in seconds.
2. Organize items by epic and related entities.
3. Support quick-entry syntax for structured capture.
4. Make it easy to filter, search, review, and revisit items.
5. Support visual inspiration through mood boards.
6. Keep the architecture flexible enough to add alternate views later.

---

## 3. Non-Goals for v1

The following are explicitly out of scope for v1:

- Multi-user support
- User authentication and user sessions
- Cloud sync
- Mobile apps
- Push notifications
- Rich team collaboration
- Comments / activity feeds
- Full CRM/contact management
- Natural language date parsing
- Drag-and-drop Kanban implementation in v1

Kanban and other specialized views should be supported by the architecture, but do not need to be implemented in the initial release.

---

## 4. Core Product Principles

1. Capture must stay fast.
2. The system must not require perfect organization up front.
3. Search and filtering must be strong.
4. The data model must support multiple views over the same underlying objects.
5. Visual content must be treated as a first-class part of some items.
6. The app must remain simple enough to self-host and maintain.

---

## 5. Core Object Model

### 5.1 Epic

An epic is a top-level organizational bucket.

Examples:
- House
- Personal
- Money
- Health
- Work
- Family
- Shopping

Each item may belong to one or more epics. Items may also exist without an epic and remain in Inbox/Unassigned state.

### 5.2 Item

An item is the central object in the system.

Each item represents one of the following:
- Task
- Idea
- Note
- Someday

Items are the primary records displayed in all views.

### 5.3 Entity

An entity represents a person, company, vendor, service, or other external actor connected to an item.

Examples:
- Mom
- Chase
- HOA
- Contractor
- Dentist Office

Entities are used for filtering, grouping, and dependency tracking.

### 5.4 Tag

Tags are lightweight labels used to support secondary grouping and filtering.

Examples:
- quick
- outdoor
- urgent
- phone-call

### 5.5 Mood Board Asset

A mood board asset is an image associated with an item for inspiration, planning, or visual reference.

Mood board support is required for items that benefit from visual thinking, similar to Pinterest- or Tumblr-style image grids.

Examples:
- Backyard inspiration images
- Bathroom remodel concepts
- Outfit ideas
- Party theme references
- Furniture or design combinations

### 5.6 View Definition

The system must support multiple ways to render the same items.

Examples:
- List view
- Card view
- Board/Kanban view
- Timeline-like view
- Mood board-centric view

View mode must be treated as a presentation concern, not a separate data model.

---

## 6. Object Relationships

- One Epic can have many Items.
- One Item can belong to many Epics.
- One Item can have many Tags.
- One Tag can belong to many Items.
- One Item can link to many Entities.
- One Entity can link to many Items.
- One Item can have many Mood Board Assets.
- One Item can be displayed in multiple view modes.

### Relationship Intent

- Epic organizes an item by life area and an item may span multiple life areas when needed.
- Entity adds relationship context such as waiting on, involved, or reference.
- Tag adds lightweight labels.
- Mood Board Assets add visual context.
- Views are renderings of the same items, not separate records.

---

## 7. Item Types

The system must support the following item types:

- `task`
- `idea`
- `note`
- `someday`

### Rules

- Type is optional during quick capture.
- If omitted, default type is `idea`.
- Users must be able to change item type later.
- Items must retain their identity even if their type changes.

---

## 8. Item Statuses

The system must support these statuses:

- `inbox`
- `next`
- `doing`
- `waiting`
- `done`

### Rules

- Newly created items default to `inbox`.
- `waiting` indicates the item is blocked or dependent on an external entity.
- `done` is valid for tasks and optionally available for ideas/notes if the user chooses to close them.
- Completed items must remain queryable and filterable.
- Users must be able to reopen completed items.

---

## 9. Quick Entry Syntax

The app must support structured quick capture through inline tokens.

### Supported Syntax

```text
Title text #epic -type @entity !priority due:YYYY-MM-DD
```

### Examples

```text
Call bank about payoff #money -task @chase !high due:2026-04-20
Idea for backyard bar lighting #house -idea
Keep HOA notes #house -note @hoa
Ask mom about Easter dessert #personal -task @mom
```

### Token Meanings

- `#epic` → assigns or references an epic
- `-type` → sets item type
- `@entity` → links an entity to the item
- `!priority` → sets priority
- `due:YYYY-MM-DD` → sets due date

### Supported Types

- `-task`
- `-idea`
- `-note`
- `-someday`

### Supported Priorities

- `!low`
- `!med`
- `!high`

### Parsing Rules

- Token order may be arbitrary.
- Unknown tokens must not crash creation.
- The raw input string must be stored with the item.
- Parsed tokens must be normalized before persistence.
- Missing entities may be auto-created.
- Missing epics may be auto-created or flagged for user review depending on configuration.
- Remaining non-token text becomes the item title.
- A future enhancement may allow details/body parsing, but v1 only requires title extraction.

---

## 10. Entity Requirements

Entities must be first-class records, not just freeform strings.

### Entity Types

Supported entity types must include:
- person
- family
- friend
- vendor
- company
- service
- team
- other

### Entity Link Roles

An item-to-entity link must support a role field.

Supported roles for v1:
- `waiting_on`
- `involved`
- `reference`

### Blocking Flag

An item-to-entity link must support a boolean flag for blocking/dependency status.

### Examples

- Roof quote task linked to Contractor as `waiting_on`
- Insurance task linked to Chase as `involved`
- House note linked to HOA as `reference`

### Rules

- An item may link to multiple entities.
- An entity may link to many items.
- Entities must be filterable.
- Inactive entities must remain available historically for old records.

---

## 11. Mood Board Requirements

Some items must support a visual mood board made of multiple images.

### Purpose

Mood boards help the user visualize ideas that are not well represented by text alone.

### Examples of use cases

- Home improvement inspiration
- Remodel planning
- Party themes
- Clothing or style combinations
- Backyard design
- Decor concepts

### Mood Board Capabilities for v1

- Attach multiple images to an item
- Display images in a tiled visual grid
- Support mixed image sizes or aspect ratios without breaking layout
- Allow image captions or notes
- Allow sorting or manual ordering of images
- Allow removing images from a board
- Allow opening an image in a larger preview

### v1 Constraints

- Local uploads only
- No external scraping integrations required
- No built-in Pinterest import required
- No AI image generation required as part of the product

### Design Requirement

Mood board display should feel visually closer to a masonry/tile grid than a plain attachment list.

---

## 12. View System Requirements

The architecture must support multiple renderings of the same underlying item dataset.

### v1 Required Views

- Standard list view
- Basic card/grid view
- Item detail view
- Mood board section within item detail when applicable

### Future View Support (must be planned for)

- Kanban / board view
- Priority-oriented view
- Timeline / due-date-oriented view
- Entity-centric view
- Epic-centric dashboard view

### Architectural Rule

View choice must not change the underlying data model. Views are presentation modes over shared item records.

### Implication for Architecture

- API responses must provide enough normalized data for multiple frontend view types.
- Frontend state must treat view mode as a UI concern.
- Backend must not hardcode a single list-based assumption into its endpoints.

---

## 13. Filtering and Search Requirements

Filtering is a core feature and must be treated as part of the product, not an afterthought.

### Filterable Fields

The system must support filtering items by:
- epic
- item type
- status
- entity
- blocking status
- priority
- due state
- tags
- pinned
- archived state
- presence of mood board assets

### Search

Search must support title and details at minimum.

Future expansion may include search across:
- tags
n- entity names
- epic names
- image captions

### Filter Behavior

- Filters should compose cleanly.
- Default behavior should use AND logic between active filters.
- Sort order should be explicit and predictable.

---

## 14. Review Workflow Requirements

The app must include a review workflow to prevent the system from becoming a junk drawer.

### Review Page Goals

Surface items that need attention, such as:
- inbox items
- overdue tasks
- items waiting on others
- stale items not updated recently
- items missing an epic
- items missing useful metadata
- ideas with no follow-up

### Review is required because

Without review, capture becomes clutter instead of a usable system.

---

## 15. Frontend Requirements

### Stack

- Alpine.js
- Tailwind CSS
- Vanilla JavaScript

### Frontend Principles

- Keep JavaScript lightweight.
- Avoid heavy SPA frameworks.
- Frontend must consume the REST API rather than rely on server-rendered data templates.
- The frontend may be served by the Python backend, but data loading must happen through API calls.

### UI Requirements

The interface must support:
- Quick capture input
- Item list rendering
- Filter controls
- Inline state changes where practical
- Item detail view
- Mood board grid rendering
- Responsive layout for desktop and smaller screens

---

## 16. Backend Requirements

### Stack

- Python
- FastAPI
- SQLAlchemy
- Alembic
- MySQL

### Backend Principles

- REST API first
- Thin route layer
- Business rules in service layer
- Clean validation and predictable response shapes
- Support extensibility for future view types

### Required API Domains

- Items
- Epics
- Entities
- Tags
- Mood board assets
- Parser / quick-entry preview
- Review summaries

---

## 17. Data Storage Requirements

### Database

- MySQL is the primary system of record.
- Data must be structured for long-term use and schema evolution.
- Migrations are required.

### Images / Mood Board Assets

For v1, the system must define where uploaded image files live.

Recommended options:
- Local filesystem with metadata in MySQL
- or object-like local storage path managed by the app

The DB should store metadata, not raw image blobs, unless there is a strong reason otherwise.

### Metadata for Mood Board Asset

At minimum:
- item relationship
- file path
- original filename
- sort order
- caption
- created_at

---

## 18. Deployment Requirements

### Runtime Model

- Single user only
- Local network only
- Runs on a small always-on server
- No login or session support required

### Operational Requirements

- Must run reliably as a service
- Must support environment-based configuration
- Must support DB migrations on deploy/update
- Must support static asset serving

### Hosting Assumption

The app should be accessible only from the local network unless intentionally exposed later.

---

## 19. Security Requirements

Even though the app is local-network only, it must not assume the network is inherently safe.

### Minimum Requirements

- Bind only to intended interfaces
- Restrict exposure to local network
- Lock down CORS
- Validate uploaded files
- Sanitize filenames and file paths
- Prevent directory traversal through upload handling
- Validate API inputs strictly

### Strong Recommendation

Place the app behind a simple reverse proxy if needed for cleaner internal hosting.

---

## 20. Backup and Recovery Requirements

The app must support practical recovery from server or database failure.

### Required considerations

- MySQL backup strategy
- restore procedure
- uploaded image backup strategy
- schema migration safety
- export/import strategy for core data

### Rule

Images and DB records must be backed up together or in a coordinated way, otherwise mood boards become broken references.

---

## 21. Extensibility Requirements

The app must be designed so the same underlying items can later be rendered in different views without schema redesign.

### This means

- View mode must not be hardcoded into the item schema in a brittle way.
- API contracts must support multiple clients or multiple page renderings.
- Frontend components should be designed so list, card, and board views can consume shared item data.
- Mood board support must remain compatible with future project-oriented and Kanban-style layouts.

---

## 22. Suggested v1 Screens

1. Dashboard
2. Inbox / All Items
3. Epic Detail
4. Entity Detail
5. Item Detail
6. Review Page
7. Settings / Admin

### Dashboard should show

- inbox count
- waiting items
- overdue items
- recent captures
- items with mood boards
- activity by epic

---

## 23. Suggested v1 Build Order

1. Finalize schema and migrations
2. Implement core item/epic/entity/tag models
3. Implement item CRUD and filtering API
4. Implement quick-entry parser endpoint
5. Implement Alpine/Tailwind frontend shell
6. Implement list and detail pages
7. Implement entity linking and filtering
8. Implement mood board upload/display
9. Implement review workflow
10. Harden deployment, backup, and upload handling

---

## 24. v1 Success Criteria

v1 is successful if the user can:

1. Capture an item in a few seconds
2. Assign or infer epic/type/entity through quick syntax
3. Filter items reliably by epic, entity, status, and priority
4. Open an item and attach/view a useful mood board
5. Review neglected and blocked items
6. Use the app comfortably on the local network without auth/session complexity
7. Extend the app later with alternate views without redoing the data model

---

## 25. Final Product Positioning

This product is a single-user, self-hosted personal backlog and inspiration app that combines structured capture, dependency-aware organization, strong filtering, and visual mood boards, while leaving room for future alternate views such as Kanban without changing the core data model.
