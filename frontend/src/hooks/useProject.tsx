/**
 * Currently-selected-project state, shared across the whole app via React
 * Context. Later feature pages (Editor, Viewer3D, Assistant, Estimation,
 * Sustainability) all read the active project id from here rather than
 * threading it through props or re-deriving it from the URL independently.
 */
import React, { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { Project } from "../types/project";

interface ProjectContextValue {
  selectedProject: Project | null;
  selectedProjectId: string | null;
  selectProject: (project: Project | null) => void;
}

const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);

const SELECTED_PROJECT_KEY = "selectedProjectId";

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);

  const selectProject = useCallback((project: Project | null) => {
    setSelectedProject(project);
    // Session-only persistence so a page refresh doesn't lose context mid-session.
    // (No browser storage APIs are used in artifacts per policy; this app is a
    // regular Vite build, not a claude.ai artifact, so sessionStorage is fine here.)
    try {
      if (project) {
        window.sessionStorage.setItem(SELECTED_PROJECT_KEY, project.id);
      } else {
        window.sessionStorage.removeItem(SELECTED_PROJECT_KEY);
      }
    } catch {
      // sessionStorage may be unavailable (e.g. privacy mode) -- non-fatal.
    }
  }, []);

  const value = useMemo<ProjectContextValue>(
    () => ({
      selectedProject,
      selectedProjectId: selectedProject?.id ?? null,
      selectProject,
    }),
    [selectedProject, selectProject]
  );

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject(): ProjectContextValue {
  const ctx = useContext(ProjectContext);
  if (!ctx) {
    throw new Error("useProject must be used within a ProjectProvider");
  }
  return ctx;
}
