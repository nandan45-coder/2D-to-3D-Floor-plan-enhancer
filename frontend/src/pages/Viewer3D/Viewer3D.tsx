import PageHeader from "../../components/PageHeader";
import EmptyState from "../../components/EmptyState";
import { useProject } from "../../hooks/useProject";

/**
 * Placeholder page -- feature content is built in Phase 4-5 of the
 * 40-prompt plan. This prompt (3) only wires up navigation and layout.
 */
export default function Viewer3D() {
  const { selectedProject } = useProject();

  return (
    <div>
      <PageHeader sheet="A-04" title="3D Viewer" description="Walk through the generated building, place furniture, and adjust lighting." />
      <EmptyState
        title={selectedProject ? "This sheet isn't drawn yet" : "Select a project first"}
        description={
          selectedProject
            ? "This feature is built in a later phase of the development plan (Phase 4-5)."
            : "Choose or create a project from the Dashboard to work with this feature."
        }
      />
    </div>
  );
}
