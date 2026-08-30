"use client";

import React, { useState, useEffect, useRef } from "react";

// ── Types ──────────────────────────────────────────────────────────────────

interface FeatureImportance {
  feature: string;
  value: number;
}

interface TimelineStep {
  step: number;

  // Current observed (window t-1 — last window in the LSTM input sequence)
  current_observed_label: string;
  current_observed_time: string;

  // Baseline classifier
  baseline_predicted_state: string;
  baseline_probability: number;
  baseline_shap: FeatureImportance[];

  // Current MITRE stage (from baseline + rule engine)
  current_mitre_stage: string;
  current_rule_stage: string;
  triggered_rules: string[];
  detection_source: string;

  // LSTM forecast (predicting the NEXT window)
  forecast_next_state: string;
  forecast_probability: number;
  forecast_mitre_stage: string;
  forecast_attribution: FeatureImportance[];

  // Actual future (window t — revealed after forecast)
  actual_future_label: string;
  actual_future_time: string;

  // Validation
  forecast_correct: boolean;
  lead_time_seconds: number;

  metrics: Record<string, number>;
}

interface SummaryMetrics {
  overall_forecast_accuracy: number;
  attack_forecast_accuracy: number;
  total_attack_steps: number;
  mean_lead_time_seconds: number;
  per_class_metrics: Record<
    string,
    { precision: number; recall: number; f1: number }
  >;
  seq_len: number;
  window_size: string;
}

interface ReplayData {
  host: string;
  total_steps: number;
  steps: TimelineStep[];
  summary: SummaryMetrics;
}

interface GeneralizationResults {
  indist_accuracy: number;
  ood_accuracy: number;
  accuracy_delta: number;
  ood_sequences: number;
}

// ── Helpers ────────────────────────────────────────────────────────────────

const getLabelColor = (label: string | undefined | null) => {
  if (!label) return "bg-zinc-800 text-zinc-400 border-zinc-700";
  if (label === "Benign") return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
  if (label.includes("DoS") || label.includes("DDoS")) return "bg-rose-500/20 text-rose-400 border-rose-500/30";
  if (label.includes("Bot")) return "bg-indigo-500/20 text-indigo-400 border-indigo-500/30";
  if (label.includes("Brute")) return "bg-amber-500/20 text-amber-400 border-amber-500/30";
  if (label.includes("SQL") || label.includes("XSS")) return "bg-orange-500/20 text-orange-400 border-orange-500/30";
  return "bg-purple-500/20 text-purple-400 border-purple-500/30";
};

const getStageColor = (stage: string | undefined | null) => {
  if (!stage) return "bg-zinc-800 text-zinc-400 border-zinc-700";
  const s = stage.toLowerCase();
  if (s.includes("normal")) return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
  if (s.includes("reconnaissance") || s.includes("discovery")) return "bg-amber-500/10 text-amber-400 border-amber-500/20";
  if (s.includes("credential") || s.includes("access") || s.includes("exploitation")) return "bg-orange-500/10 text-orange-400 border-orange-500/20";
  if (s.includes("command") || s.includes("lateral")) return "bg-indigo-500/10 text-indigo-400 border-indigo-500/20";
  if (s.includes("impact") || s.includes("exfil")) return "bg-rose-500/10 text-rose-400 border-rose-500/20";
  return "bg-zinc-800 text-zinc-400 border-zinc-700";
};

const ForecastBadge = ({ correct, isBenignBenign }: { correct: boolean; isBenignBenign: boolean }) => {
  if (isBenignBenign)
    return <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-500 border border-zinc-700">⬜ Benign→Benign</span>;
  if (correct)
    return <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">✅ Correct</span>;
  return <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30">❌ Incorrect</span>;
};

// ── Main Component ─────────────────────────────────────────────────────────

export default function Dashboard() {
  const [hosts, setHosts] = useState<string[]>([]);
  const [selectedHost, setSelectedHost] = useState<string>("");
  const [replayData, setReplayData] = useState<ReplayData | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1000);
  const [genResults, setGenResults] = useState<GeneralizationResults | null>(null);
  const [activeTab, setActiveTab] = useState<"live" | "generalization" | "evaluation">("live");
  const [showBaseline, setShowBaseline] = useState<boolean>(true);
  const [error, setError] = useState<string>("");
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Load host list + generalization on mount
  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/replay/list")
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((d) => { setHosts(d); if (d.length > 0) setSelectedHost(d[0]); })
      .catch(() => setError("FastAPI backend is offline or loading failed. Make sure server.py is running."));

    fetch("http://127.0.0.1:8000/api/generalization")
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then(setGenResults)
      .catch(() => console.log("Generalization results not available yet."));
  }, []);

  // Load replay when host changes
  useEffect(() => {
    if (!selectedHost) return;
    setIsPlaying(false);
    setCurrentStepIndex(0);
    setReplayData(null);
    fetch(`http://127.0.0.1:8000/api/replay/host/${encodeURIComponent(selectedHost)}`)
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then((d) => { setReplayData(d); setError(""); })
      .catch((e) => setError(`Error loading replay for ${selectedHost}: ${e.message}`));
  }, [selectedHost]);

  // Playback timer
  useEffect(() => {
    if (isPlaying) {
      timerRef.current = setInterval(() => {
        setCurrentStepIndex((prev) => {
          if (replayData && prev < replayData.steps.length - 1) return prev + 1;
          setIsPlaying(false);
          return prev;
        });
      }, playbackSpeed);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isPlaying, replayData, playbackSpeed]);

  const step = replayData?.steps[currentStepIndex];
  const summary = replayData?.summary;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans p-6">

      {/* ── Header ── */}
      <header className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-zinc-800 pb-6 mb-6 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 rounded-full bg-rose-500 animate-pulse" />
            <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-red-400 via-rose-400 to-indigo-400 bg-clip-text text-transparent">
              CrossThreat Security Engine
            </h1>
          </div>
          <p className="text-sm text-zinc-400 mt-1">
            Temporal Cyber-Threat Forecasting · CURRENT → FORECAST → ACTUAL
          </p>
        </div>

        <div className="flex gap-2 bg-zinc-900/60 p-1 rounded-lg border border-zinc-800/80">
          {(["live", "evaluation", "generalization"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium rounded-md transition-all capitalize ${activeTab === tab
                ? "bg-zinc-800 text-white shadow-sm"
                : "text-zinc-400 hover:text-zinc-200"
                }`}
            >
              {tab === "live" ? "Live Replay" : tab === "evaluation" ? "Evaluation" : "OOD Test"}
            </button>
          ))}
        </div>
      </header>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-lg mb-6 text-sm">
          <strong>Connection Alert: </strong>{error}
        </div>
      )}

      {/* ── Live Replay Tab ── */}
      {activeTab === "live" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

          {/* Left: Controls + Timeline */}
          <div className="lg:col-span-8 space-y-6">

            {/* Playback Controls */}
            <div className="bg-zinc-900/40 backdrop-blur-sm border border-zinc-800/60 rounded-xl p-5 shadow-xl">
              <h2 className="text-lg font-bold mb-4 text-zinc-200 flex items-center gap-2">
                <span>🎮</span> Threat Replay Controller
              </h2>

              <div className="flex flex-col md:flex-row items-stretch md:items-center gap-4 justify-between">
                <div className="flex items-center gap-3">
                  <label className="text-xs text-zinc-400 font-medium">Target Host:</label>
                  <select
                    value={selectedHost}
                    onChange={(e) => setSelectedHost(e.target.value)}
                    className="bg-zinc-900 border border-zinc-800 text-zinc-100 text-sm rounded-lg focus:ring-rose-500 focus:border-rose-500 p-2.5 outline-none min-w-[180px]"
                  >
                    {hosts.map((h) => <option key={h} value={h}>{h}</option>)}
                  </select>
                </div>

                <div className="flex items-center justify-center gap-2">
                  <button onClick={() => { setIsPlaying(false); setCurrentStepIndex(0); }}
                    className="p-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700/50 text-zinc-300 transition-colors" title="Reset">⏮️</button>
                  <button onClick={() => setCurrentStepIndex((p) => Math.max(0, p - 1))}
                    disabled={currentStepIndex === 0}
                    className="p-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700/50 text-zinc-300 disabled:opacity-40 transition-colors">◀️</button>
                  <button onClick={() => setIsPlaying(!isPlaying)}
                    className={`px-5 py-2.5 rounded-lg font-bold transition-all flex items-center gap-2 ${isPlaying ? "bg-amber-600 hover:bg-amber-500" : "bg-rose-600 hover:bg-rose-500"} text-white`}>
                    {isPlaying ? "⏸️ Pause" : "▶️ Play Replay"}
                  </button>
                  <button onClick={() => setCurrentStepIndex((p) => Math.min((replayData?.steps.length ?? 1) - 1, p + 1))}
                    disabled={!replayData || currentStepIndex === replayData.steps.length - 1}
                    className="p-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700/50 text-zinc-300 disabled:opacity-40 transition-colors">▶️</button>
                </div>

                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <label className="text-xs text-zinc-400">Speed:</label>
                    <select value={playbackSpeed} onChange={(e) => setPlaybackSpeed(Number(e.target.value))}
                      className="bg-zinc-900 border border-zinc-800 text-zinc-100 text-xs rounded-md p-1.5 outline-none">
                      <option value={2000}>0.5x</option>
                      <option value={1000}>1.0x</option>
                      <option value={500}>2.0x</option>
                    </select>
                  </div>
                  <button onClick={() => setShowBaseline(!showBaseline)}
                    className={`px-3 py-1.5 text-xs font-semibold rounded-md border transition-all ${showBaseline ? "bg-zinc-800 text-white border-zinc-700" : "bg-transparent text-zinc-500 border-zinc-800/80"}`}>
                    Comparison: {showBaseline ? "ON" : "OFF"}
                  </button>
                </div>
              </div>

              {replayData && (
                <div className="mt-5 space-y-2">
                  <div className="flex justify-between text-xs text-zinc-400">
                    <span>Sequence Progress:</span>
                    <span className="font-mono text-zinc-300 font-bold">{currentStepIndex + 1} / {replayData.steps.length}</span>
                  </div>
                  <input type="range" min={0} max={replayData.steps.length - 1} value={currentStepIndex}
                    onChange={(e) => setCurrentStepIndex(Number(e.target.value))}
                    className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-rose-500" />
                </div>
              )}
            </div>

            {/* ── Three-Panel: CURRENT → FORECAST → ACTUAL ── */}
            {step && (
              <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-5 shadow-lg space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-400">
                    🔮 Temporal Forecast Validation — Step {step.step}
                  </h3>
                  <ForecastBadge
                    correct={step.forecast_correct}
                    isBenignBenign={step.actual_future_label === "Benign" && step.forecast_next_state === "Benign"}
                  />
                </div>

                {/* Three panels */}
                <div className="grid grid-cols-3 gap-3">

                  {/* Panel 1: Current Observed (t-1) */}
                  <div className="bg-zinc-950/60 border border-zinc-800 rounded-xl p-4 space-y-2">
                    <span className="text-[10px] uppercase font-bold tracking-widest text-zinc-500 block">
                      📍 Current Observed
                    </span>
                    <span className="text-[10px] font-mono text-zinc-600 block">{step.current_observed_time}</span>
                    <span className={`inline-block text-xs px-2.5 py-1 rounded-full font-bold border ${getLabelColor(step.current_observed_label)}`}>
                      {step.current_observed_label}
                    </span>
                    <div className={`text-[10px] px-2 py-1 rounded-lg border mt-1 ${getStageColor(step.current_mitre_stage)}`}>
                      {step.current_mitre_stage}
                    </div>
                    <span className="text-[9px] text-zinc-600 block">Source: {step.detection_source}</span>
                  </div>

                  {/* Arrow + Lead Time */}
                  <div className="flex flex-col items-center justify-center gap-2">
                    <div className="text-zinc-600 text-xl font-bold tracking-widest">→</div>
                    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-2 text-center">
                      <span className="text-[9px] text-zinc-500 block uppercase font-semibold">LSTM Forecast</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-bold border block mt-1 ${getLabelColor(step.forecast_next_state)}`}>
                        {step.forecast_next_state}
                      </span>
                      <span className="text-[10px] font-mono text-indigo-400 block mt-1">
                        {(step.forecast_probability * 100).toFixed(0)}% conf
                      </span>
                      <div className="w-full bg-zinc-800 h-1 rounded-full mt-1.5 overflow-hidden">
                        <div className="bg-indigo-500 h-full rounded-full" style={{ width: `${step.forecast_probability * 100}%` }} />
                      </div>
                      <span className="text-[9px] text-zinc-500 block mt-1">{step.forecast_mitre_stage}</span>
                    </div>
                    <div className="text-zinc-600 text-xl font-bold tracking-widest">→</div>
                    <div className="text-center">
                      <span className="text-[9px] text-zinc-500 block uppercase font-semibold">Lead Time</span>
                      <span className="text-sm font-mono font-bold text-zinc-300">{(step.lead_time_seconds ?? 0).toFixed(0)}s</span>
                    </div>
                  </div>

                  {/* Panel 3: Actual Future (t) */}
                  <div className={`border rounded-xl p-4 space-y-2 ${step.forecast_correct ? "bg-emerald-500/5 border-emerald-500/20" : step.actual_future_label === "Benign" ? "bg-zinc-950/60 border-zinc-800" : "bg-rose-500/5 border-rose-500/20"}`}>
                    <span className="text-[10px] uppercase font-bold tracking-widest text-zinc-500 block">
                      🔭 Actual Future
                    </span>
                    <span className="text-[10px] font-mono text-zinc-600 block">{step.actual_future_time}</span>
                    <span className={`inline-block text-xs px-2.5 py-1 rounded-full font-bold border ${getLabelColor(step.actual_future_label)}`}>
                      {step.actual_future_label}
                    </span>
                    <div className="mt-2">
                      {step.forecast_correct ? (
                        <span className="text-[10px] text-emerald-400 font-semibold">✅ Forecast matched</span>
                      ) : (
                        <span className="text-[10px] text-rose-400 font-semibold">
                          ❌ Expected {step.forecast_next_state}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Rule alerts (only shown when rules actually fire) */}
                {step.triggered_rules.length > 0 && (
                  <div className="space-y-1.5 pt-2 border-t border-zinc-800/40">
                    <span className="text-[10px] uppercase font-bold text-amber-500">⚡ Rule Engine Alerts</span>
                    {step.triggered_rules.map((r, i) => (
                      <div key={i} className="bg-amber-500/10 border border-amber-500/20 text-amber-300 p-2 rounded-lg text-[10px] flex items-center gap-2">
                        <span className="text-amber-500">⚡</span>{r}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Trajectory Timeline */}
            {replayData && step && (
              <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-5 shadow-lg">
                <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-400 mb-4">
                  📈 Attack Trajectory (Observed → Forecast → Actual)
                </h3>
                <div className="relative pl-6 border-l border-zinc-800 space-y-4">
                  {replayData.steps.slice(0, currentStepIndex + 1).map((s, idx) => {
                    const isLast = idx === currentStepIndex;
                    const isBB = s.actual_future_label === "Benign" && s.forecast_next_state === "Benign";
                    return (
                      <div key={s.step} className="relative">
                        <span className={`absolute -left-[30px] top-1.5 h-4 w-4 rounded-full border-2 ${isLast ? "bg-rose-500 border-rose-400 ring-4 ring-rose-500/20" : "bg-zinc-900 border-zinc-700"}`} />
                        <div className={`p-3 rounded-lg border transition-all ${isLast ? "bg-zinc-900/80 border-zinc-700" : "bg-zinc-950/40 border-zinc-900/80 opacity-60"}`}>
                          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                            <span className="text-[10px] text-zinc-500 font-mono">
                              Step {s.step} · {s.current_observed_time}→{s.actual_future_time}
                            </span>
                            <ForecastBadge correct={s.forecast_correct} isBenignBenign={isBB} />
                          </div>
                          <div className="mt-2 flex flex-wrap gap-2 text-[10px]">
                            <div className="flex items-center gap-1.5">
                              <span className="text-zinc-500">Now:</span>
                              <span className={`px-2 py-0.5 rounded-full font-bold border ${getLabelColor(s.current_observed_label)}`}>{s.current_observed_label}</span>
                            </div>
                            <span className="text-zinc-700">→</span>
                            <div className="flex items-center gap-1.5">
                              <span className="text-zinc-500">Forecast:</span>
                              <span className={`px-2 py-0.5 rounded-full font-bold border ${getLabelColor(s.forecast_next_state)}`}>{s.forecast_next_state}</span>
                              <span className="text-zinc-600">({(s.forecast_probability * 100).toFixed(0)}%)</span>
                            </div>
                            <span className="text-zinc-700">→</span>
                            <div className="flex items-center gap-1.5">
                              <span className="text-zinc-500">Actual:</span>
                              <span className={`px-2 py-0.5 rounded-full font-bold border ${getLabelColor(s.actual_future_label)}`}>{s.actual_future_label}</span>
                              <span className="text-zinc-600">{(s.lead_time_seconds ?? 0).toFixed(0)}s</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Traffic Metrics */}
            {step && (
              <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-5 shadow-lg">
                <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-400 mb-3">
                  📊 Current Window Traffic Statistics
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {[
                    { label: "Flow Count", val: step.metrics.flow_count?.toFixed(0) },
                    { label: "Avg Duration", val: `${(step.metrics.duration_avg / 1e3).toFixed(1)} ms` },
                    { label: "Fwd / Bwd Pkts", val: `${step.metrics.fwd_pkts_sum?.toFixed(0)} / ${step.metrics.bwd_pkts_sum?.toFixed(0)}` },
                    { label: "Dst IPs / Ports", val: `${step.metrics.unique_dst_ips?.toFixed(0)} / ${step.metrics.unique_dst_ports?.toFixed(0)}` },
                    { label: "SYN Flags", val: step.metrics.syn_flag_sum?.toFixed(0) },
                    { label: "RST Flags", val: step.metrics.rst_flag_sum?.toFixed(0) },
                    { label: "Bytes/s (avg)", val: step.metrics.flow_bytes_avg?.toFixed(1) },
                    { label: "TCP Ratio", val: `${((step.metrics.protocol_tcp_ratio ?? 0) * 100).toFixed(0)}%` },
                  ].map((m) => (
                    <div key={m.label} className="bg-zinc-900/80 border border-zinc-800/50 p-3 rounded-lg">
                      <span className="text-[10px] text-zinc-500">{m.label}</span>
                      <p className="text-base font-bold text-zinc-100 font-mono mt-0.5">{m.val}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right: Status + Explainability */}
          <div className="lg:col-span-4 space-y-6">

            {/* Summary bar */}
            {summary && (
              <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-4 shadow-xl">
                <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-400 mb-3">
                  📋 Host Forecast Summary
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-zinc-950/60 border border-zinc-800 p-3 rounded-lg text-center">
                    <span className="text-[10px] text-zinc-500 block uppercase font-semibold">Overall Acc</span>
                    <p className="text-xl font-extrabold font-mono mt-1 text-zinc-100">{(summary.overall_forecast_accuracy * 100).toFixed(1)}%</p>
                  </div>
                  <div className="bg-zinc-950/60 border border-zinc-800 p-3 rounded-lg text-center">
                    <span className="text-[10px] text-zinc-500 block uppercase font-semibold">Attack Acc</span>
                    <p className="text-xl font-extrabold font-mono mt-1 text-rose-400">{(summary.attack_forecast_accuracy * 100).toFixed(1)}%</p>
                  </div>
                  <div className="bg-zinc-950/60 border border-zinc-800 p-3 rounded-lg text-center">
                    <span className="text-[10px] text-zinc-500 block uppercase font-semibold">Attack Steps</span>
                    <p className="text-xl font-extrabold font-mono mt-1 text-amber-400">{summary.total_attack_steps}</p>
                  </div>
                  <div className="bg-zinc-950/60 border border-zinc-800 p-3 rounded-lg text-center">
                    <span className="text-[10px] text-zinc-500 block uppercase font-semibold">Avg Lead Time</span>
                    <p className="text-xl font-extrabold font-mono mt-1 text-indigo-400">{summary.mean_lead_time_seconds.toFixed(0)}s</p>
                  </div>
                </div>
              </div>
            )}

            {/* Model Comparison */}
            {showBaseline && step && (
              <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-4 shadow-xl">
                <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-400 mb-3">
                  ⚖️ Model Advantage Analysis
                </h3>
                <p className="text-[10px] text-zinc-500 mb-3">
                  Baseline RF sees window t-1 features now. LSTM sees past 5 windows to predict t (before it arrives).
                </p>
                <div className="grid grid-cols-2 gap-3 text-center">
                  <div className="bg-zinc-950/80 border border-zinc-800 p-3 rounded-lg">
                    <span className="text-[10px] text-zinc-500 uppercase block font-bold">RF Baseline</span>
                    <p className="text-sm font-extrabold text-amber-400 mt-1">{step.baseline_predicted_state}</p>
                    <span className="text-[9px] text-zinc-600 block mt-0.5">({(step.baseline_probability * 100).toFixed(0)}% conf)</span>
                  </div>
                  <div className="bg-zinc-950/80 border border-indigo-500/20 p-3 rounded-lg">
                    <span className="text-[10px] text-zinc-500 uppercase block font-bold">LSTM Forecast</span>
                    <p className="text-sm font-extrabold text-indigo-400 mt-1">{step.forecast_next_state}</p>
                    <span className="text-[9px] text-zinc-600 block mt-0.5">({(step.forecast_probability * 100).toFixed(0)}% conf)</span>
                  </div>
                </div>
                <div className="text-[10px] text-zinc-500 mt-3 bg-zinc-950/50 p-2.5 rounded-lg border border-zinc-800/20">
                  {step.actual_future_label !== "Benign" && step.baseline_predicted_state === "Benign" && step.forecast_correct ? (
                    <span className="text-emerald-400 font-semibold">
                      ⚡ LSTM predicted the incoming {step.actual_future_label} attack before the window arrived. Baseline missed it.
                    </span>
                  ) : step.actual_future_label !== "Benign" && !step.forecast_correct ? (
                    <span className="text-rose-400">
                      Model missed the {step.actual_future_label} — predicted {step.forecast_next_state}. This is an honest failure case.
                    </span>
                  ) : (
                    <span>LSTM uses {summary?.seq_len ?? 5} windows of context ({summary?.window_size ?? "30s"} each) to forecast the next network state.</span>
                  )}
                </div>
              </div>
            )}

            {/* Why Panel */}
            {step && (
              <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-4 shadow-xl space-y-4">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-400">🔍 Why Panel</h3>
                  <p className="text-[10px] text-zinc-500 mt-1">Feature attribution for model predictions.</p>
                </div>

                {/* LSTM gradient attribution */}
                <div className="space-y-2">
                  <h4 className="text-[10px] font-bold text-zinc-300 uppercase tracking-wide flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
                    LSTM Forecast Drivers (Input × Gradient)
                  </h4>
                  {step.forecast_attribution.map((a, i) => {
                    const max = Math.max(...step.forecast_attribution.map((x) => Math.abs(x.value)), 1e-5);
                    return (
                      <div key={i} className="space-y-0.5">
                        <div className="flex justify-between text-[10px] font-mono">
                          <span className="text-zinc-400">{a.feature}</span>
                          <span className="text-zinc-500">{a.value.toFixed(4)}</span>
                        </div>
                        <div className="w-full bg-zinc-800 h-1 rounded-full overflow-hidden">
                          <div className="bg-indigo-400 h-full rounded-full" style={{ width: `${(Math.abs(a.value) / max) * 100}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Baseline SHAP */}
                {showBaseline && (
                  <div className="space-y-2 pt-3 border-t border-zinc-800/50">
                    <h4 className="text-[10px] font-bold text-zinc-300 uppercase tracking-wide flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                      RF Baseline Drivers (SHAP)
                    </h4>
                    {step.baseline_shap.map((a, i) => {
                      const max = Math.max(...step.baseline_shap.map((x) => Math.abs(x.value)), 1e-5);
                      return (
                        <div key={i} className="space-y-0.5">
                          <div className="flex justify-between text-[10px] font-mono">
                            <span className="text-zinc-400">{a.feature}</span>
                            <span className="text-zinc-500">{a.value.toFixed(4)}</span>
                          </div>
                          <div className="w-full bg-zinc-800 h-1 rounded-full overflow-hidden">
                            <div className="bg-amber-400 h-full rounded-full" style={{ width: `${(Math.abs(a.value) / max) * 100}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Evaluation Tab ── */}
      {activeTab === "evaluation" && summary && (
        <div className="max-w-5xl mx-auto space-y-6">
          <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-6 shadow-xl">
            <h2 className="text-xl font-bold text-zinc-200 mb-1">📊 Forecast Evaluation Report</h2>
            <p className="text-sm text-zinc-500 mb-5">
              Host: <span className="font-mono text-zinc-300">{replayData?.host}</span> ·
              Sequence length: {summary.seq_len} windows · Window: {summary.window_size} ·
              Total steps: {replayData?.total_steps}
            </p>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {[
                { label: "Overall Forecast Acc", val: `${(summary.overall_forecast_accuracy * 100).toFixed(2)}%`, color: "text-zinc-100" },
                { label: "Attack Forecast Acc", val: `${(summary.attack_forecast_accuracy * 100).toFixed(2)}%`, color: "text-rose-400" },
                { label: "Attack Steps", val: String(summary.total_attack_steps), color: "text-amber-400" },
                { label: "Avg Lead Time", val: `${summary.mean_lead_time_seconds.toFixed(1)}s`, color: "text-indigo-400" },
              ].map((m) => (
                <div key={m.label} className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl text-center">
                  <span className="text-[10px] text-zinc-500 uppercase font-semibold block">{m.label}</span>
                  <p className={`text-2xl font-extrabold font-mono mt-1 ${m.color}`}>{m.val}</p>
                </div>
              ))}
            </div>

            {/* Per-class table */}
            <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-400 mb-3">Per-Class Metrics</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-zinc-800">
                    <th className="pb-2 text-zinc-500 font-semibold pr-4">Class</th>
                    <th className="pb-2 text-zinc-500 font-semibold text-right">Precision</th>
                    <th className="pb-2 text-zinc-500 font-semibold text-right">Recall</th>
                    <th className="pb-2 text-zinc-500 font-semibold text-right">F1</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(summary.per_class_metrics).map(([cls, m]) => (
                    <tr key={cls} className="border-b border-zinc-900/60 hover:bg-zinc-900/30">
                      <td className="py-2 pr-4">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${getLabelColor(cls)}`}>{cls}</span>
                      </td>
                      <td className="py-2 font-mono text-right text-zinc-300">{(m.precision * 100).toFixed(1)}%</td>
                      <td className="py-2 font-mono text-right text-zinc-300">{(m.recall * 100).toFixed(1)}%</td>
                      <td className="py-2 font-mono text-right text-zinc-300">{(m.f1 * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-5 bg-zinc-950/50 border border-zinc-800/30 p-4 rounded-lg text-xs text-zinc-500 space-y-1">
              <p><strong className="text-zinc-400">Temporal model:</strong> LSTM trained to predict label of window t+1 from input sequence [t-4…t]. No data leakage — future window features are never in the input.</p>
              <p><strong className="text-zinc-400">Forecast validation:</strong> At each step, the forecast is generated BEFORE window t is revealed. <code className="text-zinc-400">forecast_correct</code> compares <code className="text-zinc-400">forecast_label</code> vs <code className="text-zinc-400">actual_future_label</code>.</p>
              <p><strong className="text-zinc-400">Data source:</strong> Synthetic mock data (~2000 records/day, 15% random attack injection). Not real CSE-CIC-IDS2018. Genuine temporal attack escalation patterns are not guaranteed.</p>
            </div>
          </div>
        </div>
      )}

      {activeTab === "evaluation" && !summary && (
        <div className="max-w-xl mx-auto text-center py-20 text-zinc-500">
          <p>Select a host in the Live Replay tab to load evaluation metrics.</p>
        </div>
      )}

      {/* ── OOD Generalization Tab ── */}
      {activeTab === "generalization" && (
        <div className="max-w-4xl mx-auto space-y-6">
          {genResults ? (
            <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-6 shadow-xl space-y-6">
              <div>
                <h2 className="text-xl font-bold text-zinc-200">📁 Out-of-Distribution Generalization Test</h2>
                <p className="text-sm text-zinc-400 mt-1">
                  Temporal LSTM evaluated on synthetic CIC-IDS2017 (different attack mix, unseen during training).
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {[
                  { label: "In-Dist Accuracy (IDS2018 test)", val: `${(genResults.indist_accuracy * 100).toFixed(2)}%`, color: "text-zinc-100" },
                  { label: "OOD Accuracy (IDS2017)", val: `${(genResults.ood_accuracy * 100).toFixed(2)}%`, color: "text-indigo-400" },
                  {
                    label: "Generalization Delta",
                    val: `${(genResults.accuracy_delta * 100).toFixed(2)}%`,
                    color: genResults.accuracy_delta < -0.1 ? "text-rose-400" : "text-emerald-400",
                  },
                ].map((m) => (
                  <div key={m.label} className="bg-zinc-900/80 border border-zinc-800/50 p-4 rounded-xl">
                    <span className="text-xs text-zinc-500 uppercase font-semibold block">{m.label}</span>
                    <p className={`text-3xl font-extrabold font-mono mt-1 ${m.color}`}>{m.val}</p>
                  </div>
                ))}
              </div>

              <div className="bg-zinc-950/50 border border-zinc-800/30 p-5 rounded-lg text-sm space-y-3">
                <h3 className="font-bold text-zinc-300">🔍 Generalization Assessment</h3>
                <p className="text-zinc-400">
                  Model trained on partitioned temporal subsets from synthetic IDS2018 (Days 1–7 of mock data).
                  OOD test uses synthetic IDS2017 data with different attack types (PortScan, Web Attack – Brute Force)
                  not seen during training. Unknown OOD labels are mapped to the closest known categories.
                </p>
                <div className="border-t border-zinc-800/50 pt-3 text-xs text-zinc-500 space-y-1">
                  <p>• OOD sequences evaluated: <span className="font-bold text-zinc-300">{genResults.ood_sequences}</span></p>
                  <p>• Accuracy drop: <span className="font-bold text-zinc-300">{(Math.abs(genResults.accuracy_delta) * 100).toFixed(1)}%</span></p>
                  <p>• Status: {genResults.accuracy_delta > -0.15
                    ? <span className="text-emerald-400 font-bold">Stable (&lt;15% drop)</span>
                    : <span className="text-rose-400 font-bold">Overfit warning (&gt;15% drop)</span>}
                  </p>
                  <p className="text-zinc-600 pt-1">Note: Both IDS2018 and IDS2017 data are synthetic mocks. Generalization results reflect synthetic distribution shift only.</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-8 text-center space-y-3">
              <span className="text-3xl">⏳</span>
              <h3 className="font-bold text-zinc-200">Evaluating OOD Generalization...</h3>
              <p className="text-sm text-zinc-500">Running data pipeline on synthetic IDS2017 data.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
