/**
 * Mirrors backend/app/floorplan/schema.py field-for-field.
 *
 * This is the shared FloorPlan data contract (see docs/ARCHITECTURE.md
 * Section 4 and docs/FLOORPLAN_SCHEMA.md). STABILITY RULE: do not add,
 * remove, or repurpose a field here without updating the backend schema and
 * both docs first -- the two must always match exactly.
 */

export type SourceType = "ai_detection" | "manual_correction";

export type Units = "feet" | "meters" | "inches" | "centimeters";

export type WallType = "exterior" | "interior";

export type DoorSwing = "left" | "right" | "sliding" | "none";

export interface Point2D {
  x: number;
  y: number;
}

/** Fields shared by every element type. */
export interface ElementBase {
  id: string;
  confidence: number | null;
  source: SourceType;
  metadata: Record<string, unknown>;
}

export interface Room extends ElementBase {
  name: string;
  /** Ordered vertices forming a closed room boundary (minimum 3 points). */
  polygon: Point2D[];
  room_type: string | null;
}

export interface Wall extends ElementBase {
  start: Point2D;
  end: Point2D;
  thickness: number | null;
  height: number | null;
  wall_type: WallType;
}

export interface Door extends ElementBase {
  /** id of the Wall this door is set into. */
  wall_id: string;
  /** Normalized position along the wall, start=0, end=1. */
  position: number;
  width: number;
  height: number | null;
  swing: DoorSwing | null;
}

export interface Window extends ElementBase {
  /** id of the Wall this window is set into. */
  wall_id: string;
  /** Normalized position along the wall, start=0, end=1. */
  position: number;
  width: number;
  height: number | null;
  sill_height: number | null;
}

export interface Stair extends ElementBase {
  /** Footprint of the staircase. */
  polygon: Point2D[];
  step_count: number | null;
  direction: string | null;
}

/** An OCR-extracted or manually placed measurement line/label. */
export interface DimensionAnnotation extends ElementBase {
  start: Point2D;
  end: Point2D;
  value: number;
  /** Raw text as extracted/entered, e.g. "12ft 6in". */
  label: string | null;
}

export interface FurnitureItem extends ElementBase {
  furniture_type: string;
  position: Point2D;
  /** Degrees, clockwise from the coordinate system's +x axis. */
  rotation: number;
  width: number | null;
  depth: number | null;
  height: number | null;
  /** id of the Room this item is placed in, if known. */
  room_id: string | null;
}

/** Document-level metadata. Distinct from per-element `metadata` on ElementBase. */
export interface FloorPlanMetadata {
  building_name: string | null;
  detection_version: string | null;
  source_image_reference: string | null;
  notes: string | null;
  extra: Record<string, unknown>;
}

/**
 * The top-level FloorPlan document -- the shared contract itself.
 * See backend/app/floorplan/schema.py::FloorPlan for the source of truth.
 */
export interface FloorPlan {
  project_id: string;
  units: Units;
  rooms: Room[];
  walls: Wall[];
  doors: Door[];
  windows: Window[];
  stairs: Stair[];
  dimensions: DimensionAnnotation[];
  furniture: FurnitureItem[];
  metadata: FloorPlanMetadata;
}
