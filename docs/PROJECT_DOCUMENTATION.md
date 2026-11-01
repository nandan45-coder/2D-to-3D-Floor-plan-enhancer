# Floor Plan to 3D Building Intelligence System

### Project documentation and completion report

Version 1.0, October 2026

---

## Contents

1. About the project
2. What the finished system can do
3. How it is built
4. The floor plan data model
5. Module by module
6. Accounts and security
7. Installing and running it
8. Running it with Docker
9. Using the application
10. API overview
11. Testing and results
12. Problems we ran into and how we solved them
13. Project status
14. Known limitations
15. Third-party licences
16. Ideas for the next version

---

## 1. About the project

Most floor plans still live as flat images or PDFs. You can look at them, but you can't ask them anything: how big
the kitchen is, how much paint the bedroom walls need, whether the rooms get enough daylight, or what it would feel
like to stand in the living room. The goal of this project was to close that gap.

The system takes an ordinary 2D floor plan, detects the walls, rooms, doors, windows and stairs on it, and turns it
into a structured digital plan. The user checks and corrects that plan in an editor. From the corrected plan the
system builds a 3D model that you can walk through, furnish, paint and light, and on top of it we added an assistant
that answers questions about the building, a material and cost estimate, a sustainability assessment, and reports
and exports.

The work was planned as a 30-day MVP in ten phases:

| Phase | Content |
|---|---|
| 1 | Foundation: backend, frontend, database, project structure |
| 2 | Floor plan detection (computer vision and OCR) |
| 3 | Manual correction in a 2D editor |
| 4 | Generating the 3D model |
| 5 | Walkthrough, furniture, wall painting and lighting |
| 6 | The building assistant |
| 7 | Area, material and cost estimation |
| 8 | Sustainability analysis |
| 9 | Connecting everything into one workflow, reports and export |
| 10 | Testing, bug fixing, deployment and final documentation |

Along the way we also added user accounts, a redesigned interface with a guided workflow, a "draw your own plan"
option, balconies, and password reset by email code.

All ten phases are complete.

---

## 2. What the finished system can do

**Getting a plan in**
- Upload a floor plan as PNG, JPEG or PDF (first page), or start from an empty sheet and draw it.
- Automatic detection of walls, rooms, doors, windows and stairs.
- Room names and dimension labels are read with OCR, and the scale of the drawing is worked out from the
  dimension labels (formats like `12'-0"`, `28' - 0"`, `13'-4" X 9'-0"`, `3.5 m`).

**Correcting it**
- A 2D editor with tools for walls, rooms, doors, windows, dimensions, stairs and furniture, plus splitting walls
  and recomputing rooms from walls.
- Low-confidence detections are highlighted, and an issues panel lists problems. Errors block saving, warnings don't.
- Undo and redo, snapping, the uploaded drawing shown underneath for tracing, and unsaved work is kept while you move
  around the site.

**3D**
- A 3D building generated from the saved plan: walls with real door and window openings, floors, ceilings, stairs,
  balconies with railings, door leaves and glass.
- First-person walkthrough at eye height with collision against walls and furniture.
- Furniture from a catalogue with real sizes, placed in 2D or in 3D.
- Wall painting per wall side or per room.
- Daylight with a movable sun and night mode with room lights.
- Download of the building as a GLB 3D model.

**Understanding it**
- An assistant that answers questions in plain language: room sizes, wall areas for painting, doors and windows,
  which rooms connect, furniture, colours, building dimensions, problems in the plan, the cost and the score.
- Area calculation per room and for the whole building.
- Material quantities (bricks, cement, sand, aggregate, steel, tiles, flooring, paint, doors, windows, railings),
  paint per colour, and a preliminary cost with editable rates.
- A sustainability score based on window-to-floor ratio, daylight, ventilation and room connectivity, with
  recommendations that show the numbers behind them.

**Sharing it**
- A full project report as PDF, an estimate PDF, the 3D model as GLB, and the complete project data as JSON.

**Accounts**
- Sign up, sign in, profile with photo or avatar, change password, and forgot password with a 6-digit email code.
- Each user sees only their own projects.

---

## 3. How it is built

```
Browser (React + TypeScript)
  Dashboard, Upload, 2D Editor, 3D Viewer, Assistant, Estimation, Sustainability, Report, Profile
  3D geometry, walkthrough, painting and GLB export are computed here
        |
        |  JSON over HTTP, session cookie
        v
FastAPI backend (Python)
  routes:   auth, account, projects, detection, corrections, assistant, estimation, sustainability,
            activity, reports
  services: projects, floor plans, storage, accounts, password reset, email, estimation,
            sustainability, export
  logic:    detection (OpenCV, YOLO), OCR (Tesseract), geometry and validation (Shapely),
            estimation, sustainability (NetworkX), assistant tools, PDF reports (ReportLab)
        |
        v
SQLite database + files on disk (uploads, avatars, 3D snapshots)

Optional outside services: Gemini or OpenAI for the assistant, an SMTP server for reset codes.
```

A few design decisions shaped everything else:

- **One shared data model.** Every part of the system reads and writes the same JSON floor plan document (Section 4).
  Detection produces it, the editor corrects it, and the 3D model, assistant, estimate and sustainability analysis
  all read it. Nothing keeps its own private copy of the building.
- **Numbers come from the backend.** Areas, costs and scores are always calculated on the server from the saved
  plan. The browser only displays them.
- **3D is built in the browser.** We first planned a server-side 3D service, but building the geometry in the browser
  meant the model updates instantly after an edit, and the walkthrough and 3D furniture editing needed the geometry
  there anyway. The GLB download uses the same code, so it always matches what you see.
- **SQLite instead of PostgreSQL.** The original plan was PostgreSQL. For a system that has to run on a laptop and
  on a small demo server, a single database file turned out to be much simpler. The code uses SQLAlchemy, so
  PostgreSQL can still be configured later.
- **No model training.** We used a pretrained YOLOv8 model for doors and windows, off-the-shelf OCR engines, and
  existing LLM APIs for the assistant.

### Technology used

| Part | Technology |
|---|---|
| Frontend | React 18, TypeScript 5.7, Vite 6, Tailwind CSS 3.4, React Router 7 |
| 2D editor | Konva 10 with react-konva |
| 3D | three.js 0.171, React Three Fiber 8, drei |
| Backend | Python 3.12, FastAPI 0.115, Uvicorn, Pydantic 2, SQLAlchemy 2, Alembic |
| Detection | OpenCV 4.13, NumPy, Shapely 2.1, PyMuPDF (PDFs), Ultralytics 8.4.163 with PyTorch 2.13 (CPU) |
| OCR | Tesseract 5 through pytesseract; EasyOCR 1.7.2 as an optional fallback |
| Analysis | NetworkX (room graph) |
| Assistant | Gemini or OpenAI with tool calling (optional), plus a built-in offline mode |
| Reports | ReportLab |
| Database | SQLite (through SQLAlchemy, with Alembic migrations) |
| Tests | pytest, Vitest, Playwright |
| Deployment | Docker, Docker Compose, nginx |

### Folder structure

```
backend/      FastAPI application (app/), database migrations, tests, requirements
frontend/     React application (src/), tests
models/       detection/best.pt, the YOLO model for doors and windows
data/         samples/: two sample plans and an example floor plan JSON
docker/       Dockerfiles, nginx configuration, deploy.env.example
docs/         this document and screenshots
scripts/      sample plan generator
docker-compose.yml, README.md
```

Inside `backend/app`:

| Folder | What it contains |
|---|---|
| `api/` | the routes and the access check (signed in, own project) |
| `core/` | settings, database setup, password hashing and sessions, errors, logging |
| `models/`, `schemas/` | database tables and request / response models |
| `services/` | the use cases (projects, floor plans, accounts, estimation, export ...) |
| `cv/` | the detection pipeline |
| `ocr/` | text reading and matching labels to rooms |
| `floorplan/` | the floor plan schema, validation, geometry helpers, SVG thumbnails |
| `estimation/` | areas, materials, rates, cost |
| `sustainability/` | room graph, daylight, ventilation, scoring |
| `llm/` | the assistant: tools, providers, prompts, answer checking |
| `reports/` | PDF generation |
| `cli.py` | admin commands (reset a password, list users or projects, reassign projects) |

---

## 4. The floor plan data model

Each project stores one floor plan document. In short:

```json
{
  "project_id": "...",
  "units": "feet",
  "rooms": [], "walls": [], "doors": [], "windows": [],
  "stairs": [], "dimensions": [], "furniture": [],
  "metadata": { "building_name": null, "detection_version": null,
                "source_image_reference": null, "notes": null, "extra": {} }
}
```

- Coordinates are 2D with the origin at the top left of the drawing (y grows downwards), in the document's `units`
  (feet, inches, centimeters or meters). Detection writes feet.
- Every element has an `id` that is unique in the whole document, a `confidence` (from detection, empty after a manual
  edit), a `source` (`ai_detection` or `manual_correction`) and a free-form `metadata` object.
- Rooms are polygons with a name and an optional type (bedroom, kitchen, balcony ...).
- Walls have a start, an end, a thickness, an optional height and a type: exterior, interior or railing.
- Doors and windows sit on a wall: `wall_id` plus a position from 0 (wall start) to 1 (wall end) and a width.
  Windows can have a sill height.
- Stairs are polygons with an optional step count and direction. Dimensions are measured lines with their value and
  original label text.
- Furniture items have a type from the catalogue, a centre position, rotation, size and the room they stand in.
- Wall paint is stored in the wall's `metadata` per side and per room.

Validation happens in three layers: field rules (types, ranges, finite numbers, coordinates within ±1,000,000),
structural rules (unique ids, doors and windows point to real walls, furniture points to real rooms), and when the
editor saves, geometric rules. Geometric errors (a room outline crossing itself, a wall with no length, an invalid
paint colour) block saving; warnings (an opening past a wall end, overlapping openings, a loose wall end, overlapping
rooms, an unnamed room, duplicate walls, a dimension that doesn't match the drawing, furniture outside a room or
overlapping) are shown but don't block.

Results like areas and costs are never stored in the document. They are always calculated from it when needed. An
example document is in `data/samples/example_floorplan.json`.

---

## 5. Module by module

### 5.1 Detection

Detection runs when a file is uploaded and usually takes a few seconds (the first run after starting the backend takes
longer because the YOLO model has to load).

1. **Loading.** Images are opened after checking their size from the file header, so a small file that would
   expand to gigabytes in memory is refused before it's decoded (limit 40 megapixels, 15 MB). PDFs are rendered at
   200 DPI from the first page.
2. **Preprocessing.** The image is scaled to a working size (800 to 3000 px on the long side), converted to
   grayscale, denoised, straightened if it's slightly rotated, and turned into black and white.
3. **Walls.** Thick dark lines are found with a Hough line transform and merged into wall segments, then classified
   as exterior or interior.
4. **Rooms.** Rooms are the enclosed regions between the walls. A clean-up step then removes tiny slivers, repairs
   outlines that cross themselves, and trims outlines that were traced around several rooms at once.
5. **Doors and windows.** A fine-tuned YOLOv8 model detects them. If it finds no doors on a plan, a classical method
   (gaps in walls and the short line of the door leaf) is used instead. Openings are attached to the nearest wall.
6. **Stairs.** Found from groups of short parallel lines.
7. **Text.** Tesseract reads the text. Room names are matched to the room they sit in, and dimension labels are
   matched to walls or room sizes. If Tesseract isn't working on a machine and EasyOCR is installed, EasyOCR is used.
8. **Scale.** The drawing's pixels-per-foot comes from dimension labels that match a wall or a room size. If no label
   can be used, the system assumes a typical building width and says so in a note on the plan.

### 5.2 The 2D editor

The editor works directly on the floor plan document. The drawing tools have keyboard shortcuts (V select, H pan,
W wall, R room, D door, N window, M dimension, T stair, S split wall). The editor validates as you work, keeps an undo
history, snaps to walls and optionally to a grid, and shows the original drawing underneath. Expensive geometry,
like recomputing rooms from walls, runs on the server and comes back as one undoable step. Saving is protected by a
revision number, so two tabs can't overwrite each other's work without noticing.

### 5.3 3D, walkthrough, furniture and lighting

The 3D builder turns the saved plan into geometry: wall pieces around every opening, floor and ceiling per room, stair
steps, door leaves, glass, railings on balcony edges, and furniture models. The viewer has an overview, a top view and
a walk mode (W A S D, mouse look, Shift to run) with collision. Furniture can be added, moved, rotated, duplicated and
deleted in 3D, and walls can be painted per side or per room. Lighting has a day mode with a sun you can move through
the day and a night mode with room lights. Edits made in 3D are saved into the same plan as edits made in 2D. On a
real plan the viewer renders a frame in about a millisecond.

### 5.4 The assistant

We didn't want an assistant that invents numbers. Every fact comes from one of 22 small deterministic functions
("tools") that read the plan, the estimate or the sustainability result: list rooms, get a room, compare rooms, wall
surfaces for painting, openings, connections, furniture, colours, building dimensions, plan problems, cost, score, app
help and a small calculator.

- When an AI provider key (Gemini or OpenAI) is configured, the language model decides which tools to call, up to six
  rounds per question, and writes the answer. Every number in that answer is checked against the tool results. If
  something can't be verified, the plain tool answer is shown instead.
- Without a key, or when the provider is down, a built-in simple mode answers common questions directly from the
  same tools.
- Answers always use the last saved plan, and the page shows which values came from the plan.

### 5.5 Estimation

Areas are calculated per room: floor, perimeter, net wall area after openings, and skirting. From those, plus the
building's walls and openings, come material quantities. The default rates are in Indian rupees, with 30 % labour,
5 % contingency and 0 % tax, a 2.7 m wall height and 0.15 m walls. Every rate and percentage can be changed on the page,
the total updates as you type, and saved rates belong to the project. Implausible values (a rate above 100,000,000, a
percentage above 200, a wall height above 20 m) are refused with a clear message. A plan with 100 rooms is estimated in
about a second.

### 5.6 Sustainability

The building is turned into a graph of rooms connected by doors (NetworkX). Four indicators are calculated per room
and for the building: window-to-floor ratio (target 10 %), daylight (window direction and the north angle),
ventilation (cross ventilation needs windows on different sides) and connectivity. They are combined into a score out
of 100 with a band: Good (80 and up), Fair (60 to 79) or Needs attention (below 60). Rule-based recommendations name
the room and the numbers involved, for example how much window area is missing. The north direction can be set per
project.

### 5.7 Reports and export

- **Full report PDF:** the plan, a 3D view captured from the viewer, the areas, the estimate and the sustainability
  results.
- **Estimate PDF.**
- **GLB 3D model:** generated in the browser from the same code as the viewer, and checked with the official glTF
  validator.
- **Project JSON:** the plan, the original detection result, settings, results and activity. File names are kept,
  server paths and secrets are left out.

Download names keep the project's name, including non-English letters.

---

## 6. Accounts and security

- Passwords are hashed with scrypt. Sessions are random tokens stored as SHA-256 hashes and sent in an httpOnly,
  SameSite cookie (Secure in production). A session lasts 30 days.
- Every project route checks the owner. Another user's project answers "not found", so the API never confirms it
  exists.
- After 5 wrong passwords for an email from the same network address, sign-in is blocked for 10 minutes for that
  address only. That way someone else can't lock you out. One address with 30 failures across any emails is blocked
  too.
- Password reset codes have 6 digits, work once, expire after 10 minutes and allow 5 tries. A new code can be requested
  once a minute and 5 times an hour, and the "forgot password" form accepts 20 requests an hour per address. The page
  never tells whether an email has an account. Only a salted hash of each code is stored.
- Uploads are limited by size and pixel count before decoding, coordinates must be finite and in range, and rates
  must be plausible.
- Errors return a short JSON message. In production a stack trace is never sent to the browser, and the interactive
  API documentation is turned off.
- Every API response carries security headers. The Docker web server also sends a Content-Security-Policy.
- Secrets (API keys, email password) live only in `.env` files, which are excluded from Git and from the Docker images.

---

## 7. Installing and running it

These instructions are for Windows 10/11. On macOS or Linux the steps are the same, with `source .venv/bin/activate`
and Tesseract installed through `brew` or `apt`.

**Requirements**

| Software | Version |
|---|---|
| Python | 3.12 |
| Node.js | 22 LTS |
| Tesseract OCR | 5.x, installed in `C:\Program Files\Tesseract-OCR` (UB Mannheim installer) |
| Microsoft Visual C++ Redistributable | x64, 2015-2022 (needed by PyTorch) |
| Browser | Chrome or Edge |

**Backend** (in a Command Prompt; in PowerShell the activate step may need script execution to be allowed)

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
copy .env.example .env
python -m pip install --upgrade pip
pip install torch==2.13.0 torchvision==0.28.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python -m pytest -q                  # should end with 486 passed, 7 skipped
uvicorn app.main:app --reload        # http://localhost:8000
```

The database is created automatically on the first start (`backend/dev.db`). While the backend runs in development, an
interactive API page is available at `http://localhost:8000/docs`.

**Frontend**

```bat
cd frontend
copy .env.example .env
npm ci
npm test                             # 343 passed
npm run dev                          # http://localhost:5173
```

**Settings in `backend/.env`**

| Setting | Purpose |
|---|---|
| `APP_ENV`, `DEBUG` | development or production; debug is always off in production |
| `DATABASE_URL`, `STORAGE_PATH` | database and upload folder (relative paths are relative to the backend folder) |
| `CORS_ORIGINS` | addresses allowed to call the API |
| `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` | the assistant's AI provider (`offline` for simple mode) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | email for reset codes |
| `TESSERACT_CMD` | full path to tesseract.exe, only if it isn't in the default folder or on PATH |
| `SESSION_DAYS`, `SESSION_COOKIE_SECURE` | session length, HTTPS-only cookie |

Without SMTP settings, reset codes are printed in the backend window during development, which is handy for testing.
For Gmail use `smtp.gmail.com`, port 587, `starttls` and an App Password. You can check the assistant's key and model
with `python -m app.llm.check`. An admin can reset a password from the terminal with
`python -m app.cli reset-password someone@example.com`.

**Common problems**

| Problem | Fix |
|---|---|
| The website says "Can't reach the server" | start the backend (it retries automatically) |
| `Failed to resolve import "@fontsource/..."` | run `npm ci` in the frontend folder |
| A Tailwind / PostCSS error after installing packages | `npm install -D tailwindcss@3.4.19` (the project uses Tailwind 3) |
| OCR-related test failures | make sure Tesseract 5 is in `C:\Program Files\Tesseract-OCR`, or set `TESSERACT_CMD` |
| `npm` errors with EPERM on a OneDrive folder | pause OneDrive syncing while installing |

---

## 8. Running it with Docker

For a server, or a PC with Docker Desktop, the whole system runs in two containers:

- **backend:** Python 3.12, Tesseract, CPU PyTorch, the YOLO model. It runs as a normal user, and its data is stored
  in a volume.
- **frontend:** nginx serves the built website and forwards `/api/...` to the backend, so the browser only talks to
  one address. The backend port isn't exposed at all.

```powershell
copy docker\deploy.env.example docker\deploy.env    # fill in the settings
docker compose up -d --build                          # http://localhost:8080
```

| Task | Command |
|---|---|
| status | `docker compose ps` |
| logs | `docker compose logs -f backend` |
| stop / start | `docker compose down` / `docker compose up -d` |
| after code changes | `docker compose up -d --build` |
| reset a password | `docker compose exec backend python -m app.cli reset-password someone@example.com` |
| back up the data | `docker compose cp backend:/data ./backup-data` |

`docker compose down -v` deletes the data volume, so all accounts and projects are lost.

At startup the backend logs a warning for settings that are fine on a laptop but wrong for a public site: a cookie that
isn't HTTPS-only, `localhost` in the allowed addresses, no email set up, or no AI key. On a public server, put HTTPS in
front of the containers (a cloud load balancer or a reverse proxy like Caddy), then set `SESSION_COOKIE_SECURE=true`
and `CORS_ORIGINS` to the real address.

**When handing the project over**, include `package-lock.json` and leave out `.env` files, `docker/deploy.env`,
`backend/dev.db`, `backend/data/`, `node_modules/`, `.venv/` and `dist/`. The `.gitignore` already excludes all of
them.

---

## 9. Using the application

A typical session follows the steps in the sidebar, and every page has a "Next step" button.

1. **Create a project** on the Dashboard (name and optional description).
2. **Upload a plan** or choose "Draw your own floor plan". The summary shows what was detected.
3. **Check it in the 2D editor.** Fix walls, rooms, doors and windows, name the rooms, add furniture, then save.
   Amber and red elements are the ones detection was unsure about. The Issues tab lists anything to fix.
4. **Open the 3D Viewer.** Look around, walk through, add furniture, paint walls, try night mode.
5. **Ask the assistant**, for example "How big is the kitchen?", "Which rooms connect to the bedroom?" or "What is the
   estimated cost?".
6. **Estimation:** areas, materials and cost. Change rates and save them for the project.
7. **Sustainability:** the score, the indicators per room and the recommendations. Set the north direction if the top
   of the plan isn't north.
8. **Report:** download the PDF report, the estimate PDF, the GLB model and the project JSON.

The 3D Viewer opens once a plan with rooms and walls has been saved, and the analysis pages once the plan has been
opened in 3D. This guides new users through the workflow in the right order.

For good detection results, use a clear, straight-on plan with dark lines on a light background, readable room names
and at least one dimension label.

---

## 10. API overview

The backend has 49 endpoints, all JSON, with one error format:

```json
{"error": {"code": "VALIDATION_ERROR", "message": "Give the project a name.", "details": null}}
```

| Group | Endpoints |
|---|---|
| Auth | sign up, sign in, sign out, current user, forgot password / verify code / reset |
| Account | profile name, avatar (preset, initials, photo), change password, reset with an email code |
| Projects | list, create, get, rename, delete |
| Detection | upload and detect, status, result, original image |
| Floor plan | get, save (with revision check), validate, recompute rooms, reset to detection, blank plan, SVG thumbnail |
| Assistant | ask a question |
| Estimation | estimate, live preview with unsaved rates, get and save rates |
| Sustainability | assessment (with optional north preview), get and save north |
| Activity | project activity, recent activity, record a viewer event |
| Reports | report PDF, estimate PDF, project JSON export, store and get the 3D snapshot |

Status codes used: 401 (not signed in), 404 (not found or not yours), 405, 409 (no plan yet, outdated revision,
email already registered), 413 (file too large), 415 (wrong file type), 422 (validation, with a readable message),
429 (too many attempts), 500 (unexpected error, fixed message), 503 (feature not set up on this server). The full,
clickable list with request formats is at `/docs` on a development backend.

---

## 11. Testing and results

**Automated tests**

| Suite | Result |
|---|---|
| Backend (pytest): detection, OCR, validation, geometry, editor API, 3D-related data, assistant tools and answers, estimation, sustainability, reports, export, accounts, password reset, security limits, configuration | 486 passed, 7 skipped |
| Frontend (Vitest): editor state and operations, 3D builder, walkthrough, painting, furniture, utilities, components | 343 passed |
| TypeScript check and production build | passing |

The 7 skipped tests need a private real floor plan image that isn't part of the repository.

**End-to-end testing.** Besides the unit tests, we tested the real application in a browser with Playwright scripts
at every stage of the project. These scripts were run in our test environment and aren't part of the repository.
The final run went through the complete workflow with the cottage sample, using the interface only:

| # | Step | Result |
|---|---|---|
| 1 | Upload a floor plan | passed |
| 2 | Detect elements (2 rooms, 5 walls, 2 doors, 1 window) | passed |
| 3 | Correct the plan (rename a room, add a window) | passed |
| 4 | Save the corrected plan | passed |
| 5 | Generate the 3D model | passed |
| 6 | Walk inside (eye height 1.60 m) | passed |
| 7 | Add furniture | passed |
| 8 | Day and night lighting | passed |
| 9 | Ask questions (room size, connections, window count) | passed |
| 10 | Calculate areas | passed |
| 11 | Estimate materials and cost | passed |
| 12 | Sustainability analysis | passed |
| 13 | Recommendations | passed |
| 14 | Export the GLB (0 validator errors), project JSON and report PDF | passed |

The same workflow also passed inside the Docker containers.

**Other checks**
- Accessibility scan (axe-core) of all 11 pages: no violations after fixing contrast and ARIA issues.
- Mobile width (390 px): no horizontal scrolling on any page.
- Docker: both images build, every page works with the security policy on, data survives restarts, the backend runs
  as a normal user, and no secrets end up in the images.
- Security probes: hostile and oversized inputs, decompression-bomb images, other users' projects, forged headers
  against the sign-in limit, prompt injection against the assistant.

**Performance**

| Measurement | Result |
|---|---|
| Detection of a typical plan | a few seconds (first run 10-30 s while the model loads) |
| Estimate, 100-room plan | about 1.1 s |
| Estimate, 400-room plan | about 4.4 s |
| 3D frame time, real plan | about 1 ms |
| Website first load (main bundle) | 416 KB (129 KB compressed). The editor and 3D code load when opened |

---

## 12. Problems we ran into and how we solved them

**Real plans are not like sample plans.** The samples always worked. When we tried real floor plans, detection
produced 23 rooms on a house with 7 (most of them tiny slivers between walls and text), one room outline crossed
itself and blocked saving, and common professional formats like `28' - 0"` and `13'-4" X 9'-0"` weren't being read, so
the scale was guessed and areas came out about 80 % too large. We added the room clean-up step and support for those
formats. The same plan now gives 6 rooms, saves without errors, and gets its scale from the labels.

**Area calculation got slow on big plans.** Each wall face was tested against every room, so 100 rooms took 32 seconds
and 400 rooms almost 8 minutes. A spatial index (Shapely STRtree) brought that down to about 1 and 4 seconds.

**Large images could use up memory.** An 88 KB PNG of 20,000 x 20,000 white pixels took 2.4 GB of RAM to open. Image
sizes are now checked from the header before decoding.

**A library with side effects.** Importing the YOLO library replaced the image-opening function for the whole backend.
After that, any broken image upload made it try to install an extra package at runtime. We now load that library in a
way that keeps its changes contained.

**Windows-specific surprises.** A different, older Tesseract on the PATH gave different OCR results, an extra OCR
engine installed globally on one machine was being used instead of Tesseract, and OneDrive locked files during tests
and installs. We fixed the lookup order (Tesseract in its standard folder first, EasyOCR only as a fallback), pinned
the versions of the large packages, and documented the OneDrive workaround.

**Small things users noticed.** Unsaved rate edits disappeared when you left the Estimation page, a stopped backend
showed the sign-in page instead of a clear message, toolbars wrapped on smaller screens, and download names lost
non-English letters. All of these were fixed during the final testing round.

---

## 13. Project status

**The project is complete and ready for demonstration and delivery as an MVP.** The full workflow from upload to export
works in the browser, both in the normal setup and in Docker. There are no open blocking or major defects, and the
cost estimate and sustainability score show their "preliminary" notices both on screen and in the PDFs.

| Area | State |
|---|---|
| Upload, detection, OCR, scale | complete. Works on samples and real plans, and real plans should be checked in the editor |
| 2D editor | complete |
| 3D, walkthrough, furniture, painting, lighting | complete |
| Assistant | complete. Simple mode works without a key, free-form questions need Gemini or OpenAI |
| Estimation, sustainability | complete. Preliminary by design |
| Reports and export | complete |
| Accounts and password reset | complete |
| Tests | 486 backend, 343 frontend, full workflow in the browser |
| Deployment | laptop setup and Docker setup, both tested |

---

## 14. Known limitations

- **Detection is a draft.** On real plans the door and window model misses some openings (on one test plan it found
  1 of about 7 doors), and rooms may need re-drawing. When no dimension label can be read, the scale is an estimate,
  and the plan says so.
- **Cost** is a preliminary estimate from typical quantities and editable rates. It is not a professional engineering
  or quantity-surveying quote.
- **The sustainability score** is a preliminary, explainable indicator. It is not a certified green-building rating or
  an engineering simulation.
- **Lighting and rendering** are a visualization, not a professional lighting simulation.
- **The assistant's** simple mode understands common questions in English. It doesn't give structural, safety, legal
  or building-code advice.
- **Single floor only.** Multi-storey buildings aren't supported yet.
- **One backend process with SQLite** is right for a laptop, a demo or a small team. A large multi-user service would
  need PostgreSQL and shared sign-in limits.
- **Desktop first.** The editor and 3D viewer are designed for a desktop browser (Chrome or Edge). Pages work on phones
  but aren't optimized for them.

---

## 15. Third-party licences

The project uses open-source components under their own licences: React, three.js, Konva, FastAPI, OpenCV, Shapely,
NetworkX and ReportLab (MIT / BSD / Apache style), Tesseract (Apache 2.0), PyMuPDF (AGPL-3.0) and Ultralytics YOLO
(AGPL-3.0). The AGPL components come with obligations when the software is offered to others as a network service (the
source code of the service has to be made available) unless a commercial licence is bought from Artifex or
Ultralytics. This should be checked before any commercial deployment.

---

## 16. Ideas for the next version

1. Train the door and window model further on more real plans. This is the biggest accuracy gap.
2. Support multi-storey buildings.
3. Move to PostgreSQL and run detection as a background job, so several backend processes can share the load.
4. Export to IFC and DXF for architects and engineers, and build a larger furniture and material library.
5. Add rate tables for different regions and local climate data for the sustainability score.
6. Sort out the AGPL licences (or replace those components) before a commercial launch.
