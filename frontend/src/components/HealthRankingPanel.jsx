import { useState, useEffect, useMemo } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function getScoreColor(score) {
  if (score >= 90) return '#22c55e';
  if (score >= 70) return '#eab308';
  return '#ef4444';
}

function getScoreBgColor(score) {
  if (score >= 90) return 'rgba(34, 197, 94, 0.1)';
  if (score >= 70) return 'rgba(234, 179, 8, 0.1)';
  return 'rgba(239, 68, 68, 0.1)';
}

function ScoreTrendIcon({ trend }) {
  if (trend === 'up') {
    return (
      <span className="score-trend-icon" style={{ color: '#22c55e' }}>
        ↑
      </span>
    );
  }
  if (trend === 'down') {
    return (
      <span className="score-trend-icon" style={{ color: '#ef4444' }}>
        ↓
      </span>
    );
  }
  return (
    <span className="score-trend-icon" style={{ color: '#64748b' }}>
      →
    </span>
  );
}

function TrendChart({ history }) {
  if (!history || history.length === 0) {
    return <div className="health-empty">暂无历史数据</div>;
  }

  const w = 400, h = 150, pad = { t: 10, r: 10, b: 25, l: 35 };
  const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;

  const getX = (i) => pad.l + (i / Math.max(history.length - 1, 1)) * iw;
  const getY = (v) => pad.t + ih - (v / 100) * ih;

  const points = history.map((p, i) => ({
    x: getX(i),
    y: getY(p.overall_score),
    score: p.overall_score,
    time: p.snapshot_hour || p.timestamp,
  }));

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');

  const yTicks = [0, 25, 50, 75, 100];

  const formatTime = (timeStr) => {
    if (!timeStr) return '';
    const d = new Date(timeStr);
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:00`;
  };

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} style={{ maxWidth: '100%' }}>
      {yTicks.map((tick, i) => (
        <g key={i}>
          <line
            x1={pad.l}
            y1={getY(tick)}
            x2={w - pad.r}
            y2={getY(tick)}
            stroke="#1e293b"
            strokeDasharray="2,2"
          />
          <text
            x={pad.l - 5}
            y={getY(tick) + 4}
            textAnchor="end"
            fill="#64748b"
            fontSize="10"
          >
            {tick}
          </text>
        </g>
      ))}
      <path
        d={linePath}
        fill="none"
        stroke="#3b82f6"
        strokeWidth="2"
      />
      {points.map((p, i) => (
        <circle
          key={i}
          cx={p.x}
          cy={p.y}
          r="3"
          fill="#3b82f6"
        >
          <title>{`${formatTime(p.time)}: ${p.score.toFixed(1)}分`}</title>
        </circle>
      ))}
      {points.length > 0 && (
        <text
          x={points[points.length - 1].x}
          y={pad.t - 2}
          textAnchor="end"
          fill="#94a3b8"
          fontSize="10"
        >
          {formatTime(points[points.length - 1].time)}
        </text>
      )}
      {points.length > 0 && (
        <text
          x={pad.l}
          y={pad.t - 2}
          textAnchor="start"
          fill="#94a3b8"
          fontSize="10"
        >
          {formatTime(points[0].time)}
        </text>
      )}
    </svg>
  );
}

function ScoreDetailRow({ label, score, weight, rawValue }) {
  const color = getScoreColor(score);
  return (
    <div className="health-score-detail-row">
      <div className="health-score-detail-label">
        <span>{label}</span>
        <span className="health-score-weight">权重 {(weight * 100).toFixed(0)}%</span>
      </div>
      <div className="health-score-detail-value">
        <div className="health-score-bar-track">
          <div
            className="health-score-bar-fill"
            style={{ width: `${score}%`, backgroundColor: color }}
          />
        </div>
        <span className="health-score-num" style={{ color }}>
          {score.toFixed(1)}
        </span>
      </div>
      {rawValue && (
        <div className="health-score-raw">{rawValue}</div>
      )}
    </div>
  );
}

export default function HealthRankingPanel({ scores, groups }) {
  const [sortOrder, setSortOrder] = useState('asc');
  const [selectedGroupId, setSelectedGroupId] = useState(null);
  const [threshold, setThreshold] = useState('');
  const [expandedTargetId, setExpandedTargetId] = useState(null);
  const [targetDetail, setTargetDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [historyDate, setHistoryDate] = useState('');
  const [historySnapshots, setHistorySnapshots] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [selectedSnapshot, setSelectedSnapshot] = useState(null);

  const groupOptions = useMemo(() => {
    if (!groups) return [];
    return groups;
  }, [groups]);

  const filteredScores = useMemo(() => {
    if (!scores) return [];

    let result = [...scores];

    if (selectedGroupId !== null) {
      result = result.filter(s => s.group_id === selectedGroupId);
    }

    if (threshold && !isNaN(parseFloat(threshold))) {
      const t = parseFloat(threshold);
      result = result.filter(s => s.overall_score < t);
    }

    if (sortOrder === 'asc') {
      result.sort((a, b) => a.overall_score - b.overall_score);
    } else {
      result.sort((a, b) => b.overall_score - a.overall_score);
    }

    return result;
  }, [scores, sortOrder, selectedGroupId, threshold]);

  const avgScore = useMemo(() => {
    if (!scores || scores.length === 0) return 0;
    const sum = scores.reduce((acc, s) => acc + s.overall_score, 0);
    return (sum / scores.length).toFixed(1);
  }, [scores]);

  const loadTargetDetail = async (targetId) => {
    if (expandedTargetId === targetId) {
      setExpandedTargetId(null);
      setTargetDetail(null);
      return;
    }

    setExpandedTargetId(targetId);
    setLoadingDetail(true);

    try {
      const res = await fetch(`${API_BASE}/api/health/scores/${targetId}`);
      if (res.ok) {
        const data = await res.json();
        setTargetDetail(data);
      }
    } catch (e) {
      console.error('Failed to load target health detail:', e);
    } finally {
      setLoadingDetail(false);
    }
  };

  const toggleSortOrder = () => {
    setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
  };

  const loadHistorySnapshots = async () => {
    if (!historyDate) return;

    setLoadingHistory(true);
    try {
      const res = await fetch(`${API_BASE}/api/health/ranking/snapshots?date=${historyDate}&days=1`);
      if (res.ok) {
        const data = await res.json();
        setHistorySnapshots(data.snapshots || []);
      }
    } catch (e) {
      console.error('Failed to load history snapshots:', e);
    } finally {
      setLoadingHistory(false);
    }
  };

  const loadSnapshotDetail = async (snapshotId) => {
    try {
      const res = await fetch(`${API_BASE}/api/health/ranking/snapshots/${snapshotId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedSnapshot(data);
      }
    } catch (e) {
      console.error('Failed to load snapshot detail:', e);
    }
  };

  const toggleHistoryPanel = () => {
    setShowHistory(prev => !prev);
    if (!showHistory) {
      const today = new Date();
      const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
      const dateStr = yesterday.toISOString().split('T')[0];
      setHistoryDate(dateStr);
    }
  };

  return (
    <div className="health-ranking-panel">
      <div className="health-ranking-header">
        <h3 className="health-ranking-title">健康评分排行榜</h3>
        <div className="health-ranking-actions">
          <button className="health-history-btn" onClick={toggleHistoryPanel}>
            {showHistory ? '关闭历史' : '📜 历史快照'}
          </button>
        </div>
      </div>

      {showHistory && (
        <div className="health-history-panel">
          <div className="health-history-controls">
            <div className="health-filter-item">
              <label>选择日期:</label>
              <input
                type="date"
                value={historyDate}
                onChange={(e) => setHistoryDate(e.target.value)}
                className="health-filter-input"
              />
            </div>
            <button
              className="health-sort-btn"
              onClick={loadHistorySnapshots}
              disabled={loadingHistory}
            >
              {loadingHistory ? '加载中...' : '查询'}
            </button>
          </div>

          <div className="health-history-list">
            {loadingHistory ? (
              <div className="health-loading">加载中...</div>
            ) : historySnapshots.length === 0 ? (
              <div className="health-empty">该日期暂无快照数据</div>
            ) : (
              <div className="health-snapshot-list">
                {historySnapshots.map((snapshot) => (
                  <div
                    key={snapshot.id}
                    className="health-snapshot-item"
                    onClick={() => loadSnapshotDetail(snapshot.id)}
                  >
                    <span className="health-snapshot-time">
                      {new Date(snapshot.snapshot_time).toLocaleString('zh-CN')}
                    </span>
                    <span className="health-snapshot-info">
                      共 {snapshot.total_targets} 个目标
                    </span>
                    <span className="health-snapshot-avg" style={{ color: getScoreColor(snapshot.avg_score) }}>
                      均分: {snapshot.avg_score?.toFixed(1) || '-'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {selectedSnapshot && (
            <div className="health-snapshot-detail">
              <div className="health-snapshot-detail-header">
                <h4>快照详情 - {new Date(selectedSnapshot.snapshot_time).toLocaleString('zh-CN')}</h4>
                <button
                  className="health-close-btn"
                  onClick={() => setSelectedSnapshot(null)}
                >
                  ✕
                </button>
              </div>
              <div className="health-snapshot-ranking">
                {selectedSnapshot.ranking_data && selectedSnapshot.ranking_data.map((item, index) => (
                  <div key={item.target_id} className="health-snapshot-rank-item">
                    <span className="health-snapshot-rank-num">{index + 1}</span>
                    <span className="health-snapshot-rank-name">{item.target_name}</span>
                    <span
                      className="health-snapshot-rank-score"
                      style={{ color: getScoreColor(item.overall_score) }}
                    >
                      {item.overall_score?.toFixed(1)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="health-ranking-stats">
        <span className="health-stat">
          总数: <strong>{scores ? scores.length : 0}</strong>
        </span>
        <span className="health-stat">
          平均分: <strong style={{ color: getScoreColor(avgScore) }}>{avgScore}</strong>
        </span>
      </div>

      <div className="health-ranking-filters">
        <div className="health-filter-item">
          <label>排序:</label>
          <button
            className="health-sort-btn"
            onClick={toggleSortOrder}
          >
            {sortOrder === 'asc' ? '低分优先 ↑↓' : '高分优先 ↓↑'}
          </button>
        </div>

        <div className="health-filter-item">
          <label>分组:</label>
          <select
            value={selectedGroupId ?? ''}
            onChange={(e) => setSelectedGroupId(e.target.value ? parseInt(e.target.value) : null)}
            className="health-filter-select"
          >
            <option value="">全部分组</option>
            {groupOptions.map(g => (
              <option key={g.id} value={g.id}>{g.name}</option>
            ))}
          </select>
        </div>

        <div className="health-filter-item">
          <label>低于阈值:</label>
          <input
            type="number"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            placeholder="如: 70"
            className="health-filter-input"
            min="0"
            max="100"
          />
        </div>
      </div>

      <div className="health-ranking-list">
        {filteredScores.length === 0 ? (
          <div className="health-empty">暂无数据</div>
        ) : (
          filteredScores.map((score, index) => (
            <div key={score.id} className="health-ranking-item">
              <div
                className="health-ranking-row"
                onClick={() => loadTargetDetail(score.target_id)}
              >
                <div className="health-rank-num">
                  {index + 1}
                </div>

                <div className="health-rank-info">
                  <div className="health-target-name">{score.target_name}</div>
                  <div className="health-group-name">{score.group_name || '未分组'}</div>
                </div>

                <div className="health-rank-score">
                  <div
                    className="health-score-badge"
                    style={{
                      backgroundColor: getScoreBgColor(score.overall_score),
                      color: getScoreColor(score.overall_score),
                    }}
                  >
                    {score.overall_score.toFixed(1)}
                  </div>
                  <ScoreTrendIcon trend={score.score_trend} />
                </div>

                <div className="health-rank-expand-icon">
                  {expandedTargetId === score.target_id ? '−' : '+'}
                </div>
              </div>

              {expandedTargetId === score.target_id && (
                <div className="health-ranking-detail">
                  {loadingDetail ? (
                    <div className="health-loading">加载中...</div>
                  ) : targetDetail ? (
                    <div className="health-detail-content">
                      <div className="health-detail-section">
                        <h4>评分明细</h4>
                        <ScoreDetailRow
                          label="可用率 (7天)"
                          score={score.availability_score}
                          weight={0.4}
                          rawValue={`${score.availability_7d?.toFixed(2) || 0}%`}
                        />
                        <ScoreDetailRow
                          label="响应延迟"
                          score={score.latency_score}
                          weight={0.2}
                          rawValue={`${score.avg_latency_ms?.toFixed(0) || 0}ms`}
                        />
                        <ScoreDetailRow
                          label="告警次数 (7天)"
                          score={score.alert_score}
                          weight={0.2}
                          rawValue={`${score.alert_count_7d || 0}次`}
                        />
                        <ScoreDetailRow
                          label="连续稳定运行"
                          score={score.stability_score}
                          weight={0.2}
                          rawValue={`${score.consecutive_healthy_hours || 0}小时`}
                        />
                      </div>

                      <div className="health-detail-section">
                        <h4>7天评分趋势</h4>
                        <TrendChart history={targetDetail.history_7d || []} />
                      </div>
                    </div>
                  ) : (
                    <div className="health-empty">暂无详情数据</div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      <style>{`
        .health-ranking-panel {
          background: #0f172a;
          border: 1px solid #1e293b;
          border-radius: 8px;
          padding: 16px;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          color: #f1f5f9;
        }

        .health-ranking-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }

        .health-ranking-actions {
          display: flex;
          gap: 8px;
        }

        .health-ranking-title {
          margin: 0;
          font-size: 16px;
          font-weight: 600;
          color: #f1f5f9;
        }

        .health-ranking-stats {
          display: flex;
          gap: 16px;
          font-size: 13px;
          color: #94a3b8;
        }

        .health-ranking-filters {
          display: flex;
          gap: 12px;
          margin-bottom: 16px;
          padding-bottom: 12px;
          border-bottom: 1px solid #1e293b;
          flex-wrap: wrap;
        }

        .health-filter-item {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          color: #94a3b8;
        }

        .health-filter-select,
        .health-filter-input {
          background: #1e293b;
          border: 1px solid #334155;
          color: #f1f5f9;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
        }

        .health-sort-btn {
          background: #1e293b;
          border: 1px solid #334155;
          color: #f1f5f9;
          padding: 4px 10px;
          border-radius: 4px;
          font-size: 12px;
          cursor: pointer;
        }

        .health-sort-btn:hover {
          background: #334155;
        }

        .health-ranking-list {
          max-height: 500px;
          overflow-y: auto;
        }

        .health-ranking-item {
          border-bottom: 1px solid #1e293b;
        }

        .health-ranking-item:last-child {
          border-bottom: none;
        }

        .health-ranking-row {
          display: flex;
          align-items: center;
          padding: 10px 8px;
          cursor: pointer;
          gap: 12px;
        }

        .health-ranking-row:hover {
          background: rgba(59, 130, 246, 0.05);
        }

        .health-rank-num {
          width: 30px;
          text-align: center;
          font-weight: 600;
          color: #64748b;
          font-size: 14px;
        }

        .health-rank-info {
          flex: 1;
          min-width: 0;
        }

        .health-target-name {
          font-size: 14px;
          font-weight: 500;
          color: #f1f5f9;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .health-group-name {
          font-size: 12px;
          color: #64748b;
          margin-top: 2px;
        }

        .health-rank-score {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .health-score-badge {
          padding: 4px 10px;
          border-radius: 12px;
          font-weight: 600;
          font-size: 14px;
          min-width: 55px;
          text-align: center;
        }

        .score-trend-icon {
          font-size: 16px;
          font-weight: bold;
        }

        .health-rank-expand-icon {
          width: 20px;
          text-align: center;
          color: #64748b;
          font-size: 18px;
        }

        .health-ranking-detail {
          padding: 0 12px 16px 50px;
          background: rgba(15, 23, 42, 0.5);
        }

        .health-detail-content {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
        }

        .health-detail-section h4 {
          margin: 0 0 12px 0;
          font-size: 13px;
          font-weight: 600;
          color: #94a3b8;
        }

        .health-score-detail-row {
          margin-bottom: 10px;
        }

        .health-score-detail-label {
          display: flex;
          justify-content: space-between;
          margin-bottom: 4px;
          font-size: 12px;
          color: #94a3b8;
        }

        .health-score-weight {
          color: #64748b;
        }

        .health-score-detail-value {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .health-score-bar-track {
          flex: 1;
          height: 6px;
          background: #1e293b;
          border-radius: 3px;
          overflow: hidden;
        }

        .health-score-bar-fill {
          height: 100%;
          border-radius: 3px;
          transition: width 0.3s ease;
        }

        .health-score-num {
          min-width: 40px;
          text-align: right;
          font-weight: 600;
          font-size: 13px;
        }

        .health-score-raw {
          font-size: 11px;
          color: #64748b;
          margin-top: 2px;
        }

        .health-empty,
        .health-loading {
          text-align: center;
          padding: 20px;
          color: #64748b;
          font-size: 13px;
        }

        .health-history-btn {
          background: #1e293b;
          border: 1px solid #334155;
          color: #f1f5f9;
          padding: 6px 12px;
          border-radius: 6px;
          font-size: 12px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .health-history-btn:hover {
          background: #334155;
        }

        .health-history-panel {
          background: rgba(30, 41, 59, 0.5);
          border: 1px solid #334155;
          border-radius: 8px;
          padding: 12px;
          margin-bottom: 16px;
        }

        .health-history-controls {
          display: flex;
          gap: 12px;
          align-items: center;
          margin-bottom: 12px;
          flex-wrap: wrap;
        }

        .health-snapshot-list {
          max-height: 200px;
          overflow-y: auto;
        }

        .health-snapshot-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 12px;
          background: #0f172a;
          border: 1px solid #1e293b;
          border-radius: 6px;
          margin-bottom: 6px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .health-snapshot-item:hover {
          background: #1e293b;
          border-color: #334155;
        }

        .health-snapshot-time {
          font-size: 13px;
          color: #f1f5f9;
        }

        .health-snapshot-info {
          font-size: 12px;
          color: #94a3b8;
        }

        .health-snapshot-avg {
          font-size: 13px;
          font-weight: 600;
        }

        .health-snapshot-detail {
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid #334155;
        }

        .health-snapshot-detail-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 10px;
        }

        .health-snapshot-detail-header h4 {
          margin: 0;
          font-size: 13px;
          color: #f1f5f9;
        }

        .health-close-btn {
          background: none;
          border: none;
          color: #64748b;
          cursor: pointer;
          font-size: 16px;
          padding: 2px 8px;
          border-radius: 4px;
        }

        .health-close-btn:hover {
          background: #1e293b;
          color: #f1f5f9;
        }

        .health-snapshot-ranking {
          max-height: 300px;
          overflow-y: auto;
        }

        .health-snapshot-rank-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 6px 8px;
          border-bottom: 1px solid #1e293b;
        }

        .health-snapshot-rank-num {
          width: 24px;
          text-align: center;
          font-weight: 600;
          color: #64748b;
          font-size: 12px;
        }

        .health-snapshot-rank-name {
          flex: 1;
          font-size: 12px;
          color: #94a3b8;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .health-snapshot-rank-score {
          font-weight: 600;
          font-size: 12px;
          min-width: 45px;
          text-align: right;
        }

        @media (max-width: 600px) {
          .health-detail-content {
            grid-template-columns: 1fr;
          }

          .health-ranking-filters {
            flex-direction: column;
          }
        }
      `}</style>
    </div>
  );
}
