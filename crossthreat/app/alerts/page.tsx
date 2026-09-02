"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../../components/api";
import { DashboardShell } from "../../components/dashboard-shell";
import { useReplaySession } from "../../components/replay-session";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>({});
  const { host, currentStep } = useReplaySession();

  useEffect(() => {
    async function load() {
      if (!host) return;
      try {
        const [list, summaryData] = await Promise.all([
          api<any>(`/api/alerts?host=${encodeURIComponent(host)}&step=${currentStep}`),
          api<any>(`/api/alerts/summary?host=${encodeURIComponent(host)}&step=${currentStep}`),
        ]);
        setAlerts(list.alerts || list);
        setSummary(summaryData.summary || summaryData);
      } catch (_error) {
        setAlerts([]);
      }
    }
    void load();
    const interval = window.setInterval(load, 2500);
    return () => window.clearInterval(interval);
  }, [host, currentStep]);

  return (
    <DashboardShell title="Alerts Center" subtitle="Live alert feed and severity distribution">
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.27em] text-slate-500">High</div>
            <div className="mt-2 font-mono text-3xl font-black text-red-400">{summary.high ?? "—"}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Alert severity distribution</div>
            <div className="space-y-3">
              {(["high", "medium", "low"] as const).map((severity) => {
                const count = Number(summary[severity] || 0);
                const total = Math.max(Number(summary.high || 0) + Number(summary.medium || 0) + Number(summary.low || 0), 1);
                return <div key={severity}><div className="flex justify-between text-sm uppercase text-slate-300"><span>{severity}</span><span className="font-mono">{count}</span></div><div className="mt-1 h-2 rounded bg-slate-800"><div className="h-full rounded bg-gradient-to-r from-red-500 to-cyan-500" style={{ width: `${count / total * 100}%` }} /></div></div>;
              })}
            </div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.27em] text-slate-500">Medium</div>
            <div className="mt-2 font-mono text-3xl font-black text-amber-400">{summary.medium ?? "—"}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.27em] text-slate-500">Low</div>
            <div className="mt-2 font-mono text-3xl font-black text-emerald-400">{summary.low ?? "—"}</div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
          <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Live alerts</div>
          <div className="overflow-hidden rounded-xl border border-slate-800">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-950/90 text-[10px] uppercase tracking-[0.22em] text-slate-400">
                <tr>
                  <th className="px-3 py-3">Time</th>
                  <th className="px-3 py-3">Alert Type</th>
                  <th className="px-3 py-3">Source</th>
                  <th className="px-3 py-3">Severity</th>
                  <th className="px-3 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {alerts.length ? alerts.map((alert: any) => (
                  <tr key={alert.id} className="border-t border-slate-800 bg-slate-950/40">
                    <td className="px-3 py-3 font-mono text-cyan-300">{alert.time}</td>
                    <td className="px-3 py-3 text-slate-200">
                      <Link href={`/alerts/${alert.id}`} className="hover:text-cyan-300">{alert.type}</Link>
                    </td>
                    <td className="px-3 py-3 font-mono text-slate-200">{alert.source}</td>
                    <td className="px-3 py-3">
                      <span className={`rounded-full px-2 py-1 text-[10px] uppercase tracking-[0.2em] ${
                        alert.severity === "High" ? "bg-red-500/10 text-red-300" : alert.severity === "Medium" ? "bg-amber-500/10 text-amber-300" : "bg-emerald-500/10 text-emerald-300"
                      }`}>
                        {alert.severity}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-slate-300">{alert.status}</td>
                  </tr>
                )) : <tr><td colSpan={5} className="px-3 py-3 text-slate-400">Loading live alert feed…</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
