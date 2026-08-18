import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Loading from "../../components/Loading";
import ErrorState from "../../components/ErrorState";
import EmptyState from "../../components/EmptyState";
import PageHeader from "../../components/PageHeader";
import { createProject, listProjects, type ApiError } from "../../services/api";
import { useProject } from "../../hooks/useProject";
import type { Project } from "../../types/project";

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");
  const [error, setError] = useState<ApiError | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const { selectProject } = useProject();
  const navigate = useNavigate();

  async function loadProjects() {
    setStatus("loading");
    setError(null);
    try {
      const data = await listProjects();
      setProjects(data);
      setStatus("ready");
    } catch (err) {
      setError(err as ApiError);
      setStatus("error");
    }
  }

  useEffect(() => {
    loadProjects();
  }, []);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;

    setCreating(true);
    setCreateError(null);
    try {
      const project = await createProject({
        name: name.trim(),
        description: description.trim() || undefined,
      });
      setProjects((prev) => [project, ...prev]);
      setName("");
      setDescription("");
    } catch (err) {
      setCreateError((err as ApiError).message);
    } finally {
      setCreating(false);
    }
  }

  function handleOpenProject(project: Project) {
    selectProject(project);
    navigate("/upload");
  }

  return (
    <div>
      <PageHeader
        sheet="A-01"
        title="Dashboard"
        description="Every building starts here. Create a project, then upload a floor plan to begin."
      />

      <section className="mb-10 rounded-md border border-graphite-faint/30 bg-paper-panel p-5 shadow-panel">
        <h2 className="font-display text-sm font-semibold text-ink">New Project</h2>
        <form onSubmit={handleCreate} className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-start">
          <div className="flex-1">
            <label htmlFor="project-name" className="sr-only">
              Project name
            </label>
            <input
              id="project-name"
              type="text"
              required
              placeholder="Project name, e.g. Lakeside Cottage"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded border border-graphite-faint/50 bg-white px-3 py-2 text-sm text-graphite placeholder:text-graphite-faint focus:border-blueprint"
            />
          </div>
          <div className="flex-1">
            <label htmlFor="project-description" className="sr-only">
              Description (optional)
            </label>
            <input
              id="project-description"
              type="text"
              placeholder="Description (optional)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded border border-graphite-faint/50 bg-white px-3 py-2 text-sm text-graphite placeholder:text-graphite-faint focus:border-blueprint"
            />
          </div>
          <button
            type="submit"
            disabled={creating || !name.trim()}
            className="whitespace-nowrap rounded bg-ink px-4 py-2 text-sm font-medium text-white transition hover:bg-ink-light disabled:cursor-not-allowed disabled:opacity-40"
          >
            {creating ? "Creating…" : "Create Project"}
          </button>
        </form>
        {createError && <p className="mt-2 text-xs text-redline">{createError}</p>}
      </section>

      <section>
        <h2 className="mb-4 font-display text-sm font-semibold text-ink">Projects</h2>

        {status === "loading" && <Loading label="Loading projects…" />}

        {status === "error" && error && (
          <ErrorState
            title="Couldn't load projects"
            message={error.message}
            onRetry={loadProjects}
          />
        )}

        {status === "ready" && projects.length === 0 && (
          <EmptyState
            title="No projects yet"
            description="Create your first project above to start converting a floor plan into a 3D building."
          />
        )}

        {status === "ready" && projects.length > 0 && (
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {projects.map((project) => (
              <li key={project.id}>
                <button
                  type="button"
                  onClick={() => handleOpenProject(project)}
                  className="flex w-full flex-col items-start gap-1 rounded-md border border-graphite-faint/30 bg-paper-panel p-4 text-left shadow-panel transition hover:border-blueprint"
                >
                  <span className="font-display text-sm font-semibold text-ink">{project.name}</span>
                  {project.description && (
                    <span className="text-xs text-graphite-muted">{project.description}</span>
                  )}
                  <span className="mt-2 inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-blueprint">
                    <span className="h-1.5 w-1.5 rounded-full bg-approved" />
                    {project.status}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
