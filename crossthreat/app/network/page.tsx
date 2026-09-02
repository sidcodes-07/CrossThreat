"use client";

import { useEffect, useState } from "react";
import { api } from "../../components/api";
import { DashboardShell } from "../../components/dashboard-shell";
import { useReplaySession } from "../../components/replay-session";

export default function NetworkMonitorPage() {
  const [topology, setTopology] = useState<any>({ nodes: [], edges: [] });
  const [protocolBreakdown, setProtocolBreakdown] = useState<any[]>([]);
  const [topPairs, setTopPairs] = useState<any[]>([]);
  const [traffic, setTraffic] = useState<any[]>([]);
  const { host, currentStep } = useReplaySession();

  useEffect(() => {
    async function load() {
      if (!host) return;
      try {
        const [network, protocol, pairs, trafficData] = await Promise.all([
          api<any>(`/api/network/topology?host=${encodeURIComponent(host)}&step=${currentStep}`),
          api<any>(`/api/network/protocol-breakdown?host=${encodeURIComponent(host)}&step=${currentStep}`),
          api<any>(`/api/network/top-pairs?host=${encodeURIComponent(host)}&step=${currentStep}`),
          api<any[]>(`/api/network/traffic-over-time?host=${encodeURIComponent(host)}&step=${currentStep}`),
        ]);
        setTopology(network || { nodes: [], edges: [] });
        setProtocolBreakdown(protocol);
        setTopPairs(pairs);
        setTraffic(trafficData || []);
      } catch (_error) {
        setTopology({ nodes: [], edges: [] });
      }
    }
    void load();
    const interval = window.setInterval(load, 2500);
    return () => window.clearInterval(interval);
  }, [host, currentStep]);

  return (
    <DashboardShell title="Network Monitor" subtitle="Live topology and traffic concentration">
      <div className="space-y-6">
        <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Interactive topology</div>
            <div className="flex min-h-[420px] items-center justify-center rounded-xl border border-slate-800 bg-[radial-gradient(circle_at_center,_rgba(34,211,238,0.12),_rgba(15,23,42,0.1)_50%,_rgba(2,6,23,1)_100%)] p-4">
              <div className="relative h-[330px] w-full max-w-[700px]">
                {topology.nodes.length ? topology.nodes.map((node: any, index: number) => (
                  <div
                    key={node.id || `node-${index}`}
                    className="absolute flex -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border text-[10px] font-semibold uppercase tracking-[0.18em]"
                    style={{
                      left: node.x || `${(index + 1) * 22}%`,
                      top: node.y || `${(index % 3 + 1) * 28}%`,
                      width: node.id === "10.0.0.5" ? 84 : 60,
                      height: node.id === "10.0.0.5" ? 84 : 60,
                      background: node.severity === "high" ? "rgba(239,68,68,0.2)" : node.severity === "medium" ? "rgba(245,158,11,0.15)" : "rgba(16,185,129,0.15)",
                      borderColor: node.severity === "high" ? "rgba(239,68,68,0.7)" : node.severity === "medium" ? "rgba(245,158,11,0.7)" : "rgba(34,197,94,0.75)",
                      boxShadow: node.severity === "high" ? "0 0 18px rgba(239,68,68,0.25)" : "0 0 18px rgba(34,211,238,0.12)",
                      color: "#e2e8f0",
                    }}
                  >
                    {node.label || node.id}
                  </div>
                )) : <div className="text-slate-400">Loading network topology…</div>}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
              <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Flow summary</div>
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Total flows</div>
                  <div className="mt-2 font-mono text-2xl font-black text-cyan-300">                  {topology.summary?.total_flows ?? "—"}</div>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Active connections</div>
                  <div className="mt-2 font-mono text-2xl font-black text-violet-300">                  {topology.summary?.active_connections ?? "—"}</div>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Bytes</div>
                  <div className="mt-2 font-mono text-xl font-black text-emerald-300">                  {topology.summary?.bytes ?? "—"}</div>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Peak</div>
                  <div className="mt-2 font-mono text-xl font-black text-red-300">                  {topology.summary?.peak ?? "—"}</div>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
              <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Traffic volume over replay time</div>
              <div className="flex h-44 items-end gap-1 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                {traffic.length ? traffic.map((point: any, index: number) => <div key={`traffic-${index}`} title={`Step ${point.step}: ${point.flows} flows`} className="flex-1 rounded-t bg-violet-400/80" style={{ height: `${Math.max(3, Math.min(Number(point.flows) / Math.max(...traffic.map((item: any) => Number(item.flows)), 1) * 100, 100))}%` }} />) : <div className="m-auto text-sm text-slate-500">No traffic history available.</div>}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
              <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Protocol breakdown</div>
              <div className="space-y-3">
                {protocolBreakdown.length ? protocolBreakdown.map((item: any) => (
                  <div key={item.protocol}>
                    <div className="mb-1 flex items-center justify-between text-sm text-slate-300">
                      <span>{item.protocol}</span>
                      <span className="font-mono text-cyan-300">{item.percent}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                      <div className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500" style={{ width: `${item.percent}%` }} />
                    </div>
                  </div>
                )) : <div className="text-slate-400">Loading protocol breakdown…</div>}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
          <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Top communication pairs</div>
          <div className="overflow-hidden rounded-xl border border-slate-800">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-950/90 text-[10px] uppercase tracking-[0.22em] text-slate-400">
                <tr>
                  <th className="px-3 py-3">Source</th>
                  <th className="px-3 py-3">Dest</th>
                  <th className="px-3 py-3">Protocol</th>
                  <th className="px-3 py-3">Bytes</th>
                  <th className="px-3 py-3">Packets</th>
                </tr>
              </thead>
              <tbody>
                {topPairs.length ? topPairs.map((pair: any, idx: number) => (
                  <tr key={`${pair.source}-${pair.dest}-${idx}`} className="border-t border-slate-800 bg-slate-950/40">
                    <td className="px-3 py-3 font-mono text-slate-200">{pair.source}</td>
                    <td className="px-3 py-3 font-mono text-slate-200">{pair.dest}</td>
                    <td className="px-3 py-3 text-slate-200">{pair.protocol}</td>
                    <td className="px-3 py-3 font-mono text-cyan-300">{pair.bytes}</td>
                    <td className="px-3 py-3 font-mono text-cyan-300">{pair.packets}</td>
                  </tr>
                )) : <tr><td colSpan={5} className="px-3 py-3 text-slate-400">Loading communication pairs…</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
