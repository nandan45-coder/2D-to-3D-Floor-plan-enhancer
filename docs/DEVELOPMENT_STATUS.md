# DEVELOPMENT_STATUS.md

Running log of completed, in-progress, and pending work. Updated after every prompt using the standard
`PROMPT STATUS` block. Most recent entry at the top.

---

## Phase Progress Overview

| Phase | Days | Status |
|---|---|---|
| 1. Foundation | 1–2 | 🟢 Complete (4 of 4 prompts) |
| 2. AI Detection | 3–5 | 🟡 In Progress (Prompt 6 done — 2 of 4 complete) |
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
