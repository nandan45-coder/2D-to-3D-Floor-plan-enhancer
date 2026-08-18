import PageHeader from "../../components/PageHeader";
import EmptyState from "../../components/EmptyState";
import { useProject } from "../../hooks/useProject";

/**
 * Placeholder page -- feature content is built in Phase 6 of the
 * 40-prompt plan. This prompt (3) only wires up navigation and layout.
 */
export default function Assistant() {
  const { selectedProject } = useProject();

  return (
    <div>
      <PageHeader sheet="A-05" title="Assistant" description="Ask grounded questions about the building using real project data." />
      <EmptyState
        title={selectedProject ? "This sheet isn't drawn yet" : "Select a project first"}
        description={
          selectedProject
            ? "This feature is built in a later phase of the development plan (Phase 6)."
            : "Choose or create a project from the Dashboard to work with this feature."
        }
      />
    </div>
  );
}
