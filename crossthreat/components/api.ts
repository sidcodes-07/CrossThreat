export async function api<T>(path: string): Promise<T> {
  const response = await fetch(`http://127.0.0.1:8000${path}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export type HostSummary = {
  host: string;
  total_steps: number;
  steps: Array<{
    step: number;
    current_observed_label: string;
    current_observed_time: string;
    current_mitre_stage: string;
    forecast_next_state: string;
    forecast_probability: number;
    forecast_mitre_stage: string;
    forecast_attribution: Array<{ feature: string; value: number }>;
    actual_future_label: string;
    actual_future_time: string;
    forecast_correct: boolean;
    lead_time_seconds: number;
    metrics: Record<string, number>;
  }>;
  summary: {
    overall_forecast_accuracy: number;
    attack_forecast_accuracy: number;
    mean_lead_time_seconds: number;
  };
};

export type ReplayHost = {
  host: string;
  flow_count: number;
  replay_steps: number;
};
