"""
Generates synthetic sample floor plan images for testing the detection
pipeline (backend/app/cv, backend/app/ocr).

These are NOT real scanned floor plans -- they are simple line drawings
(black lines on white background) that deterministically exercise the
detection pipeline's core structural logic: wall lines, room-enclosing
boundaries, door/window gaps, a stair region, and OCR-readable text labels.

Real scanned/hand-drawn plans are noisier than these synthetic fixtures;
that gap is an explicitly documented MVP limitation in
docs/DETECTION_PIPELINE.md, not an oversight. These fixtures exist so the
pipeline's logic can be tested deterministically without depending on
sourcing/licensing real floor plan scan datasets within the project timeline.

Run with:
    python scripts/generate_sample_floorplans.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "data" / "samples"

# Scale used when drawing: 20 px per foot. Encoding a known scale lets tests
# verify unit calibration against a ground truth.
PX_PER_FOOT = 20


def _load_font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def generate_two_room_cottage(path: Path) -> None:
    """
    A simple two-room rectangular building, matching the layout in
    data/samples/example_floorplan.json (24ft x 16ft, exterior walls + one
    interior dividing wall, an exterior door, an interior door, two windows).

    Canvas has a margin around the building so wall/room detection has to
    correctly distinguish the building from empty background, and a small
    resolution pad so the working-resolution min/max logic in
    preprocessing.py is meaningfully exercised (not a trivial 1:1 case).
    """
    margin = 100
    width_ft, height_ft = 24, 16
    building_w = width_ft * PX_PER_FOOT
    building_h = height_ft * PX_PER_FOOT
    canvas_w = building_w + margin * 2
    canvas_h = building_h + margin * 2 + 60  # extra bottom space for a dimension label

    img = Image.new("L", (canvas_w, canvas_h), color=255)
    draw = ImageDraw.Draw(img)

    x0, y0 = margin, margin
    x1, y1 = x0 + building_w, y0 + building_h
    wall_px = 4

    # Exterior walls, drawn with a gap in the top wall (entry door) and a
    # gap in the right wall (window) -- gaps are exactly what the Tier-2
    # door/window heuristic looks for.
    door_gap_start = x0 + int(0.15 * building_w)
    door_gap_end = x0 + int(0.15 * building_w) + 3 * PX_PER_FOOT  # ~3ft door

    window_gap_start = y0 + int(0.35 * building_h)
    window_gap_end = window_gap_start + 3 * PX_PER_FOOT  # ~3ft window

    # Top wall (split by door gap)
    draw.line([(x0, y0), (door_gap_start, y0)], fill=0, width=wall_px)
    draw.line([(door_gap_end, y0), (x1, y0)], fill=0, width=wall_px)
    # Bottom wall (continuous)
    draw.line([(x0, y1), (x1, y1)], fill=0, width=wall_px)
    # Left wall (continuous)
    draw.line([(x0, y0), (x0, y1)], fill=0, width=wall_px)
    # Right wall (split by window gap)
    draw.line([(x1, y0), (x1, window_gap_start)], fill=0, width=wall_px)
    draw.line([(x1, window_gap_end), (x1, y1)], fill=0, width=wall_px)

    # Interior dividing wall at 14ft from the left, with a gap for the
    # interior door connecting the two rooms.
    interior_x = x0 + 14 * PX_PER_FOOT
    int_door_gap_start = y0 + int(0.45 * building_h)
    int_door_gap_end = int_door_gap_start + int(2.8 * PX_PER_FOOT)
    draw.line([(interior_x, y0), (interior_x, int_door_gap_start)], fill=0, width=wall_px)
    draw.line([(interior_x, int_door_gap_end), (interior_x, y1)], fill=0, width=wall_px)

    # A short door-swing leaf line near the exterior door gap, so the Tier-2
    # heuristic's "gap + nearby short line => classify as door" path is
    # meaningfully exercised (distinguishing it from the plain window gap).
    leaf_x = door_gap_start
    leaf_y = y0
    draw.line([(leaf_x, leaf_y), (leaf_x + 18, leaf_y + 18)], fill=0, width=2)

    # A small stair region: a cluster of evenly spaced short parallel lines,
    # near the bottom-right corner, inside the bedroom.
    stair_x0 = x1 - int(3.5 * PX_PER_FOOT)
    stair_y0 = y0 + int(0.7 * building_h)
    for i in range(6):
        y = stair_y0 + i * 10
        draw.line([(stair_x0, y), (stair_x0 + 55, y)], fill=0, width=2)

    # Room labels (OCR targets).
    font = _load_font(16)
    draw.text((x0 + 30, y0 + 30), "Living Room", fill=0, font=font)
    draw.text((interior_x + 20, y0 + 30), "Bedroom", fill=0, font=font)

    # A dimension label under the building, with a dimension line above it,
    # spanning the building's full width -- lets unit calibration be tested
    # against a known ground truth (24 ft over `building_w` px).
    dim_y = y1 + 25
    draw.line([(x0, dim_y), (x1, dim_y)], fill=0, width=1)
    draw.text((x0 + building_w // 2 - 20, dim_y + 5), "24 ft", fill=0, font=font)

    img.save(path)


def generate_simple_studio(path: Path) -> None:
    """
    A smaller single-room studio, no interior walls -- exercises the
    "one enclosed region only" path and a differently-proportioned canvas.
    """
    margin = 80
    width_ft, height_ft = 14, 10
    building_w = width_ft * PX_PER_FOOT
    building_h = height_ft * PX_PER_FOOT
    canvas_w = building_w + margin * 2
    canvas_h = building_h + margin * 2

    img = Image.new("L", (canvas_w, canvas_h), color=255)
    draw = ImageDraw.Draw(img)

    x0, y0 = margin, margin
    x1, y1 = x0 + building_w, y0 + building_h
    wall_px = 4

    door_gap_start = x0 + int(0.4 * building_w)
    door_gap_end = door_gap_start + int(2.5 * PX_PER_FOOT)

    draw.line([(x0, y0), (door_gap_start, y0)], fill=0, width=wall_px)
    draw.line([(door_gap_end, y0), (x1, y0)], fill=0, width=wall_px)
    draw.line([(x0, y1), (x1, y1)], fill=0, width=wall_px)
    draw.line([(x0, y0), (x0, y1)], fill=0, width=wall_px)
    draw.line([(x1, y0), (x1, y1)], fill=0, width=wall_px)

    leaf_x = door_gap_start
    draw.line([(leaf_x, y0), (leaf_x + 16, y0 + 16)], fill=0, width=2)

    font = _load_font(16)
    draw.text((x0 + 20, y0 + 20), "Studio", fill=0, font=font)

    img.save(path)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cottage_path = OUTPUT_DIR / "sample_floorplan_cottage.png"
    studio_path = OUTPUT_DIR / "sample_floorplan_studio.png"
    generate_two_room_cottage(cottage_path)
    generate_simple_studio(studio_path)
    print(f"Wrote {cottage_path}")
    print(f"Wrote {studio_path}")


if __name__ == "__main__":
    main()
