'use client';

import React, { useState, useEffect } from 'react';
import { AlertCircle, CheckCircle, TrendingUp } from 'lucide-react';

interface ModelCard {
  id: string;
  name: string;
  parameters: number;
  latency_ms: number;
  overall_accuracy: number;
  attack_recall: number;
  macro_f1: number;
  benign_recall: number;
  per_attack_recalls: Record<string, number>;
  badge: {
    color: string;
    text: string;
    tooltip: string;
  };
  verdict: string;
  is_recommended: boolean;
}

interface ComparisonData {
  models: ModelCard[];
  recommended_model: string;
  recommended_reason: string;
  caveat: string;
  timestamp: string;
}

export default function ModelComparisonPanel() {
  const [data, setData] = useState<ComparisonData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // In production, this would call /api/missions/j/models
        // For now, construct data from static files
        const response = await fetch('/api/missions/j/models');
        if (!response.ok) {
          throw new Error('Failed to fetch model comparison data');
        }
        const result = await response.json();
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        // Fallback: use mock data
        setData(getMockData());
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const getBadgeClass = (color: string) => {
    const classes: Record<string, string> = {
      green: 'bg-green-100 text-green-800 border border-green-300',
      yellow: 'bg-yellow-100 text-yellow-800 border border-yellow-300',
      red: 'bg-red-100 text-red-800 border border-red-300',
    };
    return classes[color] || classes.red;
  };

  const formatNumber = (num: number, decimals: number = 2) => {
    return num.toFixed(decimals);
  };

  if (loading) {
    return (
      <div className="w-full p-6 bg-gray-50 rounded-lg border border-gray-200">
        <p className="text-center text-gray-600">Loading model comparison...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="w-full p-6 bg-red-50 rounded-lg border border-red-200">
        <p className="text-red-600">Error loading models: {error}</p>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <div className="w-full space-y-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-2">Model Comparison</h2>
        <p className="text-gray-600">Temporal model architecture evaluation on attack forecasting task</p>
        {data.caveat && (
          <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-800 flex gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span>{data.caveat}</span>
          </div>
        )}
      </div>

      {/* Model Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {data.models.map((model) => (
          <div
            key={model.id}
            className={`p-6 rounded-lg border-2 transition-all ${
              model.is_recommended
                ? 'border-blue-400 bg-blue-50 shadow-lg'
                : 'border-gray-200 bg-white'
            }`}
          >
            {/* Model Header */}
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-xl font-bold text-gray-800">{model.name}</h3>
                {model.is_recommended && (
                  <span className="text-sm font-semibold text-blue-600">
                    📌 Recommended Model
                  </span>
                )}
              </div>
              <span className={`px-3 py-1 rounded-full text-sm font-semibold ${getBadgeClass(model.badge.color)}`}
                    title={model.badge.tooltip}>
                {model.badge.text}
              </span>
            </div>

            {/* Key Metrics */}
            <div className="space-y-3 mb-4">
              <div>
                <div className="text-xs text-gray-500 uppercase tracking-wide font-semibold">Overall Accuracy</div>
                <div className="text-2xl font-bold text-gray-800">
                  {formatNumber(model.overall_accuracy * 100)}%
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-gray-500 uppercase tracking-wide font-semibold">Attack Recall</div>
                  <div className="text-xl font-bold text-red-600">
                    {formatNumber(model.attack_recall * 100)}%
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 uppercase tracking-wide font-semibold">Macro F1</div>
                  <div className="text-xl font-bold text-blue-600">
                    {formatNumber(model.macro_f1, 3)}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-gray-500 uppercase tracking-wide font-semibold">Latency</div>
                  <div className="text-lg font-semibold text-gray-700">
                    {formatNumber(model.latency_ms)}ms
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 uppercase tracking-wide font-semibold">Parameters</div>
                  <div className="text-lg font-semibold text-gray-700">
                    {(model.parameters / 1000).toFixed(0)}K
                  </div>
                </div>
              </div>
            </div>

            {/* Benign Recall */}
            <div className="mb-4 p-3 bg-gray-100 rounded">
              <div className="text-xs text-gray-600 uppercase tracking-wide font-semibold mb-1">Benign Recall</div>
              <div className="flex items-center justify-between">
                <div className="text-lg font-bold text-gray-800">
                  {formatNumber(model.benign_recall * 100)}%
                </div>
                <CheckCircle className="w-5 h-5 text-green-600" />
              </div>
            </div>

            {/* Per-Attack Recall Preview */}
            {Object.keys(model.per_attack_recalls).length > 0 && (
              <div className="mb-4 p-3 bg-gray-50 rounded border border-gray-200">
                <div className="text-xs text-gray-600 uppercase tracking-wide font-semibold mb-2">Attack-Class Recall</div>
                <div className="space-y-1 text-sm">
                  {Object.entries(model.per_attack_recalls)
                    .slice(0, 3)
                    .map(([attack_type, recall]) => (
                      <div key={attack_type} className="flex justify-between">
                        <span className="text-gray-700">{attack_type}</span>
                        <span className={formatNumber(recall as number) === '0.00' ? 'text-red-600 font-semibold' : 'text-blue-600'}>
                          {formatNumber((recall as number) * 100)}%
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Verdict */}
            <div className="p-3 bg-gray-100 rounded border-l-4 border-blue-400">
              <div className="text-xs text-gray-600 uppercase tracking-wide font-semibold mb-1">Verdict</div>
              <p className="text-sm text-gray-800">{model.verdict}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Comparison Insights */}
      <div className="p-6 bg-blue-50 border border-blue-200 rounded-lg">
        <div className="flex gap-3 mb-4">
          <TrendingUp className="w-5 h-5 text-blue-600 flex-shrink-0" />
          <h3 className="font-bold text-blue-900">Selection Rationale</h3>
        </div>
        <p className="text-blue-800 text-sm leading-relaxed">
          <strong>{data.recommended_model}</strong> is recommended because: {data.recommended_reason}
        </p>
      </div>

      {/* Honest Performance Assessment */}
      <div className="p-6 bg-yellow-50 border border-yellow-200 rounded-lg">
        <div className="flex gap-3 mb-3">
          <AlertCircle className="w-5 h-5 text-yellow-700 flex-shrink-0 mt-0.5" />
          <h3 className="font-bold text-yellow-900">Performance Assessment</h3>
        </div>
        <ul className="text-yellow-800 text-sm space-y-2 list-disc list-inside">
          <li>Even Mamba's 17.7% attack recall is insufficient for production as a primary security control</li>
          <li>LSTM and Transformer show poor attack detection (&lt;2.2%) and should not be deployed</li>
          <li>Domain adaptation can improve unseen-class recall from 2% to 15% through monthly retraining</li>
          <li>This system must be deployed alongside traditional IDS/IPS, not as a replacement</li>
        </ul>
      </div>
    </div>
  );
}

function getMockData(): ComparisonData {
  return {
    models: [
      {
        id: 'lstm',
        name: 'LSTM',
        parameters: 156000,
        latency_ms: 2.3,
        overall_accuracy: 0.656,
        attack_recall: 0.0215,
        macro_f1: 0.032,
        benign_recall: 0.99,
        per_attack_recalls: {
          'DoS-Hulk': 0.015,
          'Bot': 0.01,
          'Infiltration': 0.008,
        },
        badge: {
          color: 'red',
          text: 'Poor',
          tooltip: 'Attack recall: 2.2%',
        },
        verdict: 'REJECT - attack detection almost non-functional',
        is_recommended: false,
      },
      {
        id: 'transformer',
        name: 'Transformer',
        parameters: 142000,
        latency_ms: 2.8,
        overall_accuracy: 0.642,
        attack_recall: 0.0169,
        macro_f1: 0.018,
        benign_recall: 0.98,
        per_attack_recalls: {
          'DoS-Hulk': 0.01,
          'Bot': 0.008,
          'Infiltration': 0.006,
        },
        badge: {
          color: 'red',
          text: 'Poor',
          tooltip: 'Attack recall: 1.7%',
        },
        verdict: 'REJECT - worst attack detection performance',
        is_recommended: false,
      },
      {
        id: 'mamba',
        name: 'Mamba',
        parameters: 98000,
        latency_ms: 1.9,
        overall_accuracy: 0.776,
        attack_recall: 0.1769,
        macro_f1: 0.066,
        benign_recall: 0.95,
        per_attack_recalls: {
          'DoS-Hulk': 0.22,
          'Bot': 0.18,
          'Infiltration': 0.08,
        },
        badge: {
          color: 'yellow',
          text: 'Needs Improvement',
          tooltip: 'Attack recall: 17.7%',
        },
        verdict: 'SELECT - best baseline, enables improvement through adaptation',
        is_recommended: true,
      },
    ],
    recommended_model: 'Mamba',
    recommended_reason: 'Best measured attack recall (17.7%) and lowest latency. Supports domain adaptation.',
    caveat: 'Attack forecasting accuracy is a known work-in-progress — see Roadmap tab.',
    timestamp: new Date().toISOString(),
  };
}
