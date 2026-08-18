interface PageHeaderProps {
  sheet: string;
  title: string;
  description?: string;
}

/**
 * Shared header used at the top of every page (Dashboard included) so the
 * "sheet number" motif established in NavBar carries through consistently,
 * and so feature pages built in later prompts don't each reinvent a title
 * block.
 */
export default function PageHeader({ sheet, title, description }: PageHeaderProps) {
  return (
    <div className="mb-8 border-b border-graphite-faint/30 pb-5">
      <p className="font-mono text-xs uppercase tracking-wider text-blueprint">{sheet}</p>
      <h1 className="mt-1 text-2xl font-semibold text-ink">{title}</h1>
      {description && <p className="mt-1.5 max-w-2xl text-sm text-graphite-muted">{description}</p>}
    </div>
  );
}
