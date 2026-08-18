# FLOORPLAN_SCHEMA.md

The canonical FloorPlan data contract. Every subsystem (detection, correction editor, 3D generation,
LLM assistant, estimation, sustainability, export) reads from or writes to this exact shape.

**Source of truth:** `backend/app/floorplan/schema.py` (Pydantic v2). The TypeScript mirror lives at
`frontend/src/types/floorplan.ts` and must match field-for-field. A worked example satisfying every
rule below lives at `data/samples/example_floorplan.json`.

**Stability rule (see `docs/ARCHITECTURE.md` Section 4):** no subsystem may introduce a new top-level
field, remove a field, or change what an existing field means without updating this document and
`docs/ARCHITECTURE.md` first. Adding a new *optional* field to an existing element type is acceptable
without a version bump; anything else is a breaking change.

---

## Coordinate system

- 2D, origin at the **top-left** of the source floor plan image/drawing.
- `x` increases rightward, `y` increases downward (standard image/screen convention — **not**
  standard Cartesian).
- All coordinates and lengths are in the unit given by the document's top-level `units` field.
- How this maps into the 3D scene's coordinate system (Three.js: y-up) is defined separately in
  `docs/3D_GENERATION_DESIGN.md` (Phase 4 3D generation design) — this document only defines the 2D contract.

---

## Top-level document: `FloorPlan`

| Field | Type | Required | Notes |
|---|---|---|---|
| `project_id` | `string` | Yes | Must be non-blank. Identifies which `Project` record this document belongs to. |
| `units` | `"feet" \| "meters" \| "inches" \| "centimeters"` | Yes (default `"feet"`) | Applies to every coordinate/length in the document. |
| `rooms` | `Room[]` | Yes (default `[]`) | |
| `walls` | `Wall[]` | Yes (default `[]`) | |
| `doors` | `Door[]` | Yes (default `[]`) | |
| `windows` | `Window[]` | Yes (default `[]`) | |
| `stairs` | `Stair[]` | Yes (default `[]`) | |
| `dimensions` | `DimensionAnnotation[]` | Yes (default `[]`) | OCR-extracted or manually placed measurement lines/labels — distinct from the geometry itself. |
| `furniture` | `FurnitureItem[]` | Yes (default `[]`) | |
| `metadata` | `FloorPlanMetadata` | Yes (default empty) | Document-level metadata. Distinct from per-element `metadata`. |

**Do not add feature-specific fields here** (e.g. estimation totals, sustainability scores). Those are
computed on demand by their own modules from this data — they are never stored on the FloorPlan itself.

---

## Shared element fields: `ElementBase`

Every element in every collection (`Room`, `Wall`, `Door`, `Window`, `Stair`, `DimensionAnnotation`,
`FurnitureItem`) includes these fields in addition to its own:

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | `string` | Yes | Must be unique **across the entire document**, not just within its own collection. Enforced by the structural validator, not Pydantic field validation alone. |
| `confidence` | `number \| null` | No | Range `0.0`–`1.0`. Populated by AI detection; `null` or `1.0` for manually created/corrected elements. |
| `source` | `"ai_detection" \| "manual_correction"` | Yes (default `"manual_correction"`) | |
| `metadata` | `object` | Yes (default `{}`) | Free-form, element-specific. |

---

## `Room`

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | `string` | Yes | |
| `polygon` | `Point2D[]` | Yes | Minimum 3 points. Ordered vertices forming a closed boundary (do not repeat the first point as the last). |
| `room_type` | `string \| null` | No | Free-form, e.g. `"bedroom"`, `"kitchen"`. |

## `Wall`

| Field | Type | Required | Notes |
|---|---|---|---|
| `start`, `end` | `Point2D` | Yes | |
| `thickness` | `number \| null` | No | Must be `> 0` if present. No hard default at the schema level — 3D generation (Phase 4) applies a documented default for walls with none set. |
| `height` | `number \| null` | No | Must be `> 0` if present. Same default-handling note as `thickness`. |
| `wall_type` | `"exterior" \| "interior"` | Yes (default `"interior"`) | |

## `Door`

| Field | Type | Required | Notes |
|---|---|---|---|
| `wall_id` | `string` | Yes | Must reference an existing `Wall.id` in the same document (structural validator enforces this). |
| `position` | `number` | Yes | Normalized `0.0`–`1.0` along the wall, `0` = wall's `start`, `1` = wall's `end`. |
| `width` | `number` | Yes | Must be `> 0`. |
| `height` | `number \| null` | No | Must be `> 0` if present. |
| `swing` | `"left" \| "right" \| "sliding" \| "none" \| null` | No | |

## `Window`

| Field | Type | Required | Notes |
|---|---|---|---|
| `wall_id` | `string` | Yes | Must reference an existing `Wall.id` (structural validator enforces this). |
| `position` | `number` | Yes | Normalized `0.0`–`1.0` along the wall. |
| `width` | `number` | Yes | Must be `> 0`. |
| `height` | `number \| null` | No | Must be `> 0` if present. |
| `sill_height` | `number \| null` | No | Must be `>= 0` if present. |

## `Stair`

| Field | Type | Required | Notes |
|---|---|---|---|
| `polygon` | `Point2D[]` | Yes | Minimum 3 points — the staircase's footprint. |
| `step_count` | `integer \| null` | No | Must be `> 0` if present. |
| `direction` | `string \| null` | No | Free-form, e.g. `"up"`, `"down"`. |

## `DimensionAnnotation`

| Field | Type | Required | Notes |
|---|---|---|---|
| `start`, `end` | `Point2D` | Yes | Endpoints of the measurement line. |
| `value` | `number` | Yes | Must be `> 0`. The measured length, in the document's `units`. |
| `label` | `string \| null` | No | Raw text as extracted/entered, e.g. `"24'-0\""`. |

## `FurnitureItem`

| Field | Type | Required | Notes |
|---|---|---|---|
| `furniture_type` | `string` | Yes | Free-form, e.g. `"bed"`, `"sofa"`, `"dining_table"`. |
| `position` | `Point2D` | Yes | |
| `rotation` | `number` | Yes (default `0`) | Degrees, clockwise from the coordinate system's `+x` axis. |
| `width`, `depth`, `height` | `number \| null` | No | Must be `> 0` if present. |
| `room_id` | `string \| null` | No | If present, must reference an existing `Room.id` (structural validator enforces this). |

## `FloorPlanMetadata` (document-level)

| Field | Type | Required | Notes |
|---|---|---|---|
| `building_name` | `string \| null` | No | |
| `detection_version` | `string \| null` | No | Version tag of the detection pipeline that produced this document, if any. |
| `source_image_reference` | `string \| null` | No | Path/reference to the originally uploaded file. |
| `notes` | `string \| null` | No | |
| `extra` | `object` | Yes (default `{}`) | Free-form escape hatch — prefer adding a real optional field here over stuffing data into `extra` long-term. |

## `Point2D`

| Field | Type | Required |
|---|---|---|
| `x` | `number` | Yes |
| `y` | `number` | Yes |

---

## Validation layers

1. **Field-level** (`backend/app/floorplan/schema.py`, Pydantic v2): types, required/optional, numeric
   ranges (e.g. `confidence` in `[0,1]`, `width > 0`), minimum polygon length.
2. **Structural** (`backend/app/floorplan/validator.py`): checks that span multiple elements and that
   Pydantic's per-field validators cannot see on their own:
   - Every `id` is unique across the **entire document**, not just within its own collection.
   - Every `Door.wall_id` / `Window.wall_id` references a `Wall` that actually exists.
   - Every `FurnitureItem.room_id` (if set) references a `Room` that actually exists.

Both layers must pass for a FloorPlan document to be considered valid. Use
`validate_floorplan(data) -> FloorPlanValidationResult` for a non-raising check (inspect `.is_valid` /
`.errors`), or `parse_floorplan(data) -> FloorPlan` to raise `ValidationAppError` (mapped to an HTTP 422
with the standard `{"error": {...}}` shape) on failure.

---

## Storage

`Project.floorplan_data` (`backend/app/models/project.py`) is a single JSON/JSONB column holding one
FloorPlan document per project — `JSON` on SQLite (local dev/tests), `JSONB` on PostgreSQL (production),
via the same column definition. It is nullable: a freshly created project has no FloorPlan until Phase 2
(AI detection) or Phase 3 (manual creation) populates it.

This is intentionally a single "current" document, not a version history. How raw-detection output and
manually-corrected output are represented on top of this column (e.g. overwrite vs. separate versions)
is decided in Phase 2/3 without requiring a change to this column's type or name.

---

## Example

See `data/samples/example_floorplan.json` for a complete, valid, two-room building exercising every
element type (rooms, walls — exterior and interior, doors, windows, a stair, dimension annotations, and
a furniture item).
