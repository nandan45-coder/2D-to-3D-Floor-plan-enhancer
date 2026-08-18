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
