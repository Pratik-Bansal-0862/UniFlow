"use client";

import { useEffect, useMemo, useState } from "react";

type Point = {
  id: string;
  document_id: string;
  source_name: string;
  chunk_index: number;
  page_number?: number | null;
  preview: string;
  x: number;
  y: number;
  z: number;
};
type Payload = { method: string; note: string; total: number; points: Point[] };

export function EmbeddingExplorer() {
  const [payload, setPayload] = useState<Payload | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("all");
  const [selectedId, setSelectedId] = useState("");
  const [yaw, setYaw] = useState(-0.55);
  const [pitch, setPitch] = useState(0.35);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/embedding-explorer?limit=500", { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail ?? "Could not load embeddings");
      setPayload(data as Payload);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not load embeddings");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    fetch("/api/embedding-explorer?limit=500", { cache: "no-store" })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data?.detail ?? "Could not load embeddings");
        if (!cancelled) setPayload(data as Payload);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load embeddings");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const sources = useMemo(() => [...new Set((payload?.points ?? []).map((point) => point.source_name))].sort(), [payload]);
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (payload?.points ?? []).filter((point) =>
      (source === "all" || point.source_name === source) &&
      (!needle || `${point.source_name} ${point.preview} ${point.id}`.toLowerCase().includes(needle))
    );
  }, [payload, query, source]);
  const selected = filtered.find((point) => point.id === selectedId) ?? filtered[0] ?? null;

  const projected = useMemo(() => {
    if (!filtered.length) return [];
    const cosY = Math.cos(yaw), sinY = Math.sin(yaw);
    const cosP = Math.cos(pitch), sinP = Math.sin(pitch);
    const rotated = filtered.map((point) => {
      const rx = point.x * cosY + point.z * sinY;
      const rz = -point.x * sinY + point.z * cosY;
      const ry = point.y * cosP - rz * sinP;
      const depth = point.y * sinP + rz * cosP;
      return { point, rx, ry, depth };
    });
    const maxX = Math.max(1e-9, ...rotated.map((p) => Math.abs(p.rx)));
    const maxY = Math.max(1e-9, ...rotated.map((p) => Math.abs(p.ry)));
    const maxDepth = Math.max(1e-9, ...rotated.map((p) => Math.abs(p.depth)));
    return rotated.map((item) => ({
      ...item,
      sx: 360 + (item.rx / maxX) * 300,
      sy: 220 - (item.ry / maxY) * 175,
      radius: 3.5 + ((item.depth / maxDepth + 1) / 2) * 2,
    })).sort((a, b) => a.depth - b.depth);
  }, [filtered, yaw, pitch]);

  if (loading) return <section className="rounded-2xl border p-6"><p>Loading stored embedding projection…</p></section>;
  if (error) return <section className="rounded-2xl border p-6"><h2 className="font-semibold">Embedding explorer</h2><p className="mt-2 text-sm text-red-600">{error}</p><button className="mt-3 rounded-lg border px-3 py-2 text-sm" onClick={() => void load()}>Retry</button></section>;

  return (
    <section className="space-y-4 rounded-2xl border p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="text-xl font-semibold">Knowledge map</h2><p className="mt-1 max-w-2xl text-sm opacity-70">Explore chunks already indexed from your documents. This is a rotatable 3D view of a PCA projection of the stored embeddings.</p></div>
        <div className="rounded-xl border px-3 py-2 text-sm"><strong>{filtered.length}</strong> / {payload?.total ?? 0} chunks</div>
      </div>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_220px]">
        <input aria-label="Search indexed chunks" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search source text…" className="min-w-0 rounded-lg border bg-transparent px-3 py-2 text-sm" />
        <select aria-label="Filter by document" value={source} onChange={(e) => setSource(e.target.value)} className="rounded-lg border bg-transparent px-3 py-2 text-sm">
          <option value="all">All documents</option>{sources.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
      </div>
      {filtered.length === 0 ? <div className="rounded-xl border border-dashed p-8 text-center text-sm opacity-70">No indexed chunks match this filter. Upload and index a document, or clear the search.</div> : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(260px,0.8fr)]">
          <div className="min-w-0 rounded-xl border p-2">
            <svg viewBox="0 0 720 450" role="img" aria-label="Interactive rotatable three-dimensional PCA projection of indexed document embeddings" className="w-full">
              <line x1="40" y1="220" x2="680" y2="220" stroke="currentColor" opacity=".10" />
              <line x1="360" y1="35" x2="360" y2="405" stroke="currentColor" opacity=".10" />
              {projected.map(({ point, sx, sy, depth, radius }) => {
                const active = selected?.id === point.id;
                const opacity = active ? 1 : 0.35 + ((depth / Math.max(1e-9, ...projected.map((p) => Math.abs(p.depth))) + 1) / 2) * 0.4;
                return <g key={point.id} role="button" tabIndex={0} aria-label={`Select chunk ${point.chunk_index} from ${point.source_name}`} onClick={() => setSelectedId(point.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedId(point.id); } }} style={{ cursor: "pointer", outline: "none" }}>
                  <circle cx={sx} cy={sy} r={active ? radius + 3 : radius} fill="currentColor" opacity={opacity} stroke={active ? "currentColor" : "none"} strokeWidth="2" />
                  <title>{point.source_name} · chunk {point.chunk_index} · depth {depth.toFixed(3)}</title>
                </g>;
              })}
              <text x="360" y="438" textAnchor="middle" fill="currentColor" fontSize="11" opacity=".6">PC axes 1–3 · perspective projection</text>
            </svg>
            <div className="grid gap-3 px-2 pb-2 sm:grid-cols-2">
              <label className="text-xs opacity-70">Rotate horizontal
                <input aria-label="Rotate horizontal" className="mt-1 block w-full" type="range" min="-3.14" max="3.14" step="0.05" value={yaw} onChange={(e) => setYaw(Number(e.target.value))} />
              </label>
              <label className="text-xs opacity-70">Rotate vertical
                <input aria-label="Rotate vertical" className="mt-1 block w-full" type="range" min="-1.4" max="1.4" step="0.05" value={pitch} onChange={(e) => setPitch(Number(e.target.value))} />
              </label>
            </div>
            <p className="px-2 pb-2 text-xs opacity-60">Each point is an existing indexed chunk. Rotate the view to inspect depth; PCA axes are mathematical components, not human-interpretable categories.</p>
          </div>
          <aside className="min-w-0 rounded-xl border p-4">
            {selected ? <>
              <p className="text-xs uppercase tracking-wide opacity-60">Selected chunk</p>
              <h3 className="mt-1 break-words font-semibold">{selected.source_name}</h3>
              <p className="mt-1 text-xs opacity-60">Chunk {selected.chunk_index}{selected.page_number != null && selected.page_number >= 0 ? ` · page ${selected.page_number}` : ""}</p>
              <div className="my-3 h-px bg-current opacity-10" />
              <p className="whitespace-pre-wrap break-words text-sm leading-6">{selected.preview || "No text preview stored for this chunk."}</p>
              <button className="mt-4 rounded-lg border px-3 py-2 text-sm" onClick={() => navigator.clipboard?.writeText(selected.preview)} disabled={!selected.preview}>Copy preview</button>
            </> : <p className="text-sm opacity-70">Select a point to inspect its source chunk.</p>}
          </aside>
        </div>
      )}
      <p className="text-xs opacity-60">{payload?.method ?? "PCA"} · {payload?.note ?? "Coordinates are an approximate projection."}</p>
    </section>
  );
}
