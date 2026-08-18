interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

/**
 * Consistent error surface for every page. Backend errors always arrive in
 * the {code, message, details} shape (see services/api.ts::ApiError) so any
 * caller can pass `error.message` straight in here.
 */
export default function ErrorState({ title = "Something went wrong", message, onRetry }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-3 rounded-md border border-redline/30 bg-redline-soft px-5 py-4 text-graphite"
    >
      <div>
        <p className="font-display text-sm font-semibold text-redline">{title}</p>
        <p className="mt-1 text-sm text-graphite-muted">{message}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded border border-redline/40 bg-white px-3 py-1.5 text-xs font-medium text-redline transition hover:bg-redline hover:text-white"
        >
          Try again
        </button>
      )}
    </div>
  );
}
