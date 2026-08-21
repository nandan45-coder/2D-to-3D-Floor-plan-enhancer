/**
 * Centralized API client.
 *
 * Every backend call in the app goes through this file -- no component or
 * hook should call axios/fetch directly. This is what Prompt 3's
 * "no duplicate API logic outside services/api.ts" constraint enforces, and
 * it's the single place later phases (detection, corrections, 3D,
 * assistant, estimation, sustainability, export) extend as their endpoints
 * come online.
 */
import axios, { AxiosError, AxiosInstance } from "axios";
import type { Project, ProjectCreateInput, ProjectUpdateInput } from "../types/project";
import type { FloorPlan } from "../types/floorplan";

const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

/**
 * Normalized error shape thrown by every function below, regardless of
 * whether the failure was a backend error response, a network failure, or
 * something else. Callers (hooks/components) only ever need to handle this
 * one shape.
 */
export interface ApiError {
  code: string;
  message: string;
  details?: unknown;
  status?: number;
}

function normalizeError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ error?: { code: string; message: string; details?: unknown } }>;

    if (axiosError.response) {
      const body = axiosError.response.data;
      if (body?.error) {
        return {
          code: body.error.code,
          message: body.error.message,
          details: body.error.details,
          status: axiosError.response.status,
        };
      }
      return {
        code: "HTTP_ERROR",
        message: `Request failed with status ${axiosError.response.status}.`,
        status: axiosError.response.status,
      };
    }

    // A request timeout (client gave up waiting) and a genuinely unreachable
    // server both leave axiosError.request truthy with no response -- but
    // they mean very different things and need different messages. This
    // matters especially for slow synchronous endpoints like floor plan
    // detection (see uploadFloorPlan below), where "the server is down" and
    // "detection is just taking a while on a complex image" look identical
    // to axios but are not the same problem for the user to act on.
    if (axiosError.code === "ECONNABORTED" || /timeout/i.test(axiosError.message)) {
      return {
        code: "TIMEOUT",
        message:
          "The request took longer than expected and timed out. This can happen with large or highly " +
          "detailed floor plans, since detection runs synchronously. Try again -- if it keeps happening, " +
          "check that the backend is still running (it may still be processing your previous request).",
      };
    }

    if (axiosError.request) {
      return {
        code: "NETWORK_ERROR",
        message: "Could not reach the server. Check that the backend is running and reachable.",
      };
    }
  }

  return {
    code: "UNKNOWN_ERROR",
    message: error instanceof Error ? error.message : "An unexpected error occurred.",
  };
}

// --- Health -----------------------------------------------------------

export interface HealthStatus {
  status: string;
  service: string;
  environment: string;
  database: string;
}

export async function getHealth(): Promise<HealthStatus> {
  try {
    const { data } = await apiClient.get<HealthStatus>("/health");
    return data;
  } catch (error) {
    throw normalizeError(error);
  }
}

// --- Projects -----------------------------------------------------------

export async function listProjects(): Promise<Project[]> {
  try {
    const { data } = await apiClient.get<Project[]>("/projects");
    return data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function getProject(projectId: string): Promise<Project> {
  try {
    const { data } = await apiClient.get<Project>(`/projects/${projectId}`);
    return data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function createProject(payload: ProjectCreateInput): Promise<Project> {
  try {
    const { data } = await apiClient.post<Project>("/projects", payload);
    return data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function updateProject(projectId: string, payload: ProjectUpdateInput): Promise<Project> {
  try {
    const { data } = await apiClient.patch<Project>(`/projects/${projectId}`, payload);
    return data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function deleteProject(projectId: string): Promise<void> {
  try {
    await apiClient.delete(`/projects/${projectId}`);
  } catch (error) {
    throw normalizeError(error);
  }
}

// --- Detection (Prompt 7) ------------------------------------------------

export type DetectionStatus = "not_started" | "processing" | "complete" | "failed";

export interface DetectionSummary {
  room_count: number;
  wall_count: number;
  door_count: number;
  window_count: number;
  stair_count: number;
  dimension_count: number;
  calibration_source: string | null;
  notes: string | null;
}

export interface DetectionStatusResponse {
  status: DetectionStatus;
  error: string | null;
}

export interface DetectionUploadResponse extends DetectionStatusResponse {
  summary: DetectionSummary | null;
}

// Detection runs synchronously within the upload request (see
// backend/app/api/routes/detection.py's design note) and its runtime
// scales with image complexity -- a dense real-world floor plan with many
// rooms, labels, and dimension marks can take well past the default 15s
// timeout used for every other (near-instant) call. This is a separate,
// generous timeout applied only to this one request.
const DETECTION_TIMEOUT_MS = 120000; // 2 minutes

/**
 * Uploads a floor plan file and runs detection on it synchronously (see
 * backend/app/api/routes/detection.py for why upload+trigger are combined
 * into one request rather than split across separate calls). This can take
 * anywhere from a couple seconds (simple, clean line art) to a minute or
 * more (dense, real-world scans with many rooms and labels) -- callers
 * should show a loading state for the duration of the await and should not
 * assume it resolves quickly.
 *
 * IMPORTANT: this deliberately overrides Content-Type to `undefined` rather
 * than setting it to "multipart/form-data" directly. The apiClient instance
 * sets a default "application/json" Content-Type for every other call; a
 * multipart request needs a boundary parameter that only the browser can
 * generate when it sees a FormData body with no Content-Type already set.
 * Explicitly setting undefined here removes the instance default for this
 * one request and lets axios/the browser fill in the correct header.
 */
export async function uploadFloorPlan(projectId: string, file: File): Promise<DetectionUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  try {
    const { data } = await apiClient.post<DetectionUploadResponse>(
      `/projects/${projectId}/floorplan/upload`,
      formData,
      { headers: { "Content-Type": undefined }, timeout: DETECTION_TIMEOUT_MS }
    );
    return data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function getDetectionStatus(projectId: string): Promise<DetectionStatusResponse> {
  try {
    const { data } = await apiClient.get<DetectionStatusResponse>(`/projects/${projectId}/floorplan/status`);
    return data;
  } catch (error) {
    throw normalizeError(error);
  }
}

export async function getDetectionResult(projectId: string): Promise<FloorPlan> {
  try {
    const { data } = await apiClient.get<FloorPlan>(`/projects/${projectId}/floorplan/result`);
    return data;
  } catch (error) {
    throw normalizeError(error);
  }
}
