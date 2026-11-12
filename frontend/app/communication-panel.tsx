"use client";

import { useState } from "react";

export function CommunicationPanel() {
  const [recipientType, setRecipientType] = useState("recruiter");
  const [recipientName, setRecipientName] = useState("");
  const [company, setCompany] = useState("");
  const [intent, setIntent] = useState("");
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function handleDraft(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setCopied(false);

    try {
      const res = await fetch("/api/agents/communication", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          recipient_type: recipientType,
          recipient_name: recipientName || "Hiring Manager",
          company_or_institution: company,
          specific_intent: intent,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to draft email");
      setDraft(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleCopy() {
    if (draft?.body) {
      navigator.clipboard.writeText(draft.body);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <div className="space-y-6">
      <div className="p-6 bg-white rounded-xl border border-slate-200 shadow-sm">
        <h2 className="text-xl font-semibold text-slate-800">Communication Agent</h2>
        <p className="text-sm text-slate-500 mt-1">
          Draft tailored outreach, cold inquiries, and networking messages grounded in your verified background.
        </p>

        <form onSubmit={handleDraft} className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700">Recipient Type</label>
              <select
                value={recipientType}
                onChange={(e) => setRecipientType(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
              >
                <option value="recruiter">Recruiter / Hiring Manager</option>
                <option value="professor">Professor / Academic Advisor</option>
                <option value="alumni">Alumni / Professional Network</option>
                <option value="follow_up">Post-Interview Follow-Up</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700">Recipient Name</label>
              <input
                type="text"
                placeholder="e.g. Dr. Vance or Sarah Jenkins"
                value={recipientName}
                onChange={(e) => setRecipientName(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">Company or Institution</label>
            <input
              type="text"
              placeholder="e.g. Google or Dept. of Computer Science"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">Specific Intent / Topic</label>
            <textarea
              required
              rows={2}
              placeholder="e.g. Seeking Summer 2027 Software Engineering internship or research assistant opportunity"
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            {loading ? "Generating Draft..." : "Generate Professional Draft"}
          </button>
        </form>

        {error && (
          <div className="mt-4 p-3 bg-red-50 text-red-700 text-sm rounded-lg border border-red-200">
            {error}
          </div>
        )}
      </div>

      {draft && (
        <div className="p-6 bg-white rounded-xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex justify-between items-center border-b pb-3">
            <div>
              <span className="text-xs uppercase text-slate-400 font-semibold tracking-wider">Subject</span>
              <p className="font-medium text-slate-900 text-sm">{draft.subject}</p>
            </div>
            <button
              onClick={handleCopy}
              className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium px-3 py-1.5 rounded transition-colors"
            >
              {copied ? "Copied!" : "Copy Email"}
            </button>
          </div>

          <div>
            <span className="text-xs uppercase text-slate-400 font-semibold tracking-wider">Draft Body</span>
            <pre className="mt-2 text-sm text-slate-800 whitespace-pre-wrap font-sans bg-slate-50 p-4 rounded-lg border border-slate-100 leading-relaxed">
              {draft.body}
            </pre>
          </div>

          {draft.suggested_next_steps?.length > 0 && (
            <div className="pt-2">
              <span className="text-xs uppercase text-slate-400 font-semibold tracking-wider">Next Steps</span>
              <ul className="list-disc list-inside text-xs text-slate-600 mt-1 space-y-0.5">
                {draft.suggested_next_steps.map((step: string, i: number) => (
                  <li key={i}>{step}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}