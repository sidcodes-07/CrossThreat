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
        const selectedHost = hosts?.hosts?.[0] || host;
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
                  )) : <tr><td colSpan={4} className="px-3 py-3 text-slate-400">Loading forecast table…</td></tr>}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Prediction confidence over time</div>
            <div className="h-56 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
              <svg viewBox="0 0 260 180" className="h-full w-full">
                <path d="M 0 120 L 60 90 L 120 100 L 180 70 L 240 55 L 260 30" stroke="#00D9FF" strokeWidth="3" fill="none" />
                <path d="M 0 135 L 60 125 L 120 115 L 180 85 L 240 72 L 260 60" stroke="#A855F7" strokeWidth="3" fill="none" />
              </svg>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
          <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Prediction explanation (XAI)</div>
          <div className="space-y-3 text-sm text-slate-300">
            {evidence.length ? evidence.map((item: any, index: number) => (
              <div key={`${host}-evidence-${index}`} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                <div className="font-semibold text-slate-100">{item.label || "Evidence"}</div>
                <p className="mt-2 text-slate-300">{item.explanation || item.description || "Model confidence is being reconstructed from stage-attribution metrics and the live evidence stream."}</p>
              </div>
            )) : <div className="text-slate-400">Loading evidence explanation…</div>}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
