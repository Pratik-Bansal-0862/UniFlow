"use client";
import { EmbeddingExplorer } from "@/components/embedding-explorer";
import { useCallback, useState } from "react";
import OpportunitiesPanel from "./opportunities-panel";
import StudentProfilePanel from "./student-profile-panel";
import GoogleIntegrationsPanel from "./google-integrations-panel";

import { AcademicPanel } from "./academic-panel";
import { CommunicationPanel } from "./communication-panel";

type ApiResult = {
  detail?: string;
  message?: string;
  email?: string;
  full_name?: string | null;
  id?: string;
  is_active?: boolean;
  [key: string]: unknown;
};

type DocumentCategory = "personal" | "reference" | "unverified";

type UserDocument = {
  id: string;
  filename: string;
  category: DocumentCategory;
  status: string;
  created_at: string;
};

type RetrievedChunk = {
  document_id: string;
  filename: string;
  text: string;
  chunk_index: number;
  distance: number | null;
  category: DocumentCategory;
};

type SearchResponse = {
  results?: RetrievedChunk[];
  answer?: string | null;
  answer_status?: string;
  detail?: string;
};

type PlannedStep = {
  step_id: string;
  description: string;
  tool_name: string | null;
  requires_approval: boolean;
  depends_on: string[];
};

type AgentPlan = {
  objective: string;
  status: "draft" | "ready" | "blocked";
  steps: PlannedStep[];
  evidence_ids: string[];
  warnings: string[];
};

type PlanResponse = Partial<AgentPlan> & { detail?: string };

type Section = "Overview" | "Opportunities" | "Student Profile" | "AI Planner" | "Academic Agent" | "Communication Agent" | "Documents" | "Tasks" | "Approvals" | "Settings";

const navigation: { label: Section; icon: string; subtitle: string }[] = [
  { label: "Overview", icon: "home", subtitle: "Your student workspace" },
  { label: "Opportunities", icon: "compass", subtitle: "Discover and track opportunities" },
  { label: "Student Profile", icon: "user-round", subtitle: "Review your skills and experience" },
  { label: "AI Planner", icon: "sparkles", subtitle: "Turn goals into action plans" },
  { label: "Academic Agent", icon: "sparkles", subtitle: "Study roadmaps and coursework planning" },
  { label: "Communication Agent", icon: "sparkles", subtitle: "Draft professional outreach and emails" },
  { label: "Documents", icon: "file-text", subtitle: "Upload and search your files" },
  { label: "Tasks", icon: "check-square", subtitle: "Keep your next steps organized" },
  { label: "Approvals", icon: "clipboard-check", subtitle: "Review actions before they happen" },
  { label: "Settings", icon: "settings", subtitle: "Account and workspace" },
];

export default function Home() {
  const [section, setSection] = useState<Section>("Overview");
  const [mode, setMode] = useState<"register" | "login">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [authResult, setAuthResult] = useState<ApiResult | null>(null);
  const [profileResult, setProfileResult] = useState<ApiResult | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<ApiResult | null>(null);
  const [documents, setDocuments] = useState<UserDocument[]>([]);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState("5");
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [objective, setObjective] = useState(
    "Find suitable software engineering internships for summer 2027. Identify missing application requirements and prepare a checklist. Do not submit applications or send emails.",
  );
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function readResponse(response: Response): Promise<ApiResult> {
    const data: unknown = await response.json();
    if (typeof data === "object" && data !== null) {
      return {
        ...(data as ApiResult),
        ...(!response.ok ? { http_status: response.status } : {}),
      };
    }
    return { detail: "The server returned an unexpected response.", http_status: response.status };
  }

  const loadDocuments = useCallback(async () => {
    setDocumentsError(null);
    try {
      const response = await fetch("/api/documents", { cache: "no-store" });
      const data: unknown = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof data === "object" && data !== null && "detail" in data
            ? String(data.detail)
            : "Could not load documents."
        );
      }
      if (!Array.isArray(data)) throw new Error("Unexpected document-list response.");
      setDocuments(data as UserDocument[]);
    } catch (error) {
      setDocumentsError(error instanceof Error ? error.message : "Could not load documents.");
    }
  }, []);

  async function changeDocumentCategory(documentId: string, category: DocumentCategory) {
    setBusy(`category-${documentId}`);
    setDocumentsError(null);
    try {
      const response = await fetch("/api/documents", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: documentId, category }),
      });
      const data: unknown = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof data === "object" && data !== null && "detail" in data
            ? String(data.detail)
            : "Could not update document category."
        );
      }
      await loadDocuments();
      setUploadResult({
        message: `Document category updated to ${category}.`,
      });
    } catch (error) {
      setDocumentsError(error instanceof Error ? error.message : "Could not update category.");
    } finally {
      setBusy(null);
    }
  }

  async function submitAuth(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("auth");
    setAuthResult(null);
    setProfileResult(null);
    try {
      let response: Response;
      if (mode === "register") {
        response = await fetch("/api/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password, full_name: fullName || null }),
        });
      } else {
        const form = new FormData();
        form.set("username", email);
        form.set("password", password);
        response = await fetch("/api/auth/login", { method: "POST", body: form });
      }
      const data = await readResponse(response);
      setAuthResult(response.ok && mode === "login" ? { message: "Login successful." } : data);
      if (response.ok && mode === "login") {
        void checkProfile();
      }
    } catch {
      setAuthResult({ detail: "Could not contact UniFlow. Check that Next.js and FastAPI are running." });
    } finally {
      setBusy(null);
    }
  }

  async function checkProfile() {
    setBusy("profile");
    setProfileResult(null);
    try {
      const response = await fetch("/api/auth/me", { cache: "no-store" });
      const data = await readResponse(response);
      setProfileResult(data);
      if (response.ok) setSection("Overview");
    } catch {
      setProfileResult({ detail: "Could not contact the profile route." });
    } finally {
      setBusy(null);
    }
  }

  async function uploadDocument(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setUploadResult({ detail: "Choose a PDF or DOCX file first." });
      return;
    }
    const lowerName = file.name.toLowerCase();
    if (!lowerName.endsWith(".pdf") && !lowerName.endsWith(".docx")) {
      setUploadResult({ detail: "Only PDF and DOCX files are supported." });
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      setUploadResult({ detail: "The file must be no larger than 15 MB." });
      return;
    }
    setBusy("upload");
    setUploadResult(null);
    setSearchResult(null);
    try {
      const form = new FormData();
      form.set("file", file);
      const response = await fetch("/api/documents/upload", { method: "POST", body: form });
      setUploadResult(await readResponse(response));
      if (response.ok) {
        setFile(null);
        await loadDocuments();
      }
    } catch {
      setUploadResult({ detail: "Could not contact the upload route. Check that Next.js and FastAPI are running." });
    } finally {
      setBusy(null);
    }
  }

  async function searchDocuments(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsedLimit = Number(limit);
    if (!Number.isInteger(parsedLimit) || parsedLimit < 1 || parsedLimit > 20) {
      setSearchResult({ detail: "Result limit must be a whole number from 1 to 20." });
      return;
    }
    setBusy("search");
    setSearchResult(null);
    try {
      const response = await fetch("/api/documents/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, limit: parsedLimit }),
      });
      const data: unknown = await response.json();
      if (!response.ok) {
        setSearchResult({
          detail: typeof data === "object" && data !== null && "detail" in data
            ? String(data.detail)
            : `Search failed with HTTP ${response.status}.`,
        });
      } else {
        setSearchResult(data as SearchResponse);
      }
    } catch {
      setSearchResult({ detail: "Could not contact the search route. Check that Next.js and FastAPI are running." });
    } finally {
      setBusy(null);
    }
  }

  async function createPlan(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!objective.trim() || objective.length > 2000) {
      setPlan({ detail: "Enter an objective of 1Ã¢â‚¬â€œ2000 characters." });
      return;
    }
    setBusy("plan");
    setPlan(null);
    try {
      const response = await fetch("/api/orchestrator/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ objective: objective.trim(), limit: 5 }),
      });
      const data: unknown = await response.json();
      if (typeof data === "object" && data !== null) {
        const result = data as PlanResponse;
        setPlan(response.ok ? result : { ...result, detail: result.detail ?? `Planning failed (HTTP ${response.status}).` });
      } else {
        setPlan({ detail: "The planner returned an unexpected response." });
      }
    } catch {
      setPlan({ detail: "Could not reach the planner. Check that Next.js and FastAPI are running." });
    } finally {
      setBusy(null);
    }
  }

  const signedIn = profileResult !== null && !profileResult.detail && Boolean(profileResult.email);
  const displayName = profileResult?.full_name || profileResult?.email || "Student";

  function openSection(next: Section) {
    setSection(next);

    if (next === "Documents") {
      void loadDocuments();
    }
  }

  return (
    <main className="min-h-screen bg-[#f5f7fb] text-slate-900">
      <div className="mx-auto flex min-h-screen max-w-[1600px]">
        <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white px-5 py-7 md:flex">
          <button className="mb-10 flex items-center gap-3 text-left" onClick={() => openSection("Overview")} type="button">
            <span className="grid h-10 w-10 place-items-center rounded-2xl bg-indigo-600 text-lg font-bold text-white">U</span>
            <span>
              <span className="block text-lg font-bold tracking-tight">UniFlow</span>
              <span className="block text-xs text-slate-500">Your student OS</span>
            </span>
          </button>
          <p className="mb-3 px-3 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">Workspace</p>
          <nav className="space-y-1">
            {navigation.map((item) => (
              <button key={item.label} type="button" onClick={() => openSection(item.label)}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-medium transition ${section === item.label ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}>
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-white text-indigo-600 shadow-sm">
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {item.icon === "home" && <><path d="m3 10 9-7 9 7" /><path d="M5 9v12h14V9M9 21v-7h6v7" /></>}
    {item.icon === "compass" && <><circle cx="12" cy="12" r="9" /><path d="m15.5 8.5-2 5-5 2 2-5z" /></>}
    {item.icon === "sparkles" && <><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" /><path d="m19 14 1 2.5 2 1-2 1-1 2.5-1-2.5-2-1 2-1z" /></>}
    {item.icon === "file-text" && <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v5h4M9 12h6M9 16h6" /></>}
    {item.icon === "check-square" && <><rect x="4" y="4" width="16" height="16" rx="2" /><path d="m8 12 3 3 5-6" /></>}
    {item.icon === "clipboard-check" && <><rect x="5" y="5" width="14" height="16" rx="2" /><path d="M9 5V3h6v2m-7 7 2 2 4-4" /></>}
    {item.icon === "settings" && <><circle cx="12" cy="12" r="3" /><path d="m19.4 15 .1.1 1.1 1.9-2 3.4-2.2-.6a8 8 0 0 1-2 .9L14 23h-4l-.4-2.3a8 8 0 0 1-2-.9l-2.2.6-2-3.4 1.1-1.9a8 8 0 0 1 0-2.2l-1.1-1.9 2-3.4 2.2.6a8 8 0 0 1 2-.9L10 5h4l.4 2.3a8 8 0 0 1 2 .9l2.2-.6 2 3.4-1.1 1.9a8 8 0 0 1-.1 2.1z" transform="translate(0 -2) scale(1 .95)" /></>}
  </svg>
</span>
                <span className="flex-1">{item.label}</span>
                {["Tasks", "Approvals"].includes(item.label) && <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[9px] font-bold uppercase text-slate-500">Soon</span>}
              </button>
            ))}
          </nav>
          <div className="mt-auto rounded-2xl bg-slate-50 p-4">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold"><span className="h-2 w-2 rounded-full bg-emerald-500" /> Workspace status</div>
            <p className="text-xs leading-5 text-slate-500">Planner and document tools connect to your UniFlow backend. External actions are not executed by this draft planner.</p>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/90 px-5 py-4 backdrop-blur md:px-9">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-600">Student workspace</p>
              <h1 className="mt-1 truncate text-xl font-bold tracking-tight md:text-2xl">{section}</h1>
            </div>
            <div className="flex items-center gap-3">
              <button type="button" onClick={checkProfile} disabled={busy !== null}
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">
                {busy === "profile" ? "Checking..." : "Check session"}
              </button>
              <div className="grid h-10 w-10 place-items-center rounded-full bg-indigo-100 text-sm font-bold text-indigo-700">{signedIn ? String(displayName).slice(0, 1).toUpperCase() : "S"}</div>
            </div>
          </header>

          <div className="border-b border-slate-200 bg-white px-4 py-2 md:hidden">
            <div className="flex gap-2 overflow-x-auto">
              {navigation.map((item) => <button key={item.label} onClick={() => openSection(item.label)} type="button" className={`shrink-0 rounded-lg px-3 py-2 text-xs font-semibold ${section === item.label ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600"}`}>{item.label}</button>)}
            </div>
          </div>

          <div className="mx-auto max-w-6xl space-y-7 px-4 py-6 md:px-9 md:py-9">
            {section === "Opportunities" && <OpportunitiesPanel />}
            {section === "Student Profile" && <StudentProfilePanel />}
            {section === "Academic Agent" && <AcademicPanel />}
            {section === "Communication Agent" && <CommunicationPanel />}
            {section === "Overview" && (
              <>
                <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-700 via-indigo-600 to-violet-600 p-7 text-white md:p-10">
                  <div className="relative z-[1] max-w-2xl">
                    <p className="text-sm font-semibold text-indigo-100">A calmer way to manage college life</p>
                    <h2 className="mt-3 text-3xl font-bold leading-tight tracking-tight md:text-4xl">Make room for what matters.</h2>
                    <p className="mt-4 max-w-xl text-sm leading-6 text-indigo-100 md:text-base">Bring your student documents together, turn goals into practical plans, and keep important decisions in your hands.</p>
                    <div className="mt-7 flex flex-wrap gap-3">
                      <button type="button" onClick={() => setSection("AI Planner")} className="rounded-xl bg-white px-5 py-3 text-sm font-bold text-indigo-700 shadow-sm hover:bg-indigo-50">Create an AI plan <span aria-hidden="true">ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â€</span></button>
                      <button type="button" onClick={() => openSection("Documents")} className="rounded-xl border border-white/30 bg-white/10 px-5 py-3 text-sm font-semibold text-white hover:bg-white/15">Manage documents</button>
                    </div>
                  </div>
                  <div aria-hidden="true" className="absolute -right-10 -top-20 h-72 w-72 rounded-full border-[36px] border-white/10" />
                  <div aria-hidden="true" className="absolute -bottom-28 right-32 h-64 w-64 rounded-full border-[28px] border-white/10" />
                </section>

                <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  <MetricCard eyebrow="AI WORKSPACE" title="AI Planner" value="Ready to try" detail="Generate an evidence-grounded draft" onClick={() => setSection("AI Planner")} />
                  <MetricCard eyebrow="YOUR FILES" title="Documents" value="Upload & search" detail="PDF and DOCX Ã‚Â· up to 15 MB" onClick={() => openSection("Documents")} />
                  <MetricCard eyebrow="ORGANIZATION" title="Tasks" value="Coming soon" detail="Task tracking is not connected yet" onClick={() => setSection("Tasks")} />
                  <MetricCard eyebrow="USER CONTROL" title="Approvals" value="Coming soon" detail="No external actions run automatically" onClick={() => setSection("Approvals")} />
                </section>

                <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
                  <section className="rounded-2xl border border-slate-200 bg-white p-6">
                    <div className="flex items-start justify-between gap-4">
                      <div><p className="text-xs font-bold uppercase tracking-[0.15em] text-slate-400">Quick start</p><h3 className="mt-2 text-lg font-bold">Build your student context</h3><p className="mt-1 text-sm text-slate-500">Upload a resume or opportunity brief to ground your first plan.</p></div>
                      <span className="grid h-10 w-10 place-items-center rounded-xl bg-indigo-50 text-lg text-indigo-700">ÃƒÂ¢Ã…â€œÃ‚Â³</span>
                    </div>
                    <ol className="mt-5 space-y-4">
                      <QuickStep number="01" title="Sign in to your workspace" detail="Use your existing account or create one below." />
                      <QuickStep number="02" title="Upload a relevant PDF or DOCX" detail="A resume, opportunity description, or project brief can help." />
                      <QuickStep number="03" title="Ask the AI Planner for a draft" detail="Review the evidence and warnings before acting." />
                    </ol>
                  </section>
                  <section className="rounded-2xl border border-slate-200 bg-white p-6">
                    <p className="text-xs font-bold uppercase tracking-[0.15em] text-slate-400">Account</p>
                    <h3 className="mt-2 text-lg font-bold">{signedIn ? `Welcome, ${String(displayName)}` : "Sign in to get started"}</h3>
                    <p className="mt-2 text-sm leading-6 text-slate-500">{signedIn ? "Your session was checked successfully. Your documents and plans are scoped to your account." : "Authentication protects your personal document workspace. Sign in below, then use Check session to verify access."}</p>
                    {profileResult && <ResponsePanel title="Profile response" data={profileResult} />}
                <GoogleIntegrationsPanel />
                    {authResult && <ResponsePanel title="Authentication response" data={authResult} />}
                  </section>
                </div>

                <section className="rounded-2xl border border-slate-200 bg-white p-6">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div><p className="text-xs font-bold uppercase tracking-[0.15em] text-slate-400">Account access</p><h3 className="mt-2 text-lg font-bold">{mode === "register" ? "Create your account" : "Welcome back"}</h3><p className="mt-1 text-sm text-slate-500">Use the existing secure authentication routes.</p></div>
                    <div className="flex rounded-xl bg-slate-100 p-1">
                      <button type="button" onClick={() => { setMode("register"); setAuthResult(null); }} className={`rounded-lg px-3 py-2 text-sm font-semibold ${mode === "register" ? "bg-white text-indigo-700 shadow-sm" : "text-slate-500"}`}>Register</button>
                      <button type="button" onClick={() => { setMode("login"); setAuthResult(null); }} className={`rounded-lg px-3 py-2 text-sm font-semibold ${mode === "login" ? "bg-white text-indigo-700 shadow-sm" : "text-slate-500"}`}>Login</button>
                    </div>
                  </div>
                  <form onSubmit={submitAuth} className="mt-5 grid gap-4 md:grid-cols-2">
                    {mode === "register" && <Field label="Full name (optional)"><input value={fullName} onChange={(event) => setFullName(event.target.value)} maxLength={200} className={inputClass} placeholder="Student name" /></Field>}
                    <Field label="Email"><input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} className={inputClass} placeholder="student@example.com" /></Field>
                    <Field label="Password"><input type="password" required minLength={mode === "register" ? 12 : undefined} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} className={inputClass} placeholder={mode === "register" ? "At least 12 characters" : "Your password"} /></Field>
                    <div className="flex items-end"><button type="submit" disabled={busy !== null} className={primaryButton}>{busy === "auth" ? "Please waitÃ¢â‚¬ÂÃ‚Â¦" : mode === "register" ? "Create account" : "Sign in"}</button></div>
                  </form>
                  {authResult && <ResponsePanel title="Authentication response" data={authResult} />}
                </section>
              </>
            )}

            {section === "AI Planner" && (
              <>
                <section className="rounded-2xl border border-slate-200 bg-white p-6 md:p-8">
                  <div className="flex items-start gap-4"><span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-indigo-50 text-2xl text-indigo-700">ÃƒÂ¢Ã…â€œÃ‚Â³</span><div><p className="text-xs font-bold uppercase tracking-[0.15em] text-indigo-600">Evidence-grounded planning</p><h2 className="mt-1 text-2xl font-bold tracking-tight">What would you like to work toward?</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">UniFlow uses your relevant uploaded documents to create a draft plan. It does not send emails, submit applications, or perform external actions.</p></div></div>
                  <form onSubmit={createPlan} className="mt-7 space-y-4">
                    <label className="block text-sm font-semibold text-slate-700">Your objective<textarea required minLength={1} maxLength={2000} rows={5} value={objective} onChange={(event) => setObjective(event.target.value)} className={`${inputClass} mt-2 resize-y leading-6`} placeholder="Describe the outcome you want and any constraintsÃ¢â‚¬ÂÃ‚Â¦" /></label>
                    <div className="flex flex-wrap items-center justify-between gap-3"><span className="text-xs text-slate-400">{objective.length}/2000 characters Ã‚Â· Upload relevant documents first</span><button type="submit" disabled={busy !== null} className={primaryButton}>{busy === "plan" ? "Building draftÃ¢â‚¬ÂÃ‚Â¦" : "Generate draft plan ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â€"}</button></div>
                  </form>
                </section>

                {plan && (
                  <section aria-live="polite" className="space-y-5">
                    {plan.detail && <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{plan.detail}</div>}
                    {plan.status && <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-5"><div><p className="text-xs font-bold uppercase tracking-[0.15em] text-slate-400">Planner status</p><h3 className="mt-1 text-xl font-bold">{plan.status === "blocked" ? "More context needed" : "Draft plan created"}</h3></div><span className={`rounded-full px-3 py-1.5 text-xs font-bold uppercase tracking-wide ${plan.status === "blocked" ? "bg-amber-100 text-amber-800" : "bg-indigo-100 text-indigo-700"}`}>{plan.status}</span></div>}
                    {plan.steps && plan.steps.length > 0 && <div className="rounded-2xl border border-slate-200 bg-white p-6"><h3 className="text-lg font-bold">Your next steps</h3><div className="mt-5 space-y-4">{plan.steps.map((step, index) => <article key={step.step_id} className="flex gap-4 rounded-xl border border-slate-100 p-4"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-indigo-50 text-sm font-bold text-indigo-700">{String(index + 1).padStart(2, "0")}</span><div className="min-w-0 flex-1"><h4 className="font-semibold">{step.description}</h4><p className="mt-1 text-xs text-slate-400">Step ID: {step.step_id}{step.depends_on.length ? ` Ã‚Â· Depends on: ${step.depends_on.join(", ")}` : ""}</p>{step.requires_approval && <span className="mt-2 inline-flex rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800">Would require approval</span>}</div></article>)}</div></div>}
                    {plan.warnings && plan.warnings.length > 0 && <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5"><h3 className="font-bold text-amber-900">Things to review</h3><ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-amber-900">{plan.warnings.map((warning, index) => <li key={`${index}-${warning}`}>{warning}</li>)}</ul></div>}
                    {plan.evidence_ids && <p className="text-xs text-slate-400">Evidence chunks referenced: {plan.evidence_ids.length}. Verify important details before relying on this draft.</p>}
                  </section>
                )}
                <section className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5"><h3 className="font-bold">No relevant evidence yet?</h3><p className="mt-1 text-sm leading-6 text-slate-500">Upload a resume, opportunity listing, or other relevant PDF/DOCX before generating a plan. The planner will block rather than invent evidence when it cannot find relevant documents.</p><button type="button" onClick={() => openSection("Documents")} className="mt-4 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold hover:bg-slate-100">Go to Documents</button></section>
              </>
            )}

            {section === "Documents" && (
              <>
                <section className="rounded-2xl border border-slate-200 bg-white p-6 md:p-8">
                  <div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.15em] text-indigo-600">Knowledge base</p><h2 className="mt-1 text-2xl font-bold tracking-tight">Your documents</h2><p className="mt-2 text-sm leading-6 text-slate-500">Upload PDF or DOCX files to make relevant context available to document search and AI planning.</p></div><span className="grid h-11 w-11 place-items-center rounded-xl bg-indigo-50 text-xl text-indigo-700">ÃƒÂ¢Ã¢â‚¬â€œÃ‚Â¤</span></div>
                  <form onSubmit={uploadDocument} className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5">
                    <label className="block text-sm font-semibold">Choose a document<input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="mt-3 block w-full text-sm text-slate-600 file:mr-4 file:rounded-lg file:border-0 file:bg-indigo-100 file:px-4 file:py-2 file:font-semibold file:text-indigo-700 hover:file:bg-indigo-200" /></label>
                    <p className="mt-3 text-xs text-slate-400">PDF or DOCX Ã‚Â· Maximum 15 MB</p>
                    {file && <p className="mt-2 text-sm text-slate-600">Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)</p>}
                    <button type="submit" disabled={busy !== null} className={`${primaryButton} mt-5`}>{busy === "upload" ? "Uploading and processingÃ¢â‚¬ÂÃ‚Â¦" : "Upload document"}</button>
                  </form>
                  {uploadResult && <ResponsePanel title="Upload result" data={uploadResult} />}
                </section>

                <section className="rounded-2xl border border-slate-200 bg-white p-6 md:p-8">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-[0.15em] text-indigo-600">Source classification</p>
                      <h2 className="mt-1 text-xl font-bold">Document library</h2>
                      <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                        New uploads start as Unverified. Mark your own resume and personal records as Personal.
                        Use Reference for someone else&apos;s resume or other material. Reference and Unverified
                        documents should not be treated as facts about you.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void loadDocuments()}
                      disabled={busy !== null}
                      className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      Refresh documents
                    </button>
                  </div>

                  {documentsError && (
                    <div role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                      {documentsError}
                    </div>
                  )}

                  {documents.length === 0 ? (
                    <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">
                      No documents are loaded. If you are signed in and have uploaded files, use Refresh documents.
                    </p>
                  ) : (
                    <div className="mt-5 space-y-3">
                      {documents.map((document) => (
                        <article
                          key={document.id}
                          className="flex flex-col gap-3 rounded-xl border border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between"
                        >
                          <div className="min-w-0">
                            <h3 className="break-words font-semibold text-slate-900">{document.filename}</h3>
                            <p className="mt-1 text-xs text-slate-500">
                              Status: {document.status} Â· Added {new Date(document.created_at).toLocaleDateString()}
                            </p>
                          </div>
                          <label className="flex shrink-0 flex-col gap-1 text-sm">
                            <span className="font-medium text-slate-700">Category</span>
                            <select
                              value={document.category}
                              disabled={busy !== null}
                              onChange={(event) =>
                                void changeDocumentCategory(
                                  document.id,
                                  event.target.value as DocumentCategory
                                )
                              }
                              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 disabled:opacity-50"
                            >
                              <option value="personal">Personal â€” about me</option>
                              <option value="reference">Reference â€” other person/source</option>
                              <option value="unverified">Unverified â€” not classified</option>
                            </select>
                          </label>
                        </article>
                      ))}
                    </div>
                  )}
                </section>

                <section className="rounded-2xl border border-slate-200 bg-white p-6 md:p-8">
                  <p className="text-xs font-bold uppercase tracking-[0.15em] text-indigo-600">Semantic search</p><h2 className="mt-1 text-xl font-bold">Find information in your files</h2><p className="mt-2 text-sm text-slate-500">Get an AI-generated answer grounded in your files, alongside the source text it uses.</p>
                  <form onSubmit={searchDocuments} className="mt-5 space-y-4">
                    <label className="block text-sm font-semibold">Search query<textarea required minLength={1} maxLength={2000} value={query} onChange={(event) => setQuery(event.target.value)} rows={3} className={`${inputClass} mt-2 resize-y`} placeholder="What does my resume say about project experience?" /></label>
                    <div className="flex flex-wrap items-end gap-4"><label className="block text-sm font-semibold">Maximum results (1Ã¢â‚¬â€œ20)<input type="number" min={1} max={20} step={1} required value={limit} onChange={(event) => setLimit(event.target.value)} className={`${inputClass} mt-2 w-36`} /></label><button type="submit" disabled={busy !== null} className={primaryButton}>{busy === "search" ? "SearchingÃ¢â‚¬ÂÃ‚Â¦" : "Search documents"}</button></div>
                  </form>
                  {searchResult?.detail && <div className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{searchResult.detail}</div>}
                  {searchResult && (
                    <div className="mt-6 rounded-xl border border-indigo-200 bg-indigo-50/60 p-5">
                      <p className="text-xs font-bold uppercase tracking-[0.15em] text-indigo-700">
                        AI answer
                      </p>
                      {searchResult.answer ? (
                        <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-800">
                          {searchResult.answer}
                        </p>
                      ) : (
                        <p className="mt-3 text-sm leading-6 text-slate-600">
                          {searchResult.answer_status === "insufficient_evidence"
                            ? "The available document excerpts do not contain enough evidence to answer confidently."
                            : searchResult.answer_status === "no_evidence"
                              ? "No relevant document evidence was found for this question."
                              : searchResult.answer_status === "unavailable"
                                ? "The AI answer service is currently unavailable. You can still review the retrieved source chunks below."
                                : searchResult.answer_status === "invalid_response"
                                  ? "The AI service returned an unusable answer. Review the retrieved source chunks below."
                                  : "No AI answer was returned. Review the retrieved source chunks below."}
                        </p>
                      )}
                      {searchResult.answer_status && (
                        <p className="mt-3 text-xs text-slate-500">
                          Status: {searchResult.answer_status.replaceAll("_", " ")}
                        </p>
                      )}
                    </div>
                  )}                  {searchResult?.results && <div className="mt-6 space-y-4"><h3 className="font-bold">Retrieved chunks: {searchResult.results.length}</h3>{searchResult.results.length === 0 && <p className="text-sm text-slate-500">No matching chunks were returned. Check that a document was uploaded and that your query relates to its contents.</p>}{searchResult.results.map((item, index) => <article key={`${item.document_id}-${item.chunk_index}-${index}`} className="rounded-xl border border-slate-200 p-4"><div className="flex flex-wrap items-start justify-between gap-2"><h4 className="font-semibold">{item.filename}</h4><span className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-500">Chunk {item.chunk_index} Â· Distance {typeof item.distance === "number" && Number.isFinite(item.distance) ? item.distance.toFixed(4) : "n/a"}</span></div><p className="mt-2 text-xs font-medium text-slate-600">Source category: <span className={item.category === "personal" ? "text-emerald-700" : item.category === "reference" ? "text-indigo-700" : "text-amber-700"}>{item.category}</span></p><p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-600">{item.text}</p></article>)}</div>}
                </section>
              </>
            )}

            {(section === "Tasks" || section === "Approvals") && <ComingSoon section={section} onGoPlanner={() => setSection("AI Planner")} />}
            {section === "Settings" && (
              <section className="rounded-2xl border border-slate-200 bg-white p-6 md:p-8">
                <p className="text-xs font-bold uppercase tracking-[0.15em] text-indigo-600">Workspace settings</p>
                <h2 className="mt-1 text-2xl font-bold">Account and session</h2>
                <p className="mt-2 text-sm leading-6 text-slate-500">UniFlow keeps the authentication token in an HTTP-only cookie. Check your current session below; no token or secret is displayed here.</p>
                <button
                  type="button"
                  onClick={checkProfile}
                  disabled={busy !== null}
                  className="mt-5 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  {busy === "profile" ? "Checking..." : "Check current session"}
                </button>
                {profileResult && <ResponsePanel title="Profile response" data={profileResult} />}
                <GoogleIntegrationsPanel />
              </section>
            )}

            <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-5 text-xs text-slate-400"><span>UniFlow Ã‚Â· Student productivity workspace</span><span>AI plans are drafts Ã‚Â· You stay in control</span></footer>
          </div>
        </div>
      </div>
          <div className="mx-auto w-full max-w-7xl px-4 py-6"><EmbeddingExplorer /></div>
    </main>
  );
}

const inputClass = "block w-full rounded-xl border border-slate-200 bg-white px-3.5 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-50";
const primaryButton = "inline-flex items-center justify-center rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block text-sm font-semibold text-slate-700">{label}<span className="mt-2 block">{children}</span></label>;
}

function MetricCard({ eyebrow, title, value, detail, onClick }: { eyebrow: string; title: string; value: string; detail: string; onClick: () => void }) {
  return <button type="button" onClick={onClick} className="rounded-2xl border border-slate-200 bg-white p-5 text-left transition hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-md"><p className="text-[10px] font-bold tracking-[0.15em] text-slate-400">{eyebrow}</p><h3 className="mt-3 text-base font-bold">{title}</h3><p className="mt-2 text-sm font-semibold text-indigo-700">{value}</p><p className="mt-1 text-xs leading-5 text-slate-500">{detail}</p></button>;
}

function QuickStep({ number, title, detail }: { number: string; title: string; detail: string }) {
  return <li className="flex gap-3"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-slate-100 text-xs font-bold text-slate-600">{number}</span><div><p className="text-sm font-semibold">{title}</p><p className="mt-1 text-xs leading-5 text-slate-500">{detail}</p></div></li>;
}

function ResponsePanel({ title, data }: { title: string; data: ApiResult }) {
  return <section aria-live="polite" className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4"><h3 className="text-sm font-bold">{title}</h3><pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words text-xs leading-5 text-slate-600">{JSON.stringify(data, null, 2)}</pre></section>;
}

function ComingSoon({ section, onGoPlanner }: { section: "Tasks" | "Approvals"; onGoPlanner: () => void }) {
  const isTasks = section === "Tasks";
  return (
    <section className="rounded-3xl border border-slate-200 bg-white px-6 py-12 text-center md:px-12">
      <span className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-indigo-50 text-3xl text-indigo-700">
        {isTasks ? "T" : "A"}
      </span>
      <p className="mt-6 text-xs font-bold uppercase tracking-[0.16em] text-indigo-600">Planned feature</p>
      <h2 className="mt-2 text-2xl font-bold">
        {isTasks ? "A clearer next step, every time." : "Your approval, always required."}
      </h2>
      <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-slate-500">
        {isTasks
          ? "Task creation, status tracking, and reminders are not connected to the backend yet. We are keeping this area honest instead of showing mock tasks."
          : "Approval queues and controlled execution are not implemented yet. UniFlow currently creates draft plans only; it does not send emails or submit applications."}
      </p>
      <button
        type="button"
        onClick={onGoPlanner}
        className="mt-6 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700"
      >
        Try the AI Planner
      </button>
    </section>
  );
}

