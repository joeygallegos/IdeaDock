# Project Visual Boards Plan

Status: requirements and design plan; implementation has not started.

## Goal

Provide a focused page where a user can open a project, browse its uploaded images in a left-side deck, and arrange images, text labels, and color swatches on an open canvas to explore mood boards and visual directions.

Images remain independently editable placements. Combining them on a board does not flatten them into a single image or modify the original uploads.

## Functional Requirements

| Area | Requirement |
| --- | --- |
| Navigation | Project → Visual boards → Open or create a named board. |
| Boards | Multiple named boards per project. |
| Workspace | A focused screen with an open canvas, pan, and zoom. |
| Image deck | A left-side deck containing uploads from all project notes/tasks and images uploaded directly to the project. |
| Adding images | Drag images from the deck, upload files, drop files, or paste images from the clipboard. |
| Image ownership | Images uploaded from a board belong to the project and are reusable on every board in that project. |
| Arrangement | Move, resize proportionally, overlap, and change image layer order. Basic arrangement is sufficient for the first version. |
| Other objects | Editable text labels and color swatches. |
| Swatches | Select a color manually, enter a hex code, or sample a color by clicking inside an image. |
| Intended use | Keep boards in IdeaDock as saved visual references. |
| Input model | `Select` is the default tool. Empty-canvas drag creates a marquee; panning requires Space-drag, middle-mouse drag, a trackpad pan gesture, or the visible `Hand` tool. |
| Non-drag access | Every core action, including placing an asset, selecting, moving, proportionally resizing, and removing an object, has a keyboard-accessible path. |
| Smaller screens | Smaller screens open boards in an explicitly labeled, browse-only `View only` mode with pan and zoom but no editing actions. |
| Recovery | Save conflicts preserve local edits until the user makes an explicit, confirmed choice to open the latest version, keep local changes as a board copy, or compare before replacing the latest version. |

## Proposed Screen Layout

- **Slim top bar:** Back to project, board name/switcher, save status, undo, and redo.
- **Collapsible left deck:** Project image thumbnails, source note/task where applicable, and a selected-asset preview with `Add to board`.
- **Main canvas:** A large neutral workspace with freely positioned objects.
- **Selection toolbar:** Relevant controls for selected objects, including duplicate, layer order, and remove.
- **Canvas navigation:** Zoom controls, zoom percentage, and Fit board.

The canvas occupies most of the screen. Hide the normal task list, capture box, and project metadata while working. Use a neutral canvas background so interface colors do not influence judgments about the images.

## Proposed Interaction Rules

These are the first-version functional interaction decisions.

### Board Management

- Create, rename, reopen, duplicate, and delete named boards.
- On the board list, the full card body—preview, name, metadata, and surrounding surface—forms one large open target. A separate overflow button opens `Rename`, `Duplicate`, and `Delete` without opening the board.
- The overflow button has a minimum 44 by 44 CSS-pixel pointer or touch target, a board-specific accessible name, and its own keyboard focus stop.
- Duplicating a board creates an independent arrangement that references the same source images.
- Deleting a board preserves its source uploads.
- Existing boards remain reachable after all project tasks are completed.

### Adding Images

- Dragging from the deck creates a placement at the drop location and leaves the source image in the deck.
- Allow multiple placements of the same image on one board and reuse across boards.
- Dropping files onto the canvas uploads them to the project library and places them near the drop location.
- Uploading into the deck adds images to the library without automatically placing them on the canvas.
- Pasting an image uploads it to the project library and places it within the visible canvas area.
- Pasting while editing a text label retains normal text-editing behavior.
- Selecting a deck thumbnail shows a persistent selected state and a compact preview with the image, source, filename or caption, and a prominent `Add to board` action.
- `Add to board` places the selected asset near the center of the visible canvas as an alternative to dragging, while preserving the deck's selection and scroll position so the action can be repeated.
- Include uploads from completed project items; do not inherit the dashboard's active-work filter.
- Show each asset once in the deck, even when project membership is represented through multiple relationships.

### Selecting and Arranging

- `Select` is the default and visibly active tool. Primary-button drag on empty canvas draws a marquee, and clicking empty canvas clears the current selection.
- Shift-click toggles an object in the selection. Shift-drag adds objects inside a marquee to the current selection; an unmodified marquee replaces it.
- Pan with Space plus primary-button drag, middle-mouse drag, a trackpad pan gesture, or the visible `Hand` tool. Space is temporary; choosing `Hand` keeps pan active until the user returns to `Select`.
- The active tool has a distinct pressed state and matching cursor so an empty-canvas drag never has an ambiguous result.
- Select one or multiple objects and clearly indicate the selection.
- When multiple objects are selected, show a group boundary and a count such as `3 selected` in the contextual toolbar.
- On first multi-selection use, show a dismissible hint for Shift-click and marquee selection; do not require the hint to proceed.
- Move, duplicate, or remove selected objects together.
- Preserve image proportions when resizing.
- Arrow keys move a selected object or group by one canvas unit; Shift+Arrow moves it by ten. A keyboard-focused resize handle or equivalent size control uses Arrow keys to resize images proportionally, with Shift+Arrow providing the larger step.
- Allow overlapping images and changes to layer order.
- Removing an object from a board removes only that placement, not its source upload or placements on other boards.

### Text and Color

- Add and edit short text labels.
- Label the creation control `Add object`; its menu items are `Text label` and `Color swatch`. Keep image upload as the separate `Upload images` action.
- Create swatches with a color picker or a valid hex value.
- Sampling enters a temporary picker mode: click inside an image to create a swatch, or press Escape to cancel.
- Invalid color input produces a clear validation message without discarding the previous valid color.

### Canvas Navigation

- Pan with the defined alternate gestures or `Hand` tool and zoom without changing saved object positions or sizes.
- Fit board brings all objects into view.
- Reopening a board restores its saved arrangement and last canvas view.
- Collapsing the image deck provides additional workspace.

## Saving and Recovery

- Automatically save completed edits.
- Display clear Saving, Saved, and Couldn't save—Retry states.
- Never report success before the server confirms persistence.
- Preserve unsaved edits in the current session after a failed save and offer retry.
- Warn before leaving with unsaved changes.
- Provide undo/redo for additions, movement, resizing, layer changes, text/swatches, and removals during the current editing session.
- Detect a conflicting save from another tab before writing, pause autosave for that board, retain the current local edits, and never silently overwrite the newer saved version.
- Present three clear recovery paths: `Open latest`, `Keep my changes as a copy`, and `Compare versions`.
- `Keep my changes as a copy` is the emphasized safe choice; it creates a new named board from the complete local state and leaves the latest saved board unchanged.
- `Open latest` explains that the current local edits will be left behind and requires confirmation before loading the latest saved version.
- `Replace latest` is available only after `Compare versions`, explains which version will be replaced, requires confirmation, and is never the default or focused action.
- Keep the conflict state and local edits intact if the user dismisses recovery or a recovery action fails, and provide a retry path.

## Image Ownership and Lifecycle

### Current Behavior

Uploads currently belong to individual notes/tasks. The existing Mood Board Focus view displays one item's image gallery; it does not save freeform arrangements.

### Required Extension

- Introduce project-owned uploads for images added directly from a board.
- Combine project-owned uploads and uploads attached to project notes/tasks into one deck.
- Preserve existing item-upload ownership and behavior.
- Save board placements as references to source assets plus layout information, rather than copying image files for every placement.
- Keep board layout data separate from the underlying notes/tasks; a board does not duplicate those records.

### Proposed Safeguards

- Distinguish Remove from board from permanent source-image deletion.
- Block permanent deletion of a source image while boards use it, and identify the affected boards.
- Moving a source note/task out of a project updates the available deck but preserves existing board placements.
- If a source image cannot be loaded, show a clear placeholder without losing the placement or disrupting the rest of the board.

## Usability and Accessibility

- Desktop-first editing; smaller screens open in fit-to-board browse mode with a persistent `View only` label.
- In `View only`, allow pan, zoom, board switching, and read-only image/object/detail drawers. Hide or disable every mutating control, and show concise guidance once that editing requires a larger screen.
- Provide visible, high-contrast keyboard focus for every interactive control and canvas object.
- Give every icon-only action, including undo, redo, board overflow, canvas tools, zoom controls, and resize handles, an accessible name and a tooltip shown on hover and keyboard focus.
- Disabled controls remain identifiable, expose their disabled state to assistive technology, and do not receive an actionable focus state.
- Use a minimum 44 by 44 CSS-pixel pointer or touch target for icon-only controls and resize handles; the visible icon or handle may be smaller than its hit area.
- Support keyboard alternatives for adding, selecting, moving, proportionally resizing, and removing objects.
- Do not intercept board shortcuts while the user is typing in a text field.
- Empty board: explain both paths—drag an image, or select one and choose `Add to board`—and offer `Upload images`, `Add text label`, and `Add color swatch` actions.
- Empty deck: offer upload and paste guidance.
- Show per-file upload progress and failures; successfully uploaded files remain usable when another file fails.
- Keep selection controls contextual and the overall interface focused.

## Outside the First Version

- Cropping and rotation.
- Freehand drawing, shapes, and connectors.
- Automatic palette generation and AI image blending.
- Automatic layouts.
- Real-time collaboration.
- Image export, public sharing, and a separate presentation mode.
- Full mobile editing.

## Implementation Sequence

1. **Persistence and ownership:** Define project boards, project-owned assets, placement references, layout fields, and save-conflict handling. Plan the migration while preserving existing uploads.
2. **Project entry and image deck:** Add board navigation, named-board management, the focused page, and combined project image browsing. Ensure completed projects' boards remain accessible.
3. **Canvas interaction:** Add image placement, selection, multi-selection, movement, proportional resize, layer ordering, pan, zoom, and Fit board.
4. **Content creation:** Add direct upload/drop/paste, text labels, manual swatches, and image color sampling.
5. **Reliability and accessibility:** Add autosave, undo/redo, save errors, deletion safeguards, keyboard alternatives, and empty/loading/error states.
6. **Verification and documentation:** Verify the acceptance criteria and failure cases, review modified-code comments, and update README with the new workflow and operational details.

Use the existing architecture and helpers where practical. No new dependencies are selected by this plan; adding any requires the repository's dependency review and approval process.

## Acceptance Criteria

1. Create two named boards in one project and reopen either board independently.
2. See uploads from the project's notes/tasks, including completed items, alongside direct project uploads.
3. Use the same image on both boards with different sizes, positions, and layer orders without changing the source image.
4. Drop or paste a new image onto one board and find it in the project deck from the other board.
5. Add text labels and swatches using manual selection, hex entry, and image sampling.
6. Select multiple objects and move, duplicate, or remove them together.
7. Remove a placement without deleting the source image or affecting other placements.
8. Close and reopen a saved board with its composition and canvas view preserved.
9. Undo and redo supported edits during an editing session.
10. Clearly report failed uploads and saves, retain current unsaved edits, and support retry without misleading success states.
11. Detect a save conflict between two tabs without silently overwriting newer changes.
12. Reach existing boards after all project tasks are completed.
13. Pan, zoom, and Fit board without changing object layout data.
14. Prevent source-image deletion while a board references it and identify where it is used.
15. Complete core add/select/move/remove actions without requiring drag-and-drop.
16. With `Select` active, drag empty canvas to marquee-select; then pan the same board with Space-drag, middle-mouse drag, a trackpad gesture, and the visible `Hand` tool without moving or selecting objects.
17. Use Shift-click and Shift-marquee to extend a selection, see the exact selected-object count, and dismiss the first-use multi-select hint without blocking the task.
18. Select an asset in the deck, review its source and filename or caption, and use `Add to board` repeatedly without losing the deck selection or scroll position.
19. Resolve a simulated save conflict by opening the latest board or keeping local edits as a copy; reach `Replace latest` only through comparison and explicit confirmation, with no local edits lost on dismissal or recovery failure.
20. On a smaller screen, immediately identify the board as `View only`, inspect it with pan/zoom and read-only drawers, and find no enabled editing action.
21. Use the `Add object` control to create a `Text label` and `Color swatch` without confusing either action with `Upload images`.
22. Operate icon-only actions and resize handles by keyboard, pointer, or touch: names and tooltips are available, focus is visible, disabled states are conveyed, targets are at least 44 by 44 CSS pixels, and image resizing remains proportional.
23. Open a board by activating its preview or name, and open its management menu from the distinct 44 by 44 CSS-pixel overflow target without opening the board.

## Verification Plan

- Test persistence and reload of every supported object type and layout property.
- Test project image collection, asset deduplication, completed items, and project isolation.
- Test direct uploads and paste alongside the existing item-upload workflow.
- Test placement removal, board deletion, source deletion safeguards, and source-item project changes.
- Test pan/zoom coordinate handling when adding and moving images at different zoom levels.
- Test the Select/Hand state and cursor, marquee replacement, Shift-click/Shift-marquee extension, selection count, Space-drag, middle-mouse drag, trackpad pan, and first-use hint dismissal.
- Test failed uploads, failed saves, retries, missing images, and conflicting tab edits. For conflicts, exercise each recovery path, confirmation, dismissal, and recovery failure; verify that overwrite is never the default and retained local work remains recoverable.
- Verify keyboard interactions, one-unit and ten-unit movement, proportional keyboard resize, text-editing shortcut behavior, selected-asset focus/preview, deck scroll retention, and empty states.
- At representative viewport widths, verify that browse-only mode has a persistent `View only` label, offers only pan/zoom and read-only drawers, and contains no enabled mutation path.
- Inspect accessible names, hover/focus tooltips, focus visibility and order, announced disabled states, and 44 by 44 CSS-pixel pointer or touch targets for icon controls, resize handles, and board-card overflow.
- Test the board-card open target and overflow target independently with pointer, touch, and keyboard input.
- Exercise a representative board with many images to assess interaction responsiveness before finalizing supported size expectations.

No implementation tests have been run as part of this planning document.
