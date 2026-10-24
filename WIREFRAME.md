# Project Visual Boards — UX Wireframe

Status: high-level UX direction; not an implementation specification.

This wireframe translates the product requirements in `PLAN.md` into a focused visual-board workflow and applies the visual character in `DESIGN.md` to the surrounding interface. The canvas itself remains neutral so the product chrome does not distort judgments about imagery and color.

## Experience Model

```text
Project
   └── Visual boards
          ├── Open an existing board
          └── Create a named board
                    ↓
             Focused board workspace
                    ↓
        Arrange images, text, and swatches
                    ↓
             Autosaved project reference
```

The workspace has one dominant task: composing the board. Asset browsing and editing controls remain close at hand but visually secondary. Project tasks, capture controls, and project metadata are absent while editing.

## 1. Project Entry — Visual Boards

Visual boards should appear as a project destination, not as an attribute of one note or task.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│  IDEA DOCK  /  Project name                                                 │
│                                                                              │
│  Project name                                                               │
│  [Overview]  [Notes & tasks]  [Visual boards]                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Visual boards                                            [+ New board]      │
│  Saved visual directions for this project.                                   │
│                                                                              │
│  ┌─────────────────────────┐   ┌─────────────────────────┐                   │
│  │ [board preview mosaic]  │   │ [board preview mosaic]  │                   │
│  │                         │   │                         │                   │
│  │ Launch direction        │   │ Photography references │                   │
│  │ Edited 12 min ago       │   │ Edited yesterday       │                   │
│  └─────────────────────────┘   └─────────────────────────┘                   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

UX notes:

- Selecting the `Visual boards` project destination reveals every board, including boards for completed projects.
- The board preview and name are one large open target. Rename, duplicate, and delete live in a secondary overflow menu.
- `New board` is the single emphasized action. Creation asks only for a name, then opens the workspace.
- Do not show editing tools here. This screen is for choosing or creating a board.

### First-board empty state

```text
                         No visual boards yet

          Collect project images, colors, and short notes in one place.
                             [+ Create board]
```

Keep this concise. Do not introduce a sample board or a large marketing illustration.

## 2. Board Workspace — Default Desktop

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ Project   [Launch direction ▾]         Saved      ↶ Undo  ↷ Redo   •••   │
├──────────────────────┬───────────────────────────────────────────────────────┤
│ PROJECT IMAGES       │                                                       │
│                      │                 NEUTRAL CANVAS                        │
│ [Search images…]     │                                                       │
│                      │         ┌──────────────────────┐                      │
│ [+ Upload] [Add ▾]   │         │                      │    ┌──────────────┐  │
│                      │         │       image          │    │    image     │  │
│ ┌──────┐ ┌──────┐    │         │                      │    └──────────────┘  │
│ │ img  │ │ img  │    │         └──────────────────────┘                      │
│ └──────┘ └──────┘    │                    ┌───────────────────┐              │
│ Note title  Task…    │                    │ “Visual direction”│              │
│                      │                    └───────────────────┘              │
│ ┌──────┐ ┌──────┐    │                                ┌────────┐             │
│ │ img  │ │ img  │    │                                │ swatch │             │
│ └──────┘ └──────┘    │                                └────────┘             │
│ Project    Note…     │                                                       │
│                      │                                                       │
│          [‹ Collapse]│                                                       │
├──────────────────────┴───────────────────────────────────────────────────────┤
│                                 [−]  72%  [+]   [Fit board]                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Hierarchy

1. **Primary — canvas:** occupies most of the viewport and receives the eye first.
2. **Secondary — image deck:** provides ingredients without competing with the composition.
3. **Tertiary — top and bottom chrome:** board identity, persistence, history, and view controls.

### Top bar

- `Project` returns to the project without implying that the board is closed or exported.
- The board name opens a switcher with other boards and a `New board` action. Rename remains in the overflow menu.
- Save state is quiet when healthy: `Saving…`, `Saved`, or a meaningful failed state.
- Undo and redo remain visible but subdued; disable them when no history is available.
- Destructive and infrequent actions such as delete board stay in the overflow menu.

### Image deck

- Show a compact thumbnail grid with a short source label: project upload, note title, or task title.
- Selecting a thumbnail reveals a larger preview and `Add to board`; dragging is an additional shortcut, not the only path.
- Search filters by filename, caption, and source title. More advanced filters can remain undisclosed in the first version.
- `Add` opens a small menu for `Text label` and `Color swatch`. Image upload has its own visible action because it is frequent and works even when the deck is empty.
- Collapsing the deck leaves a narrow reopen control and gives its width back to the canvas.
- Do not imply that dragging an image removes it from the deck.

### Canvas

- Use an off-white or very light neutral surface without blue/violet tint, decorative orbs, shadows, or glass effects.
- Reserve atmospheric gradients and translucent surfaces for the top bar and deck.
- The pointer moves objects by default. Panning uses the canvas background, middle mouse/trackpad gesture, or an explicit temporary pan control.
- Drop location determines placement. Paste places the image near the center of the visible viewport.
- Multiple placements may reference the same source image; the deck does not mark an image as “used up.”

### Canvas navigation

- Keep zoom controls anchored near the bottom-right of the canvas.
- `Fit board` brings every object into view without changing stored object positions or sizes.
- The percentage is a view state, not board content.

## 3. Selection and Editing

Object editing is contextual. Controls appear only when something is selected.

```text
                    ┌──────────────────────────────┐
                    │ Duplicate  ↓ Back  ↑ Front  │
                    │                    Remove    │
                    └──────────────────────────────┘

              ┌───────────────────────────────────┐
              │                                   │
              │          selected image           │
              │                                   │
              └───────────────────────────────────┘
                 ◉                             ◉
```

- Place the contextual toolbar near the selection when space permits, while preventing it from covering resize handles.
- Use a single blue-violet selection outline, visible resize handles, and a non-color-only selected state.
- Image resizing remains proportional.
- Multi-select shows a group boundary and only actions that apply to the entire group: move, duplicate, layer, and remove.
- Label selection replaces image-specific controls with concise text controls.
- Swatch selection exposes color value, picker, and `Sample from image`.

### Remove language

The contextual action is explicitly `Remove from board`. Permanent deletion of a source image belongs in the project library and must explain which boards reference it. These actions should never look or sound interchangeable.

## 4. Adding a Color Swatch

```text
┌────────────────────────────────────┐
│ Color swatch                       │
│                                    │
│ [ color field ]  Hex [ #635BFF ]  │
│                                    │
│ [Sample from image]       [Done]   │
│ Invalid hex. Previous color kept.  │  ← shown only when needed
└────────────────────────────────────┘
```

- This is a compact popover rather than a full modal because the canvas must remain visible for comparison.
- `Sample from image` enters a temporary, clearly labeled mode: `Choose a color from an image · Esc to cancel`.
- Clicking an image creates or updates the swatch and exits sampling mode.
- Invalid input never replaces the last valid color.

## 5. Empty Board and Empty Deck

### Empty board with available images

```text
┌──────────────────────┬───────────────────────────────────────────────────────┐
│ PROJECT IMAGES       │                                                       │
│ [thumbnail grid]     │              Start this visual direction              │
│                      │                                                       │
│                      │       Drag an image here, or select one and choose     │
│                      │                       Add to board.                    │
│                      │                                                       │
│                      │             [Upload image]  [Add text]                │
└──────────────────────┴───────────────────────────────────────────────────────┘
```

The empty canvas provides a keyboard-friendly next step and upload option without becoming a large decorative card.

### Empty image deck

```text
PROJECT IMAGES

No project images yet.
Upload an image, drop one on the canvas,
or paste from your clipboard.

[Upload images]
```

Text labels and swatches remain available even when no images exist.

## 6. Save, Upload, and Recovery States

Healthy autosave stays quiet. Problems receive emphasis because they affect trust.

```text
Healthy:       Saved
In progress:   Saving…
Failed:        Couldn't save — your changes are still here. [Retry]
Conflict:      This board changed in another tab. [Review options]
Leaving:       Unsaved changes are still being retried. Leave anyway?
```

- Never replace the canvas with a loading screen during background save.
- Preserve unsaved work in the current session after failure.
- For multiple uploads, show progress and failure on each asset; one failed file does not invalidate successful files.
- A missing source image keeps its position and dimensions as a labeled placeholder so the composition does not collapse.

## 7. Board Switcher

```text
┌────────────────────────────────────┐
│ Switch board                       │
│                                    │
│ ✓ Launch direction                │
│   Photography references          │
│   Packaging studies               │
│ ────────────────────────────────── │
│ + New board                        │
└────────────────────────────────────┘
```

Use a compact switcher from the title rather than a persistent second navigation rail. Board management actions remain secondary to opening a board.

## 8. Smaller Screens

The first version protects browsing and review rather than forcing desktop editing into a narrow viewport.

```text
┌──────────────────────────────┐
│ ‹ Project       Launch…  ••• │
├──────────────────────────────┤
│                              │
│       BOARD — FIT VIEW       │
│                              │
│  Pinch to zoom · Drag to pan │
│                              │
├──────────────────────────────┤
│ [Images] [Objects] [Details] │
└──────────────────────────────┘
```

- Open in fit-to-board browse mode.
- Allow pan and zoom for inspection.
- The deck moves into a bottom sheet or full-height drawer.
- Editing controls are hidden or clearly disabled with concise guidance to use a larger screen; do not present a half-functional editor.
- Keep back navigation, board identity, and save status visible.

## Visual Emphasis

- **One strong accent:** blue-violet for primary actions, selection, and focus.
- **Quiet chrome:** translucent white surfaces, subtle tinted borders, and restrained shadow around the workspace shell.
- **Neutral creative field:** no ambient color inside the canvas.
- **Typography:** Fraunces may identify the board on entry screens; dense workspace controls use Manrope for clarity.
- **Shape:** retain LoopList rounding on outer chrome and popovers, but avoid wrapping every control group in another card.
- **Motion:** short toolbar/popover entrances and subtle hover lift only. Object movement follows the pointer directly without decorative animation.

## Key Interaction Rules

| User intent | Primary path | Non-drag alternative |
| --- | --- | --- |
| Place an existing image | Drag thumbnail to canvas | Select thumbnail → `Add to board` |
| Add a new image | Drop or paste on canvas | `Upload` from deck |
| Add text | `Add` → `Text label` | Keyboard-accessible Add menu |
| Add a swatch | `Add` → `Color swatch` | Enter a hex or sample an image |
| Move around board | Pan canvas background / trackpad | Temporary pan control |
| Remove content | Select → `Remove from board` | Delete/Backspace when not typing |
| Recover the view | `Fit board` | Keyboard-accessible canvas controls |

## Intentional Focus

1. **The composition** is always the strongest visual element.
2. **The next useful input**—project images—is visible but collapsible.
3. **Persistence problems** interrupt the otherwise quiet status treatment only when the user needs to act.

Everything else is progressively disclosed so the workspace feels like a creative surface, not an administration dashboard.
