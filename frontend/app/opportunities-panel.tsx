"use client";

import { useCallback, useEffect, useState } from "react";

type Opportunity = {
  id: string;
  source: "gmail" | "external" | "manual";
  source_id: string | null;
  title: string;
  organization: string | null;
  description: string | null;
  application_url: string | null;
  location: string | null;
  opportunity_type: string | null;
  deadline: string | null;
  status: "discovered" | "saved" | "applied" | "dismissed" | "expired";
  match_score: number | null;
  match_rationale: string | null;
  missing_requirements: string[];
  source_metadata: Record<string, unknown>;
  created_at: string;
};

type Draft = {
  title: string;
  organization: string;
  description: string;
  application_url: string;
  location: string;
  opportunity_type: string;
  deadline: string;
};

const emptyDraft: Draft = {
  title: "",
  organization: "",
  description: "",
  application_url: "",
  location: "",
  opportunity_type: "Internship",
  deadline: "",
};

const statuses = ["all", "discovered", "saved", "applied", "dismissed", "expired"] as const;
type Filter = (typeof statuses)[number];

const inputClass =
  "mt-1 block w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-50";

const buttonClass =
  "rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50";

function readableError(data: unknown, fallback: string) {
  if (
    typeof data === "object" &&
    data !== null &&
    "detail" in data &&
    typeof data.detail === "string"
  ) {
    return data.detail;
  }
  return fallback;
}

function dateLabel(value: string | null) {
  if (!value) return "No deadline listed";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Deadline not available"
    : date.toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
}

export default function OpportunitiesPanel() {
  const [items, setItems] = useState<Opportunity[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = filter === "all" ? "" : `?status=${filter}`;
      const response = await fetch(`/api/opportunities${query}`, {
        cache: "no-store",
      });
      const data: unknown = await response.json();

      if (!response.ok) {
        throw new Error(readableError(data, `Could not load opportunities (${response.status}).`));
      }

      if (!Array.isArray(data)) {
        throw new Error("The backend returned an unexpected opportunity response.");
      }

      setItems(data as Opportunity[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load opportunities.");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    // This effect loads remote data; load() updates state after the request completes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function createManual(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");

    const payload = {
      source: "manual",
      source_id: null,
      title: draft.title.trim(),
      organization: draft.organization.trim() || null,
      description: draft.description.trim() || null,
      application_url: draft.application_url.trim() || null,
      location: draft.location.trim() || null,
      opportunity_type: draft.opportunity_type.trim() || null,
      deadline: draft.deadline ? new Date(draft.deadline).toISOString() : null,
      source_metadata: { entry_method: "student_manual" },
    };

    try {
      const response = await fetch("/api/opportunities", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data: unknown = response.status === 204 ? null : await response.json();

      if (!response.ok) {
        throw new Error(readableError(data, `Could not save opportunity (${response.status}).`));
      }

      setDraft(emptyDraft);
      setShowForm(false);
      setFilter("all");
      setNotice("Manual opportunity added to your workspace.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save opportunity.");
    } finally {
      setSaving(false);
    }
  }

  async function changeStatus(item: Opportunity, status: Opportunity["status"]) {
    setBusyId(item.id);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`/api/opportunities/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      const data: unknown = await response.json();

      if (!response.ok) {
        throw new Error(readableError(data, `Could not update opportunity (${response.status}).`));
      }

      setNotice(`“${item.title}” marked ${status}.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update opportunity.");
    } finally {
      setBusyId(null);
    }
  }

  async function deleteItem(item: Opportunity) {
    if (!window.confirm(`Delete “${item.title}” from your workspace?`)) return;

    setBusyId(item.id);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`/api/opportunities/${item.id}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        const data: unknown = await response.json();
        throw new Error(readableError(data, `Could not delete opportunity (${response.status}).`));
      }
      setNotice("Opportunity deleted.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete opportunity.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-3xl bg-gradient-to-br from-indigo-700 via-indigo-600 to-violet-600 p-7 text-white md:p-9">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-indigo-100">
          Student opportunities
        </p>
        <div className="mt-5"><OpportunityDiscoveryButton onComplete={() => { void load(); }} /></div>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Your next opportunity starts here.</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-indigo-100">
              Keep internships, scholarships, and other opportunities organized. External discovery
              and Gmail syncing are separate integrations and are not active in this screen yet.
            </p>
          </div>
          <button type="button" onClick={() => setShowForm((value) => !value)}
            className="rounded-xl bg-white px-4 py-3 text-sm font-bold text-indigo-700 hover:bg-indigo-50">
            {showForm ? "Close form" : "＋ Add opportunity"}
          </button>
        </div>
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ["All shown", items.length],
            ["Discovered", items.filter((x) => x.status === "discovered").length],
            ["Saved", items.filter((x) => x.status === "saved").length],
            ["Applied", items.filter((x) => x.status === "applied").length],
          ].map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-white/15 bg-white/10 p-4">
              <p className="text-xs text-indigo-100">{label}</p>
              <p className="mt-1 text-2xl font-bold">{value}</p>
            </div>
          ))}
        </div>
      </section>

      {showForm && (
        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <h3 className="text-lg font-bold">Add an opportunity</h3>
          <p className="mt-1 text-sm text-slate-500">
            This creates a manual record; it is not represented as an online discovery.
          </p>
          <form onSubmit={createManual} className="mt-5 grid gap-4 md:grid-cols-2">
            <label className="text-sm font-semibold">Title *
              <input required maxLength={250} value={draft.title}
                onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                className={inputClass} placeholder="Software Engineering Intern" />
            </label>
            <label className="text-sm font-semibold">Organization
              <input maxLength={250} value={draft.organization}
                onChange={(e) => setDraft({ ...draft, organization: e.target.value })}
                className={inputClass} placeholder="Company or institution" />
            </label>
            <label className="text-sm font-semibold">Type
              <input maxLength={80} value={draft.opportunity_type}
                onChange={(e) => setDraft({ ...draft, opportunity_type: e.target.value })}
                className={inputClass} placeholder="Internship, scholarship..." />
            </label>
            <label className="text-sm font-semibold">Location
              <input maxLength={250} value={draft.location}
                onChange={(e) => setDraft({ ...draft, location: e.target.value })}
                className={inputClass} placeholder="Remote or city" />
            </label>
            <label className="text-sm font-semibold">Application URL
              <input type="url" value={draft.application_url}
                onChange={(e) => setDraft({ ...draft, application_url: e.target.value })}
                className={inputClass} placeholder="https://..." />
            </label>
            <label className="text-sm font-semibold">Deadline
              <input type="date" value={draft.deadline}
                onChange={(e) => setDraft({ ...draft, deadline: e.target.value })}
                className={inputClass} />
            </label>
            <label className="text-sm font-semibold md:col-span-2">Description
              <textarea rows={4} value={draft.description}
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                className={inputClass} placeholder="Requirements, notes, or why it interests you" />
            </label>
            <div className="flex gap-3 md:col-span-2">
              <button disabled={saving} className={buttonClass} type="submit">
                {saving ? "Saving..." : "Save opportunity"}
              </button>
              <button type="button" disabled={saving} onClick={() => setShowForm(false)}
                className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold">
                Cancel
              </button>
            </div>
          </form>
        </section>
      )}

      {error && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
      {notice && <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}

      <section className="rounded-2xl border border-slate-200 bg-white p-5 md:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold">Opportunity list</h3>
            <p className="mt-1 text-sm text-slate-500">Your records, scoped to your signed-in account.</p>
          </div>
          <button type="button" onClick={() => void load()} disabled={loading}
            className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold hover:bg-slate-50 disabled:opacity-50">
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {statuses.map((value) => (
            <button type="button" key={value} onClick={() => setFilter(value)}
              className={`rounded-full px-3 py-2 text-xs font-semibold capitalize ${
                filter === value ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}>
              {value === "all" ? "All statuses" : value}
            </button>
          ))}
        </div>

        {loading ? (
          <p className="py-12 text-center text-sm text-slate-500">Loading your opportunities...</p>
        ) : items.length === 0 ? (
          <div className="py-12 text-center">
            <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-indigo-50 text-2xl text-indigo-700">↗</div>
            <h4 className="mt-4 font-bold">No opportunities here yet</h4>
            <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-500">
              Add an opportunity manually to start organizing your list. Online discovery will be
              connected separately once a verifiable free source is integrated.
            </p>
            <button type="button" onClick={() => setShowForm(true)} className={`${buttonClass} mt-4`}>
              Add your first opportunity
            </button>
          </div>
        ) : (
          <div className="mt-5 space-y-4">
            {items.map((item) => (
              <article key={item.id} className="rounded-2xl border border-slate-200 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="text-base font-bold">{item.title}</h4>
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-slate-600">
                        {item.source === "manual" ? "Manual entry" : item.source}
                      </span>
                      <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-[10px] font-bold capitalize text-indigo-700">
                        {item.status}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-slate-600">
                      {[item.organization, item.location, item.opportunity_type].filter(Boolean).join(" · ") || "Organization details not provided"}
                    </p>
                  </div>
                  {item.match_score !== null && (
                    <span className="rounded-xl bg-emerald-50 px-3 py-2 text-sm font-bold text-emerald-700">
                      {item.match_score}% match
                    </span>
                  )}
                </div>

                {item.description && <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-600">{item.description}</p>}
                {item.match_rationale && <p className="mt-3 text-sm leading-6 text-slate-600"><strong>Match notes:</strong> {item.match_rationale}</p>}
                {item.missing_requirements?.length > 0 && (
                  <div className="mt-3 rounded-xl bg-amber-50 p-3">
                    <p className="text-xs font-bold text-amber-900">Requirements to check</p>
                    <ul className="mt-1 list-disc pl-5 text-sm text-amber-900">
                      {item.missing_requirements.map((requirement, index) => <li key={`${index}-${requirement}`}>{requirement}</li>)}
                    </ul>
                  </div>
                )}

                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
                  <div className="text-xs text-slate-500">
                    <p>{dateLabel(item.deadline)}</p>
                    <p className="mt-1">Added {dateLabel(item.created_at)}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {item.application_url && (
                      <a href={item.application_url} target="_blank" rel="noreferrer"
                        className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold hover:bg-slate-50">
                        Open listing ↗
                      </a>
                    )}
                    {item.status === "discovered" && <button disabled={busyId === item.id} onClick={() => void changeStatus(item, "saved")} className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">Save</button>}
                    {item.status === "saved" && <button disabled={busyId === item.id} onClick={() => void changeStatus(item, "applied")} className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">Mark applied</button>}
                    {item.status !== "dismissed" && item.status !== "applied" && (
                      <button disabled={busyId === item.id} onClick={() => void changeStatus(item, "dismissed")} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 disabled:opacity-50">Dismiss</button>
                    )}
                    <button disabled={busyId === item.id} onClick={() => void deleteItem(item)} className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700 disabled:opacity-50">Delete</button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function OpportunityDiscoveryButton({ onComplete }: { onComplete: () => void }) {
  const [discovering, setDiscovering] = useState(false);
  const [message, setMessage] = useState("");

  async function discover() {
    setDiscovering(true);
    setMessage("");
    try {
      const response = await fetch("/api/opportunities/discover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : typeof data.error === "string"
              ? data.error
              : "Opportunity discovery failed."
        );
      }
      const count =
        typeof data.added === "number" ? data.added :
        typeof data.created === "number" ? data.created :
        typeof data.discovered === "number" ? data.discovered : null;
      const sourcesChecked =
        typeof data.sources_checked === "number" ? data.sources_checked : null;
      const sourceErrors = Array.isArray(data.source_errors)
        ? data.source_errors.length
        : 0;

      if (sourcesChecked === 0 && typeof data.message === "string") {
        setMessage(data.message);
      } else if (sourceErrors > 0) {
        setMessage(
          `Discovery added ${count ?? 0} opportunities, but ${sourceErrors} source(s) reported errors.`
        );
      } else if (count !== null) {
        setMessage(
          `${typeof data.message === "string" ? data.message + " " : ""}${count} new opportunities found.`
        );
      } else {
        setMessage(
          typeof data.message === "string"
            ? data.message
            : "Discovery finished. Refreshing opportunities…"
        );
      }
      onComplete();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Discovery failed.");
    } finally {
      setDiscovering(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-2">
      <button
        type="button"
        onClick={discover}
        disabled={discovering}
        className="rounded-xl border border-white/30 bg-white px-4 py-2.5 text-sm font-semibold text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
      >
        {discovering ? "Discovering…" : "Discover opportunities"}
      </button>
      {message && <p role="status" className="max-w-xl text-sm text-white">{message}</p>}
    </div>
  );
}




