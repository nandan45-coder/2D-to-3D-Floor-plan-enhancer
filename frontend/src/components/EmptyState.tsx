import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

export default function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-md border border-dashed border-graphite-faint/50 bg-paper-panel px-6 py-16 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-full border border-blueprint/40 text-blueprint">
        <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" stroke="currentColor" strokeWidth={1.5}>
          <path d="M12 5v14M5 12h14" strokeLinecap="round" />
        </svg>
      </div>
      <p className="font-display text-sm font-semibold text-ink">{title}</p>
      {description && <p className="max-w-sm text-sm text-graphite-muted">{description}</p>}
      {action}
    </div>
  );
}
