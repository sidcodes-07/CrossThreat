"use client";

import { useEffect, useState } from "react";
import { api } from "../../components/api";
import { DashboardShell } from "../../components/dashboard-shell";

export default function ReportsPage() {
  const [summary, setSummary] = useState<any>({});
  const [attackTypes, setAttackTypes] = useState<any[]>([]);

  useEffect(() => {
    async function load() {
      try {
        const [summaryData, typesData] = await Promise.all([
          api<any>("/api/reports/summary"),
          api<any>("/api/reports/attack-types"),
        ]);
        setSummary(summaryData.summary || summaryData);
        setAttackTypes(typesData.attack_types || typesData);
      } catch (_error) {
        setSummary({});
      }
    }
    void load();
  }, []);

  return (
    <DashboardShell title="Reports & Analytics" subtitle="Executive and operational reporting across forecast history">
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-4">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">Total attacks</div>
            <div className="mt-2 font-mono text-3xl font-black text-cyan-300">{summary.total_attacks ?? 128}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">High severity</div>
            <div className="mt-2 font-mono text-3xl font-black text-red-300">{summary.high_severity ?? 34}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">Blocked attacks</div>
            <div className="mt-2 font-mono text-3xl font-black text-emerald-300">{summary.blocked_attacks ?? 94}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">Avg response</div>
            <div className="mt-2 font-mono text-3xl font-black text-amber-300">{summary.avg_response_time ?? "08m"}</div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Attacks over time</div>
            <div className="h-60 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
              <svg viewBox="0 0 260 180" className="h-full w-full">
                <path d="M 0 140 L 50 120 L 100 125 L 150 90 L 200 78 L 260 40" stroke="#00D9FF" strokeWidth="3" fill="none" />
              </svg>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Top attack types</div>
            <div className="space-y-3">
              {attackTypes.length ? attackTypes.map((item: any) => (
                <div key={item.type || item.name}>
                  <div className="mb-1 flex items-center justify-between text-sm text-slate-300">
                    <span>{item.type || item.name}</span>
                    <span className="font-mono text-cyan-300">{item.value ?? item.percent ?? 0}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                    <div className="h-full rounded-full bg-gradient-to-r from-red-500 to-cyan-500" style={{ width: `${Math.min(item.value ?? item.percent ?? 0, 100)}%` }} />
                  </div>
                </div>
              )) : <div className="text-slate-400">Loading attack distribution…</div>}
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
