"use client";

import { useEffect, useState } from "react";
import { api } from "../../components/api";
import { DashboardShell } from "../../components/dashboard-shell";
import { useReplaySession } from "../../components/replay-session";

type FeatureImportance = { name?: string; feature?: string; importance?: number };
type ProbabilityBucket = { bucket: string; count: number };
type EvidenceItem = { label: string; value: number };
type Performance = {
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  auc_roc?: number | null;
  probability_distribution?: ProbabilityBucket[];
};

export default function ModelInsightsPage() {
  const [performance, setPerformance] = useState<Performance>({});
  const [features, setFeatures] = useState<FeatureImportance[]>([]);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const { host } = useReplaySession();

  useEffect(() => {
    async function load() {
      try {
        if (!host) return;
        const [modelPerformance, featureImportance, evidenceData] = await Promise.all([
          api<Performance>("/api/models/performance"),
          api<{ top_features?: FeatureImportance[]; features?: FeatureImportance[] }>("/api/models/feature-importance"),
          api<EvidenceItem[]>(`/api/evidence/${encodeURIComponent(host)}`),
        ]);
        setPerformance(modelPerformance || {});
        setFeatures(featureImportance?.top_features || featureImportance?.features || []);
        setEvidence(evidenceData || []);
      } catch {
        setPerformance({});
      }
    }
    void load();
    const interval = window.setInterval(load, 2500);
    return () => window.clearInterval(interval);
  }, [host]);

  const metrics = [
    { label: "Accuracy", value: performance.accuracy, color: "text-cyan-300" },
    { label: "Precision", value: performance.precision, color: "text-emerald-300" },
    { label: "Recall", value: performance.recall, color: "text-amber-300" },
    { label: "F1", value: performance.f1, color: "text-violet-300" },
    { label: "AUC-ROC", value: performance.auc_roc, color: "text-red-300" },
  ];

  return (
    <DashboardShell title="Model Insights" subtitle="Performance and feature attribution for the active attacker forecast model">
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-5">
          {metrics.map((metric) => (
            <div key={metric.label} className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
              <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">{metric.label}</div>
              <div className={`mt-2 font-mono text-3xl font-black ${metric.color}`}>              {typeof metric.value === "number" ? `${metric.value.toFixed(1)}%` : "N/A"}</div>
            </div>
          ))}
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Global feature importance</div>
            <div className="space-y-4">
              {features.length ? features.map((feature) => (
                <div key={feature.name || feature.feature}>
                  <div className="mb-1 flex items-center justify-between text-sm text-slate-300">
                    <span>{feature.name || feature.feature}</span>
                    <span className="font-mono text-cyan-300">{typeof feature.importance === "number" ? feature.importance.toFixed(3) : "—"}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                    <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-500" style={{ width: `${Math.min((feature.importance ?? 0) * 100, 100)}%` }} />
                  </div>
                </div>
              )) : <div className="text-slate-400">Global importance unavailable.</div>}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Model probability distribution</div>
            <div className="h-60 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
              {performance.probability_distribution?.length ? (
                <div className="flex h-full items-end gap-2">
                  {performance.probability_distribution.map((bucket) => (
                    <div key={bucket.bucket} className="flex flex-1 flex-col items-center gap-2">
                      <div className="w-full rounded-t bg-cyan-400/80" style={{ height: `${Math.min(Number(bucket.count), 100)}%` }} />
                      <span className="font-mono text-[9px] text-slate-500">{bucket.bucket}</span>
                    </div>
                  ))}
                </div>
              ) : <div className="grid h-full place-items-center text-sm text-slate-500">Probability distribution unavailable.</div>}
            </div>
          </div>
        </div>
        <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
          <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Top contributing features for {host || "active session"}</div>
          <div className="space-y-3">
            {evidence.length ? evidence.map((item, index) => (
              <div key={`${host}-xai-${index}`} className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-sm">
                <span className="text-slate-200">{item.label}</span>
                <span className="font-mono text-cyan-300">{Number(item.value).toFixed(6)}</span>
              </div>
            )) : <div className="text-slate-400">Feature attribution unavailable for the active prediction.</div>}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
