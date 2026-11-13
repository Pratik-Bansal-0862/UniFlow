"use client";

import { useCallback, useEffect, useState } from "react";

type ActionStatus = "pending_approval" | "approved" | "executing" | "succeeded" | "failed" | "rejected";
type ApprovalStatus = "pending" | "approved" | "rejected" | "expired";

type AgentAction = {
  id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  status: ActionStatus;
  result?: Record<string, unknown> | null;
  error_code?: string | null;
  created_at: string;
};

type Approval = {
  id: string;
  action_id: string;
  status: ApprovalStatus;
  expires_at?: string | null;
  created_at: string;
};

type ApiError = { detail?: string };

const button = "rounded-xl px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50";
const primary = `${button} bg-indigo-600 text-white hover:bg-indigo-700`;
const secondary = `${button} border border-slate-200 text-slate-700 hover:bg-slate-50`;
const field = "mt-1 block w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-50";

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    cache: "no-store",
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error((data as ApiError)?.detail || `Request failed (${response.status}).`);
  }
  return data as T;
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "?";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function TasksApprovalsPanel({ section }: { section: "Tasks" | "Approvals" }) {
  const [actions, setActions] = useState<AgentAction[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [summary, setSummary] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [actionData, approvalData] = await Promise.all([
        requestJson<AgentAction[]>("/api/actions"),
        requestJson<Approval[]>("/api/approvals"),
      ]);
      setActions(actionData);
      setApprovals(approvalData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load actions.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialData() {
      try {
        const [actionData, approvalData] = await Promise.all([
          requestJson<AgentAction[]>("/api/actions"),
          requestJson<Approval[]>("/api/approvals"),
        ]);

        if (!cancelled) {
          setActions(actionData);
          setApprovals(approvalData);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load actions.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadInitialData();

    return () => {
      cancelled = true;
    };
  }, []);

  async function createGmailDraft(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("gmail");
    setError(null);
    setMessage(null);
    try {
      const data = await requestJson<{ draft_id: string }>("/api/integrations/google/gmail/drafts", {
        method: "POST",
        body: JSON.stringify({
          to: to.trim(),
          subject: subject.trim(),
          body,
          idempotency_key: crypto.randomUUID(),
        }),
      });
      setMessage(`Gmail draft created. Approval is required before sending. Draft ID: ${data.draft_id}`);
      setTo(""); setSubject(""); setBody("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create Gmail draft.");
    } finally {
      setBusy(null);
    }
  }

  async function requestCalendarEvent(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!start || !end || new Date(end) <= new Date(start)) {
      setError("The event end time must be later than its start time.");
      return;
    }
    setBusy("calendar");
    setError(null);
    setMessage(null);
    try {
      await requestJson("/api/integrations/google/calendar/events", {
        method: "POST",
        body: JSON.stringify({
          summary: summary.trim(),
          start: new Date(start).toISOString(),
          end: new Date(end).toISOString(),
          timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
          description: description.trim() || null,
          location: location.trim() || null,
          idempotency_key: crypto.randomUUID(),
        }),
      });
      setMessage("Calendar request created. It will not be added until approved and executed.");
      setSummary(""); setStart(""); setEnd(""); setDescription(""); setLocation("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not request calendar event.");
    } finally {
      setBusy(null);
    }
  }

  async function decide(approval: Approval, decision: "approve" | "reject") {
    const action = actions.find((item) => item.id === approval.action_id);
    const prompt = decision === "approve"
      ? `Approve this ${action?.tool_name || "action"} request? This does not execute it.`
      : "Reject this action request?";
    if (!window.confirm(prompt)) return;

    setBusy(`approval-${approval.id}`);
    setError(null);
    setMessage(null);
    try {
      await requestJson(`/api/approvals/${encodeURIComponent(approval.id)}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision }),
      });
      setMessage(decision === "approve"
        ? "Approval recorded. Execution is a separate step."
        : "Action request rejected.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update approval.");
    } finally {
      setBusy(null);
    }
  }

  async function execute(action: AgentAction) {
    const approval = approvals.find((item) => item.action_id === action.id);
    if (!approval || approval.status !== "approved" || action.status !== "approved") {
      setError("This action does not have a confirmed approved status.");
      return;
    }

    const isGmail = action.tool_name === "gmail.send";
    const isCalendar = action.tool_name === "calendar.create_event";
    if (!isGmail && !isCalendar) {
      setError(`No execution handler is configured for ${action.tool_name}.`);
      return;
    }

    const prompt = isGmail
      ? `Send the approved Gmail draft to ${displayValue(action.arguments.to)} with subject "${displayValue(action.arguments.subject)}"?`
      : `Create the approved calendar event "${displayValue(action.arguments.summary)}"?`;
    if (!window.confirm(prompt)) return;

    setBusy(`execute-${action.id}`);
    setError(null);
    setMessage(null);
    try {
      const path = isGmail
        ? `/api/integrations/google/gmail/actions/${encodeURIComponent(action.id)}/execute`
        : `/api/integrations/google/calendar/actions/${encodeURIComponent(action.id)}/execute`;
      await requestJson(path, { method: "POST" });
      setMessage(isGmail
        ? "Gmail execution completed. Check your Sent folder."
        : "Calendar execution completed. Check Google Calendar.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Execution failed. Check the action status before retrying.");
      await refresh();
    } finally {
      setBusy(null);
    }
  }

  const pendingApprovals = approvals.filter((item) => item.status === "pending");

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 md:p-8">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.15em] text-indigo-600">
              {section === "Tasks" ? "Action workspace" : "Human approval gate"}
            </p>
            <h2 className="mt-1 text-2xl font-bold text-slate-900">
              {section === "Tasks" ? "Tasks and actions" : "Approval queue"}
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              Create requests, review details, and control when approved actions execute.
            </p>
          </div>
          <button type="button" className={secondary} onClick={() => void refresh()} disabled={loading || busy !== null}>
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {error && <p role="alert" className="mt-5 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        {message && <p role="status" className="mt-5 rounded-xl bg-indigo-50 p-3 text-sm text-indigo-700">{message}</p>}

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs text-slate-500">Total actions</p><p className="mt-1 text-2xl font-bold text-slate-900">{actions.length}</p></div>
          <div className="rounded-xl bg-amber-50 p-4"><p className="text-xs text-amber-700">Awaiting approval</p><p className="mt-1 text-2xl font-bold text-amber-900">{pendingApprovals.length}</p></div>
          <div className="rounded-xl bg-emerald-50 p-4"><p className="text-xs text-emerald-700">Completed</p><p className="mt-1 text-2xl font-bold text-emerald-900">{actions.filter((item) => item.status === "succeeded").length}</p></div>
        </div>
      </section>

      {section === "Tasks" && <>
        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <h3 className="text-lg font-bold text-slate-900">Prepare a Gmail draft</h3>
          <p className="mt-1 text-sm text-slate-500">Creates a draft and approval request. It does not send the email.</p>
          <form className="mt-5 space-y-4" onSubmit={createGmailDraft}>
            <label className="block text-sm font-semibold text-slate-700">Recipient email<input className={field} type="email" required maxLength={320} value={to} onChange={(e) => setTo(e.target.value)} /></label>
            <label className="block text-sm font-semibold text-slate-700">Subject<input className={field} required maxLength={998} value={subject} onChange={(e) => setSubject(e.target.value)} /></label>
            <label className="block text-sm font-semibold text-slate-700">Email body<textarea className={field} required maxLength={100000} rows={6} value={body} onChange={(e) => setBody(e.target.value)} /></label>
            <button className={primary} type="submit" disabled={busy !== null}>{busy === "gmail" ? "Creating draft..." : "Create Gmail draft"}</button>
          </form>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <h3 className="text-lg font-bold text-slate-900">Request a Calendar event</h3>
          <p className="mt-1 text-sm text-slate-500">Submits an event request for approval. It does not immediately change your calendar.</p>
          <form className="mt-5 space-y-4" onSubmit={requestCalendarEvent}>
            <label className="block text-sm font-semibold text-slate-700">Event title<input className={field} required maxLength={500} value={summary} onChange={(e) => setSummary(e.target.value)} /></label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block text-sm font-semibold text-slate-700">Start<input className={field} type="datetime-local" required value={start} onChange={(e) => setStart(e.target.value)} /></label>
              <label className="block text-sm font-semibold text-slate-700">End<input className={field} type="datetime-local" required value={end} onChange={(e) => setEnd(e.target.value)} /></label>
            </div>
            <label className="block text-sm font-semibold text-slate-700">Location (optional)<input className={field} maxLength={1000} value={location} onChange={(e) => setLocation(e.target.value)} /></label>
            <label className="block text-sm font-semibold text-slate-700">Description (optional)<textarea className={field} rows={3} maxLength={10000} value={description} onChange={(e) => setDescription(e.target.value)} /></label>
            <p className="text-xs text-slate-400">Times use your browser timezone: {Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"}.</p>
            <button className={primary} type="submit" disabled={busy !== null}>{busy === "calendar" ? "Submitting request..." : "Request Calendar event"}</button>
          </form>
        </section>
      </>}

      <section className="rounded-2xl border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div><h3 className="text-lg font-bold text-slate-900">{section === "Approvals" ? "Review requests" : "Action history"}</h3><p className="mt-1 text-sm text-slate-500">Approval and execution are separate steps. Review details before deciding.</p></div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{actions.length} records</span>
        </div>

        {loading ? <p className="mt-5 text-sm text-slate-500">Loading actions and approvals...</p>
          : actions.length === 0 ? <p className="mt-5 rounded-xl bg-slate-50 p-5 text-sm text-slate-500">No actions yet. Create a Gmail draft or Calendar request to get started.</p>
          : <div className="mt-5 space-y-4">
            {actions.map((action) => {
              const approval = approvals.find((item) => item.action_id === action.id);
              const canExecute = action.status === "approved" && approval?.status === "approved";
              const canDecide = action.status === "pending_approval" && approval?.status === "pending";
              return <article key={action.id} className="rounded-xl border border-slate-200 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div><h4 className="font-semibold text-slate-900">{action.tool_name === "gmail.send" ? "Gmail email" : action.tool_name === "calendar.create_event" ? "Calendar event" : action.tool_name}</h4><p className="mt-1 text-xs text-slate-500">Created {formatDate(action.created_at)}</p></div>
                  <div className="flex flex-wrap gap-2 text-xs font-semibold"><span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">Action: {action.status.replaceAll("_", " ")}</span>{approval && <span className="rounded-full bg-indigo-50 px-3 py-1 text-indigo-700">Approval: {approval.status}</span>}</div>
                </div>
                <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                  {Object.entries(action.arguments).map(([key, value]) => <div key={key} className="min-w-0"><dt className="text-xs font-medium text-slate-400">{key.replaceAll("_", " ")}</dt><dd className="mt-1 break-words text-slate-700">{displayValue(value)}</dd></div>)}
                </dl>
                {action.error_code && <p className="mt-3 rounded-lg bg-red-50 p-3 text-xs text-red-700">Error code: {action.error_code}. Check the external service before retrying.</p>}
                {action.result && <details className="mt-3"><summary className="cursor-pointer text-xs font-semibold text-slate-500">Execution result</summary><pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-3 text-xs text-slate-600">{JSON.stringify(action.result, null, 2)}</pre></details>}
                <div className="mt-4 flex flex-wrap gap-2">
                  {canDecide && approval && <>
                    <button type="button" className={primary} disabled={busy !== null} onClick={() => void decide(approval, "approve")}>{busy === `approval-${approval.id}` ? "Saving..." : "Approve"}</button>
                    <button type="button" className={`${button} border border-red-200 text-red-700 hover:bg-red-50`} disabled={busy !== null} onClick={() => void decide(approval, "reject")}>Reject</button>
                  </>}
                  {canExecute && <button type="button" className={primary} disabled={busy !== null} onClick={() => void execute(action)}>{busy === `execute-${action.id}` ? "Executing..." : "Execute approved action"}</button>}
                </div>
              </article>;
            })}
          </div>}
      </section>
    </div>
  );
}
