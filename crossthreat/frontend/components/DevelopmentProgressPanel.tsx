import React, { useEffect, useState } from 'react';
import './DevelopmentProgressPanel.css';

interface Mission {
  id: string;
  name: string;
  status: string;
  key_finding: string;
  order: number;
}

interface MissionsData {
  timestamp: string;
  total_missions: number;
  completed: number;
  missions: Mission[];
}

interface MissionDetails {
  [key: string]: any;
}

const DevelopmentProgressPanel: React.FC = () => {
  const [missionsData, setMissionsData] = useState<MissionsData | null>(null);
  const [expandedMission, setExpandedMission] = useState<string | null>(null);
  const [missionDetails, setMissionDetails] = useState<MissionDetails>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchMissions = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/missions/summary');
        if (!response.ok) {
          throw new Error(`Failed to fetch missions: ${response.statusText}`);
        }
        const json = await response.json();
        setMissionsData(json);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchMissions();
  }, []);

  const handleExpandMission = async (missionId: string) => {
    if (expandedMission === missionId) {
      setExpandedMission(null);
      return;
    }

    if (missionDetails[missionId]) {
      setExpandedMission(missionId);
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/missions/${missionId}/details`);
      if (!response.ok) {
        throw new Error(`Failed to fetch mission details: ${response.statusText}`);
      }
      const json = await response.json();
      setMissionDetails((prev) => ({ ...prev, [missionId]: json }));
      setExpandedMission(missionId);
    } catch (err) {
      console.error('Error fetching mission details:', err);
    }
  };

  if (loading) {
    return <div className="development-progress loading">Loading development progress...</div>;
  }

  if (error) {
    return <div className="development-progress error">Error: {error}</div>;
  }

  if (!missionsData) {
    return <div className="development-progress error">No data available</div>;
  }

  return (
    <div className="development-progress">
      <div className="progress-header">
        <h2>Development Progress</h2>
        <div className="progress-stats">
          <span className="stat">
            {missionsData.completed} of {missionsData.total_missions} Missions Complete
          </span>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{
                width: `${(missionsData.completed / missionsData.total_missions) * 100}%`,
              }}
            ></div>
          </div>
        </div>
      </div>

      <div className="missions-timeline">
        {missionsData.missions.map((mission) => (
          <div key={mission.id} className="timeline-item">
            <div className="timeline-marker">
              <span className="mission-number">{mission.order}</span>
              {mission.order < missionsData.missions.length && (
                <div className="timeline-line"></div>
              )}
            </div>

            <div className="mission-card">
              <div
                className="mission-card-header"
                onClick={() => handleExpandMission(mission.id)}
                style={{ cursor: 'pointer' }}
              >
                <div className="mission-title-section">
                  <h3>{mission.name}</h3>
                  <span className="status-badge complete">✓ {mission.status}</span>
                </div>
                <button className="expand-button">
                  {expandedMission === mission.id ? '▼' : '▶'}
                </button>
              </div>

              <p className="mission-finding">{mission.key_finding}</p>

              {expandedMission === mission.id && missionDetails[mission.id] && (
                <div className="mission-details">
                  <MissionDetailsContent mission={mission} details={missionDetails[mission.id]} />
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="footer-info">
        <p>Last updated: {new Date(missionsData.timestamp).toLocaleString()}</p>
        <p className="roadmap-link">See Roadmap tab for future improvements</p>
      </div>
    </div>
  );
};

interface MissionDetailsContentProps {
  mission: Mission;
  details: MissionDetails;
}

const MissionDetailsContent: React.FC<MissionDetailsContentProps> = ({ mission, details }) => {
  switch (mission.id) {
    case 'd':
      return (
        <div className="details-content">
          <h4>Model Architecture Comparison</h4>
          <p>
            Tested three temporal models on CIC-IDS2018 dataset with 5-element sliding windows.
            Focal Loss LSTM achieved significant improvement in attack recall.
          </p>
          <div className="details-table">
            <table>
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Attack Recall</th>
                  <th>Overall Accuracy</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>LSTM (Focal Loss)</td>
                  <td>80.5%</td>
                  <td>28.2%</td>
                  <td>✓ Recommended</td>
                </tr>
                <tr>
                  <td>LSTM (Baseline)</td>
                  <td>0.0%</td>
                  <td>91.6%</td>
                  <td>✗ Failed</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      );

    case 'e':
      return (
        <div className="details-content">
          <h4>Confusion Matrix & Per-Class Verification</h4>
          <p>Full confusion matrices generated and verified against ground truth.</p>
          <div className="details-metrics">
            <div className="metric-box">
              <span className="metric-label">Test Set Accuracy</span>
              <span className="metric-value">28.2%</span>
            </div>
            <div className="metric-box">
              <span className="metric-label">OOD (CIC-IDS2017) Accuracy</span>
              <span className="metric-value">19.9%</span>
            </div>
            <div className="metric-box">
              <span className="metric-label">Correctly Predicted Attacks</span>
              <span className="metric-value">79</span>
            </div>
            <div className="metric-box">
              <span className="metric-label">Classes with Zero Recall</span>
              <span className="metric-value">8</span>
            </div>
          </div>
        </div>
      );

    case 'f':
      return (
        <div className="details-content">
          <h4>Attack Severity / Network-Layer Classification</h4>
          <p>Mapped each attack type to OSI layers and security controls.</p>
          <div className="attack-mapping">
            <div className="mapping-item">
              <strong>DoS/DDoS:</strong> Network/Transport Layer → Firewall, IDS/IPS
            </div>
            <div className="mapping-item">
              <strong>Brute Force:</strong> Application Layer → WAF, Rate limiting, Account lockout
            </div>
            <div className="mapping-item">
              <strong>SQL Injection:</strong> Application Layer → WAF, Parameterized queries
            </div>
            <div className="mapping-item">
              <strong>Infiltration:</strong> Application/Session Layer → Endpoint detection, Network monitoring
            </div>
          </div>
        </div>
      );

    case 'g':
      return (
        <div className="details-content">
          <h4>Feature Dependency & Importance Analysis</h4>
          <p>Analyzed 12 input features using correlation, mutual information, and permutation importance.</p>
          <div className="feature-categories">
            <div className="feature-category">
              <h5>Load-Bearing Features</h5>
              <ul>
                <li>Flow Bytes/sec</li>
                <li>Flow Packets/sec</li>
                <li>Forward Packet Count</li>
              </ul>
            </div>
            <div className="feature-category">
              <h5>Redundant Features (>0.85 correlation)</h5>
              <ul>
                <li>Backward PSH Flags</li>
                <li>Backward URG Flags</li>
              </ul>
            </div>
          </div>
        </div>
      );

    case 'h':
      return (
        <div className="details-content">
          <h4>Ground-Truth Correspondence Check</h4>
          <p>Verified that model predictions align with CIC-IDS2018 documented attack scenarios.</p>
          <div className="verification-summary">
            <p>✓ 79 correctly predicted attacks verified against ground truth</p>
            <p>✓ Predictions align with documented attack timing and types</p>
            <p>✓ No train/test leakage detected</p>
          </div>
        </div>
      );

    case 'i':
      return (
        <div className="details-content">
          <h4>Dataset Landscape Justification</h4>
          <p>CIC-IDS2018 selected for its day-by-day attack scheduling enabling temporal forecasting.</p>
          <div className="dataset-comparison">
            <div className="dataset-card selected">
              <strong>CIC-IDS2018 (Selected)</strong>
              <ul>
                <li>20K network flows</li>
                <li>Day-by-day attack scheduling</li>
                <li>Real temporal sequences</li>
              </ul>
            </div>
            <div className="dataset-card">
              <strong>NSL-KDD (Not Selected)</strong>
              <ul>
                <li>1999-era traffic</li>
                <li>Outdated attack patterns</li>
                <li>Limited temporal context</li>
              </ul>
            </div>
          </div>
        </div>
      );

    default:
      return <div className="details-content">Mission details not available</div>;
  }
};

export default DevelopmentProgressPanel;
