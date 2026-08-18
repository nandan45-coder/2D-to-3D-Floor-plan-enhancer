# DETECTION_PIPELINE.md

Implementation-ready design for the computer-vision + OCR pipeline that converts an uploaded 2D floor
plan (image or PDF) into a schema-valid `FloorPlan` JSON document (see `docs/FLOORPLAN_SCHEMA.md` and
`backend/app/floorplan/schema.py`).

**Scope of this document:** design only. No detection code is implemented here — that begins in
Phase 2 implementation. `backend/app/cv/` and `backend/app/ocr/` remain empty folders during this design phase.

**Guiding constraint (per `docs/ARCHITECTURE.md` and the 30-day scope-control plan):** every technique
chosen below is either classical, well-understood computer vision or an existing pretrained model — no
model is trained or fine-tuned from scratch in this project. Detection accuracy is targeted at an "MVP
usable starting point," not production-grade digitization. **Phase 3's manual correction editor is the
explicit safety net for every detection error this pipeline makes.** This document does not chase
perfect accuracy; it chases a pipeline that reliably produces *something structurally valid and roughly
correct* for a human to fix.

---

## 1. Supported input types and limits

| Constraint | Value | Reason |
|---|---|---|
| Formats | PNG, JPG/JPEG, PDF | Covers scanned plans, exported CAD images, and PDF exports — the common cases for a floor plan upload. |
| PDF handling | **First page only** for the MVP | Multi-page floor plan sets (e.g. separate pages per floor) are out of scope for a 30-day MVP. Documented limitation, surfaced to the user at upload time (Phase 2). |
| Max upload size | 15 MB | Generous for a single scanned page/CAD export; prevents pathological uploads from stalling the pipeline. |
| Working resolution | Long edge capped at **3000px**, downscaled preserving aspect ratio if larger | Classical CV (Hough transforms, morphology) has runtime and noise-sensitivity that scales poorly with resolution; 3000px is well above what's needed for wall/room detection accuracy. |
| Minimum usable resolution | Long edge **≥ 800px** | Below this, line detection and OCR both degrade sharply. Images below this threshold are **upscaled** (bicubic) as a best-effort rather than rejected outright, but flagged with a lower confidence tier and a note in `metadata.notes`. |

---

## 2. Preprocessing pipeline

Applied in this order to every accepted upload before any detection step runs:

1. **Load & rasterize.** Images load directly; PDFs are rasterized to a PNG at a target DPI (~200) via
   `pdf2image`/`PyMuPDF`, first page only.
2. **Resize to working resolution** per the limits in Section 1. The scale factor applied here is
   retained — every downstream pixel coordinate must be divided back through it before final assembly,
   and it feeds into the unit-calibration step in Section 8.
3. **Grayscale conversion.**
4. **Denoise.** `cv2.fastNlMeansDenoising` (or a lighter median blur for large images, to keep runtime
   reasonable) — floor plan scans commonly have paper texture/JPEG artifacts that create false line
   segments in Hough detection if left unfiltered.
5. **Binarize.** Adaptive thresholding (`cv2.adaptiveThreshold`, Gaussian) rather than a single global
   Otsu threshold — floor plan scans frequently have uneven lighting/scanning artifacts across the page.
6. **Deskew.** Estimate the dominant skew angle from the binarized image (via `cv2.minAreaRect` on the
   largest text/line contours, or a Hough-based dominant-angle vote) and rotate to correct. Floor plans
   are expected to be predominantly axis-aligned (walls at 0°/90°) — this assumption is exploited
   throughout the design and is documented explicitly as an MVP limitation for heavily rotated or
   non-orthogonal (angled-wall) floor plans.

Output of this stage: a clean, denoised, deskewed, binarized working image, plus the scale factor and
rotation applied (needed later to map detections back to the original upload's coordinate space if ever
required, and to compute the pixel-to-unit calibration in Section 8).

---

## 3. Wall / line detection — chosen approach: **classical CV (primary), not a pretrained model**

**Decision:** walls are detected with classical CV (morphology + Hough Line Transform), not a
pretrained segmentation model.

**Why, explicitly:** a pretrained *floor-plan-specific* wall segmentation model (e.g. approaches trained
on the CubiCasa5k dataset) does exist in the research literature, but sourcing a ready-to-use, licensed,
pip-installable checkpoint for this specific task within a 30-day MVP window is not reliably available.
Classical CV, by contrast, requires no model download, no GPU, is fully deterministic and debuggable,
and floor plan walls are a genuinely good fit for line-detection techniques (long, straight, high-contrast
segments) — this is not a compromise so much as the right tool for this specific sub-problem. This
decision is revisited as a documented future upgrade path, not a permanent constraint.

**Pipeline:**

1. **Isolate wall-like structures.** Apply morphological opening with long horizontal and long vertical
   structuring elements separately (e.g. a `1×25` and `25×1` kernel, tuned to image resolution) on the
   binarized image. This suppresses short strokes (text, furniture symbols, dimension ticks) while
   preserving long straight wall lines — the single most important noise-reduction step in the pipeline.
2. **Detect line segments.** Run `cv2.HoughLinesP` (probabilistic Hough transform) on the isolated wall
   mask, tuned for near-axis-aligned lines (per the deskew assumption in Section 2).
3. **Merge collinear/adjacent segments.** Cluster line segments that are collinear and within a small
   gap tolerance (endpoint-distance threshold) into single consolidated wall centerlines. This closes
   small gaps from broken scan lines or door/window openings interrupting a wall's line detection.
4. **Estimate thickness.** For each merged wall centerline, measure the perpendicular width of the
   corresponding blob in the binarized (non-morphed) image to estimate `Wall.thickness`.
5. **Classify exterior vs. interior.** Walls forming the outer boundary of the largest enclosing contour
   of the whole plan are tagged `wall_type: "exterior"`; all others `"interior"` — a simple, reliable
   heuristic given axis-aligned assumptions.

**Output → schema mapping:** each merged wall → one `Wall` (`start`, `end`, `thickness`, `wall_type`,
`confidence`, `source: "ai_detection"`). `height` is left `null` — the schema explicitly permits this,
and default wall height is applied downstream in Phase 4 (3D generation), not guessed here.

---

## 4. Room detection — derived geometrically, no separate model

Rooms are **not** independently detected; they are derived deterministically from the wall geometry
produced in Section 3:

1. Render the merged wall centerlines back onto a blank canvas at their estimated thickness, producing
   a clean binary wall mask.
2. Invert the mask and run `cv2.findContours` with hierarchy (`RETR_CCOMP`) to find enclosed interior
   regions bounded by walls.
3. **Filter by area.** Discard contours below a minimum area threshold (tuned in real units via the
   calibration step, Section 8) to exclude noise pockets and gaps that aren't real rooms.
4. **Simplify.** Reduce each contour to a clean polygon via `cv2.approxPolyDP` with a small tolerance,
   satisfying the schema's `Room.polygon` minimum-3-point requirement while avoiding a noisy
   pixel-for-pixel boundary.

**Output → schema mapping:** each surviving region → one `Room` (`polygon`, `confidence` derived from
how cleanly closed its bounding walls are — see Section 6). `name` and `room_type` are **not** set here;
they come from the OCR association step in Section 5. A room with no OCR-matched label keeps
`name: "Unnamed Room"` as an explicit placeholder (never left blank) and a lower confidence, since an
unlabeled room is exactly the kind of gap the correction editor exists to close.

---

## 5. Door, window, and stair detection — tiered strategy

Unlike walls, these elements are small, symbol-like, and far more visually variable across drafting
conventions — a harder fit for pure classical CV. **Two-tier strategy, decided honestly rather than
overpromising a specific checkpoint's availability:**

**Tier 1 (preferred): pretrained object detector.** A lightweight `YOLOv8n` model (via the `ultralytics`
package — CPU inference is fast enough for MVP use, no GPU required) run over the preprocessed image to
produce bounding boxes + class + confidence for door/window/stair symbols. **Open decision, to be
resolved before implementation, not assumed here:** whether a suitable pretrained checkpoint for
architectural door/window/stair symbols can actually be sourced and legally used within the project
timeline. This is flagged explicitly rather than assumed, per the constraint against overpromising tool
availability.

**Tier 2 (fallback, always available, no external dependency): classical heuristics.** If no Tier-1
model is available/usable, or as a supplement for symbol types Tier 1 misses:
- **Doors:** a gap in an otherwise-continuous wall line, combined with a short line segment or partial
  arc near the gap (the door leaf/swing arc), tagged as a door candidate at that gap's position.
- **Windows:** a short parallel double-line break within a wall segment (the two lines representing the
  window's glass/frame profile as drawn), distinguished from a door gap by the absence of a leaf/arc.
- **Stairs:** a cluster of evenly-spaced parallel short line segments within a bounded region (the tread
  pattern), consistent spacing and length being the key discriminator from other line clusters.

Whichever tier produces a detection, the result is normalized to the same output shape before assembly
(Section 8) — the rest of the pipeline does not need to know which tier produced a given element.

**Output → schema mapping:**
- Door/window bounding box center → projected onto its nearest wall's centerline → `Door.wall_id` /
  `Window.wall_id` + `position` (normalized 0–1 along that wall, per the schema).
- Door/window bounding box width, measured along the wall's direction and converted to real units via
  calibration (Section 8) → `Door.width` / `Window.width`. This is the only linear dimension of a
  door/window that this pipeline can determine.
- `Door.height`, `Window.height`, and `Window.sill_height` are **vertical dimensions that are not
  visible in a top-down 2D floor plan view at all** — a plan shows the wall opening's width, not its
  elevation. These fields are therefore **always left `null`** by this pipeline (not "not confidently
  detected" — genuinely not present in the input), and sensible defaults are applied downstream in
  Phase 4 (3D generation), exactly like `Wall.height`. Documenting this explicitly here so detection pipeline
  implementation doesn't spend time chasing a signal that doesn't exist in a plan-view image.
- `Door.swing` — inferred from the arc's curve direction where a Tier-1/Tier-2 arc is detected;
  left `null` when no arc is confidently found (e.g. the door was only located via a wall gap with no
  visible swing line).
- Stair region → simplified polygon → `Stair.polygon`. `direction` is set when an arrow/tread-sequence
  pattern gives a confident up/down read (Tier 2 heuristic); `step_count` is set only when individual
  tread lines are cleanly countable within the region — both are left `null` otherwise, per the schema's
  optionality.

---

## 6. Confidence scoring — per element type

Every `ElementBase.confidence` populated by this pipeline follows one of these rules, always clipped to
`[0.0, 1.0]`:

| Element type | Confidence source |
|---|---|
| `Wall` | Normalized Hough-vote strength combined with how consistent the merged segment's collinearity was (tighter merges → higher confidence). |
| `Room` | How completely its boundary is composed of detected walls vs. inferred/gap-filled edges — a room fully enclosed by high-confidence walls scores higher than one with gaps that had to be closed algorithmically. |
| `Door` / `Window` / `Stair` (Tier 1) | The object detector's own class confidence score, used directly. |
| `Door` / `Window` / `Stair` (Tier 2 heuristic) | A fixed, deliberately conservative confidence ceiling (e.g. `0.5`) — heuristic detections are structurally plausible but meaningfully less reliable than a trained detector's score, and should visually stand out as "needs review" in the Phase 3 editor. |
| `DimensionAnnotation` (OCR) | The OCR engine's own per-text-block confidence, discounted further if the text-to-geometry association (Section 7) was ambiguous (e.g. multiple candidate lines equally near the text). |

This tiering matters downstream: the 2D correction editor (Phase 3) can use confidence to visually flag
"low confidence — please review" elements, and low-confidence Tier 2 heuristic detections are exactly
the elements most likely to need a human's attention.

---

## 7. OCR — engine selection and text association

**Selected engine: EasyOCR (primary), Tesseract/`pytesseract` (fallback).**

**Why:** EasyOCR is pure PyTorch, installs cleanly via pip with no external binary dependency, and — most
importantly for this use case — handles **rotated text natively**, which matters because floor plan
dimension labels and some room names are frequently printed vertically or at an angle. Its tradeoff is
that it downloads pretrained detection/recognition weights on first run, requiring network access.
**Tesseract is the offline fallback**: no weight download required (system-installed binary + wrapper),
lower accuracy on rotated/stylized text, but guarantees the pipeline can still produce *some* OCR output
in a fully offline environment. `PaddleOCR` (mentioned as an option in `docs/ARCHITECTURE.md`) was
considered and set aside for the MVP specifically because of its heavier install footprint
(the full PaddlePaddle framework) relative to EasyOCR's plain PyTorch dependency, which is already a
project dependency elsewhere.

**Pipeline:**

1. Run OCR once over the full preprocessed image (not per-room-crop, to catch text that spans or sits
   near room boundaries), producing text blocks with bounding boxes, rotation, and per-block confidence.
2. **Classify each text block** by simple pattern matching:
   - Matches a measurement pattern (e.g. `\d+'-?\d*"?`, `\d+(\.\d+)?\s*(ft|m|cm|in)`) → candidate
     dimension label.
   - Matches a room-type keyword list (`bedroom`, `kitchen`, `bathroom`, `living room`, `closet`,
     `garage`, `hallway`, etc., case-insensitive, extensible list maintained in code, not hardcoded
     inline) → candidate room name.
   - Anything else → attached as free-form `metadata` on the nearest element, not force-fit into a
     structured field.
3. **Associate room-name candidates to rooms** via a point-in-polygon test (Shapely `Polygon.contains`)
   against each detected `Room.polygon` — the room whose polygon contains the text block's center point
   claims that label as its `name` (and best-effort `room_type` from the keyword match).
4. **Associate dimension candidates to geometry.** If a plausible nearby dimension line was also
   detected geometrically (a long thin line near the text, distinct from wall lines), its endpoints
   become `DimensionAnnotation.start`/`end`. If no such line is found, a short default span centered on
   the text block's bounding box is used instead, and this fallback is reflected in a lower confidence
   score (Section 6) — the annotation is still schema-valid, just explicitly lower-trust.

---

## 8. Postprocessing, cleanup, and unit calibration

Applied after raw detection, before final assembly:

- **Wall merging** (already covered in Section 3, step 3) — deduplicates near-collinear/overlapping
  segments into single walls.
- **Endpoint snapping.** Wall endpoints within a small pixel tolerance of each other are snapped
  together, closing tiny gaps that would otherwise prevent clean room-contour extraction in Section 4.
- **Room-area noise filtering** (already covered in Section 4, step 3).
- **Door/window non-max suppression.** Overlapping Tier-1 detector boxes for the same symbol are
  collapsed to the single highest-confidence box before wall projection.
- **Unit calibration — the critical, explicit step.** The schema's coordinates are in real-world units
  (`feet`/`meters`/etc.), but every detection above happens in **pixel space**. A pixel-to-unit scale
  factor must be established before final coordinates can be written into the `FloorPlan` document:
  1. **Preferred:** if at least one OCR-detected dimension label (Section 7) was successfully associated
     with a geometric line whose pixel length is known, compute `scale = stated_value / pixel_length`
     from that pairing. If multiple such pairings exist, use their median for robustness against a
     single misread digit.
  2. **Fallback:** if no dimension label was confidently associated with geometry, apply a **documented
     default assumption** (e.g. assume the longest detected exterior wall run corresponds to a plausible
     default building width) and set `units: "feet"` with every element's confidence discounted and
     `metadata.notes` explicitly stating that no calibration reference was found and coordinates are a
     rough estimate pending manual correction. This is a deliberate, visible degradation — never a
     silent guess presented with false confidence.

---

## 9. Assembly — from raw detections to a validated `FloorPlan`

1. Collect all detected/derived elements from Sections 3–7 into their respective schema collections
   (`rooms`, `walls`, `doors`, `windows`, `stairs`, `dimensions`). `furniture` is left empty — furniture
   detection/placement is out of scope for Phase 2 (it's introduced manually in Phase 5).
2. Assign every element a unique `id` (collection-prefixed, e.g. `wall-{n}`, `room-{n}`), `source:
   "ai_detection"`, and the confidence value computed per Section 6.
3. Populate `FloorPlan.metadata`: `detection_version` (a version tag for this pipeline, incremented as
   the pipeline evolves), `source_image_reference` (the stored upload path), and `notes` (calibration
   fallback warnings, low-resolution upscaling warnings, or any other pipeline-level caveats worth
   surfacing to a human reviewer).
4. Set `units` per the calibration outcome (Section 8) and `project_id` from the calling context.
5. **Validate before returning.** The assembled dict is passed through the existing
   `app.floorplan.validator.parse_floorplan()` from the schema foundation — **this pipeline does not implement its
   own validation logic**; it reuses the canonical validator so detection output is held to exactly the
   same structural rules (unique ids, valid `wall_id` references, etc.) as manually-edited data. If
   assembly ever produces a `wall_id` reference to a wall that was filtered out in postprocessing, that
   is a pipeline bug to fix in the detection testing pass, not a case for the validator to special-case.

**Every FloorPlan field's detection source, at a glance:**

| Schema field | Detection source |
|---|---|
| `project_id` | Calling context (the project being processed), not detected. |
| `units` | Unit calibration (Section 8). |
| `rooms[].polygon` | Derived from wall geometry (Section 4). |
| `rooms[].name` / `room_type` | OCR association (Section 7), placeholder `"Unnamed Room"` if none matched. |
| `walls[].start/end/thickness/wall_type` | Classical CV line detection (Section 3). |
| `walls[].height` | Not visible in a top-down plan view — always `null`, default applied later in Phase 4. |
| `doors[].wall_id` / `position` | Projection onto nearest detected wall (Section 5). |
| `doors[].width`, `windows[].width` | Bounding-box/gap width along the wall, converted via unit calibration (Section 5, Section 8). |
| `doors[].height`, `windows[].height`, `windows[].sill_height` | Vertical dimensions, not visible in a top-down plan view — always `null` from this pipeline, defaults applied later in Phase 4 (Section 5). |
| `doors[].swing` | Arc-direction inference where a swing arc is confidently detected; otherwise `null` (Section 5). |
| `stairs[].polygon` | Tiered detector / parallel-line heuristic (Section 5). |
| `stairs[].step_count` / `direction` | Set only when confidently inferable (countable treads / arrow); `null` otherwise. |
| `dimensions[]` | OCR text matching a measurement pattern, associated to nearby geometry (Section 7). |
| `furniture[]` | Out of scope for Phase 2 — always empty from this pipeline. |
| every element's `confidence` | Section 6. |
| every element's `source` | Always `"ai_detection"` for pipeline output. |
| `metadata.*` | Assembly step (Section 9), calibration/quality notes. |

---

## 10. Conceptual walkthrough (design validation)

**Walkthrough 1 — the schema foundation example fixture's building, imagined as a scan:** a simple rectangular
two-room layout with an exterior door, an interior connecting door, two windows, and one small stair
region. Preprocessing deskews and binarizes cleanly (clean synthetic-style input). Wall detection finds
the 4 exterior + 1 interior wall as long straight Hough segments with high confidence. Room detection
correctly derives 2 enclosed regions. OCR finds "Living Room" and "Bedroom" text and associates each to
its containing polygon via point-in-polygon. The exterior/interior doors are found via Tier 1 (or Tier 2
gap-detection if no model is available) and projected onto their respective walls. This walkthrough maps
cleanly onto every schema field with no gaps — confirming the design output is schema-compatible.

**Walkthrough 2 — a lower-quality hand-drawn scan with a skewed page and no dimension text:** deskew
partially corrects the rotation (documented limitation: heavy skew or non-orthogonal walls degrade
results). Wall/room detection still produces a rough structural layout, but with lower confidence scores
throughout due to less clean line detection. No dimension label is found, so unit calibration falls back
to the documented default-assumption path (Section 8), and `metadata.notes` explicitly flags this.
Several door/window detections fall to Tier 2 heuristics with the conservative confidence ceiling. The
output is still schema-valid and passes `parse_floorplan()`, but is visibly lower-confidence throughout
— exactly the scenario the Phase 3 correction editor exists to handle, and exactly why confidence scoring
(Section 6) matters as a signal rather than decoration.

Both walkthroughs confirm: the design always produces a structurally valid `FloorPlan`, degrading via
confidence scores and metadata notes rather than failing outright, on both a clean and a difficult input.

---

## 11. Explicitly out of scope for this pipeline (Phase 2)

- Multi-page PDF floor plan sets (first page only).
- Non-orthogonal (angled) wall layouts — the axis-aligned assumption is load-bearing throughout Sections
  2–4 and is a known MVP limitation, not an oversight.
- Multi-story detection from a single image (each upload is treated as one floor).
- Furniture detection (introduced manually in Phase 5, not detected from the scan).
- Training or fine-tuning any model — Tier 1 in Section 5 uses an existing pretrained checkpoint or is
  skipped in favor of Tier 2 entirely; it is never trained within this project.

---

## 12. Summary of chosen tools (for detection pipeline implementation)

| Task | Tool |
|---|---|
| PDF rasterization | `pdf2image` or `PyMuPDF` |
| Image processing | OpenCV (`cv2`) |
| Line/wall detection | `cv2.HoughLinesP` + morphological preprocessing (classical CV, no pretrained model) |
| Room derivation | `cv2.findContours` on the wall mask (classical CV, no separate model) |
| Door/window/stair detection | `ultralytics` YOLOv8n (Tier 1, pending checkpoint sourcing) + classical heuristics (Tier 2, always available) |
| OCR | `easyocr` (primary), `pytesseract` (offline fallback) |
| Geometry/coordinates | NumPy + Shapely (point-in-polygon, polygon simplification support) |
| Schema validation | `app.floorplan.validator.parse_floorplan()` (reused from schema foundation, not reimplemented) |

All tools are pip-installable, pretrained-or-classical (no training), and consistent with the technology
stack already committed to in `docs/ARCHITECTURE.md` Section 9.
