import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#050b17] px-6 py-12 text-slate-100">
      <div className="w-full max-w-4xl rounded-3xl border border-slate-800 bg-slate-950/70 p-10 shadow-2xl shadow-cyan-950/20">
        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.25em] text-cyan-300">
          <span className="h-2 w-2 rounded-full bg-cyan-400" />
          Threat Intelligence Engine Active
        </div>

        <h1 className="mt-6 text-5xl font-black uppercase tracking-tight text-slate-100 sm:text-6xl">
          CrossThreat
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-relaxed text-slate-400">
          A passive cyber-threat forecasting dashboard for live replay, network telemetry, and model explainability.
        </p>

        <div className="mt-8">
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center rounded-full bg-gradient-to-r from-cyan-500 to-indigo-600 px-8 py-3 text-sm font-semibold uppercase tracking-[0.2em] text-white shadow-lg shadow-cyan-900/30 transition hover:brightness-110"
          >
            Launch Analyst Dashboard ?
          </Link>
        </div>
      </div>
    </main>
  );
}
