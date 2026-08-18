# ARCHITECTURE.md

## AI-Powered Floor Plan to 3D Building Intelligence System

**Status:** Finalized reference architecture
**Scope:** 30-day MVP
**Last updated:** Initial Architecture Design Phase

This document is the authoritative architecture reference for the entire project. All subsequent development
must remain consistent with what is defined here. If any feature requires a deviation from
this document, the deviation must be recorded here and in `DEVELOPMENT_STATUS.md` before implementation
continues.

---

## 1. Repository Inspection Result

The repository was inspected before this document was written. Findings:

- No existing `backend/`, `frontend/`, `models/`, `assets/`, `data/`, `docs/`, or `docker/` content was
  present prior to project initiation.
- No existing `package.json`, `requirements.txt`, or environment files were present.
- No existing database schema, migrations, API routes, React components, CV pipeline, or LLM
  integration code was present.
- No existing documentation (`README.md`, `ARCHITECTURE.md`, etc.) was present.

**Conclusion:** This is a greenfield project. The top-level repository skeleton has been created fresh
(see Section 8). No existing code was reused, modified, or deleted.

---

## 2. System Purpose

The system converts a 2D architectural floor plan (image or PDF) into a structured digital
representation, lets a user manually correct detected elements, generates an interactive 3D building
from the corrected data, and layers spatial, estimation, and sustainability intelligence on top —
including a first-person walkthrough, an LLM-grounded assistant, area/material/cost estimation, and an
explainable MVP sustainability score.

---

## 3. Layered Architecture

```
USER
  |
  v
REACT FRONTEND (TypeScript, Tailwind CSS)
  - Upload & Project Dashboard
  - 2D Floor Plan Editor
  - 3D Viewer / Walkthrough
  - AI Assistant (Chat)
  - Cost & Area Dashboard
  - Sustainability Dashboard
  |
  v
FASTAPI BACKEND / API LAYER
  - Project & File APIs
  - Floor Plan Detection Service
  - OCR Service
  - Correction / FloorPlan Service
  - 3D Generation Service
  - LLM / Tool Service
  - Estimation Service
  - Sustainability Service
  |
  v
PROCESSING LAYER
  - OpenCV / Detection / OCR
  - NumPy / Shapely Geometry
  - NetworkX Graph Analysis
  - LLM API (Gemini / OpenAI / other)
  |
  v
DATA + ASSET LAYER
  - PostgreSQL (optionally PostGIS)
  - Uploaded floor plans (file/object storage)
  - 3D assets / GLB files
  - Project JSON (FloorPlan contract)
```

This is a strict one-directional dependency chain for data flow: the frontend never talks to the
processing or data layer directly — everything routes through the FastAPI API layer. This keeps every
subsystem replaceable/testable in isolation.

---

## 4. The Shared FloorPlan Data Contract

Every major subsystem (detection, correction editor, 3D generation, LLM assistant, estimation,
sustainability, export) reads from or writes to a single canonical `FloorPlan` JSON representation.
This is the single most important architectural decision in the system: it prevents subsystems from
maintaining incompatible private representations of the same building.

Required top-level fields (finalized in full detail in schema specification):

```json
{
  "project_id": "string",
  "units": "feet | meters",
  "rooms": [],
  "walls": [],
  "doors": [],
  "windows": [],
  "stairs": [],
  "dimensions": [],
  "furniture": [],
  "metadata": {}
}
```

Each element (room, wall, door, window, stair) additionally carries: coordinates, relationships to
other elements (e.g., a door's parent wall), a confidence value (populated by AI detection, `1.0` for
manually created/corrected elements), a `source` field (`ai_detection` | `manual_correction`), and
element-specific metadata.

**Rule:** No subsystem may introduce a new top-level field or change the meaning of an existing field
without updating `docs/FLOORPLAN_SCHEMA.md` and this document.

---

## 5. Module Boundaries and Responsibilities

| Component | Responsibility |
|---|---|
| Frontend | Interaction, visualization, editing, dashboards, chat, 3D controls. Never computes domain logic (areas, costs, scores) itself — only displays backend-computed values. |
| API layer | Authentication (if used), request validation, routing, consistent response/error formatting. |
| CV/OCR layer | Turn floor-plan images into candidate architectural elements + text/dimension labels. Pretrained models only. |
| Geometry layer | Maintain coordinates, polygons, intersections, dimensions, and areas (NumPy/Shapely). |
| 3D layer | Generate/render 3D geometry and interactive navigation (Three.js / React Three Fiber). |
| LLM layer | Answer natural-language questions using structured building data via deterministic backend tools — never as the source of truth for numbers. |
| Estimation layer | Perform deterministic area/material/cost calculations with configurable rates. |
| Sustainability layer | Build a spatial graph (NetworkX) and calculate explainable, MVP-level sustainability indicators. |
| Persistence layer | Store projects, FloorPlan JSON, metadata, and references to files/assets (PostgreSQL + file/object storage). |

---

## 6. Functional Modules (Full Coverage)

The architecture covers all of the following subsystems end to end:

1. **Floor Plan AI Detection** — image preprocessing, wall/room/door/window/stair detection, OCR.
   Full pipeline design (chosen tools, per-element approach, confidence scoring, unit calibration):
   see `docs/DETECTION_PIPELINE.md` (Detection Pipeline Design). Summary: walls/rooms use classical CV (Hough line
   detection + contour extraction on the resulting wall mask, no pretrained model); doors/windows/
   stairs use a tiered approach (pretrained YOLOv8n detector where a suitable checkpoint can be
   sourced, classical heuristics as an always-available fallback); OCR uses EasyOCR primary /
   Tesseract offline fallback for room labels and dimension text.
2. **Manual 2D Correction** — interactive editor to inspect/correct detected elements.
3. **2D → 3D Generation** — converts a corrected FloorPlan into 3D geometry.
4. **Walkthrough, Furniture & Lighting** — first-person navigation, collision, furniture placement, day/night lighting (MVP-quality, not professional architectural lighting simulation).
5. **LLM Assistant** — natural-language, tool-grounded spatial Q&A.
6. **Estimation Engine** — area, material quantity, and cost calculations (preliminary MVP estimate, not a professional engineering/quantity-surveying output).
7. **Sustainability Engine** — graph-based connectivity plus daylight/ventilation/window-floor-ratio indicators (preliminary MVP estimate, not a certified green-building rating).
8. **Export** — 3D (GLB/GLTF) and structured project-data export.
9. **Persistence & Project Management** — project CRUD, versioned FloorPlan storage.
10. **Integration Layer** — the workflow wiring connecting all of the above into one continuous user journey (Upload → Export).

---

## 7. Scope Control — P0 / P1 / P2 Classification

Per the 30-day scope-control plan, every subsystem above is classified so that time pressure has a
predefined, non-negotiable order of what gets simplified first:

| Priority | Subsystems | Approach |
|---|---|---|
| **P0 — Core** | Upload, AI detection, manual correction, FloorPlan JSON contract, 2D→3D generation, walkthrough | Must be functional. Simplify algorithms/visuals if necessary, but these cannot be dropped. |
| **P1 — Intelligence** | LLM assistant, area estimation, material/cost estimation, sustainability analysis | Use deterministic calculations and API-based AI (no custom model training). Can be simplified in depth, not removed. |
| **P2 — Visual Polish** | Large furniture library, advanced rendering/shadows, multiple export formats, advanced simulations | Implement only a useful MVP version if time permits. First to be cut under time pressure. |

If the 30-day schedule slips, P2 is reduced or cut first, then P1 depth is reduced, before any P0 scope
is touched.

---

## 8. Repository Skeleton

```
project/
├── backend/       (FastAPI application — implemented starting Phase 1)
├── frontend/       (React + TypeScript application — implemented starting Phase 1)
├── models/         (pretrained CV/OCR model weights — populated starting Phase 2)
├── assets/         (furniture, materials, environment 3D assets — populated starting Phase 5)
├── data/           (sample floor plans, processed data)
├── tests/           (integration tests, cross-module)
├── docs/           (this document + all project documentation)
├── scripts/         (setup/seed scripts)
└── docker/         (containerization — populated in Phase 10)
```

Initially, only the top-level folders were created (empty, with `.gitkeep` placeholders). Implementation
files, feature code, and subfolder structures were added in subsequent development phases.

---

## 9. Technology Stack (Reference)

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript, Tailwind CSS |
| 2D editor | SVG/Canvas via Konva.js (or equivalent) |
| 3D rendering | Three.js + React Three Fiber |
| 3D assets | GLB/GLTF |
| Backend | Python + FastAPI |
| Computer vision | OpenCV + pretrained detection model |
| OCR | PaddleOCR / EasyOCR / Tesseract |
| Geometry | NumPy + Shapely |
| LLM | Gemini / OpenAI / other selected LLM API (tool/function-calling required) |
| Graph analysis | NetworkX |
| Database | PostgreSQL (optionally PostGIS) |
| Caching | Redis (optional) |
| File storage | Local/object storage |
| Testing | Pytest + a frontend test framework |
| Containerization | Docker |
| Version control | Git + GitHub |

**Explicit constraint:** pretrained CV/OCR models and existing LLM APIs are used throughout. No model is
trained from scratch in this project. This is what makes the 30-day timeline achievable.

---

## 10. Undefined Inputs/Outputs Self-Check

Every module boundary above has a defined input and output:

- CV/OCR layer: **input** = uploaded image/PDF, **output** = candidate elements + confidence scores.
- Geometry layer: **input** = raw candidate elements, **output** = validated FloorPlan JSON.
- 3D layer: **input** = corrected FloorPlan JSON, **output** = 3D scene geometry.
- LLM layer: **input** = user question + FloorPlan JSON (via tools), **output** = grounded natural-language answer.
- Estimation layer: **input** = corrected FloorPlan JSON + rate config, **output** = areas/quantities/costs.
- Sustainability layer: **input** = corrected FloorPlan JSON, **output** = indicators + score + recommendations.
- Persistence layer: **input** = any of the above, **output** = stored/retrievable project record.

No module has an undefined input or output at this stage.

---

## 11. Deviation Log

*(Empty at project start. Any future phase that must deviate from this architecture records the
deviation here, with the phase/task ID, reason, and date.)*

| Task / Phase | Deviation | Reason |
|---|---|---|
| — | — | — |
