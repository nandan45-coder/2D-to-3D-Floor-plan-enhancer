import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import EmptyState from "../../components/EmptyState";
import Loading from "../../components/Loading";
import ErrorState from "../../components/ErrorState";
import { useProject } from "../../hooks/useProject";
import {
  uploadFloorPlan,
  type ApiError,
  type DetectionUploadResponse,
} from "../../services/api";

const ACCEPTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".pdf"];
const ACCEPTED_MIME_ATTR = "image/png,image/jpeg,application/pdf";

type Stage = "idle" | "uploading" | "complete" | "detection_failed" | "request_error";

function hasAcceptedExtension(filename: string): boolean {
  const lower = filename.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export default function Upload() {
  const { selectedProject } = useProject();
  const navigate = useNavigate();

  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [isDraggingOver, setIsDraggingOver] = useState(false);

  const [stage, setStage] = useState<Stage>("idle");
  const [result, setResult] = useState<DetectionUploadResponse | null>(null);
  const [requestError, setRequestError] = useState<ApiError | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  function handleFileChosen(chosen: File | null) {
    setResult(null);
    setRequestError(null);
    setStage("idle");
    setClientError(null);

    if (!chosen) {
      setFile(null);
      setPreviewUrl(null);
      return;
    }

    if (!hasAcceptedExtension(chosen.name)) {
      setClientError(`Unsupported file type. Please choose a ${ACCEPTED_EXTENSIONS.join(", ")} file.`);
      setFile(null);
      setPreviewUrl(null);
      return;
    }

    setFile(chosen);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    // PDFs don't render as an <img> preview -- only build an object URL for images.
    setPreviewUrl(chosen.type.startsWith("image/") ? URL.createObjectURL(chosen) : null);
  }

  function onInputChange(event: ChangeEvent<HTMLInputElement>) {
    handleFileChosen(event.target.files?.[0] ?? null);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDraggingOver(false);
    handleFileChosen(event.dataTransfer.files?.[0] ?? null);
  }

  async function handleUpload() {
    if (!file || !selectedProject) return;

    setStage("uploading");
    setRequestError(null);

    try {
      const response = await uploadFloorPlan(selectedProject.id, file);
      setResult(response);
      setStage(response.status === "complete" ? "complete" : "detection_failed");
    } catch (error) {
      setRequestError(error as ApiError);
      setStage("request_error");
    }
  }

  function handleChooseDifferentFile() {
    setFile(null);
    setPreviewUrl(null);
    setResult(null);
    setRequestError(null);
    setStage("idle");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  if (!selectedProject) {
    return (
      <div>
        <PageHeader sheet="A-02" title="Upload" description="Upload a 2D floor plan image or PDF to begin detection." />
        <EmptyState
          title="Select a project first"
          description="Choose or create a project from the Dashboard to upload a floor plan."
          action={
            <button
              type="button"
              onClick={() => navigate("/")}
              className="mt-2 rounded bg-ink px-4 py-2 text-sm font-medium text-white transition hover:bg-ink-light"
            >
              Go to Dashboard
            </button>
          }
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        sheet="A-02"
        title="Upload"
        description={`Upload a 2D floor plan image or PDF for "${selectedProject.name}" to begin AI detection.`}
      />

      {stage !== "complete" && stage !== "detection_failed" && (
        <section className="rounded-md border border-graphite-faint/30 bg-paper-panel p-6 shadow-panel">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDraggingOver(true);
            }}
            onDragLeave={() => setIsDraggingOver(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click();
            }}
            className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-md border-2 border-dashed px-6 py-14 text-center transition ${
              isDraggingOver ? "border-blueprint bg-blueprint-soft/20" : "border-graphite-faint/50 hover:border-blueprint"
            }`}
          >
            <svg viewBox="0 0 24 24" fill="none" className="h-8 w-8 text-blueprint" stroke="currentColor" strokeWidth={1.5}>
              <path d="M12 16V4m0 0L7 9m5-5l5 5M5 20h14" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <p className="font-display text-sm font-semibold text-ink">
              {file ? file.name : "Drop a floor plan here, or click to browse"}
            </p>
            <p className="font-mono text-[11px] uppercase tracking-wider text-graphite-faint">
              PNG · JPG · PDF — up to 15 MB
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_MIME_ATTR}
              onChange={onInputChange}
              className="hidden"
            />
          </div>

          {clientError && <p className="mt-3 text-xs text-redline">{clientError}</p>}

          {previewUrl && (
            <div className="mt-5 flex justify-center">
              <img
                src={previewUrl}
                alt="Selected floor plan preview"
                className="max-h-80 rounded border border-graphite-faint/30 object-contain"
              />
            </div>
          )}

          {file && stage === "idle" && (
            <div className="mt-5 flex justify-center gap-3">
              <button
                type="button"
                onClick={handleUpload}
                className="rounded bg-ink px-5 py-2 text-sm font-medium text-white transition hover:bg-ink-light"
              >
                Upload &amp; Detect
              </button>
              <button
                type="button"
                onClick={handleChooseDifferentFile}
                className="rounded border border-graphite-faint/50 px-5 py-2 text-sm font-medium text-graphite-muted transition hover:border-blueprint hover:text-ink"
              >
                Choose a different file
              </button>
            </div>
          )}

          {stage === "uploading" && (
            <Loading label="Running detection… this can take up to a couple of minutes for detailed plans" />
          )}

          {stage === "request_error" && requestError && (
            <div className="mt-5">
              <ErrorState
                title="Upload failed"
                message={requestError.message}
                onRetry={file ? handleUpload : undefined}
              />
            </div>
          )}
        </section>
      )}

      {stage === "detection_failed" && result && (
        <section className="rounded-md border border-redline/30 bg-redline-soft p-6">
          <p className="font-display text-sm font-semibold text-redline">Detection couldn't process this file</p>
          <p className="mt-1 text-sm text-graphite-muted">
            {result.error || "The file was uploaded, but detection failed to produce a usable result."}
          </p>
          <button
            type="button"
            onClick={handleChooseDifferentFile}
            className="mt-4 rounded border border-redline/40 bg-white px-4 py-2 text-xs font-medium text-redline transition hover:bg-redline hover:text-white"
          >
            Try a different file
          </button>
        </section>
      )}

      {stage === "complete" && result?.summary && (
        <section className="rounded-md border border-approved/30 bg-approved-soft p-6">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-approved" />
            <p className="font-display text-sm font-semibold text-ink">Detection complete</p>
          </div>

          <dl className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3">
            {[
              ["Rooms", result.summary.room_count],
              ["Walls", result.summary.wall_count],
              ["Doors", result.summary.door_count],
              ["Windows", result.summary.window_count],
              ["Stairs", result.summary.stair_count],
              ["Dimensions", result.summary.dimension_count],
            ].map(([label, value]) => (
              <div key={label as string} className="rounded border border-graphite-faint/30 bg-white px-4 py-3">
                <dt className="font-mono text-[11px] uppercase tracking-wider text-graphite-faint">{label}</dt>
                <dd className="mt-1 font-display text-2xl font-semibold text-ink">{value as number}</dd>
              </div>
            ))}
          </dl>

          {result.summary.notes && (
            <p className="mt-5 rounded border border-blueprint/30 bg-blueprint-soft/20 px-4 py-3 text-xs text-graphite">
              <span className="font-semibold text-ink">Note: </span>
              {result.summary.notes}
            </p>
          )}

          <div className="mt-6 flex gap-3">
            <button
              type="button"
              onClick={() => navigate("/editor")}
              className="rounded bg-ink px-5 py-2 text-sm font-medium text-white transition hover:bg-ink-light"
            >
              Continue to Floor Plan Editor
            </button>
            <button
              type="button"
              onClick={handleChooseDifferentFile}
              className="rounded border border-graphite-faint/50 px-5 py-2 text-sm font-medium text-graphite-muted transition hover:border-blueprint hover:text-ink"
            >
              Upload a different file
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
