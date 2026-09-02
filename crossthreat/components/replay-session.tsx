"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, ReplayHost } from "./api";

type ReplaySessionValue = {
  hosts: string[];
  hostSummaries: ReplayHost[];
  hostsLoading: boolean;
  hostsError: boolean;
  host: string;
  currentStep: number;
  totalSteps: number;
  playing: boolean;
  speed: number;
  setHost: (host: string) => void;
  setTotalSteps: (totalSteps: number) => void;
  next: () => void;
  previous: () => void;
  reset: () => void;
  setPlaying: (playing: boolean) => void;
  setSpeed: (speed: number) => void;
};

const ReplaySessionContext = createContext<ReplaySessionValue | null>(null);

export function ReplaySessionProvider({ children }: { children: React.ReactNode }) {
  const [hosts, setHosts] = useState<string[]>([]);
  const [hostSummaries, setHostSummaries] = useState<ReplayHost[]>([]);
  const [hostsLoading, setHostsLoading] = useState(true);
  const [hostsError, setHostsError] = useState(false);
  const [host, setHostState] = useState("");
  const [currentStep, setCurrentStep] = useState(0);
  const [totalSteps, setTotalSteps] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);

  useEffect(() => {
    const savedHost = window.localStorage.getItem("crossthreat.activeHost");
    let cancelled = false;
    let retryTimer: number | undefined;
    const loadHosts = async () => {
      try {
        const response = await api<{ hosts: ReplayHost[] }>("/api/replay/hosts");
        if (cancelled) return;
        const availableHosts = response.hosts.map((summary) => summary.host);
        setHostSummaries(response.hosts);
        setHosts(availableHosts);
        setHostState(savedHost && availableHosts.includes(savedHost) ? savedHost : availableHosts[0] || "");
        setTotalSteps(response.hosts.find((summary) => summary.host === savedHost)?.replay_steps || response.hosts[0]?.replay_steps || 0);
        setHostsLoading(false);
        setHostsError(false);
      } catch {
        if (cancelled) return;
        setHostsLoading(false);
        setHostsError(true);
        retryTimer = window.setTimeout(loadHosts, 3000);
      }
    };
    void loadHosts();
    return () => {
      cancelled = true;
      if (retryTimer) window.clearTimeout(retryTimer);
    };
  }, []);

  useEffect(() => {
    if (host) window.localStorage.setItem("crossthreat.activeHost", host);
  }, [host]);

  useEffect(() => {
    if (!playing || totalSteps <= 0) return;
    const interval = window.setInterval(() => {
      setCurrentStep((step) => (step + 1) % totalSteps);
    }, Math.max(250, 2500 / speed));
    return () => window.clearInterval(interval);
  }, [playing, speed, totalSteps]);

  const setHost = useCallback((nextHost: string) => {
    setHostState(nextHost);
    setCurrentStep(0);
    setTotalSteps((steps) => {
      const matchingHost = hostSummaries.find((summary) => summary.host === nextHost);
      return matchingHost?.replay_steps || steps;
    });
  }, [hostSummaries]);
  const setTotal = useCallback((steps: number) => {
    setTotalSteps(steps);
    setCurrentStep((current) => Math.min(current, Math.max(steps - 1, 0)));
  }, []);
  const next = useCallback(() => setCurrentStep((step) => totalSteps > 0 ? Math.min(step + 1, totalSteps - 1) : step), [totalSteps]);
  const previous = useCallback(() => setCurrentStep((step) => Math.max(step - 1, 0)), []);
  const reset = useCallback(() => setCurrentStep(0), []);

  const value = useMemo<ReplaySessionValue>(() => ({
    hosts,
    hostSummaries,
    hostsLoading,
    hostsError,
    host,
    currentStep,
    totalSteps,
    playing,
    speed,
    setHost,
    setTotalSteps: setTotal,
    next,
    previous,
    reset,
    setPlaying,
    setSpeed,
  }), [currentStep, host, hostSummaries, hosts, hostsError, hostsLoading, next, previous, reset, playing, setHost, setTotal, speed, totalSteps]);

  return <ReplaySessionContext.Provider value={value}>{children}</ReplaySessionContext.Provider>;
}

export function useReplaySession() {
  const session = useContext(ReplaySessionContext);
  if (!session) throw new Error("useReplaySession must be used within ReplaySessionProvider");
  return session;
}
