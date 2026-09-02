"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "../../../components/api";
import { DashboardShell } from "../../../components/dashboard-shell";

export default function AlertDetailPage() {
  const params = useParams<{ alertId: string }>();
  const [alert, setAlert] = useState<any>(null);

  useEffect(() => {
    if (!params.alertId) return;
    async function load() {
      try {
        const detail = await api<any>(`/api/alerts/${encodeURIComponent(params.alertId)}/details`);
        setAlert(detail);
      } catch (_error) {
        setAlert(null);
      }
    }
    void load();
  }, [params.alertId]);

  if (!alert) {
    return (
      <DashboardShell title="Alert Details" subtitle="Load in progress">
        <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-8 text-slate-400">Loading alert details…</div>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell title={`Alert ${alert.id || params.alertId}`} subtitle={alert.type || "Threat event"}>
      <div className="space-y-6">
        <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.28em] text-cyan-400">Alert header</div>
              <div className="mt-2 text-2xl font-black text-slate-100">{alert.type}</div>
            </div>
            <span className={`rounded-full px-3 py-1 text-[10px] uppercase tracking-[0.2em] ${
              alert.severity === "High" ? "bg-red-500/10 text-red-300" : alert.severity === "Medium" ? "bg-amber-500/10 text-amber-300" : "bg-emerald-500/10 text-emerald-300"
            }`}>
              {alert.severity}
            </span>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Description</div>
            <p className="text-sm leading-7 text-slate-300">{alert.description}</p>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Recommended actions</div>
            <ul className="space-y-3 text-sm text-slate-300">
              {alert.recommendations?.length ? alert.recommendations.map((item: string, index: number) => (
                <li key={`${alert.id}-action-${index}`} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">{item}</li>
              )) : <li className="text-slate-500">No recommendations available yet</li>}
            </ul>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Details</div>
            <div className="grid gap-3 text-sm text-slate-300 sm:grid-cols-2">
              <div>Source / dest: <span className="font-mono text-cyan-300">{alert.source ?? "—"} → {alert.destination ?? "—"}</span></div>
              <div>Protocol: <span className="font-mono text-cyan-300">{alert.protocol ?? "—"}</span></div>
              <div>Ports: <span className="font-mono text-cyan-300">{alert.ports ?? "—"}</span></div>
              <div>Duration: <span className="font-mono text-cyan-300">{alert.duration ?? "—"}</span></div>
              <div>Packets: <span className="font-mono text-cyan-300">{alert.packets ?? "—"}</span></div>
              <div>Bytes: <span className="font-mono text-cyan-300">{alert.bytes ?? "—"}</span></div>
              <div>Risk score: <span className="font-mono text-cyan-300">{alert.risk_score ?? "—"}</span></div>
              <div>Status: <span className="font-mono text-cyan-300">{alert.status ?? "—"}</span></div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Related events</div>
            <div className="space-y-3">
              {alert.related_events?.length ? alert.related_events.map((event: any, index: number) => (
                <div key={`${alert.id}-event-${index}`} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <div className="font-mono text-xs text-cyan-300">{event.time}</div>
                  <div className="mt-1 text-sm text-slate-300">{event.text}</div>
                </div>
              )) : <div className="text-slate-500">No related events available yet</div>}
            </div>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
