/**
 * Mirrors backend/app/schemas/project.py::ProjectRead.
 *
 * NOTE: This is the base project record only (id, name, description, status,
 * timestamps). The FloorPlan JSON contract is a separate, richer type
 * introduced in Prompt 4 once the schema is finalized -- see
 * docs/ARCHITECTURE.md and (later) frontend/src/types/floorplan.ts.
 */
export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreateInput {
  name: string;
  description?: string;
}

export interface ProjectUpdateInput {
  name?: string;
  description?: string;
}
