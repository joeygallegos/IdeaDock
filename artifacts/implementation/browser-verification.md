# Live browser acceptance evidence

Environment: disposable preview_server.py on 127.0.0.1:8027; synthetic projects, completed item, PNG fixtures, and boards only. No user database/uploads were accessed. In-app browser, desktop 1280x900 and narrow viewport 390x844. Evidence complements automated tests; it does not certify untested physical devices or live MySQL.

## Executed workflows

| Plan coverage | Observed result |
| --- | --- |
| AC1,8,12,23 | Named board creation, completed-project entry, independent named local copy, reopen, rename retaining four objects, keyboard overflow separate from card open. Overflow targets measured 44x44 CSS pixels. |
| AC2,18 | Completed item's image appears in deck; selected source preview and repeated Add to board retain selection; source remains available after placement. |
| AC3,6,7,9,15,17,22 | Independent repeated placements; Shift-click exact count; one-/ten-unit keyboard movement; group duplicate/undo; proportional keyboard resize; resize target measured 44x44 at 83% zoom; pointer image move. On 120-object board, marquee selected exactly four, remove reduced count to116, undo restored120. |
| AC4,10 | Mixed picker upload: valid PNG remained usable while invalid PNG showed clear validation failure and Retry. Retry preserved successful file. Switching boards retained shared upload. Clipboard image paste uploaded and placed image. Drag from deck added placement without consuming source. |
| AC5,21 | Add object → Text label; valid hex swatch; invalid hex kept prior valid color and explicit error; image sampling created white swatch from synthetic white pixel. |
| AC11,19 | Two tabs triggered409 conflict. Local-copy action emphasized and initially focused. Replace hidden until comparison. Open latest showed explicit warning with Cancel initially focused; cancel retained local work. Local-copy completion saved independent named board with all4objects. Later confirmed Open latest loaded latest6-object composition and saved view. |
| AC13,16 | Hand-tool drag and wheel pan plus Fit board left object geometry unchanged. Empty-canvas marquee at57% selected expected four objects. Space/middle/Shift-marquee event paths are separately covered by actual-controller tests because browser controls do not offer modifier-held or middle-button drag. |
| AC20 | At390x844, persistent View only, mutation controls absent, object details readable, Arrow/Delete left geometry/count unchanged, zoom remained functional and initial fit was applied. Responsive aria-expanded/canvas guidance and stale notice issues identified and fixed with regression tests. |
| Verification plan responsiveness | Representative120 image placements using one240x160 PNG source:120 rendered objects, zero broken images. Open+Fit and inspection tool batch completed in about one second; not a formal performance benchmark or limit for120distinct high-resolution files. Selection/remove/undo responsive. |

## Review findings corrected

- Native naming prompt unsupported in the in-app browser: replaced by accessible HTML dialog.
- Native confirmation stalled browser input: replaced by accessible HTML dialog; old stalled tab later cleaned up and input resumed.
- Add object menu painted below selection toolbar: corrected stacking.
- Resize hit target could shrink with zoom: inverse scaling preserves44screen pixels.
- Responsive deck disclosure and canvas guidance mismatches corrected; desktop clears only its own View only notice.
- Open latest refreshed composition but not combined image library: fixed and browser retested after concurrent upload of recovery-fresh.png and a newer revision. Confirmed recovery displayed all six objects and the new image in its deck.

## Limits and outstanding evidence

- File chooser returned very slowly once; upload results were verified, but no inference is made about normal upload latency from tool latency.
- File-drop coordinates, typing-paste passthrough, middle/Space gestures, Shift-marquee, failure/retry and recovery dismissal races have automated controller evidence; not every path was exercised with physical hardware.
- Physical touch, real trackpad hardware, and live MySQL were not available.
- Final recovery-library and responsive-guidance browser retests passed. PM reran all33named Node tests and JavaScript syntax checks successfully after the final changes. Python22tests and HTTP smoke had already passed; backend unchanged since those checks. The user subsequently approved the installer fix; the final full Python suite passed 34 tests, including 12 installer regressions. No deployment decision remains.
