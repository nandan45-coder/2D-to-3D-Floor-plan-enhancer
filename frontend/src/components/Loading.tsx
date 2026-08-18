interface LoadingProps {
  label?: string;
  fullHeight?: boolean;
}

export default function Loading({ label = "Loading…", fullHeight = false }: LoadingProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex flex-col items-center justify-center gap-3 py-16 text-graphite-muted ${
        fullHeight ? "min-h-[60vh]" : ""
      }`}
    >
      <span className="relative flex h-8 w-8">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blueprint opacity-40" />
        <span className="relative inline-flex h-8 w-8 rounded-full border-2 border-blueprint border-t-transparent animate-spin" />
      </span>
      <span className="font-mono text-xs uppercase tracking-wider">{label}</span>
    </div>
  );
}
