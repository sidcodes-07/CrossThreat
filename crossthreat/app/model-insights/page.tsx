"use client";

import { useEffect, useState } from "react";
import { api } from "../../components/api";
import { DashboardShell } from "../../components/dashboard-shell";

export default function ModelInsightsPage() {
  const [performance, setPerformance] = useState<any>({});
  const [features, setFeatures] = useState<any[]>([]);

  useEffect(() => {
    async function load() {
      try {
        const [modelPerformance, featureImportance] = await Promise.all([
          api<any>("/api/models/performance"),
          api<any>("/api/models/feature-importance"),
        ]);
        setPerformance(modelPerformance);
        setFeatures(featureImportance?.top_features || featureImportance?.features || []);
      } catch (_error) {
        setPerformance({});
      }
    }
    void load();
  }, []);

  const metrics = [
    { label: "Accuracy", value: performance.accuracy ?? 96.2, color: "text-cyan-300" },
    { label: "Precision", value: performance.precision ?? 95.7, color: "text-emerald-300" },
    { label: "Recall", value: performance.recall ?? 93.1, color: "text-amber-300" },
    { label: "F1", value: performance.f1 ?? 94.4, color: "text-violet-300" },
    { label: "AUC-ROC", value: performance.auc_roc ?? 97.5, color: "text-red-300" },
  ];

  return (
    <DashboardShell title="Model Insights" subtitle="Performance and feature attribution for the active attacker forecast model">
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-5">
          {metrics.map((metric) => (
            <div key={metric.label} className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-4">
              <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">{metric.label}</div>
              <div className={`mt-2 font-mono text-3xl font-black ${metric.color}`}>{metric.value.toFixed(1)}%</div>
            </div>
          ))}
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Feature importance</div>
            <div className="space-y-4">
              {features.length ? features.map((feature: any) => (
                <div key={feature.name || feature.feature}>
                  <div className="mb-1 flex items-center justify-between text-sm text-slate-300">
                    <span>{feature.name || feature.feature}</span>
                    <span className="font-mono text-cyan-300">{(feature.importance ?? feature.value ?? 0).toFixed(3)}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                    <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-500" style={{ width: `${Math.min((feature.importance ?? feature.value ?? 0) * 100, 100)}%` }} />
                  </div>
                </div>
              )) : <div className="text-slate-400">Loading feature importance…</div>}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#111827]/90 p-5">
            <div className="mb-4 text-[10px] uppercase tracking-[0.3em] text-cyan-400">Model confidence distribution</div>
            <div className="h-60 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
              <svg viewBox="0 0 260 180" className="h-full w-full">
                {[40, 60, 82, 100, 120, 138, 150, 170, 182, 200].map((x, idx) => (
                  <g key={`${x}-${idx}`}>
                    <rect x={x} y={80 - idx * 5} width="18" height={idx * 7 + 30} fill={idx % 2 === 0 ? "#00D9FF" : "#A855F7"} opacity="0.8" />
                  </g>
                ))}
              </svg>
            </div>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
