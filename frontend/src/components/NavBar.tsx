import { NavLink } from "react-router-dom";
import { useProject } from "../hooks/useProject";

/**
 * Nav items are labeled like sheets in a real architectural drawing set
 * (A-01, A-02, ...) -- this is grounded in how building plans are actually
 * numbered, not decoration for its own sake, and it doubles as a quiet
 * reminder of where each page sits in the overall workflow.
 */
const NAV_ITEMS = [
  { sheet: "A-01", label: "Dashboard", to: "/" },
  { sheet: "A-02", label: "Upload", to: "/upload" },
  { sheet: "A-03", label: "Floor Plan Editor", to: "/editor" },
  { sheet: "A-04", label: "3D Viewer", to: "/viewer" },
  { sheet: "A-05", label: "Assistant", to: "/assistant" },
  { sheet: "A-06", label: "Estimation", to: "/estimation" },
  { sheet: "A-07", label: "Sustainability", to: "/sustainability" },
];

export default function NavBar() {
  const { selectedProject } = useProject();

  return (
    <nav className="flex h-full w-64 flex-shrink-0 flex-col bg-ink text-white">
      <div className="border-b border-white/10 px-5 py-5">
        <p className="font-display text-base font-semibold leading-tight text-white">Floor Plan → 3D</p>
        <p className="mt-0.5 font-mono text-[11px] uppercase tracking-wider text-blueprint-soft/80">
          Building Intelligence
        </p>
      </div>

      <ul className="flex-1 overflow-y-auto py-3">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `group flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
                  isActive
                    ? "bg-white/10 text-white"
                    : "text-white/70 hover:bg-white/5 hover:text-white"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={`font-mono text-[11px] tabular-nums ${
                      isActive ? "text-blueprint" : "text-white/40 group-hover:text-blueprint-soft"
                    }`}
                  >
                    {item.sheet}
                  </span>
                  <span className="font-body">{item.label}</span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>

      {/* Selected-project "title block" -- mirrors the stamp box on a real drawing sheet. */}
      <div className="border-t border-white/10 px-5 py-4">
        <p className="font-mono text-[10px] uppercase tracking-wider text-white/40">Active Project</p>
        <p className="mt-1 truncate font-body text-sm text-white" title={selectedProject?.name}>
          {selectedProject ? selectedProject.name : "None selected"}
        </p>
      </div>
    </nav>
  );
}
