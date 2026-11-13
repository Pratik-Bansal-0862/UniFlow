"use client";

import { useState } from "react";

type AcademicMilestone = {
  week: string | number;
  topic: string;
  estimated_hours: number | string;
  action_items?: string[];
};

type AcademicPlanResponse = {
  summary?: string;
  coursework_gaps?: string[];
  milestones?: AcademicMilestone[];
  detail?: string;
};

export function AcademicPanel() {
  const [goal, setGoal] = useState("");
  const [targetDate, setTargetDate] = useState("Next 4 weeks");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AcademicPlanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/agents/academic", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal, target_date: targetDate }),
      });
      const data = await response_data(res);
      if (!res.ok) throw new Error(data.detail || "Failed to generate plan");
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to generate plan");
    } finally {
      setLoading(false);
    }
  }

  async function response_data(res: Response): Promise<AcademicPlanResponse> {
    try {
      return (await res.json()) as AcademicPlanResponse;
    } catch {
      return {};
    }
  }

  return (
    <div className="space-y-6">
      <div className="p-6 bg-white rounded-xl border border-slate-200 shadow-sm">
        <h2 className="text-xl font-semibold text-slate-800">Academic Agent</h2>
        <p className="text-sm text-slate-500 mt-1">
          Turn your coursework, syllabus notes, and exam targets into a weekly actionable study plan.
        </p>

        <form onSubmit={handleGenerate} className="mt-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700">Study Goal or Subject</label>
            <input
              type="text"
              required
              placeholder="e.g. Master Operating Systems & Concurrency before midterms"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">Timeline</label>
            <input
              type="text"
              value={targetDate}
              onChange={(e) => setTargetDate(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            {loading ? "Generating Roadmap..." : "Generate Academic Roadmap"}
          </button>
        </form>

        {error && (
          <div className="mt-4 p-3 bg-red-50 text-red-700 text-sm rounded-lg border border-red-200">
            {error}
          </div>
        )}
      </div>

      {result && (
        <div className="space-y-4">
          <div className="p-5 bg-indigo-50 rounded-xl border border-indigo-100">
            <h3 className="font-semibold text-indigo-900">Strategy Summary</h3>
            <p className="text-sm text-indigo-800 mt-1">{result.summary}</p>
          </div>

          {(result.coursework_gaps?.length ?? 0) > 0 && (
            <div className="p-5 bg-amber-50 rounded-xl border border-amber-100">
              <h3 className="font-semibold text-amber-900">Identified Gaps</h3>
              <ul className="list-disc list-inside text-sm text-amber-800 mt-2 space-y-1">
                {(result.coursework_gaps ?? []).map((gap: string, idx: number) => (
                  <li key={idx}>{gap}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="space-y-3">
            <h3 className="text-base font-semibold text-slate-800">Weekly Milestones</h3>
            {result.milestones?.map((m: AcademicMilestone, idx: number) => (
              <div key={idx} className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm">
                <div className="flex justify-between items-center">
                  <span className="font-medium text-slate-900">{m.week}: {m.topic}</span>
                  <span className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded">
                    ~{m.estimated_hours} hrs
                  </span>
                </div>
                <ul className="list-disc list-inside text-sm text-slate-600 mt-2 space-y-1">
                  {m.action_items?.map((item: string, i: number) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}