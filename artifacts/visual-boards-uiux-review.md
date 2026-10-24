# Project Visual Boards — UI/UX Review

This review covers the high-level wireframe only. It prioritizes issues that could materially affect task success before implementation begins.

## Priority Issues

| Priority | Issue | Why it matters | Recommended direction | Effort |
| --- | --- | --- | --- | --- |
| High | Pan and marquee selection compete for the same empty-canvas drag gesture. | Users need both navigation and multi-select, but the current interaction rules do not establish which behavior wins. Accidental canvas movement or selection will make arranging objects feel unreliable. | Make `Select` the default: dragging empty canvas draws a marquee. Pan with Space + drag, middle mouse, trackpad gestures, or a visible Hand tool. Show the active tool and cursor. | Medium |
| High | Save-conflict recovery stops at `Review options`. | The user knows a conflict exists but not how to preserve both versions safely. This is where trust can be lost. | Offer explicit, non-destructive choices: `Open latest`, `Keep my changes as a copy`, and—only after comparison—`Replace latest`. Never make overwrite the default. | Medium |
| High | Mobile browse-only scope is visually ambiguous. | The `Images` and `Details` tabs can imply that editing is available even though the plan limits smaller screens to browsing. | Mark the screen `View only` and ensure tabs expose read-only content. Hide editing controls and explain once that editing requires a larger screen. | Low |
| Medium | `+ Add` is too generic beside `+ Upload`. | Users must open it to discover text labels and swatches, and may not understand why images use a separate action. | Rename it `Add object` with menu items `Text label` and `Color swatch`, or expose those two tools directly when space allows. | Low |
| Medium | Multi-selection is supported but not discoverable in the visual flow. | It is an acceptance requirement, yet the UI gives no cue for Shift-click, marquee selection, or how many objects are selected. | Show `3 selected` in the contextual toolbar and provide a short first-use hint for Shift-click and marquee selection. | Low |
| Medium | The asset deck does not yet show the selected-asset state. | A non-drag path is required, but the wireframe only mentions it in guidance text. | On asset selection, reveal a compact preview with source, filename/caption, and a prominent `Add to board` action. Preserve scroll position after placement. | Medium |
| Medium | Icon-only undo, redo, overflow, and resize controls need stronger accessibility treatment. | Meaning and availability may be unclear to keyboard and screen-reader users; small handles can be difficult for motor-impaired users. | Provide accessible names and tooltips, visible focus, disabled states, 44×44 hit areas, keyboard move/nudge, and keyboard-accessible proportional resize. | Medium |
| Low | Board-card overflow actions are visually small and close to the open-card target. | Mis-clicks may open the board instead of exposing management actions. | Increase the overflow hit target without enlarging the icon, and keep the rest of the card as the open target. | Low |

## What Is Working

- The composition clearly dominates the desktop workspace.
- The neutral canvas protects image and color judgment while the surrounding chrome retains IdeaDock’s visual identity.
- Project-level boards are separated cleanly from note/task ownership.
- `Remove from board` is correctly distinguished from deleting a source image.
- Autosave is quiet in healthy states and specific when work needs attention.
- The image deck remains visible but collapsible, which supports both discovery and focused composition.

## Quick Validation Plan

Test the prototype with five short tasks:

1. Create a second board and switch back to the first.
2. Add the same image twice without dragging.
3. Select three objects, move them, then pan the canvas.
4. Recover from a simulated save conflict without losing either version.
5. Open the board on a narrow screen and explain whether editing is available.

Watch for hesitation around `Add object`, accidental panning during selection, and uncertainty about whether changes are safely saved.
