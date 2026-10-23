"use client";

import { useCallback, useEffect, useState } from "react";

type ProfileItem = {
  value: string;
  evidence_ids: string[];
};

type Profile = Record<string, ProfileItem[]>;

type Source = {
  document_id?: string;
  filename?: string;
  chunk_index?: number;
};

type ProfileResponse = {
  profile?: Profile;
  sources?: Record<string, Source>;
  status?: string;
  updated_at?: string | null;
  detail?: string;
  message?: string;
};

const fields = [
  { key: "education", label: "Education" },
  { key: "skills", label: "Skills" },
  { key: "projects", label: "Projects" },
  { key: "experience", label: "Experience" },
  { key: "certifications", label: "Certifications" },
  { key: "interests", label: "Interests" },
  { key: "goals", label: "Career goals" },
] as const;

const emptyProfile = (): Profile =>
  Object.fromEntries(fields.map(({ key }) => [key, []]));

export default function StudentProfilePanel() {
  const [result, setResult] = useState<ProfileResponse | null>(null);
  const [draft, setDraft] = useState<Profile>(emptyProfile);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setError("");
    setNotice("");

    try {
      const response = await fetch("/api/profile", {
        cache: "no-store",
      });

      const data = (await response.json()) as ProfileResponse;

      if (!response.ok) {
        throw new Error(
          data.detail ||
            data.message ||
            `Request failed (${response.status})`,
        );
      }

      setResult(data);
      setDraft(data.profile ?? emptyProfile());
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not load your profile.",
      );
    } finally {
      setLoading(false);
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function initialLoad() {
      try {
        const response = await fetch("/api/profile", {
          cache: "no-store",
        });

        const data = (await response.json()) as ProfileResponse;

        if (!response.ok) {
          throw new Error(
            data.detail ||
              data.message ||
              `Request failed (${response.status})`,
          );
        }

        if (cancelled) return;

        setResult(data);
        setDraft(data.profile ?? emptyProfile());
        setError("");
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Could not load your profile.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoaded(true);
        }
      }
    }

    void initialLoad();

    return () => {
      cancelled = true;
    };
  }, []);

  async function extractProfile() {
    setLoading(true);
    setError("");
    setNotice("");

    try {
      const response = await fetch("/api/profile/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      const data = (await response.json()) as ProfileResponse;

      if (!response.ok) {
        throw new Error(
          data.detail ||
            data.message ||
            `Request failed (${response.status})`,
        );
      }

      setResult(data);
      setDraft(data.profile ?? emptyProfile());
      setNotice("Profile extracted and saved.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not extract your profile.",
      );
    } finally {
      setLoading(false);
      setLoaded(true);
    }
  }

  function updateItem(field: string, index: number, value: string) {
    setDraft((current) => ({
      ...current,
      [field]: (current[field] ?? []).map((item, i) =>
        i === index ? { ...item, value } : item,
      ),
    }));
  }

  function addItem(field: string) {
    setDraft((current) => ({
      ...current,
      [field]: [
        ...(current[field] ?? []),
        { value: "", evidence_ids: [] },
      ],
    }));
  }

  function removeItem(field: string, index: number) {
    setDraft((current) => ({
      ...current,
      [field]: (current[field] ?? []).filter((_, i) => i !== index),
    }));
  }

  async function saveCorrections() {
    setSaving(true);
    setError("");
    setNotice("");

    try {
      const response = await fetch("/api/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: draft }),
      });

      const data = (await response.json()) as ProfileResponse;

      if (!response.ok) {
        throw new Error(
          data.detail ||
            data.message ||
            `Request failed (${response.status})`,
        );
      }

      setResult(data);
      setDraft(data.profile ?? emptyProfile());
      setNotice("Your corrections have been saved.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not save your corrections.",
      );
    } finally {
      setSaving(false);
    }
  }

  const profile = draft;
  const sources = result?.sources ?? {};
  const itemCount = fields.reduce(
    (count, field) => count + (profile[field.key]?.length ?? 0),
    0,
  );

  return (
    <div className="space-y-6">
      <section className="rounded-3xl bg-gradient-to-br from-indigo-700 via-indigo-600 to-violet-600 p-7 text-white md:p-9">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-indigo-100">
          Your student profile
        </p>

        <h2 className="mt-2 text-3xl font-bold tracking-tight">
          Your profile, backed by your documents
        </h2>

        <p className="mt-3 max-w-2xl text-sm leading-6 text-indigo-50">
          Review extracted details, inspect their sources, and correct anything
          that is inaccurate. A profile match does not establish eligibility.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={extractProfile}
            disabled={loading || saving}
            className="rounded-xl bg-white px-5 py-3 text-sm font-semibold text-indigo-700 shadow-sm hover:bg-indigo-50 disabled:opacity-60"
          >
            {loading ? "Working..." : "Extract and save profile"}
          </button>

          <button
            type="button"
            onClick={loadProfile}
            disabled={loading || saving}
            className="rounded-xl border border-white/50 px-5 py-3 text-sm font-semibold text-white hover:bg-white/10 disabled:opacity-60"
          >
            Reload saved profile
          </button>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 md:p-8">
        <h3 className="text-lg font-bold">Before you start</h3>

        <p className="mt-2 text-sm leading-6 text-slate-600">
          Upload your resume, education details, or project portfolio in
          Documents. Make sure each document is categorized as{" "}
          <strong>personal</strong>. Reference documents are not used to build
          your personal profile.
        </p>

        {result?.updated_at && (
          <p className="mt-2 text-xs text-slate-500">
            Last saved: {new Date(result.updated_at).toLocaleString()}
          </p>
        )}
      </section>

      {error && (
        <section
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm leading-6 text-rose-800"
        >
          <h3 className="font-bold">Profile action failed</h3>
          <p className="mt-1">{error}</p>
        </section>
      )}

      {notice && (
        <p
          role="status"
          className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"
        >
          {notice}
        </p>
      )}

      {loaded && !loading && result?.status === "not_generated" && (
        <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
          No saved profile yet. Extract a profile after uploading personal
          documents.
        </p>
      )}

      <section className="rounded-2xl border border-slate-200 bg-white p-6 md:p-8">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-xl font-bold">
              Review and correct your profile
            </h3>

            <p className="mt-1 text-sm text-slate-500">
              {itemCount} profile detail{itemCount === 1 ? "" : "s"} · Status:{" "}
              {(result?.status ?? "not loaded").replaceAll("_", " ")}
            </p>
          </div>

          <button
            type="button"
            onClick={saveCorrections}
            disabled={
              saving ||
              loading ||
              !result ||
              result.status === "not_generated"
            }
            className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save corrections"}
          </button>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          {fields.map((field) => {
            const items = profile[field.key] ?? [];

            return (
              <article
                key={field.key}
                className="rounded-xl border border-slate-200 p-4"
              >
                <h4 className="font-semibold text-slate-800">
                  {field.label}
                </h4>

                <div className="mt-3 space-y-4">
                  {items.map((item, index) => (
                    <div
                      key={`${field.key}-${index}`}
                      className="rounded-lg bg-slate-50 p-3"
                    >
                      <label className="text-xs font-medium text-slate-600">
                        Profile detail
                        <textarea
                          value={item.value}
                          onChange={(event) =>
                            updateItem(field.key, index, event.target.value)
                          }
                          rows={2}
                          className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2 text-sm text-slate-800 outline-none focus:border-indigo-500"
                        />
                      </label>

                      {item.evidence_ids.length > 0 ? (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {item.evidence_ids.map((id) => {
                            const source = sources[id];

                            return (
                              <span
                                key={id}
                                className="rounded-md bg-indigo-50 px-2 py-1 text-xs text-indigo-700"
                                title={
                                  source
                                    ? `Document ID: ${source.document_id ?? "unknown"}`
                                    : "Source details unavailable"
                                }
                              >
                                {source?.filename || `Source ${id}`}
                                {typeof source?.chunk_index === "number"
                                  ? ` · Chunk ${source.chunk_index}`
                                  : ""}
                              </span>
                            );
                          })}
                        </div>
                      ) : (
                        <p className="mt-2 text-xs text-amber-700">
                          Manually added; no document evidence linked.
                        </p>
                      )}

                      <button
                        type="button"
                        onClick={() => removeItem(field.key, index)}
                        className="mt-2 text-xs font-semibold text-rose-700 hover:underline"
                      >
                        Remove detail
                      </button>
                    </div>
                  ))}

                  {items.length === 0 && (
                    <p className="text-sm text-slate-400">
                      No details added
                    </p>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => addItem(field.key)}
                  className="mt-4 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Add {field.label.toLowerCase()}
                </button>
              </article>
            );
          })}
        </div>

        <p className="mt-5 text-xs leading-5 text-slate-500">
          Source labels identify the document and chunk used during extraction.
          Editing a detail does not change the original document. Manually added
          details are saved without claiming document verification.
        </p>
      </section>
    </div>
  );
}
