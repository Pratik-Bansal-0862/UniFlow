"use client";

import { useCallback, useEffect, useState } from "react";

type GoogleStatus = {
  connected?: boolean;
  provider?: string;
  scopes?: string[];
  has_refresh_token?: boolean;
  detail?: string;
};

export default function GoogleIntegrationsPanel() {
  const [status, setStatus] = useState<GoogleStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refreshStatus = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/integrations/google/status", {
        cache: "no-store",
      });
      const data: GoogleStatus = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not check Google connection.");
      }

      setStatus(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not check Google connection."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshStatus();

    const params = new URLSearchParams(window.location.search);
    if (params.get("google") === "connected") {
      setMessage("Google authorization completed. Refreshing connection status...");
    }
  }, [refreshStatus]);

  async function connectGoogle() {
    setConnecting(true);
    setError(null);
    setMessage(null);

    try {
      const response = await fetch("/api/integrations/google/connect", {
        cache: "no-store",
      });
      const data: { authorization_url?: string; detail?: string } =
        await response.json();

      if (!response.ok || !data.authorization_url) {
        throw new Error(data.detail || "Could not start Google authorization.");
      }

      window.location.assign(data.authorization_url);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not connect Google."
      );
      setConnecting(false);
    }
  }

  async function disconnectGoogle() {
    const confirmed = window.confirm(
      "Disconnect Google from UniFlow? Gmail and Calendar actions will stop working until you reconnect."
    );

    if (!confirmed) return;

    setDisconnecting(true);
    setError(null);
    setMessage(null);

    try {
      const response = await fetch("/api/integrations/google/disconnect", {
        method: "DELETE",
      });
      const data: { detail?: string; disconnected?: boolean } =
        await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not disconnect Google.");
      }

      setMessage("Google has been disconnected from UniFlow.");
      await refreshStatus();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not disconnect Google."
      );
    } finally {
      setDisconnecting(false);
    }
  }

  const connected = status?.connected === true;
  const busy = loading || connecting || disconnecting;

  return (
    <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 md:p-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.15em] text-indigo-600">
            App integrations
          </p>
          <h3 className="mt-1 text-xl font-bold text-slate-900">
            Google Workspace
          </h3>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Connect Gmail and Google Calendar so UniFlow can retrieve messages,
            prepare email drafts, read your schedule, and create reminders.
            Actions that send emails or change your calendar will require
            approval through the Planner workflow.
          </p>
        </div>

        <span
          className={`inline-flex w-fit items-center rounded-full px-3 py-1 text-xs font-semibold ${
            loading
              ? "bg-slate-100 text-slate-600"
              : connected
                ? "bg-emerald-50 text-emerald-700"
                : "bg-amber-50 text-amber-700"
          }`}
        >
          {loading ? "Checking..." : connected ? "Connected" : "Not connected"}
        </span>
      </div>

      {error && (
        <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {message && (
        <p className="mt-4 rounded-xl bg-indigo-50 p-3 text-sm text-indigo-700">
          {message}
        </p>
      )}

      {connected && (
        <div className="mt-5 rounded-xl border border-slate-200 p-4">
          <p className="text-sm font-semibold text-slate-800">
            Google account linked successfully
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Refresh-token availability:{" "}
            {status?.has_refresh_token ? "Available" : "Not available"}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Granted permissions: {status?.scopes?.length ?? 0}
          </p>
        </div>
      )}

      <div className="mt-5 flex flex-wrap gap-3">
        {!connected && (
          <button
            type="button"
            onClick={connectGoogle}
            disabled={busy}
            className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {connecting ? "Opening Google..." : "Connect Google"}
          </button>
        )}

        {connected && (
          <button
            type="button"
            onClick={disconnectGoogle}
            disabled={busy}
            className="rounded-xl border border-red-200 px-5 py-3 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {disconnecting ? "Disconnecting..." : "Disconnect Google"}
          </button>
        )}

        <button
          type="button"
          onClick={() => void refreshStatus()}
          disabled={busy}
          className="rounded-xl border border-slate-200 px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Refresh status
        </button>
      </div>

      <p className="mt-4 text-xs leading-5 text-slate-400">
        UniFlow stores Google credentials encrypted on the backend. Do not
        share OAuth tokens or client secrets.
      </p>
    </section>
  );
}
