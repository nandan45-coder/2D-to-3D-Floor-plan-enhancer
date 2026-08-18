# PROJECT_MASTER.md

**This is the master project context and specification document.**
Any development work should begin by reviewing this file, `docs/ARCHITECTURE.md`, and
`docs/DEVELOPMENT_STATUS.md` before writing code.

---

## 1. Objective

Build a 30-day MVP of an AI-powered platform that converts a 2D architectural floor plan into a
structured digital representation, allows manual correction, generates an interactive 3D building,
and provides spatial, estimation, and sustainability intelligence — including a first-person
walkthrough, an LLM-grounded assistant, area/material/cost estimation, and an explainable
sustainability score.

Full functional scope (see `ARCHITECTURE.md` Section 6 for details):
upload → AI detection + OCR → manual 2D correction → save structured FloorPlan → automatic 3D
generation → walkthrough + furniture + lighting → LLM assistant → area/material/cost estimation →
sustainability analysis → 3D/data export.

---

## 2. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript, Tailwind CSS |
| 2D editor | Konva.js (SVG/Canvas) |
| 3D | Three.js + React Three Fiber |
| Backend | Python + FastAPI |
| CV | OpenCV + pretrained detection model |
| OCR | PaddleOCR / EasyOCR / Tesseract |
| Geometry | NumPy + Shapely |
| Graph | NetworkX |
| LLM | Gemini / OpenAI / other (tool/function-calling) |
| Database | PostgreSQL (optionally PostGIS) |
| Caching | Redis (optional) |
| Testing | Pytest (backend), frontend test framework |
| Containerization | Docker |

Full detail in `docs/ARCHITECTURE.md` Section 9.

---

## 3. Development Conventions

- **Shared data contract first.** Every module reads/writes the single canonical `FloorPlan` JSON
  object (documented in `docs/FLOORPLAN_SCHEMA.md`). No module invents its own
  parallel representation of building data.
- **Modular development.** Build one coherent feature per development task — avoid scope creep.
- **Analyze → Implement → Verify.** For any significant feature: inspect existing code first, implement
  only what's required, then test and fix before moving on.
- **Focused change scope.** Modify only the files required for the current feature or fix. Preserve completed,
  working modules.
- **Backward-compatible schema.** The FloorPlan JSON contract must remain backward compatible across
  all development phases once finalized.
- **Pretrained/API-based AI only.** No model is trained from scratch (CV, OCR, or LLM). This is a hard
  constraint, not a suggestion — it is what makes the 30-day timeline realistic.
- **MVP honesty in every user-facing output.** Estimation results are preliminary MVP estimates, not
  professional engineering/quantity-surveying quotes. Sustainability results are preliminary MVP
  estimates, not certified green-building ratings. 3D lighting is realistic MVP-quality visualization,
  not professional architectural lighting simulation. These disclaimers must appear in the actual UI,
  not just in documentation.
- **Checkpoint after each phase.** Run the application, tests, and manual verification before starting
  the next phase.
- **Status log after every task.** Update `docs/DEVELOPMENT_STATUS.md` after each meaningful task or
  phase using standard status blocks.

---

## 4. Scope Priorities (P0 / P1 / P2)

See `docs/ARCHITECTURE.md` Section 7 for the full table. Summary:

- **P0 (must work):** upload, AI detection, manual correction, FloorPlan contract, 2D→3D generation, walkthrough.
- **P1 (use deterministic calc + API-based AI):** LLM assistant, area/material/cost estimation, sustainability.
- **P2 (cut first under time pressure):** large furniture library, advanced rendering, multiple export formats, advanced simulations.

---

## 5. Repository Structure (Current)

```
project/
├── backend/     (FastAPI backend application)
├── frontend/     (React + TypeScript application)
├── models/      (empty — populated Phase 2)
├── assets/      (empty — populated Phase 5)
├── data/        (empty — sample floor plans added Phase 2)
├── tests/       (empty — integration tests added progressively)
├── docs/        (ARCHITECTURE.md, PROJECT_MASTER.md, DEVELOPMENT_STATUS.md)
├── scripts/     (empty)
└── docker/      (empty — populated Phase 10)
```

---

## 6. Current Status

**Phase:** 2 — AI Detection Pipeline
**Status:** Phase 1 Complete (Foundation), Phase 2 in progress.

See `docs/DEVELOPMENT_STATUS.md` for the detailed status log.

---

## 7. Reference Documents

- `docs/ARCHITECTURE.md` — finalized system architecture (this project's source of truth for structure).
- `docs/FLOORPLAN_SCHEMA.md` — canonical FloorPlan JSON field reference.
- `docs/DEVELOPMENT_STATUS.md` — running log of completed/in-progress/pending work, updated after every milestone.
- `docs/API_SPEC.md` — created progressively as backend routes are implemented.
