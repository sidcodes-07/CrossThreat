import React, { useEffect, useState } from 'react';
import './ModelComparisonPanel.css';

interface Model {
  id: string;
  name: string;
  type: string;
  parameters: number;
  inference_latency_ms: number;
  overall_accuracy: number;
  attack_recall: number;
  macro_f1: number;
  benign_precision: number;
  status_badge: {
    color: string;
    text: string;
  };
  verdict: string;
  recommended: boolean;
}

interface ComparisonData {
  timestamp: string;
  dataset: string;
  models: Model[];
  caveat: string;
}

const ModelComparisonPanel: React.FC = () => {
  const [data, setData] = useState<ComparisonData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/models/comparison');
        if (!response.ok) {
          throw new Error(`Failed to fetch model comparison: ${response.statusText}`);
        }
        const json = await response.json();
        setData(json);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return <div className="model-comparison loading">Loading model comparison...</div>;
  }

  if (error) {
    return <div className="model-comparison error">Error: {error}</div>;
  }

  if (!data) {
    return <div className="model-comparison error">No data available</div>;
  }

  const getBadgeColor = (color: string): string => {
    switch (color) {
      case 'green':
        return '#10b981';
      case 'yellow':
        return '#f59e0b';
      case 'red':
        return '#ef4444';
      default:
        return '#6b7280';
    }
  };

  return (
    <div className="model-comparison">
      <div className="comparison-header">
        <h2>Model Comparison Panel</h2>
        <p className="dataset-info">Dataset: {data.dataset}</p>
      </div>

      <div className="caveat-section">
        <p className="caveat-text">⚠️ {data.caveat}</p>
      </div>

      <div className="models-grid">
        {data.models.map((model) => (
          <div
            key={model.id}
            className={`model-card ${model.recommended ? 'recommended' : ''}`}
          >
            {model.recommended && <div className="recommended-badge">✓ Recommended</div>}

            <div className="card-header">
              <h3>{model.name}</h3>
              <span className="model-type">{model.type}</span>
            </div>

            <div className="model-specs">
              <div className="spec-row">
                <span className="spec-label">Parameters:</span>
                <span className="spec-value">{(model.parameters / 1000).toFixed(0)}K</span>
              </div>
              <div className="spec-row">
                <span className="spec-label">Inference Latency:</span>
                <span className="spec-value">{(model.inference_latency_ms * 1000).toFixed(2)}μs</span>
              </div>
            </div>

            <div className="metrics-section">
              <div className="metric large">
                <span className="metric-label">Overall Accuracy</span>
                <span className="metric-value">
                  {(model.overall_accuracy * 100).toFixed(1)}%
                </span>
              </div>

              <div className="metric">
                <span className="metric-label">Attack Recall</span>
                <span className="metric-value">
                  {(model.attack_recall * 100).toFixed(1)}%
                </span>
              </div>

              <div className="metric">
                <span className="metric-label">Macro F1</span>
                <span className="metric-value">
                  {model.macro_f1.toFixed(4)}
                </span>
              </div>

              <div className="metric">
                <span className="metric-label">Benign Precision</span>
                <span className="metric-value">
                  {(model.benign_precision * 100).toFixed(1)}%
                </span>
              </div>
            </div>

            <div className="status-section">
              <div
                className="status-badge"
                style={{ backgroundColor: getBadgeColor(model.status_badge.color) }}
              >
                {model.status_badge.text}
              </div>
            </div>

            <div className="verdict-section">
              <p className="verdict-text">{model.verdict}</p>
            </div>

            {!model.recommended && (
              <div className="limitations">
                <p>⚠️ Not recommended for production use</p>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="footer-info">
        <p>Last updated: {new Date(data.timestamp).toLocaleString()}</p>
      </div>
    </div>
  );
};

export default ModelComparisonPanel;
