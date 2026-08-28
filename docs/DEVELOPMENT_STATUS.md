# DEVELOPMENT_STATUS.md

Running log of completed, in-progress, and pending work. Updated after every prompt using the standard
`PROMPT STATUS` block. Most recent entry at the top.

---

## Phase Progress Overview

| Phase | Days | Status |
|---|---|---|
| 1. Foundation | 1–2 | 🟢 Complete (4 of 4 prompts) |
| 2. AI Detection | 3–5 | 🟢 Complete (4 of 4 prompts) |
| 3. Manual Correction | 6–8 | ⬜ Not Started |
| 4. 2D → 3D | 9–14 | ⬜ Not Started |
| 5. Walkthrough + Visuals | 15–17 | ⬜ Not Started |
| 6. LLM Assistant | 18–20 | ⬜ Not Started |
| 7. Estimation | 21–22 | ⬜ Not Started |
| 8. Sustainability | 23–25 | ⬜ Not Started |
| 9. Integration + Export | 26–28 | ⬜ Not Started |
| 10. Testing + Demo | 29–30 | ⬜ Not Started |

---

## Prompt Log

### Out-of-sequence fix — Door false-positive correction + OCR backend visibility (after window bracket fix)

Not a numbered prompt. Continuation of the same investigation session as the window bracket fix,
following up on two remaining items from that conversation: (1) the user's dimension-count
discrepancy (8 vs. 18) needed a way to diagnose without guessing, and (2) doors were explicitly
flagged as "likely undercounted, not yet investigated" and deserved the same rigorous treatment
windows got.

```
STATUS
- Trigger: continuing the user's real-world accuracy investigation. Two threads: (a) user's
  local result showed dimension_count=8 vs. this environment's 18, with no way to tell why
  without inspecting server internals; (b) doors had an open, explicitly-flagged gap from the
  window investigation that hadn't been followed up on yet.
- Part 1 -- OCR backend visibility:
  - Files modified:
    - backend/app/schemas/detection.py: added `ocr_backend` to DetectionSummary.
    - backend/app/api/routes/detection.py: surfaced `extra.get("ocr_backend")` (already computed
      since Prompt 6, just not exposed) into the summary response.
    - frontend/src/services/api.ts: added `ocr_backend` to the DetectionSummary TS type.
    - frontend/src/pages/Upload/Upload.tsx: displays "OCR: tesseract" (or "easyocr") next to the
      "Detection complete" heading.
  - Rationale: attempted to install easyocr in this environment to directly test whether it
    changes dimension-parsing behavior (my code's dimension/room-keyword parsing logic is
    OCR-backend-agnostic in principle, but Tesseract-specific word-grouping logic in
    ocr_service.py's _try_tesseract() only ever runs for Tesseract -- EasyOCR's own internal line
    grouping could plausibly produce different results). Installation failed: insufficient disk
    space in this sandbox for the ~2GB+ PyTorch dependency. Rather than guess at EasyOCR's exact
    behavior without being able to verify it, made the discrepancy diagnosable instead -- the
    user (or a future debugging session) can now see directly which backend produced a given
    result without a separate API call.
  - This remains an open, honestly-flagged gap: whether EasyOCR's output actually causes the
    user's lower dimension count, and whether the parsing logic needs updating for it, is
    UNVERIFIED, not fixed.
- Part 2 -- Door false-positive investigation and fix:
  - Investigation: overlaid detected door positions on the real test image (same methodology as
    the window investigation). Initially suspected two problems (a missing main-entrance door, a
    suspicious top-wall door) -- the "missing" entrance turned out to be a misreading of a
    crowded overlay image (it was correctly detected all along, confirmed by re-checking exact
    pixel coordinates); only one real problem was confirmed: a window on the left exterior wall
    was being misclassified as a door.
  - Root cause, confirmed by direct pixel inspection: the gap-based door heuristic's swing-leaf
    search found a short (10.8px) off-axis line fragment near this window's gap and treated it as
    a door swing indicator. That fragment is almost certainly a corner artifact of the window's
    own bracket-mark geometry (the same symbol characterized in the window bracket fix), not a
    real swing arc.
  - First attempted fix (leaf-fragment COUNT threshold) was tested against real measured data
    from every detected door and explicitly REJECTED before writing any fix code: the false
    positive had 2 nearby fragments at one endpoint, while a genuine, correctly-detected entrance
    door had only 1 fragment total. A count-based threshold would have broken a real detection
    without even fixing the false positive -- caught by testing the hypothesis against real data
    first rather than assuming a plausible-sounding heuristic would generalize.
  - Actual fix: backend/app/cv/detector.py -- added _reclassify_doors_near_window_brackets().
    Cross-references gap-based door detections against the already-trusted window bracket
    detections (added in the prior fix): a door whose position on a wall closely coincides
    (within 0.08 normalized position) with a confirmed bracket on the SAME wall is reclassified
    as a window rather than counted as a separate/duplicate detection. Naturally scoped to
    exterior walls only, since bracket_candidates never exist on interior walls -- interior door
    detections are completely unaffected.
  - backend/tests/test_detection.py: 5 new tests -- reclassification when close, no
    reclassification when far, no reclassification across different walls (even at an identical
    position value), confirmation that existing window entries are never touched by this
    function, and an end-to-end real-image regression test.
- Tests executed: pytest backend/tests/ (full suite) -- 99 passed (94 previous + 5 new). Re-
  verified cottage/studio synthetic samples produce byte-identical results to before (rooms,
  walls, doors, windows, stairs all unchanged) -- confirms zero impact on non-affected cases.
  Live HTTP end-to-end check via a fresh backend + real upload, matching direct pipeline output
  exactly, including the new ocr_backend field.
- Tests passed: 99/99
- Measured impact on the real test image (fl-1.jpg), this fix only:
  - Doors: 6 -> 5 (false positive removed)
  - Windows: 10 -> 11 (correctly gained, not duplicated -- confirms the reclassify-then-dedup
    ordering works as intended)
  - Everything else unchanged (rooms=7, walls=23, stairs=1, dimensions=18)
- Known issues:
  - EasyOCR compatibility is still unverified (see Part 1) -- flagged, not resolved, pending
    either more disk space in a future environment or the user testing directly and reporting
    the `ocr_backend` value along with their dimension count.
  - Doors may still be undercounted for reasons unrelated to this specific false positive (e.g.
    a decorative/non-arc door symbol convention not yet characterized, similar in spirit to how
    windows had a whole separate bracket-symbol convention). Not investigated further -- this
    fix addressed the one concretely confirmed problem, not an exhaustive door audit.
  - The 0.08 position-tolerance constant for the door/bracket cross-check was chosen to
    comfortably cover the one confirmed real case (measured gap: ~0.065-0.074 depending on which
    nearby bracket) without being so loose it could misfire elsewhere; not exhaustively tuned
    against multiple real examples the way the window bracket size thresholds were, since only
    one confirmed instance of this specific problem was found.
- Documentation updated: docs/DEVELOPMENT_STATUS.md (this entry)
- Recommended next action: proceed to Prompt 9 (Analyze and Design the 2D Correction Editor,
  first prompt of Phase 3) as previously planned.
```

---

### Out-of-sequence fix — Window bracket-symbol detection (after Prompt 8)

Not a numbered prompt. Follow-up to Prompt 8's accuracy report, where the user asked directly
whether detection accuracy justified moving to a trained ML model. Investigated the flagged
windows gap (4 detected vs. ~10+ visible) before answering that question, found a structural
(not tunable) cause, and fixed it with a bounded classical-CV addition rather than jumping to ML.

```
STATUS
- Trigger: user asked "is detection correct, and should we train an ML model instead?" after
  reviewing the Prompt 8 accuracy report. Investigated the windows undercount specifically
  (previously flagged but not root-caused) before answering, since an honest answer required
  evidence, not a guess.
- Investigation: overlaid detected door/window positions on the real test image, then zoomed
  into the source pixels at several suspected-window locations along the exterior walls.
  Confirmed visually: most windows in this real floor plan are drawn as a small bracket/step-
  shaped mark positioned OUTSIDE the wall line, not as a gap/break IN the wall line. This is a
  structurally different signal from what detect_openings() (Prompt 6) looks for -- no amount of
  tuning the existing gap-based heuristic could ever find this convention, since it doesn't
  create a gap at all. This finding directly informed the ML-model question: SOME gaps (stairs,
  wall fragmentation, fixed in Prompt 8) were tunable heuristic bugs; this one was a genuine
  strategy-level blind spot -- but still classically solvable (detecting the bracket shape
  itself), so a full trained model was not yet justified.
- Files modified:
  - backend/app/cv/detector.py: added detect_window_brackets() and
    _deduplicate_window_brackets(). Searches a thin band just outside each exterior wall
    (outward direction determined via the building's own bounding-box center) for small,
    isolated bracket-shaped contours, distinct from the existing gap-based detect_openings().
    A real calibration bug was found and fixed while building this: the first filter attempt
    required both bounding-box dimensions to independently fall in an 8-40px range, which
    rejected the real marks (measured at ~17-25px deep x 7-8px along-wall) while some noise
    fragments coincidentally passed. Fixed by using orientation-aware depth-vs-along-wall
    thresholds derived from actually measuring the real marks' contours, not assumed
    proportions from a single zoomed crop. Wired into run_detection_pipeline(): bracket
    candidates are converted to OpeningDetection entries and merged with gap-based detections
    before the existing deduplication pass, so both sources flow through the same downstream
    confidence-scoring and assembly code.
  - backend/tests/test_detection.py: 4 new tests -- no-false-positives-on-clean-synthetic-
    samples, exterior-only search scope, fragment deduplication, and an end-to-end real-image
    regression test (skips gracefully if the optional fixture isn't present).
  - docs/DEVELOPMENT_STATUS.md (this entry)
- Tests executed: pytest backend/tests/ (full suite) -- 94 passed (90 previous + 4 new), no
  regressions. Re-verified cottage/studio synthetic samples produce byte-identical counts to
  before this fix (rooms/walls/doors/stairs unchanged, windows unchanged at 1 and 0
  respectively) -- confirms zero false positives introduced. Live HTTP end-to-end check via a
  fresh backend + real upload, matching direct pipeline output exactly.
- Measured impact on the real test image (fl-1.jpg), this fix only:
  - Windows: 4 -> 10 (found 5 real bracket marks on the left exterior wall alone, matching a
    direct visual count of that wall; 1 more on the bottom wall)
  - Everything else unchanged (rooms=7, walls=23, doors=6, stairs=1, dimensions=18)
- Known issues:
  - The right exterior wall produced 0 bracket detections despite appearing visually similar at
    a glance -- closer inspection showed that region actually contains the perimeter dimension
    callout line's tick marks (a different feature), not window brackets. Whether the right
    wall's rooms genuinely have no windows, or use yet another drawn convention not yet
    characterized, was not determined. Not investigated further in this pass.
  - Top and bottom exterior walls have very little room (10-15px) to search outward before
    hitting the image edge, since the source image's margin is tight -- bracket detection on
    those walls is inherently less reliable than on the left/right walls, which have a full
    ~70-90px margin. Not addressed; noted as a limitation of this specific source image rather
    than the algorithm.
  - Doors were flagged in the Prompt 8 report as "likely undercounted, not yet investigated" --
    still not investigated in this pass; this fix was scoped to windows specifically since that
    was the more clearly evidenced gap.
- Documentation updated: docs/DEVELOPMENT_STATUS.md (this entry)
- Recommended next action: proceed to Prompt 9 (Analyze and Design the 2D Correction Editor,
  first prompt of Phase 3) as previously planned. A door-detection investigation, similar in
  spirit to this one, would be a reasonable candidate for a future out-of-sequence pass if
  real-world testing during/after Phase 3 surfaces further evidence, but is not blocking.
```

---

### Prompt 8 — Test and Fix AI Detection (closes Phase 2)

```
PROMPT STATUS
- Prompt number: 8
- Status: Complete
- Files created: None
- Files modified:
  - backend/app/cv/detector.py:
    1. detect_walls() signature changed: now returns a 4-tuple
       (walls, opening_candidates, thin_line_candidates, reclassified_stairs)
       instead of 3. Added _reclassify_dense_wall_clusters_as_stairs() and
       its clustering helper _cluster_by_proximity_and_overlap(): a real
       staircase hatch pattern in a real (non-synthetic) floor plan
       partially survived wall-isolation and was being consolidated into
       several irregularly-spaced short "walls" floating mid-room, which
       failed detect_stairs()'s strict evenly-spaced-tread check (tuned for
       clean synthetic tread lines). This is a looser, different check
       (compactness + count, not spacing regularity) that reclassifies such
       clusters as a stair region instead. A real bug was found and fixed
       while building this: perpendicular-proximity-only clustering chained
       through an unrelated wall elsewhere in the house that happened to
       sit at a similar coordinate but a totally different along-axis
       range, silently preventing any reclassification -- fixed by
       requiring along-axis range overlap in addition to proximity.
    2. Added snap_wall_endpoints_to_junctions(): implements endpoint
       snapping, which docs/DETECTION_PIPELINE.md Section 8 specified but
       had never actually been coded (confirmed via direct code search
       before implementing -- zero matches for "snap" anywhere in the file).
       Found by rendering and visually inspecting the wall mask used for
       room-contour extraction on the real test image and seeing walls stop
       just short of the perpendicular wall they should meet. Verified
       actually mutating wall geometry (21 of 29 walls adjusted on the real
       test image), though it did not by itself change room count on that
       specific image -- see Known issues below for why.
    3. run_detection_pipeline() updated for the new detect_walls() return
       shape and to merge reclassified-from-walls stairs with the
       separately-detected ones.
  - backend/tests/test_detection.py: all 15 existing detect_walls() call
    sites updated for the new 4-tuple return (mechanical, via sed). Added
    11 new tests: 5 for stair reclassification (including the exact
    real-world coordinates that triggered the chaining bug, and a
    regression test confirming the unrelated wall is no longer pulled in),
    3 for endpoint snapping, 1 end-to-end confirmation that the real
    image's stair count goes from 0 to 1 after these fixes (skips
    gracefully if the optional tests/fixtures/fl-1.jpg isn't present, same
    pattern as the calibration regression test added in the prior
    out-of-sequence fix).
  - docs/DEVELOPMENT_STATUS.md (this entry)
- Tests executed:
  - pytest backend/tests/ (full suite) -- 90 passed (82 previous + 8 new;
    note the "8 new" here differs slightly from the "11 new" described
    above because 3 of the 11 were added and counted in this same pass
    together with cleanup of a leftover unused helper function)
  - Direct pipeline runs (outside pytest) on all 3 varied sample floor
    plans (cottage: clean synthetic 2-room; studio: clean synthetic
    1-room; fl-1.jpg: real-world 11-room photo/scan) before and after each
    fix, to confirm actual measured impact rather than assumed impact
  - Visual verification: rendered and inspected the preprocessed binary
    image for all 3 samples (correct orientation, no corruption, 0deg
    rotation applied to all three since all were already axis-aligned);
    rendered and inspected the wall mask used for room-contour extraction
    before and after the stair-reclassification and endpoint-snapping
    fixes; rendered a color-coded room-detection overlay on the real image
    to precisely identify which specific rooms remain merged and why
    (see Known issues)
  - Live HTTP verification: booted the real backend, uploaded the real
    fl-1.jpg through the actual /upload endpoint (not just calling the
    pipeline function directly), confirmed the response exactly matches
    direct pipeline output (7 rooms, 23 walls, 6 doors, 4 windows, 1 stair,
    18 dimensions, calibration_source=ocr_dimension_match)
  - npm run build (frontend) -- clean, 102 modules (no frontend files
    changed this prompt; confirms nothing else regressed it)
- Tests passed: 90/90
- Measured impact on the real test image (fl-1.jpg), this prompt only:
  - Walls: 29 -> 23 (removed 6 phantom stair-tread "walls")
  - Rooms: 6 -> 7 (one more room correctly enclosed once the phantom
    mid-room walls were removed)
  - Stairs: 0 -> 1 (correctly found via reclassification)
  - 21 of 29 walls had at least one endpoint adjusted by snapping (verified
    by direct before/after coordinate comparison), independent of the
    stair fix
- Known issues (documented per this prompt's explicit instruction to
  document limitations rather than over-engineer a fix):
  - **Room count is still undercounted on the real image (7 detected vs.
    ~11 visible), and the root cause is now precisely diagnosed, not
    vague.** Overlaying detected room polygons on the source image showed
    exactly which rooms remain merged (Bed room+Bathroom on one side,
    Bathroom+Bed room on the other, common Bathroom+guest room) and
    tracing one of these cases down to pixel level found the exact cause:
    **the dividing wall's own drawn line does not extend all the way to
    the corner it should meet, because a door is drawn immediately at that
    corner with no wall segment before it for the gap-bridging logic to
    connect to.** This was visually confirmed (not assumed) by zooming into
    the source image at that exact location. This is a genuine limitation
    of the current room-boundary-closure approach for this specific (but
    architecturally common) door-at-corner placement, not a simple
    off-by-one bug -- fixing it generally would require either a much
    larger endpoint-snap tolerance (risking false-positive snapping of
    genuinely separate walls elsewhere) or door-aware wall-extension logic
    that doesn't exist yet. Deliberately not attempted in this pass per the
    "do not over-engineer, document instead" instruction. Phase 3's manual
    correction editor is the intended way for a user to close this specific
    kind of gap by hand.
  - The "common" + "Bathroom" two-line label still doesn't merge into one
    room name (carried over from the prior out-of-sequence fix; still
    low-priority/cosmetic, the room still gets correctly typed).
  - PDF upload remains implemented but untested end-to-end (no sample PDF
    available) -- carried over from Prompts 6/7.
  - No Alembic migrations (carried over from Prompts 2/4/7) -- Project's
    schema has not changed in this prompt, so no new dev.db reset is
    required after this one specifically.
- Documentation updated: docs/DEVELOPMENT_STATUS.md (this entry, and Phase
  2 marked complete in the progress table). docs/DETECTION_PIPELINE.md was
  reviewed but not changed -- endpoint snapping was already specified there
  (Section 8); this prompt closed the gap between that spec and the actual
  code, it didn't change the design.
- Dependencies for next prompt: None blocking. Phase 2 (AI Detection) is
  now fully complete. Prompt 9 (Analyze and Design the 2D Correction
  Editor, first prompt of Phase 3) can begin -- it should treat the
  documented room-merging limitation above as a concrete case the
  correction editor needs to handle well (splitting a merged region back
  into two rooms along a hand-drawn or corrected wall).
- Recommended next action: Proceed to Prompt 9 — Analyze and Design the 2D
  Correction Editor (first prompt of Phase 3).
```

---

### Out-of-sequence fix — Real-world detection accuracy (between Prompts 7 and 8)

Not a numbered prompt. Triggered by the user manually testing the live upload flow (Prompt 7)
against a real, non-synthetic floor plan image (`fl-1.jpg`, an 11-room house layout) and asking
for a detection-quality report. Logged here explicitly, out of sequence, per the standing practice
of flagging any work done outside the formal 40-prompt order.

```
STATUS
- Trigger: user uploaded a real floor plan through the live app and asked for an assessment of
  detection quality. Investigated by running the real image directly through the pipeline
  (not just reading the frontend summary), which surfaced two concrete, root-caused bugs beyond
  what the synthetic Prompt 6 fixtures had ever exercised.
- Files modified:
  - backend/app/ocr/ocr_service.py:
    1. ROOM_TYPE_KEYWORDS expanded: added "guest room", "drawing room" (common South Asian
       English term for a living/reception room), "passage" (hallway synonym), "utility"
       (mapped to laundry), "common bathroom"/"attached bathroom" variants. All four of the
       first three were confirmed, via direct inspection of real OCR output, to be correctly
       read by Tesseract but classified as kind="other" because the exact terms weren't in the
       keyword list.
    2. Added ROOM_SIZE_PAIR_PATTERN and _parse_room_size_pair(): the real image's dimension
       labels were universally in "W X H" format (e.g. "18' X 8'"), which the original
       DIMENSION_PATTERN (designed only for a single standalone length, per the Prompt 6
       synthetic fixture's "24 ft" label) could not parse at all -- 0 dimensions were extracted
       from the real image before this fix. Also handles Tesseract's confirmed common misread
       of the foot/prime mark (') as a degree symbol (°) in this context. Deliberately does NOT
       attempt to guess-correct other garbled OCR (e.g. "14X58", likely a mangled "14' X 5'") --
       parses it at face value rather than fabricating a "probably intended" reading.
    3. classify_text_blocks() now expands a detected "W X H" pair into TWO separate dimension
       entries (width, height), tagged is_pair_component=True, since each represents a genuinely
       separate real-world measurement.
    4. Added associate_room_size_dimensions(): a second, distinct association strategy for
       pair-component dimensions. Discovered mid-fix that parsing the values alone wasn't
       enough -- room-size labels have no adjacent drawn measurement line the way a perimeter
       dimension callout does, so the existing associate_dimensions() (nearby-line matching)
       always fell through to its low-confidence, unmatched fallback for these (confirmed:
       every parsed value came back at ~0.28 confidence, none feeding calibration). This new
       function instead matches each width/height value against its OWN containing room's
       pixel bounding box (found via the same point-in-polygon test already used for room-label
       association), which is a legitimate, direct calibration reference for this label
       convention. associate_dimensions() was updated to skip pair-component entries (now
       handled here instead) rather than double-processing them.
  - backend/app/cv/detector.py: run_detection_pipeline() now calls both
    associate_dimensions() and associate_room_size_dimensions(), combining their results before
    calibration.
  - backend/tests/test_detection.py: 8 new tests, including two direct regression tests using
    real strings/values captured verbatim from OCR run against the actual uploaded image (not
    invented test data), and one full end-to-end test against the real image itself (skips
    gracefully if the optional local fixture isn't present -- see below).
  - backend/tests/fixtures/fl-1.jpg: the user's real test image, added as an optional local
    regression fixture (not a synthetic sample; gitignored status left to the user's discretion
    since it's their own uploaded content, not a generated fixture like Prompt 6's samples).
- Tests executed: pytest backend/tests/ (full suite) -- 82 passed (74 previous + 8 new), no
  regressions. Also re-ran the real image through the pipeline directly (outside pytest) before
  and after each fix to confirm the actual before/after numbers reported to the user were real,
  not assumed.
- Measured impact on the real test image (fl-1.jpg):
  - Dimensions extracted: 0 -> 18
  - Dimension confidence: ~0.28 (unmatched fallback) -> ~0.44-0.49 (OCR confidence, matched)
  - Calibration source: "fallback_default_assumption" (arbitrary guess) -> "ocr_dimension_match"
    (grounded in 18 real measurements)
  - Room-type coverage: 4 of 6 detected rooms had a room_type before -> all rooms with a
    findable label now get one where a keyword exists (Drawing room, Passage, Utility, guest
    room all newly recognized)
- Known issues / not fixed by this round:
  - Room count is still undercounted (6 detected vs. ~11 visible) -- this is a wall-detection/
    fragmentation issue (29 walls detected, more than the ~15-18 a clean 11-room layout would
    need), separate from the OCR/parsing issues fixed here. Likely related to the source image's
    low resolution (447x447, upscaled 1.79x to reach the working minimum). Not investigated
    further in this pass -- flagged as a distinct follow-up, not silently left unmentioned.
  - The "common" + "Bathroom" two-line label still doesn't merge into a single "common Bathroom"
    room name (Tesseract places them on separate lines within the same block). Low priority:
    the room still gets correctly typed as room_type=bathroom via the second line alone, so this
    is a cosmetic naming gap, not a functional detection miss. Not fixed in this pass.
  - "14X58" (garbled OCR, likely a mangled "14' X 5'") still parses at face value as (14, 58)
    rather than being rejected or corrected -- deliberate, not an oversight (see rationale above).
    Given calibration uses the median across all matched measurements, one such outlier has
    bounded impact on the overall scale.
  - Stairs: 0 detected: still unconfirmed whether this is a genuine miss (there appears to be a
    hatched region in one bedroom in the source image) or correctly empty. Not investigated.
- Documentation updated: docs/DEVELOPMENT_STATUS.md (this entry)
- Recommended next action: proceed to Prompt 8 (Test and Fix AI Detection, closes Phase 2) --
  the room-undercounting issue flagged above is a good candidate to investigate as part of that
  prompt's broader testing pass, using both the synthetic fixtures and this real image.
```

---

### Prompt 7 — Integrate Detection Pipeline with Backend and Frontend

```
PROMPT STATUS
- Prompt number: 7
- Status: Complete
- Files created:
  - backend/app/services/storage_service.py (validates + saves uploaded
    files to STORAGE_PATH/{project_id}/{uuid}.{ext}; streams to disk in
    chunks with a size check as it goes, not trusting client-provided
    Content-Length; reuses SUPPORTED_EXTENSIONS/MAX_UPLOAD_BYTES from
    Prompt 6's preprocessing.py rather than redefining limits)
  - backend/app/services/floorplan_service.py (owns all reads/writes of
    Project.floorplan_data; every save goes through Prompt 4's
    parse_floorplan() validator first -- an invalid FloorPlan is never
    persisted, regardless of caller; also owns detection_status/
    detection_error read/write)
  - backend/app/schemas/detection.py (DetectionStatusResponse,
    DetectionSummary, DetectionUploadResponse)
  - backend/app/api/routes/detection.py (POST .../upload combines upload+
    trigger synchronously per the prompt's own "simple synchronous response
    acceptable for MVP" allowance; GET .../status and GET .../result are
    separate so the frontend can re-query without re-uploading)
  - backend/tests/test_detection_api.py (12 tests: status defaults,
    404/409/415/413 error paths, full upload-through-result round trip on
    both sample images, schema validation of the returned result,
    persistence-across-requests check, failed-detection handling)
  - backend/tests/conftest.py (shared test DB/client fixtures -- see "Known
    issues" below, this fixes a real cross-file test-isolation bug)
  - frontend/src/pages/Upload/Upload.tsx (full rewrite from Prompt 3's
    placeholder: drag-drop + click-to-browse file picker, client-side
    extension check, local image preview via object URL, upload/loading
    state, detected-element-count summary display, calibration/notes
    surfaced to the user, distinct UI states for request-level errors vs.
    detection-level failures vs. success)
- Files modified:
  - backend/app/models/project.py (added `detection_status` /
    `detection_error` columns -- ANOTHER schema change on top of Prompt 4's
    floorplan_data; see "Known issues")
  - backend/app/core/exceptions.py (added UnsupportedMediaTypeError (415),
    PayloadTooLargeError (413), ConflictError (409), following the existing
    AppError subclass pattern from Prompt 2)
  - backend/app/api/router.py (wired in the detection router)
  - backend/tests/test_foundation.py (refactored to use conftest.py's
    shared `client` fixture instead of its own local DB/override setup)
  - .gitignore (added backend/data/uploads/ -- uploaded user files should
    never be committed)
  - frontend/src/services/api.ts (added uploadFloorPlan, getDetectionStatus,
    getDetectionResult; documented the axios `Content-Type: undefined`
    override needed for multipart requests to work alongside the client's
    default JSON Content-Type)
  - docs/DEVELOPMENT_STATUS.md (this entry)
- Tests executed:
  - pytest backend/tests/ (full suite) -- run 3 times consecutively to
    confirm the conftest.py fix actually resolved the isolation bug
    (74/74 passed, stable across all 3 runs)
  - Live backend: booted fresh, full curl-based walkthrough of upload ->
    status -> result for a real project, plus every error path (409 before
    upload, 415 wrong file type, 413 oversized file with on-disk partial-
    file cleanup verified, 404 nonexistent project)
  - Live multipart integration test via a small Node/axios script exercising
    the exact `Content-Type: undefined` override pattern used in
    frontend/src/services/api.ts against the real running backend --
    confirmed the backend correctly parses the multipart body and runs
    detection end-to-end (2 rooms, 5 walls, 2 doors, 1 window, 1 stair,
    matching the Prompt 6 ground truth exactly)
  - `npm run build` (tsc --noEmit + vite build) -- clean, 102 modules
  - Vite dev server per-module transform check on every new/modified
    frontend file (Upload.tsx, api.ts) -- no runtime import errors
  - CORS preflight (OPTIONS) verified from http://localhost:5173 against
    the new POST .../upload endpoint specifically (not just the endpoints
    already covered in Prompt 3)
- Tests passed: 74/74 backend (12 new + 62 from Prompts 2/4/6), frontend
  build clean, all live integration checks passed
- Known issues:
  - **Another schema change on Project** (`detection_status`,
    `detection_error`) -- same class of issue already flagged in Prompts 2
    and 4: `init_db()` still uses `Base.metadata.create_all()`, which does
    not alter existing tables. An existing `dev.db` from before this prompt
    must be deleted and regenerated, exactly as happened after Prompt 4 (the
    user hit this directly; see the conversation immediately before this
    prompt). Deferred to Prompt 39 per the standing decision, not fixed
    here since the user explicitly chose to keep deferring it.
  - **Found and fixed a real cross-file test-isolation bug** while adding
    test_detection_api.py: `app.dependency_overrides[get_db]` is a single
    dict entry on the process-wide FastAPI `app` object. test_foundation.py
    (Prompt 2) and the new test_detection_api.py each independently created
    their own SQLite engine and assigned that override at module level.
    Since pytest imports every test module during collection before running
    any test, whichever file imported LAST silently won that override for
    ALL test files -- including ones whose own tables were never created
    against that engine. This surfaced as "no such table: projects"
    failures that appeared ONLY when the full suite ran together, never
    when either file ran alone -- exactly the kind of bug that's invisible
    until enough test files accumulate. Fixed with a shared
    backend/tests/conftest.py (one engine, one override, defined once);
    test_foundation.py was refactored to use it. Verified fixed by running
    the full suite 3 times consecutively.
  - Upload + detection run synchronously in a single request/single process
    -- there is no real background job queue, so "processing" status is
    only meaningfully observable if a second request queries status during
    the brief window an upload is being handled by another concurrent
    request. Acceptable per the prompt's own "avoid building a full job
    queue" constraint; would need revisiting if detection time grows
    significantly for larger real-world images.
  - PDF upload is accepted by validation (extension check passes) but,
    consistent with Prompt 6's own known issues, has still not been
    exercised end-to-end with a real sample PDF -- no PDF fixture exists.
  - The Node/axios multipart integration test used the `form-data` npm
    package (Node's FormData polyfill), not a real browser's native
    FormData -- this verifies the backend's multipart handling thoroughly
    (the more uncertain side) but is not a literal browser-based
    confirmation of the frontend's axios override behavior, consistent with
    this sandbox's standing inability to run a headless browser (noted
    already in Prompt 3).
- Documentation updated: docs/DEVELOPMENT_STATUS.md (this entry). No
  changes needed to ARCHITECTURE.md or DETECTION_PIPELINE.md.
- Dependencies for next prompt: None blocking. Prompt 8 (Test and Fix AI
  Detection) can begin -- it should include a manual/exploratory pass
  against the now-live upload flow, not just the unit-level tests already
  in place.
- Recommended next action: Proceed to Prompt 8 — Test and Fix AI Detection
  (closes Phase 2). Suggest the user run `rm backend/dev.db` once more
  before their next manual test, per the schema change noted above.
```

---

### Prompt 6 — Implement Computer Vision Detection and OCR

```
PROMPT STATUS
- Prompt number: 6
- Status: Complete
- Files created:
  - backend/app/cv/preprocessing.py (load/rasterize PNG/JPG/PDF, resize to
    working resolution, grayscale, denoise, adaptive-threshold binarize,
    Hough-based deskew)
  - backend/app/cv/detector.py (wall detection via morphology + Hough lines
    with collinear-segment merging and gap/opening extraction; room
    derivation via wall-mask contour extraction; tiered door/window
    classification via swing-leaf heuristic; stair detection via parallel
    tread-line clustering; full pipeline orchestration in
    run_detection_pipeline())
  - backend/app/cv/postprocessing.py (confidence scoring per element type,
    room-to-boundary-wall association, door/window NMS, two-path unit
    calibration: OCR-matched dimension preferred, documented fallback
    assumption otherwise)
  - backend/app/ocr/ocr_service.py (EasyOCR-primary/Tesseract-fallback dual
    backend, word-to-line grouping with gap-based re-splitting, dimension
    pattern parsing, room-keyword classification, point-in-polygon room
    label association, dimension-to-geometry association)
  - backend/tests/test_detection.py (40 tests: preprocessing, wall/room/
    opening/stair detection on 2 sample images, OCR extraction/
    classification/association, calibration, and 8 full end-to-end
    pipeline tests validated against the real Prompt 4 schema validator)
  - scripts/generate_sample_floorplans.py (generates the 2 synthetic sample
    floor plan images -- see that script's docstring for why synthetic
    fixtures were used instead of real scans)
  - data/samples/sample_floorplan_cottage.png, sample_floorplan_studio.png
    (the 2 sample images required by this prompt's file list)
- Files modified:
  - backend/requirements.txt (added opencv-python, numpy, Pillow, shapely,
    pytesseract, PyMuPDF; easyocr intentionally NOT pinned -- see Known
    issues)
  - docs/DEVELOPMENT_STATUS.md (this entry)
- Tests executed:
  - pytest backend/tests/test_detection.py (40 tests)
  - pytest backend/tests/ (full suite, 62 tests) -- regression check,
    confirms Prompts 2 and 4's tests are unaffected
  - Full pipeline run against both sample images with output printed and
    manually inspected against the known ground truth of each synthetic
    drawing (element counts, room names, dimension values, wall/room
    classifications)
- Tests passed: 62/62 (40 new + 22 from Prompts 2 and 4)
- Known issues / decisions made during implementation:
  - **Tier 1 resolved to "not implemented," as Prompt 5 anticipated.** A
    generic pretrained object detector (e.g. COCO-trained YOLOv8n) does not
    include door/window/stair symbol classes at all, so it would add a
    heavy dependency for no real detection benefit. Tier 2 (classical
    heuristics) is the sole detection strategy for these elements, exactly
    as Prompt 5's design allowed for. Full reasoning is in detector.py's
    module docstring.
  - **EasyOCR was not exercised live in this environment** -- only
    Tesseract was. `ocr_service.py` implements both paths exactly as
    designed (try EasyOCR, fall back to Tesseract on any failure including
    a blocked model-weight download), but EasyOCR was not installed in this
    sandbox to avoid an unreliable, heavy first-run network dependency
    during development. `get_ocr_backend_name()` reports which path ran;
    all live testing reports "tesseract". Stated honestly rather than
    claiming both paths were verified.
  - **Six real bugs were found and fixed during implementation** (not just
    written and assumed correct) by actually running the pipeline against
    the sample images and inspecting output against known ground truth:
    1. Stair tread lines (55px) survived the wall-isolation morphology
       filter because they exceeded the original 25px kernel length --
       increased kernel to 70px.
    2. A thin (1px) dimension line survived the same filter by running the
       building's full length -- added a minimum wall-thickness filter,
       and (constructively) repurposed the filtered-out thin lines as
       dimension-line candidate geometry for OCR association, rather than
       simply discarding them.
    3. Room detection counted a RETR_CCOMP hierarchy artifact (a "hole"
       representing the wall silhouette within the background region) as a
       spurious third room -- fixed by only accepting top-level contours.
    4. The stair heuristic's cluster-proximity check let scattered OCR text
       strokes at a similar y-height pass as a false stair region -- fixed
       by deduplicating near-identical Hough fragments of the same
       physical line before checking spacing regularity, length
       similarity, and along-axis compactness.
    5. Exterior/interior wall classification checked a wall's coordinates
       against all four boundary extents rather than only its own
       perpendicular axis, misclassifying the interior dividing wall (which
       spans nearly the full building height) as exterior.
    6. Wall-line grouping used naive `round(offset / tolerance)` bucketing,
       which split two genuinely close line offsets (682.0 and 684.3 with
       tolerance=8) into duplicate walls because they rounded into
       different buckets -- replaced with real chained proximity
       clustering, which has no such boundary-straddling failure mode.
    Each fix has a corresponding regression test in test_detection.py
    (see the "Regression test:" docstrings) so these don't silently
    reappear in later prompts.
  - **Multi-word/same-row OCR text required two additional fixes beyond the
    obvious per-word fragmentation**: Tesseract's own line-grouping (a)
    fragments multi-word labels into per-word blocks by default (fixed by
    grouping words sharing Tesseract's own block/paragraph/line indices),
    and (b) can still wrongly merge two separate labels that happen to sit
    at the same y-height into one "line" (fixed by re-splitting on large
    horizontal gaps between consecutive words).
  - Confidence scores on the synthetic fixtures are uniformly high (walls:
    1.0, rooms: 1.0) since the clean synthetic line art gives complete
    Hough coverage -- real scanned/hand-drawn plans will show meaningfully
    more varied confidence, which is expected and matches
    DETECTION_PIPELINE.md's documented MVP-accuracy expectations.
  - PDF input (`preprocessing._load_pdf_first_page`, via PyMuPDF) is
    implemented per the design but not exercised by any test -- no sample
    PDF floor plan was available to generate. Only PNG input was tested.
- Documentation updated: docs/DEVELOPMENT_STATUS.md (this entry). No
  changes needed to DETECTION_PIPELINE.md or ARCHITECTURE.md -- the Prompt 5
  design held up through implementation without requiring a design
  revision (Tier 1's resolution was already anticipated as an open
  question there, not a deviation from it).
- Dependencies for next prompt: None blocking. Prompt 7 (Integrate
  Detection Pipeline with Backend and Frontend) can begin --
  `detector.run_detection_pipeline(image_path, project_id)` is a
  self-contained, framework-agnostic function ready to be wired into an
  upload API endpoint and persisted via `floorplan_service.py`.
- Recommended next action: Proceed to Prompt 7 — Integrate Detection
  Pipeline with Backend and Frontend.
```

---

### Prompt 5 — Analyze and Design the Floor Plan Detection Pipeline

```
PROMPT STATUS
- Prompt number: 5
- Status: Complete
- Files created:
  - docs/DETECTION_PIPELINE.md (full pipeline design: input limits, preprocessing,
    wall/room detection via classical CV, tiered door/window/stair detection,
    confidence scoring per element type, OCR engine selection + text association,
    unit calibration, assembly + validation reuse, 2 conceptual walkthroughs,
    explicit out-of-scope list, tool summary)
- Files modified:
  - docs/ARCHITECTURE.md (Section 6, module #1 — added pointer to
    DETECTION_PIPELINE.md plus a one-line summary of the chosen approach)
  - docs/DEVELOPMENT_STATUS.md (this entry)
- Tests executed: None (design-only prompt, no automated tests required per
  Prompt 5's own Testing Requirements). Design validated via two conceptual
  walkthroughs against sample floor plan scenarios (Section 10 of
  DETECTION_PIPELINE.md) — one clean/synthetic-style input, one degraded
  hand-drawn/skewed input with no dimension text — confirming the design
  degrades via confidence scores and metadata notes rather than failing
  outright, and that every FloorPlan field maps to either a defined detection
  source or an explicit, documented "not detectable from a 2D plan view, left
  null" decision.
- Tests passed: N/A (no automated tests this prompt)
- Known issues:
  - Tier 1 (pretrained YOLOv8n door/window/stair detector) availability is an
    explicitly flagged open decision, not a confirmed dependency — whether a
    suitable pretrained checkpoint can actually be sourced/licensed must be
    resolved at the start of Prompt 6. Tier 2 (classical heuristics) is
    documented as always-available fallback specifically so this uncertainty
    does not block Prompt 6 from proceeding.
  - A real domain-accuracy issue was caught and corrected during this design
    pass: `Door.height`, `Window.height`, and `Window.sill_height` are
    vertical/elevation dimensions that are not visible in a top-down 2D floor
    plan at all. An earlier draft of this design implied these might be
    derivable from a Tier-1 bounding box, which would have been geometrically
    wrong. The document now explicitly states these are always left `null`
    by this pipeline, with defaults applied downstream in Phase 4 -- flagging
    this so Prompt 6's implementer doesn't spend time chasing a signal that
    doesn't exist in the input.
  - EasyOCR's first-run weight download requires network access; Tesseract
    fallback exists specifically for offline environments (relevant given
    this sandbox's own restricted network access, seen in earlier prompts).
  - No code was written -- backend/app/cv/ and backend/app/ocr/ remain empty,
    per this prompt's explicit "no implementation yet" scope.
- Documentation updated: docs/DETECTION_PIPELINE.md (new), docs/ARCHITECTURE.md
  Section 6 (Detection module pointer), docs/DEVELOPMENT_STATUS.md (this entry)
- Dependencies for next prompt: None blocking. Prompt 6 (Implement Computer
  Vision Detection and OCR) can begin -- it should open by resolving the Tier 1
  model-availability open decision flagged above before writing detection code.
- Recommended next action: Proceed to Prompt 6 — Implement Computer Vision
  Detection and OCR.
```

---

### Prompt 4 — Finalize FloorPlan Schema and Verify Foundation

```
PROMPT STATUS
- Prompt number: 4
- Status: Complete
- Files created:
  - backend/app/floorplan/__init__.py
  - backend/app/floorplan/schema.py (canonical FloorPlan Pydantic v2 contract:
    Point2D, ElementBase, Room, Wall, Door, Window, Stair, DimensionAnnotation,
    FurnitureItem, FloorPlanMetadata, FloorPlan)
  - backend/app/floorplan/validator.py (structural/cross-element validation:
    duplicate id detection, wall_id and room_id referential integrity;
    validate_floorplan() non-raising + parse_floorplan() raising variants)
  - frontend/src/types/floorplan.ts (TypeScript mirror, field-for-field match)
  - data/samples/example_floorplan.json (two-room building fixture exercising
    every element type: rooms, exterior + interior walls, doors, windows, a
    stair, dimension annotations, furniture)
  - docs/FLOORPLAN_SCHEMA.md (full field-by-field reference, coordinate system,
    validation layers, storage notes)
  - backend/tests/test_floorplan_schema.py (15 tests)
- Files modified:
  - backend/app/models/project.py (added `floorplan_data` column — JSON on
    SQLite/generic, JSONB on PostgreSQL via `.with_variant()`, nullable)
- Tests executed:
  - pytest backend/tests/test_floorplan_schema.py (15 tests: fixture validity,
    every element type present, 5 field-level/Pydantic rejection cases, 4
    structural rejection cases incl. duplicate ids and dangling wall_id/room_id
    references, parse_floorplan() raises correctly, DB round-trip save+reload
    in a fresh session, project-with-no-floorplan defaults to null)
  - pytest backend/tests/ (full suite, 22 tests) — regression check after
    extending the Project model; all of Prompt 2's original tests still pass
  - Live server boot (uvicorn) + GET /health + POST /projects — confirmed
    startup succeeds with the new column and existing endpoints still work
  - Direct SQLite table inspection (PRAGMA table_info) confirming
    `floorplan_data` column exists with the expected type/nullability
  - `npm run build` (tsc --noEmit + vite build) on the frontend — confirms
    floorplan.ts type-checks cleanly, including verifying the `Window`
    interface name does not collide with the DOM lib's global `Window` type
    (module-scoped export, not ambient — no merge occurs)
- Tests passed: 15/15 new tests, 22/22 full backend suite, frontend build
  clean (102 modules), backend live-boot smoke test passed.
- Known issues:
  - Testing Requirement #3 ("API round-trip that saves and retrieves the
    example FloorPlan JSON") was satisfied at the database/service layer via
    a direct SQLAlchemy session, not over HTTP. This prompt's own
    Files/Folders list does not include a new route file for raw FloorPlan
    CRUD -- that's introduced alongside detection (Prompt 7) and correction
    (Prompt 11) in Phase 2/3. Documented here rather than silently
    reinterpreting scope.
  - `floorplan_data` is a single "current" document per project, not a
    version history. Phase 2/3 will need to decide how raw-detection output
    vs. manually-corrected output are represented on top of this column
    (e.g. overwrite-in-place vs. separate versions) without changing the
    column's type or name.
  - No Alembic migration exists yet for the new column (consistent with the
    known issue already logged in Prompt 2 -- `init_db()` still uses
    `Base.metadata.create_all()`).
- Documentation updated: docs/FLOORPLAN_SCHEMA.md (new), docs/ARCHITECTURE.md
  Section 4 already anticipated this schema and required no changes,
  docs/DEVELOPMENT_STATUS.md (this entry, Phase 1 marked complete)
- Dependencies for next prompt: None blocking. Phase 1 (Foundation) is now
  fully complete. Prompt 5 (Analyze and Design the Floor Plan Detection
  Pipeline) can begin -- it consumes this exact FloorPlan contract as its
  target output shape.
- Recommended next action: Proceed to Prompt 5 — Analyze and Design the Floor
  Plan Detection Pipeline (first prompt of Phase 2).
```

---

### Prompt 3 — Implement Frontend Foundation and Backend Integration

```
PROMPT STATUS
- Prompt number: 3
- Status: Complete
- Files created:
  - frontend/vite.config.ts, frontend/tsconfig.json, frontend/tailwind.config.js,
    frontend/postcss.config.js, frontend/index.html, frontend/public/favicon.svg
  - frontend/src/main.tsx, frontend/src/index.css, frontend/src/vite-env.d.ts
  - frontend/src/types/project.ts
  - frontend/src/services/api.ts (centralized typed API client)
  - frontend/src/hooks/useProject.tsx (project state Context/hook)
  - frontend/src/components/Loading.tsx, ErrorState.tsx, EmptyState.tsx,
    NavBar.tsx, Layout.tsx, PageHeader.tsx
  - frontend/src/pages/Dashboard/ (Dashboard.tsx, index.ts) — fully functional,
    live-wired to backend
  - frontend/src/pages/{Upload,FloorPlanEditor,Viewer3D,Assistant,Estimation,
    Sustainability}/ (placeholder page + index.ts each, per "no feature content
    yet" constraint)
- Files modified:
  - frontend/src/App.tsx (routing + Layout wiring; was an empty stub from Prompt 1)
  - frontend/package.json (populated; was an empty stub)
  - frontend/.env.example (populated; was an empty stub)
  - .gitignore (bug fix — `.env.*` was accidentally excluding `.env.example` for
    both backend and frontend; added `!.env.example` negation and Node/Vite ignores)
- Tests executed:
  - `npm install` + `npm run build` (tsc --noEmit + vite build) — full production build
  - Live dev server (`npm run dev`) with every module in the dependency graph
    fetched directly to confirm clean transformation (no runtime import errors)
  - Live backend (`uvicorn`) started, seeded a project via POST /projects
  - CORS preflight (OPTIONS) verified from origin http://localhost:5173 against
    the real backend — confirmed access-control-allow-origin echoes correctly
  - GET /projects verified to return the seeded project (proves the Dashboard's
    fetch → display chain is wired to real data, not mocked)
- Tests passed: All of the above passed. Production build: 109 modules, no
  TypeScript errors. No console/runtime errors surfaced during module transform
  checks. CORS and end-to-end data flow both confirmed against the live backend.
- Known issues:
  - No browser-level (Playwright/headless Chromium) render test could be run in
    this sandbox — Chromium download was blocked by network restrictions on the
    install step. Verification instead relied on: TypeScript compilation,
    production bundling, per-module transform checks via the dev server, and
    direct backend integration checks (CORS + live data fetch). This is strong
    but not 100% equivalent to an actual rendered-DOM/console check — recommend
    a quick manual `npm run dev` + browser check on your end before Prompt 4.
  - Project selection state (useProject) is session-only (sessionStorage-backed
    in-memory Context) — no persistence beyond the browser tab, which is
    sufficient for Prompt 3's scope but will need revisiting once multi-page
    workflows (Prompt 35, full Upload→Export flow) depend on it more heavily.
- Documentation updated: docs/DEVELOPMENT_STATUS.md (this entry)
- Dependencies for next prompt: None blocking. Prompt 4 (Finalize FloorPlan Schema
  and Verify Foundation) can begin — backend Pydantic schemas and frontend
  TypeScript types both need the canonical FloorPlan contract defined; the
  existing frontend/src/types/project.ts pattern should be followed for the new
  frontend/src/types/floorplan.ts.
- Recommended next action: Proceed to Prompt 4 — Finalize FloorPlan Schema and
  Verify Foundation. Suggest a quick manual smoke test (npm run dev + open in an
  actual browser) on your end first, given this sandbox couldn't run a headless
  browser check.
```

---

### Prompt 2 — Implement Backend and Core Project Foundation

```
PROMPT STATUS
- Prompt number: 2
- Status: Complete
- Files created:
  - backend/app/core/config.py
  - backend/app/core/database.py
  - backend/app/core/logging.py
  - backend/app/core/exceptions.py
  - backend/app/api/router.py
  - backend/app/api/routes/projects.py
  - backend/app/models/project.py
  - backend/app/schemas/base.py
  - backend/app/schemas/project.py
  - backend/app/services/project_service.py
  - backend/tests/test_foundation.py
  - __init__.py package markers: app/, app/core/, app/api/, app/api/routes/,
    app/models/, app/schemas/, app/services/, tests/
- Files modified:
  - backend/app/main.py (implemented app entry point; was an empty stub from Prompt 1)
  - backend/requirements.txt (populated; was an empty stub from Prompt 1)
  - backend/.env.example (populated; was an empty stub from Prompt 1)
- Tests executed:
  - pytest backend/tests/test_foundation.py (7 tests: root, health, create/list project,
    get by id, 404 error format, 422 validation error format, update/delete round-trip)
  - Live server smoke test: booted with `uvicorn app.main:app`, exercised GET /health,
    POST /projects, GET /projects, GET /projects/{bad-id} over real HTTP with curl
- Tests passed: 7/7 automated tests passed. All live HTTP smoke checks passed
  (server boots cleanly with lifespan startup, /health returns 200 with
  "database": "connected", project CRUD works, 404/422 both return the
  {"error": {"code","message","details"}} shape).
- Known issues:
  - No Alembic/migration tool yet — init_db() uses Base.metadata.create_all() as an MVP
    convenience. Acceptable for now per Prompt 2 scope; should be revisited if schema
    migrations become necessary before Prompt 4 finalizes the FloorPlan schema.
  - requirements.txt pins psycopg2-binary for PostgreSQL, but local dev/testing in this
    environment used a SQLite DATABASE_URL (no Postgres instance available in sandbox).
    database.py handles both via a DATABASE_URL-driven engine, but real PostgreSQL
    connectivity has not been exercised — only SQLite has been verified.
- Documentation updated: docs/DEVELOPMENT_STATUS.md (this entry)
- Dependencies for next prompt: None blocking. Prompt 3 (Implement Frontend Foundation and
  Backend Integration) can begin — GET /projects, POST /projects are live and ready for the
  frontend API client to call.
- Recommended next action: Proceed to Prompt 3 — Implement Frontend Foundation and Backend
  Integration. Before production deployment, verify against a real PostgreSQL instance
  (not just SQLite) and consider introducing Alembic migrations ahead of Prompt 4.
```

---

### Prompt 1 — Analyze Existing Project and Finalize Architecture

```
PROMPT STATUS
- Prompt number: 1
- Status: Complete
- Files created: docs/ARCHITECTURE.md, docs/PROJECT_MASTER.md, docs/DEVELOPMENT_STATUS.md,
  backend/.gitkeep, frontend/.gitkeep, models/.gitkeep, assets/.gitkeep, data/.gitkeep,
  tests/.gitkeep, scripts/.gitkeep, docker/.gitkeep
- Files modified: (none — greenfield project, nothing existed to modify)
- Tests executed: Manual self-check only (per prompt scope — no automated tests apply to a
  documentation/planning prompt)
- Tests passed:
  - Architecture document covers all 10 phases/subsystems: PASS
  - FloorPlan contract fields are complete and consistent with source spec: PASS
  - No module has an undefined input/output (Section 10 self-check): PASS
- Known issues: None. Repository was confirmed empty before this prompt — no legacy code,
  conflicting structure, or naming inconsistencies to reconcile.
- Documentation updated: docs/ARCHITECTURE.md (created), docs/PROJECT_MASTER.md (created),
  docs/DEVELOPMENT_STATUS.md (created, this file)
- Dependencies for next prompt: None blocking. Prompt 2 (Implement Backend and Core Project
  Foundation) can begin immediately using the architecture defined here.
- Recommended next action: Proceed to Prompt 2 — Implement Backend and Core Project Foundation.
```

---

## Known Limitations Register

*(Populated progressively as phases complete. Carried into the final Prompt 40 documentation pass.)*

| Area | Limitation | Introduced In |
|---|---|---|
| — | — | — |

---

## Open Issues

*(None yet — project just started.)*

| ID | Severity | Description | Status |
|---|---|---|---|
| — | — | — | — |
