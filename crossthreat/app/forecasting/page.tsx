"use client";

import { useEffect, useState } from "react";
import { api } from "../../components/api";
import { DashboardShell } from "../../components/dashboard-shell";

export default function ForecastingPage() {
  const [host, setHost] = useState("host-01");
  const [upcoming, setUpcoming] = useState<any[]>([]);
  const [confidenceHistory, setConfidenceHistory] = useState<any[]>([]);
  const [evidence, setEvidence] = useState<any[]>([]);

  useEffect(() => {
    async function load() {
      try {
        const hosts = await api<any>("/api/replay/list");
        const selectedHost = Array.isArray(hosts) ? hosts[0] : hosts?.hosts?.[0] || host;
        setHost(selectedHost);
        const [forecast, confidence, evidenceData] = await Promise.all([
          api<any[]>(`/api/forecast/${encodeURIComponent(selectedHost)}/upcoming`),
          api<any[]>(`/api/forecast/${encodeURIComponent(selectedHost)}/confidence-history`),
          api<any[]>(`/api/evidence/${encodeURIComponent(selectedHost)}`),
        ]);
        setUpcoming(forecast);
        setConfidenceHistory(confidence);
        setEvidence(evidenceData);
      } catch (_error) {
        setUpcoming([]);
      }
    }
    void load();
    const interval = window.setInterval(load, 2500);
    return () => window.clearInterval(interval);
  }, [host]);

  return (
    <DashboardShell title="Attack Forecasting" subtitle="Upcoming transitions and explainable model confidence">
      <div className="space-y-6">
        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Upcoming attack predictions</div>
            <div className="overflow-hidden rounded-xl border border-slate-800">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-950/90 text-[10px] uppercase tracking-[0.22em] text-slate-400">
                  <tr>
                    <th className="px-3 py-3">Stage</th>
                    <th className="px-3 py-3">ETA</th>
                    <th className="px-3 py-3">Confidence</th>
                    <th className="px-3 py-3">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {upcoming.length ? upcoming.map((row: any) => (
                    <tr key={`${host}-${row.stage}`} className="border-t border-slate-800 bg-slate-950/40">
                      <td className="px-3 py-3 text-slate-200">{row.stage}</td>
                      <td className="px-3 py-3 font-mono text-cyan-300">{row.eta}</td>
                      <td className="px-3 py-3 font-mono text-amber-300">{row.confidence}%</td>
                      <td className="px-3 py-3 font-mono text-red-300">{row.risk}</td>
                    </tr>
                  )) : <tr><td colSpan={4} className="px-3 py-3 text-slate-500">No data available yet</td></tr>}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Prediction confidence over time</div>
            <div className="h-56 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
              {confidenceHistory.length ? (
                <div className="flex h-full items-end gap-2">
                  {confidenceHistory.map((point: any) => (
                    <div key={point.step} className="flex flex-1 flex-col items-center gap-2">
                      <div className="w-full rounded-t bg-cyan-400/80" style={{ height: `${Math.min(Number(point.confidence), 100)}%` }} />
                      <span className="font-mono text-[9px] text-slate-500">{point.step}</span>
                    </div>
                  ))}
                </div>
              ) : <div className="grid h-full place-items-center text-sm text-slate-500">No data available yet</div>}
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
          <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Prediction explanation (XAI)</div>
          <div className="space-y-3 text-sm text-slate-300">
            {evidence.length ? evidence.map((item: any, index: number) => (
              <div key={`${host}-evidence-${index}`} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                <div className="font-semibold text-slate-100">{item.label || "Evidence"}</div>
                <p className="mt-2 text-slate-300">{item.explanation ?? item.description ?? "No explanation available yet"}</p>
              </div>
            )) : <div className="text-slate-500">No data available yet</div>}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
