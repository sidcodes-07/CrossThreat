"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useReplaySession } from "./replay-session";

const navItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/attack-timeline", label: "Attack Timeline" },
  { href: "/network", label: "Network View" },
  { href: "/forecasting", label: "Attack Forecasting" },
  { href: "/alerts", label: "Alerts" },
  { href: "/model-insights", label: "Model Insights" },
  { href: "/reports", label: "Reports" },
  { href: "/settings", label: "Settings" },
];

export function DashboardShell({
  title,
  subtitle,
  session,
  children,
}: {
  title: string;
  subtitle?: string;
  session?: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [time, setTime] = useState("00:00:00");
  const { host, hosts, hostsLoading, hostsError, currentStep, totalSteps, playing, speed, setHost, setPlaying, next, previous, reset, setSpeed } = useReplaySession();

  useEffect(() => {
    const updateTime = () => {
      setTime(
        new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
      );
    };

    updateTime();
    const interval = window.setInterval(updateTime, 1000);
    return () => window.clearInterval(interval);
  }, []);

  const dataSource = "Network Traffic Replay";
  const dataset = "NF-UNSW-NB15-v3 Replay";
  return (
    <div className="min-h-screen bg-[#0A0E1A] text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-[1800px]">
        <aside className="w-[250px] shrink-0 border-r border-slate-800 bg-[#0D1117] px-4 py-5">
          <div className="mb-8 flex items-center gap-3 border-b border-slate-800 pb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 text-sm font-black text-white">
              CT
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-[0.28em] text-cyan-400">SOC</div>
              <div className="text-lg font-bold text-slate-100">CrossThreat</div>
            </div>
          </div>

          <nav className="space-y-2">
            {navItems.map((item) => {
              const active = pathname === item.href || (item.href === "/dashboard" && pathname === "/");
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex w-full items-center justify-between rounded-xl border px-3 py-3 transition ${
                    active
                      ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-100 shadow-[0_0_0_1px_rgba(34,211,238,0.15)]"
                      : "border-slate-800 bg-slate-900/40 text-slate-300 hover:border-slate-700 hover:bg-slate-900/70"
                  }`}
                >
                  <span className="text-sm font-medium">{item.label}</span>
                  <span className="text-[9px] uppercase tracking-[0.18em] text-slate-400">{item.label.split(" ")[0]}</span>
                </Link>
              );
            })}
          </nav>
        </aside>

        <main className="flex-1 px-5 py-6 lg:px-7">
          <header className="mb-6 rounded-2xl border border-slate-800 bg-[#111827]/90 p-4 shadow-[0_0_0_1px_rgba(31,41,55,0.7)]">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <div className="text-[10px] uppercase tracking-[0.32em] text-cyan-400">Cyber Threat</div>
                <div className="mt-1 text-2xl font-black uppercase tracking-[0.08em] text-slate-100">Forecasting Engine</div>
              </div>

              <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-slate-400">
                <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-2">
                  <div className="text-slate-500">Data Source</div>
                  <div className="mt-1 text-[11px] font-semibold normal-case tracking-normal text-slate-200">{dataSource}</div>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-2">
                  <div className="text-slate-500">Dataset</div>
                  <div className="mt-1 text-[11px] font-semibold normal-case tracking-normal text-slate-200">{dataset}</div>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-2">
                  <div className="text-slate-500">Time</div>
                  <div className="mt-1 font-mono text-[11px] text-slate-200">{time}</div>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-2">
                  <label htmlFor="active-host" className="text-slate-500">Dataset Host / IP</label>
                  {hostsLoading ? <div className="mt-1 text-[11px] text-slate-400">Loading hosts...</div> : hostsError ? <div className="mt-1 text-[11px] text-red-300">Unable to load available hosts. Retrying...</div> : hosts.length ? (
                    <div className="relative mt-1">
                      <select id="active-host" value={host} onChange={(event) => setHost(event.target.value)} className="w-[190px] appearance-none rounded-lg border border-cyan-500/30 bg-slate-950 px-3 py-1.5 pr-8 text-[11px] font-semibold normal-case tracking-normal text-cyan-100 shadow-[0_0_18px_rgba(34,211,238,0.08)] outline-none transition hover:border-cyan-400/70 focus:border-cyan-300 focus:ring-1 focus:ring-cyan-400/40">
                        {hosts.map((availableHost) => <option key={availableHost} value={availableHost}>{availableHost}</option>)}
                      </select>
                      <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-cyan-300">▾</span>
                    </div>
                  ) : <div className="mt-1 text-[11px] text-slate-400">{host || session || "No replayable hosts found."}</div>}
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-2">
                  <div className="text-slate-500">Status</div>
                  <div className="mt-1 flex items-center gap-2 text-[11px] font-semibold normal-case tracking-normal text-emerald-300">
                    <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.8)]" />
                    {playing ? "Live" : "Paused"}
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setPlaying(!playing)}
                className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-200"
              >
                {playing ? "Pause" : "Play"}
              </button>
              <div className="flex items-center gap-1">
                <button type="button" onClick={previous} className="rounded-full border border-slate-700 px-3 py-2 text-[10px] uppercase tracking-[0.2em] text-slate-300">Previous</button>
                <button type="button" onClick={next} className="rounded-full border border-slate-700 px-3 py-2 text-[10px] uppercase tracking-[0.2em] text-slate-300">Next</button>
                <button type="button" onClick={reset} className="rounded-full border border-slate-700 px-3 py-2 text-[10px] uppercase tracking-[0.2em] text-slate-300">Reset</button>
                <select value={speed} onChange={(event) => setSpeed(Number(event.target.value))} aria-label="Replay speed" className="rounded-full border border-slate-700 bg-slate-900 px-2 py-2 text-[10px] text-slate-300">
                  <option value={0.5}>0.5x</option>
                  <option value={1}>1x</option>
                  <option value={2}>2x</option>
                </select>
              </div>
            </div>
          </header>

          <section className="mb-6">
            <div className="mb-2 text-[10px] uppercase tracking-[0.3em] text-cyan-400">{title}</div>
            {subtitle ? <div className="text-sm text-slate-400">{subtitle}</div> : null}
            <div className="mt-2 text-[10px] uppercase tracking-[0.2em] text-slate-500">Replay step {totalSteps ? `${currentStep + 1} / ${totalSteps}` : "Loading"}</div>
          </section>

          {children}
        </main>
      </div>
    </div>
  );
}
