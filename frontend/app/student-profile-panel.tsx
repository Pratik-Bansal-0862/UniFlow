"use client";

import { useState } from "react";

type ProfileItem = {
  value: string;
  evidence_ids?: string[];
};

type ProfileResponse = {
  profile?: Record<string, ProfileItem[]>;
  sources?: Record<
    string,
    { document_id?: string; filename?: string; chunk_index?: number }
  >;
  status?: string;
  detail?: string;
  message?: string;
};

const fields: { key: string; label: string }[] = [
  { key: "education", label: "Education" },
  { key: "skills", label: "Skills" },
  { key: "projects", label: "Projects" },
  { key: "experience", label: "Experience" },
  { key: "certifications", label: "Certifications" },
  { key: "interests", label: "Interests" },
  { key: "goals", label: "Career goals" },
];

export default function StudentProfilePanel() {
  const [result, setResult] = useState<ProfileResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function extractProfile() {
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch("/api/profile/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      const data = (await response.json()) as ProfileResponse;

      if (!response.ok) {
        throw new Error(
          data.detail || data.message || `Request failed (${response.status})`
        );
      }

      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not extract your profile."
      );
    } finally {
      setLoading(false);
    }
  }

  const profile = result?.profile ?? {};
  const sources = result?.sources ?? {};
  const itemCount = fields.reduce(
    (count, field) =>
      count +
      (Array.isArray(profile[field.key]) ? profile[field.key].length : 0),
    0
  );

  return (
    <div className="space-y-6">
      <section className="rounded-3xl bg-gradient-to-br from-indigo-700 via-indigo-600 to-violet-600 p-7 text-white md:p-9">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-indigo-100">
          Your student profile
        </p>
        <h2 className="mt-2 text-3xl font-bold tracking-tight">
          Turn your documents into a profile
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-indigo-50">
          Extract education, skills, projects, experience, interests, and goals
          from your personal documents. The result can help rank relevant
          internships, but it does not establish eligibility.
        </p>
        <button
          type="button"
          onClick={extractProfile}
          disabled={loading}
          className="mt-6 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-indigo-700 shadow-sm transition hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Extracting profile..." : "Extract my profile"}
        </button>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 md:p-8">
        <h3 className="text-lg font-bold">Before you start</h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Upload your resume, education details, or project portfolio in
          Documents. Make sure each document is categorized as{" "}
          <strong>personal</strong>. Reference documents are not used to build
          your personal profile.
        </p>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          Extraction runs on demand. This screen does not save a permanent
          profile or provide profile editing yet. Review the extracted details
          before relying on them.
        </p>
      </section>

      {error && (
        <section
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm leading-6 text-rose-800"
        >
          <h3 className="font-bold">Profile extraction failed</h3>
          <p className="mt-1">{error}</p>
          <p className="mt-2">
            Check that you are signed in, the backend is running, and you have
            uploaded at least one personal document.
          </p>
        </section>
      )}

      {result && (
        <>
          <section className="rounded-2xl border border-slate-200 bg-white p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-xl font-bold">Extracted profile</h3>
                <p className="mt-1 text-sm text-slate-500">
                  {itemCount} profile detail{itemCount === 1 ? "" : "s"} found.
                </p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                {(result.status || "completed").replaceAll("_", " ")}
              </span>
            </div>

            {result.status === "no_personal_evidence" && (
              <p className="mt-5 rounded-xl bg-amber-50 p-4 text-sm leading-6 text-amber-900">
                No personal-document evidence was found. Open Documents, upload
                a relevant file, and check its category before trying again.
              </p>
            )}

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {fields.map((field) => {
                const items = Array.isArray(profile[field.key])
                  ? profile[field.key]
                  : [];

                return (
                  <article
                    key={field.key}
                    className="rounded-xl border border-slate-200 p-4"
                  >
                    <h4 className="font-semibold text-slate-800">
                      {field.label}
                    </h4>
                    {items.length === 0 ? (
                      <p className="mt-2 text-sm text-slate-400">
                        No details extracted
                      </p>
                    ) : (
                      <ul className="mt-3 space-y-3">
                        {items.map((item, index) => (
                          <li
                            key={`${field.key}-${index}`}
                            className="text-sm leading-6 text-slate-700"
                          >
                            <p>{item.value}</p>
                            {Array.isArray(item.evidence_ids) &&
                              item.evidence_ids.length > 0 && (
                                <div className="mt-2 flex flex-wrap gap-2">
                                  {item.evidence_ids.map((id) => {
                                    const source = sources[id];
                                    return (
                                      <span
                                        key={id}
                                        className="rounded-md bg-indigo-50 px-2 py-1 text-xs text-indigo-700"
                                        title={
                                          source
                                            ? `Document ${source.document_id ?? "unknown"}; chunk ${source.chunk_index ?? "unknown"}`
                                            : id
                                        }
                                      >
                                        {source?.filename || id}
                                        {typeof source?.chunk_index === "number"
                                          ? ` · Chunk ${source.chunk_index}`
                                          : ""}
                                      </span>
                                    );
                                  })}
                                </div>
                              )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </article>
                );
              })}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
