import PageHeader from "../../components/PageHeader";
import EmptyState from "../../components/EmptyState";
import { useProject } from "../../hooks/useProject";

/**
 * Placeholder page -- feature content is built in Phase 7 of the
 * 40-prompt plan. This prompt (3) only wires up navigation and layout.
 */
export default function Estimation() {
  const { selectedProject } = useProject();

  return (
    <div>
      <PageHeader sheet="A-06" title="Estimation" description="Area, material quantity, and preliminary cost estimates." />
      <EmptyState
        title={selectedProject ? "This sheet isn't drawn yet" : "Select a project first"}
        description={
          selectedProject
            ? "This feature is built in a later phase of the development plan (Phase 7)."
            : "Choose or create a project from the Dashboard to work with this feature."
        }
      />
    </div>
  );
}
