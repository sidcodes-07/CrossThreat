"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "../../components/api";
import { DashboardShell } from "../../components/dashboard-shell";

export default function DashboardOverviewPage() {
  const [host, setHost] = useState("host-01");
  const [state, setState] = useState<any>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [evidence, setEvidence] = useState<any[]>([]);
  const [talkers, setTalkers] = useState<any[]>([]);
  const [liveSummary, setLiveSummary] = useState({ total_flows: 1842, active_connections: 146, bytes: "2.7 GB" });

  useEffect(() => {
    async function load() {
      try {
        const hostList = await api<any>("/api/replay/list");
        const selectedHost = Array.isArray(hostList) ? hostList[0] : hostList?.hosts?.[0] || host;
        setHost(selectedHost);

        const [current, timelineData, evidenceData, talkerData] = await Promise.all([
          api<any>("/api/state/current"),
          api<any[]>(`/api/timeline/${encodeURIComponent(selectedHost)}`),
          api<any[]>(`/api/evidence/${encodeURIComponent(selectedHost)}`),
          api<any[]>("/api/network/top-talkers"),
        ]);

        setState(current);
        setTimeline(timelineData || []);
        setEvidence(evidenceData || []);
        setTalkers(talkerData || []);
      } catch (_error) {
        setState({
          current_stage: "Monitoring",
          threat_level: "Low",
          risk_score: 46.2,
          next_stage_forecast: "Reconnaissance",
          probability: 0.69,
          alternative_outcomes: [{ label: "Port Scan", probability: 64.1, stage: "Phase 1" }],
        });
      }
    }
    void load();
  }, [host]);

  const ringStyle = useMemo(() => {
    const pct = Math.max(0, Math.min(100, Number(state?.probability ?? 0.68) * 100));
    return { background: `conic-gradient(#00D9FF 0 ${pct}%, rgba(148,163,184,0.15) ${pct}% 100%)` };
  }, [state]);

  return (
    <DashboardShell title="Dashboard Overview" subtitle="Current threat posture and near-term attack progression">
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-4">
          <div className="rounded-2xl border border-slate-800 bg-[#131826]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.26em] text-slate-500">Current network state</div>
            <div className="mt-3 text-xl font-bold text-slate-100">{state?.current_stage || "Monitoring"}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#131826]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.26em] text-slate-500">Threat level</div>
            <div className="mt-3 font-mono text-3xl font-black text-red-400">{state?.threat_level || "Low"}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-[#131826]/90 p-4">
            <div className="text-[10px] uppercase tracking-[0.26em] text-slate-500">Risk score</div>
            <div className="mt-3 font-mono text-3xl font-black text-cyan-300">{Math.round(state?.risk_score ?? 46)}%</div>
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
                  <div>
                    <div className="font-mono text-3xl font-black text-cyan-300">{Math.round((state?.probability ?? 0.68) * 100)}%</div>
                  </div>
                </div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Forecast</div>
                <div className="mt-2 text-2xl font-black text-slate-100">{state?.next_stage_forecast || "Reconnaissance"}</div>
                <div className="mt-2 text-sm text-slate-400">Probability of the next stage transition over the active replay window.</div>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Alternative outcomes</div>
            <div className="space-y-3">
              {(state?.alternative_outcomes || [{ label: "Port Scan", probability: 64.1, stage: "Recon" }]).map((outcome: any, idx: number) => (
                <div key={`${outcome.label}-${idx}`} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-100">{outcome.label}</span>
                    <span className="font-mono text-cyan-300">{outcome.probability ?? 0}%</span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800">
                    <div className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500" style={{ width: `${Math.min(outcome.probability ?? 0, 100)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Attack progression timeline</div>
            <div className="grid gap-3 md:grid-cols-6">
              {(timeline.length ? timeline : [
                { stage: "Recon", label: "Reconnaissance", started: "09:00:00", duration: "40s", risk: 36 },
                { stage: "Delivery", label: "Delivery", started: "09:02:20", duration: "52s", risk: 48 },
                { stage: "Exploitation", label: "Exploitation", started: "09:05:12", duration: "68s", risk: 61 },
                { stage: "Lateral", label: "Lateral Movement", started: "09:08:10", duration: "75s", risk: 72 },
                { stage: "Impact", label: "Impact", started: "09:11:15", duration: "91s", risk: 83 },
                { stage: "Exfiltration", label: "Exfiltration", started: "09:13:00", duration: "118s", risk: 90 },
              ]).map((step: any, idx: number) => (
                <div key={`${step.stage}-${idx}`} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">{step.stage}</div>
                  <div className="mt-3 text-sm font-semibold text-slate-100">{step.label}</div>
                  <div className="mt-3 font-mono text-[11px] text-cyan-300">{step.started}</div>
                  <div className="mt-1 text-[11px] text-slate-400">{step.duration}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Live network summary</div>
            <div className="space-y-3 text-sm text-slate-300">
              <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-3"><span>Total flows</span><span className="font-mono text-cyan-300">{liveSummary.total_flows}</span></div>
              <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-3"><span>Active connections</span><span className="font-mono text-cyan-300">{liveSummary.active_connections}</span></div>
              <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-3"><span>Bytes</span><span className="font-mono text-cyan-300">{liveSummary.bytes}</span></div>
            </div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Why this forecast</div>
            <div className="space-y-3">
              {(evidence.length ? evidence : [{ label: "Feature signal", explanation: "The current model is emphasizing the strongest recent flow-volume and timing signals in the active sequence." }]).map((item: any, idx: number) => (
                <div key={`${item.label}-${idx}`} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <div className="text-sm font-semibold text-slate-100">{item.label || "Signal attribution"}</div>
                  <p className="mt-2 text-sm text-slate-300">{item.explanation || item.description || "The model is combining packet volume, latency and session timing to estimate the next stage."}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Top talkers</div>
            <div className="overflow-hidden rounded-xl border border-slate-800">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-950/80 text-[10px] uppercase tracking-[0.22em] text-slate-400">
                  <tr>
                    <th className="px-3 py-3">Host</th>
                    <th className="px-3 py-3">Flows</th>
                    <th className="px-3 py-3">Bytes</th>
                    <th className="px-3 py-3">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {(talkers.length ? talkers : [{ host: host, flows: 840, bytes: "1.9 GB", risk: 72 }]).map((t: any) => (
                    <tr key={t.host} className="border-t border-slate-800 bg-slate-950/40">
                      <td className="px-3 py-3 font-mono text-slate-200">{t.host}</td>
                      <td className="px-3 py-3 font-mono text-cyan-300">{t.flows}</td>
                      <td className="px-3 py-3 font-mono text-slate-300">{t.bytes}</td>
                      <td className="px-3 py-3 font-mono text-red-300">{t.risk}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
