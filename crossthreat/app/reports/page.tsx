"use client";

import { useEffect, useState } from "react";
import { api } from "../../components/api";
import { DashboardShell } from "../../components/dashboard-shell";
import { useReplaySession } from "../../components/replay-session";

export default function ReportsPage() {
  const [summary, setSummary] = useState<any>({});
  const [attackTypes, setAttackTypes] = useState<any[]>([]);
  const [attacksOverTime, setAttacksOverTime] = useState<any[]>([]);
  const [model, setModel] = useState<any>({});
  const { host, currentStep } = useReplaySession();

  useEffect(() => {
    async function load() {
      if (!host) return;
      try {
        const [summaryData, typesData, historyData, modelData] = await Promise.all([
          api<any>(`/api/reports/summary?host=${encodeURIComponent(host)}&step=${currentStep}`),
          api<any>(`/api/reports/attack-types?host=${encodeURIComponent(host)}&step=${currentStep}`),
          api<any>(`/api/reports/attacks-over-time?host=${encodeURIComponent(host)}&step=${currentStep}`),
          api<any>("/api/models/performance"),
        ]);
        setSummary(summaryData.summary || summaryData);
        setAttackTypes(typesData.attack_types || typesData);
        setAttacksOverTime(historyData.attacks_over_time || historyData);
        setModel(modelData || {});
      } catch (_error) {
        setSummary({});
      }
    }
    void load();
    const interval = window.setInterval(load, 2500);
    return () => window.clearInterval(interval);
  }, [host, currentStep]);

  return (
    <DashboardShell title="Reports & Analytics" subtitle="Executive and operational reporting across forecast history">
      <div className="space-y-6">
        <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 px-4 py-3 text-xs uppercase tracking-[0.2em] text-slate-400">
          Report scope: <span className="font-mono text-cyan-300">{host || "Loading host"}</span> · Replay step {currentStep + 1}
        </div>
        <div className="grid gap-4 md:grid-cols-4">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">Total attacks</div>
            <div className="mt-2 font-mono text-3xl font-black text-cyan-300">{summary.total_attacks ?? "—"}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">High severity</div>
            <div className="mt-2 font-mono text-3xl font-black text-red-300">{summary.high_severity ?? "—"}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">Blocked attacks</div>
            <div className="mt-2 font-mono text-3xl font-black text-emerald-300">{summary.blocked_attacks ?? "—"}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">Avg response</div>
            <div className="mt-2 font-mono text-3xl font-black text-amber-300">{summary.avg_response_time ?? "—"}</div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
          <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Active model performance</div>
          <div className="grid gap-3 sm:grid-cols-4">
            {["accuracy", "precision", "recall", "f1"].map((metric) => <div key={metric}><div className="flex justify-between text-xs uppercase text-slate-400"><span>{metric}</span><span className="font-mono text-cyan-300">{typeof model[metric] === "number" ? `${model[metric].toFixed(1)}%` : "N/A"}</span></div><div className="mt-1 h-2 rounded bg-slate-800"><div className="h-full rounded bg-cyan-400" style={{ width: `${Math.min(Number(model[metric] || 0), 100)}%` }} /></div></div>)}
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Attacks over time</div>
            <div className="h-60 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
              {attacksOverTime.length ? (
                <div className="flex h-full items-end gap-2">
                  {attacksOverTime.map((point: any) => (
                    <div key={point.period} className="flex flex-1 flex-col items-center gap-2">
                      <div className="w-full rounded-t bg-cyan-400/80" style={{ height: `${Math.min(Number(point.count), 100)}%` }} />
                      <span className="font-mono text-[9px] text-slate-500">{point.period}</span>
                    </div>

                  ))}
                </div>
              ) : <div className="grid h-full place-items-center text-sm text-slate-500">No data available yet</div>}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Top attack types</div>
            <div className="space-y-3">
              {attackTypes.length ? attackTypes.map((item: any) => (
                <div key={item.type || item.name}>
                  <div className="mb-1 flex items-center justify-between text-sm text-slate-300">
                    <span>{item.type || item.name}</span>
                    <span className="font-mono text-cyan-300">{item.value ?? item.percent ?? "—"}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                    <div className="h-full rounded-full bg-gradient-to-r from-red-500 to-cyan-500" style={{ width: `${Math.min(item.value ?? item.percent ?? 0, 100)}%` }} />
                  </div>
                </div>
              )) : <div className="text-slate-400">No data available yet</div>}
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
          <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Reports list</div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {[
              "Executive Summary",
              "Threat Report",
              "Attack Timeline Report",
              "Traffic Analysis",
              "Model Performance Report",
              "Compliance Report",
            ].map((name) => (
              <div key={name} className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                <span className="text-sm text-slate-200">{name}</span>
                <button type="button" className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-[10px] uppercase tracking-[0.2em] text-cyan-200">
                  Generate
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
