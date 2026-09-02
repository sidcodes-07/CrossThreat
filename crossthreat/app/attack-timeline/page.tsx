"use client";

import { useEffect, useState } from "react";
import { api } from "../../components/api";
import { DashboardShell } from "../../components/dashboard-shell";

export default function AttackTimelinePage() {
  const [host, setHost] = useState("host-01");
  const [timeline, setTimeline] = useState<any[]>([]);
  const [details, setDetails] = useState<any[]>([]);
  const [indicators, setIndicators] = useState<any[]>([]);
  const [riskHistory, setRiskHistory] = useState<any[]>([]);
  const [transitionProbs, setTransitionProbs] = useState<any[]>([]);

  useEffect(() => {
    async function load() {
      try {
        const hosts = await api<{ hosts: string[] }>("/api/replay/list");
        const selectedHost = hosts?.hosts?.[0] || host;
        setHost(selectedHost);
        const [stageList, detailList, indicatorList, riskList, probs] = await Promise.all([
          api<any[]>(`/api/timeline/${encodeURIComponent(selectedHost)}`),
          api<any[]>(`/api/timeline/${encodeURIComponent(selectedHost)}/details`),
          api<any[]>(`/api/timeline/${encodeURIComponent(selectedHost)}/indicators`),
          api<any[]>(`/api/timeline/${encodeURIComponent(selectedHost)}/risk-history`),
          api<any[]>(`/api/forecast/${encodeURIComponent(selectedHost)}/transition-probs`),
        ]);
        setTimeline(stageList);
        setDetails(detailList);
        setIndicators(indicatorList);
        setRiskHistory(riskList);
        setTransitionProbs(probs);
      } catch (_error) {
        setTimeline([]);
      }
    }
    void load();
  }, [host]);

  return (
    <DashboardShell title="Attack Timeline" subtitle="Stage-by-stage progression and risk transitions">
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.27em] text-slate-500">Selected host</div>
            <div className="mt-2 font-mono text-xl text-cyan-300">{host}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.27em] text-slate-500">Current stage</div>
            <div className="mt-2 text-xl font-bold text-amber-300">{details[0]?.stage || "Reconnaissance"}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.27em] text-slate-500">Risk score</div>
            <div className="mt-2 font-mono text-3xl font-black text-red-400">{Math.round(riskHistory[riskHistory.length - 1]?.risk_score ?? 78)}%</div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
          <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Timeline</div>
          <div className="space-y-4">
            {timeline.length ? timeline.map((item: any) => (
              <div key={`${host}-${item.stage}`} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="text-sm uppercase tracking-[0.22em] text-slate-400">{item.stage}</div>
                    <div className="mt-1 text-lg font-bold text-slate-100">{item.label}</div>
                  </div>
                  <div className="flex gap-3 text-xs text-slate-300">
                    <span>Started: <span className="font-mono text-cyan-300">{item.started}</span></span>
                    <span>Duration: <span className="font-mono text-cyan-300">{item.duration}</span></span>
                  </div>
                </div>
              </div>
            )) : <div className="text-slate-400">Loading stage progression…</div>}
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Timeline details</div>
            <div className="space-y-4">
              {details.length ? details.map((item: any) => (
                <div key={`${host}-detail-${item.stage}`} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <div className="flex items-center justify-between">
                    <div className="text-base font-bold text-slate-100">{item.stage}</div>
                    <span className={`rounded-full px-2 py-1 text-[10px] uppercase tracking-[0.2em] ${
                      item.risk >= 75 ? "bg-red-500/10 text-red-300" : item.risk >= 45 ? "bg-amber-500/10 text-amber-300" : "bg-emerald-500/10 text-emerald-300"
                    }`}>
                      {item.severity || "Medium"}
                    </span>
                  </div>
                  <div className="mt-3 grid gap-2 text-sm text-slate-300 sm:grid-cols-2">
                    <div>Start: <span className="font-mono text-cyan-300">{item.start_time}</span></div>
                    <div>Duration: <span className="font-mono text-cyan-300">{item.duration}</span></div>
                    <div>Risk score: <span className="font-mono text-cyan-300">{item.risk}</span></div>
                    <div>Confidence: <span className="font-mono text-cyan-300">{item.confidence}%</span></div>
                  </div>
                  <p className="mt-3 text-sm text-slate-400">{item.description}</p>
                </div>
              )) : <div className="text-slate-400">Loading details…</div>}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Top indicators</div>
            <div className="space-y-3">
              {indicators.length ? indicators.map((indicator: any, index: number) => (
                <div key={`${host}-indicator-${index}`} className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-100">{indicator.name}</div>
                    <div className="text-xs text-slate-400">{indicator.source}</div>
                  </div>
                  <span className={`rounded-full px-2 py-1 text-[10px] uppercase tracking-[0.2em] ${
                    indicator.severity === "High" ? "bg-red-500/10 text-red-300" : indicator.severity === "Medium" ? "bg-amber-500/10 text-amber-300" : "bg-emerald-500/10 text-emerald-300"
                  }`}>
                    {indicator.severity}
                  </span>
                </div>
              )) : <div className="text-slate-400">Loading indicators…</div>}
            </div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Transition probabilities</div>
            <div className="space-y-3">
              {transitionProbs.length ? transitionProbs.map((item: any) => (
                <div key={`${host}-prob-${item.label}`}>
                  <div className="mb-1 flex items-center justify-between text-sm text-slate-300">
                    <span>{item.label}</span>
                    <span className="font-mono text-cyan-300">{item.value}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                    <div className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500" style={{ width: `${item.value}%` }} />
                  </div>
                </div>
              )) : <div className="text-slate-400">Loading probabilities…</div>}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Risk score over time</div>
            <div className="h-52 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
              <svg viewBox="0 0 320 180" className="h-full w-full">
                <path d={riskHistory.map((point: any, idx: number) => `${idx === 0 ? "M" : "L"} ${idx * 32} ${180 - point.risk_score * 1.6}`).join(" ")} stroke="#00D9FF" strokeWidth="3" fill="none" />
              </svg>
            </div>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
