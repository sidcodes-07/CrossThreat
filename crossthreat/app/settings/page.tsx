"use client";

import { DashboardShell } from "../../components/dashboard-shell";

export default function SettingsPage() {
  return (
    <DashboardShell title="Settings" subtitle="Operational configuration and analyst preferences">
      <div className="grid gap-6 xl:grid-cols-2">
        <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
          <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Alert thresholds</div>
          <div className="space-y-4 text-sm text-slate-300">
            <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-3"><span>Critical threshold</span><span className="font-mono text-red-300">85</span></div>
            <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-3"><span>Warning threshold</span><span className="font-mono text-amber-300">60</span></div>
            <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-3"><span>Info cutoff</span><span className="font-mono text-cyan-300">35</span></div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
          <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Replay configuration</div>
          <div className="space-y-4 text-sm text-slate-300">
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">Dataset source: <span className="font-mono text-cyan-300">CIC-IDS2018</span></div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">Replay rate: <span className="font-mono text-cyan-300">1.0x</span></div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">Session: <span className="font-mono text-cyan-300">host-01</span></div>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
