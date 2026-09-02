"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "../../components/api";
import { DashboardShell } from "../../components/dashboard-shell";
import { useReplaySession } from "../../components/replay-session";

export default function DashboardOverviewPage() {
  const { host, currentStep, setTotalSteps } = useReplaySession();
  const [state, setState] = useState<any>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [evidence, setEvidence] = useState<any[]>([]);
  const [talkers, setTalkers] = useState<any[]>([]);
  const [liveSummary, setLiveSummary] = useState<any>(null);

  useEffect(() => {
    async function load() {
      try {
        if (!host) return;
        const selectedHost = host;

        const [current, timelineData, evidenceData, talkerData, networkData] = await Promise.all([
          api<any>(`/api/state/current?host=${encodeURIComponent(selectedHost)}&step=${currentStep}`),
          api<any[]>(`/api/timeline/${encodeURIComponent(selectedHost)}`),
          api<any[]>(`/api/evidence/${encodeURIComponent(selectedHost)}`),
          api<any[]>("/api/network/top-talkers"),
          api<any>(`/api/network/topology?host=${encodeURIComponent(selectedHost)}&step=${currentStep}`),
        ]);

        setState(current);
        setTimeline(timelineData || []);
        setTotalSteps(timelineData?.length || 0);
        setEvidence(evidenceData || []);
        setTalkers(talkerData || []);
        setLiveSummary(networkData?.summary || null);
      } catch (_error) {
        setState(null);
      }
    }
    void load();
    const interval = window.setInterval(load, 2500);
    return () => window.clearInterval(interval);
  }, [host, currentStep, setTotalSteps]);

  const ringStyle = useMemo(() => {
    const pct = Math.max(0, Math.min(100, Number(state?.probability ?? 0) * 100));
    return { background: `conic-gradient(#00D9FF 0 ${pct}%, rgba(148,163,184,0.15) ${pct}% 100%)` };
  }, [state]);

  return (
    <DashboardShell title="Dashboard Overview" subtitle="Current threat posture and near-term attack progression" session={host}>
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-4">
          <div className="rounded-2xl border border-slate-800 bg-[#131826]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.26em] text-slate-500">Current network state</div>
            <div className="mt-3 text-xl font-bold text-slate-100">{state?.current_stage || "No data available yet"}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#131826]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.26em] text-slate-500">Threat level</div>
            <div className="mt-3 font-mono text-3xl font-black text-red-400">{state?.threat_level || "—"}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#131826]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.26em] text-slate-500">Risk score</div>
            <div className="mt-3 font-mono text-3xl font-black text-cyan-300">{state ? `${Math.round(state.risk_score)}%` : "—"}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#131826]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.26em] text-slate-500">Host</div>
            <div className="mt-3 font-mono text-xl text-violet-300">{host}</div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Next-likely-stage</div>
            <div className="flex flex-col gap-5 md:flex-row md:items-center">
              <div className="relative grid h-26 w-26 place-items-center rounded-full p-3" style={ringStyle}>
                <div className="grid h-full w-full place-items-center rounded-full bg-[#0d1117] text-center">
                  <div className="font-mono text-3xl font-black text-cyan-300">{state ? `${Math.round(state.probability * 100)}%` : "—"}</div>
                </div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Forecast</div>
                <div className="mt-2 text-2xl font-black text-slate-100">{state?.next_stage_forecast || "No data available yet"}</div>
                <div className="mt-2 text-sm text-slate-400">Probability of the next stage transition over the active replay window.</div>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Alternative outcomes</div>
            <div className="space-y-3">
              {(state?.alternative_outcomes || []).map((outcome: any, idx: number) => (
                <div key={`${outcome.label}-${idx}`} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-100">{outcome.label}</span>
                    <span className="font-mono text-cyan-300">{outcome.probability ?? "—"}%</span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800">
                    <div className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500" style={{ width: `${Math.min(outcome.probability ?? 0, 100)}%` }} />
                  </div>
                </div>
              ))}
              {!state?.alternative_outcomes?.length ? <div className="text-sm text-slate-500">No data available yet</div> : null}
            </div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Attack progression timeline</div>
            <div className="grid gap-3 md:grid-cols-6">
              {timeline.map((step: any, idx: number) => (
                <div key={`${step.stage}-${idx}`} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">{step.stage}</div>
                  <div className="mt-3 text-sm font-semibold text-slate-100">{step.label}</div>
                  <div className="mt-3 font-mono text-[11px] text-cyan-300">{step.started}</div>
                  <div className="mt-1 text-[11px] text-slate-400">{step.duration}</div>
                </div>

              ))}
              {!timeline.length ? <div className="text-sm text-slate-500">No data available yet</div> : null}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Live network summary</div>
            <div className="space-y-3 text-sm text-slate-300">
              <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-3"><span>Total flows</span><span className="font-mono text-cyan-300">{liveSummary?.total_flows ?? "—"}</span></div>
              <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-3"><span>Active connections</span><span className="font-mono text-cyan-300">{liveSummary?.active_connections ?? "—"}</span></div>
              <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-3"><span>Bytes</span><span className="font-mono text-cyan-300">{liveSummary?.bytes ?? "—"}</span></div>
            </div>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
              <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Threat activity over replay steps</div>
              <div className="flex h-44 items-end gap-1 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                {timeline.length ? timeline.map((step: any, index: number) => <div key={`risk-${index}`} title={`Step ${index + 1}: ${step.risk}%`} className="flex-1 rounded-t bg-cyan-400/80" style={{ height: `${Math.max(2, Math.min(Number(step.risk || 0), 100))}%` }} />) : <div className="m-auto text-sm text-slate-500">No risk history available.</div>}
              </div>
              <div className="mt-2 flex justify-between text-[10px] uppercase tracking-[0.2em] text-slate-500"><span>Step 1</span><span>Model probability / risk</span><span>Step {timeline.length}</span></div>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
              <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Observed attack type distribution</div>
              <div className="space-y-3">
                {Object.entries(timeline.reduce((counts: Record<string, number>, item: any) => { const label = String(item.label || "Unknown"); counts[label] = (counts[label] || 0) + 1; return counts; }, {})).map(([label, count]) => <div key={label}><div className="flex justify-between text-sm text-slate-300"><span>{label}</span><span className="font-mono text-cyan-300">{count}</span></div><div className="mt-1 h-2 rounded bg-slate-800"><div className="h-full rounded bg-gradient-to-r from-red-500 to-cyan-500" style={{ width: `${Math.min(Number(count) / Math.max(timeline.length, 1) * 100, 100)}%` }} /></div></div>)}
                {!timeline.length ? <div className="text-sm text-slate-500">No observed attack classes available.</div> : null}
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Why this forecast</div>
            <div className="space-y-3">
              {evidence.map((item: any, idx: number) => (
                <div key={`${item.label}-${idx}`} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <div className="text-sm font-semibold text-slate-100">{item.label || "Signal attribution"}</div>
                  <p className="mt-2 text-sm text-slate-300">{item.explanation ?? item.description ?? "No evidence available yet"}</p>
                </div>
              ))}
              {!evidence.length ? <div className="text-sm text-slate-500">No data available yet</div> : null}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Top talkers</div>
            <div className="overflow-hidden rounded-xl border border-slate-800">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-950/80 text-[10px] uppercase tracking-[0.22em] text-slate-400">
                  <tr><th className="px-3 py-3">Host</th><th className="px-3 py-3">Flows</th><th className="px-3 py-3">Bytes</th><th className="px-3 py-3">Risk</th></tr>
                </thead>
                <tbody>
                  {talkers.map((t: any) => (
                    <tr key={t.host} className="border-t border-slate-800 bg-slate-950/40">
                      <td className="px-3 py-3 font-mono text-slate-200">{t.host}</td>
                      <td className="px-3 py-3 font-mono text-cyan-300">{t.flows}</td>
                      <td className="px-3 py-3 font-mono text-slate-300">{t.bytes}</td>
                      <td className="px-3 py-3 font-mono text-red-300">{t.risk}%</td>
                    </tr>
                  ))}
                  {!talkers.length ? <tr><td colSpan={4} className="px-3 py-3 text-slate-500">No data available yet</td></tr> : null}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
