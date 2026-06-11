import { useState, useEffect, useMemo, useRef } from 'react';
import LatencyChart from './LatencyChart';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function SnapshotPlayer({ snapshot, onClose }) {
  const [timelineData, setTimelineData] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [selectedTarget, setSelectedTarget] = useState(null);
  const [targetStats, setTargetStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef(null);

  useEffect(() => {
    loadTimeline();
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [snapshot.id]);

  const loadTimeline = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/snapshots/${snapshot.id}/timeline`);
      if (res.ok) {
        const data = await res.json();
        setTimelineData(data);
        setCurrentIndex(0);
      }
    } catch (e) {
      console.error('Failed to load timeline:', e);
    } finally {
      setLoading(false);
    }
  };

  const loadTargetStats = async (targetName) => {
    try {
      const res = await fetch(`${API_BASE}/api/snapshots/${snapshot.id}/targets/${encodeURIComponent(targetName)}/stats`);
      if (res.ok) {
        const data = await res.json();
        setTargetStats(data);
      }
    } catch (e) {
      console.error('Failed to load target stats:', e);
    }
  };

  const timestamps = useMemo(() => {
    if (!timelineData || !timelineData.timeline) return [];
    return Object.keys(timelineData.timeline).sort();
  }, [timelineData]);

  const currentTimestamp = useMemo(() => {
    return timestamps[currentIndex] || null;
  }, [timestamps, currentIndex]);

  const currentTargets = useMemo(() => {
    if (!timelineData || !timelineData.timeline || !currentTimestamp) return {};
    return timelineData.timeline[currentTimestamp] || {};
  }, [timelineData, currentTimestamp]);

  const alertsAtCurrentTime = useMemo(() => {
    if (!timelineData || !timelineData.alerts || !currentTimestamp) return [];
    const currentTime = new Date(currentTimestamp).getTime();
    return timelineData.alerts.filter(a => {
      const alertTime = new Date(a.timestamp).getTime();
      return Math.abs(alertTime - currentTime) < 60000;
    });
  }, [timelineData, currentTimestamp]);

  const targetNames = useMemo(() => {
    const names = new Set();
    if (timelineData && timelineData.timeline) {
      Object.values(timelineData.timeline).forEach(targets => {
        Object.keys(targets).forEach(name => names.add(name));
      });
    }
    return Array.from(names).sort();
  }, [timelineData]);

  const statusCounts = useMemo(() => {
    const counts = { healthy: 0, degraded: 0, down: 0 };
    Object.values(currentTargets).forEach(target => {
      if (target.status && counts[target.status] !== undefined) {
        counts[target.status]++;
      }
    });
    return counts;
  }, [currentTargets]);

  useEffect(() => {
    if (isPlaying && timestamps.length > 0) {
      timerRef.current = setInterval(() => {
        setCurrentIndex(prev => {
          if (prev >= timestamps.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 500 / playbackSpeed);
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [isPlaying, playbackSpeed, timestamps.length]);

  const handlePlayPause = () => {
    if (currentIndex >= timestamps.length - 1) {
      setCurrentIndex(0);
    }
    setIsPlaying(!isPlaying);
  };

  const handleSeek = (e) => {
    const index = parseInt(e.target.value);
    setCurrentIndex(index);
  };

  const handleSpeedChange = (speed) => {
    setPlaybackSpeed(speed);
  };

  const formatTime = (isoString) => {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const formatTimeShort = (isoString) => {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case 'healthy': return '健康';
      case 'degraded': return '降级';
      case 'down': return '故障';
      default: return status;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return '#22c55e';
      case 'degraded': return '#f59e0b';
      case 'down': return '#ef4444';
      default: return '#64748b';
    }
  };

  const handleTargetClick = (targetName) => {
    setSelectedTarget(targetName);
    loadTargetStats(targetName);
  };

  const progressPercent = timestamps.length > 0 ? (currentIndex / (timestamps.length - 1)) * 100 : 0;

  return (
    <div className="modal-overlay snapshot-player-overlay" onClick={onClose}>
      <div className="modal-content snapshot-player-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2>▶️ 快照回放</h2>
            <div className="snapshot-info">
              <span className="snapshot-name">{snapshot.name}</span>
              {snapshot.description && (
                <span className="snapshot-desc"> · {snapshot.description}</span>
              )}
            </div>
          </div>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        {loading ? (
          <div className="loading-state">加载时间轴数据...</div>
        ) : !timelineData ? (
          <div className="empty-state">无法加载快照数据</div>
        ) : (
          <>
            <div className="player-stats-bar">
              <div className="stat-item">
                <span className="stat-label">当前时间</span>
                <span className="stat-value time-value">{formatTime(currentTimestamp)}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">健康</span>
                <span className="stat-value" style={{ color: '#22c55e' }}>{statusCounts.healthy}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">降级</span>
                <span className="stat-value" style={{ color: '#f59e0b' }}>{statusCounts.degraded}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">故障</span>
                <span className="stat-value" style={{ color: '#ef4444' }}>{statusCounts.down}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">进度</span>
                <span className="stat-value">{currentIndex + 1} / {timestamps.length}</span>
              </div>
            </div>

            {alertsAtCurrentTime.length > 0 && (
              <div className="player-alerts">
                {alertsAtCurrentTime.map((alert, i) => (
                  <div key={i} className={`player-alert ${alert.to_status}`}>
                    ⚠️ {alert.target_name}: {alert.from_status} → {alert.to_status}
                    <span className="alert-time">{formatTimeShort(alert.timestamp)}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="player-timeline-container">
              <div className="timeline-track">
                <div
                  className="timeline-progress"
                  style={{ width: `${progressPercent}%` }}
                />
                <input
                  type="range"
                  min="0"
                  max={timestamps.length - 1}
                  value={currentIndex}
                  onChange={handleSeek}
                  className="timeline-slider"
                />
                {timestamps.map((ts, i) => {
                  const targets = timelineData.timeline[ts] || {};
                  const hasAlert = timelineData.alerts.some(a =>
                    Math.abs(new Date(a.timestamp).getTime() - new Date(ts).getTime()) < 30000
                  );
                  const hasDown = Object.values(targets).some(t => t.status === 'down');
                  const hasDegraded = Object.values(targets).some(t => t.status === 'degraded');

                  let markerColor = '#22c55e';
                  if (hasAlert) markerColor = '#ef4444';
                  else if (hasDown) markerColor = '#ef4444';
                  else if (hasDegraded) markerColor = '#f59e0b';

                  return (
                    <div
                      key={i}
                      className="timeline-marker"
                      style={{
                        left: `${(i / (timestamps.length - 1)) * 100}%`,
                        backgroundColor: markerColor
                      }}
                      title={`${formatTime(ts)} - ${Object.keys(targets).length} 个目标`}
                    />
                  );
                })}
              </div>
              <div className="timeline-labels">
                <span>{formatTimeShort(timestamps[0])}</span>
                <span>{formatTimeShort(timestamps[Math.floor(timestamps.length / 2)])}</span>
                <span>{formatTimeShort(timestamps[timestamps.length - 1])}</span>
              </div>
            </div>

            <div className="player-controls">
              <button
                className="control-btn"
                onClick={() => setCurrentIndex(0)}
                disabled={currentIndex === 0}
              >
                ⏮️
              </button>
              <button
                className="control-btn"
                onClick={() => setCurrentIndex(Math.max(0, currentIndex - 1))}
                disabled={currentIndex === 0}
              >
                ◀️
              </button>
              <button
                className="control-btn play-btn"
                onClick={handlePlayPause}
              >
                {isPlaying ? '⏸️ 暂停' : '▶️ 播放'}
              </button>
              <button
                className="control-btn"
                onClick={() => setCurrentIndex(Math.min(timestamps.length - 1, currentIndex + 1))}
                disabled={currentIndex >= timestamps.length - 1}
              >
                ▶️
              </button>
              <button
                className="control-btn"
                onClick={() => setCurrentIndex(timestamps.length - 1)}
                disabled={currentIndex >= timestamps.length - 1}
              >
                ⏭️
              </button>

              <div className="speed-controls">
                <span className="speed-label">速度:</span>
                {[0.5, 1, 2, 4].map(speed => (
                  <button
                    key={speed}
                    className={`speed-btn ${playbackSpeed === speed ? 'active' : ''}`}
                    onClick={() => handleSpeedChange(speed)}
                  >
                    {speed}x
                  </button>
                ))}
              </div>
            </div>

            <div className="player-content">
              <div className="targets-panel">
                <h3>目标列表 ({targetNames.length})</h3>
                <div className="targets-list">
                  {targetNames.map(targetName => {
                    const target = currentTargets[targetName];
                    const status = target?.status || 'unknown';
                    return (
                      <div
                        key={targetName}
                        className={`target-row ${selectedTarget === targetName ? 'selected' : ''}`}
                        onClick={() => handleTargetClick(targetName)}
                      >
                        <div
                          className="target-status-indicator"
                          style={{ backgroundColor: getStatusColor(status) }}
                        />
                        <span className="target-name">{targetName}</span>
                        <span className={`target-status-badge ${status}`}>
                          {getStatusLabel(status)}
                        </span>
                        {target?.latency_ms != null && (
                          <span className="target-latency">
                            {target.latency_ms.toFixed(0)}ms
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="detail-panel">
                {selectedTarget && targetStats ? (
                  <>
                    <h3>{selectedTarget} - 详细数据</h3>
                    <div className="detail-stats-grid">
                      <div className="detail-stat">
                        <div className="detail-stat-value">
                          {targetStats.stats.availability?.toFixed(2)}%
                        </div>
                        <div className="detail-stat-label">可用率</div>
                      </div>
                      <div className="detail-stat">
                        <div className="detail-stat-value">
                          {targetStats.stats.p50?.toFixed(0) || '-'} ms
                        </div>
                        <div className="detail-stat-label">P50 延迟</div>
                      </div>
                      <div className="detail-stat">
                        <div className="detail-stat-value">
                          {targetStats.stats.p95?.toFixed(0) || '-'} ms
                        </div>
                        <div className="detail-stat-label">P95 延迟</div>
                      </div>
                      <div className="detail-stat">
                        <div className="detail-stat-value">
                          {targetStats.stats.p99?.toFixed(0) || '-'} ms
                        </div>
                        <div className="detail-stat-label">P99 延迟</div>
                      </div>
                    </div>

                    <div className="chart-container">
                      <h4>延迟趋势（快照时间段）</h4>
                      <LatencyChart results={targetStats.results || []} />
                    </div>

                    <div className="current-status-card">
                      <h4>当前时刻状态 ({formatTimeShort(currentTimestamp)})</h4>
                      {currentTargets[selectedTarget] ? (
                        <div className="current-status-details">
                          <div className="status-row">
                            <span className="status-label">状态:</span>
                            <span
                              className="status-value"
                              style={{ color: getStatusColor(currentTargets[selectedTarget].status) }}
                            >
                              {getStatusLabel(currentTargets[selectedTarget].status)}
                            </span>
                          </div>
                          <div className="status-row">
                            <span className="status-label">延迟:</span>
                            <span className="status-value">
                              {currentTargets[selectedTarget].latency_ms != null
                                ? `${currentTargets[selectedTarget].latency_ms.toFixed(0)} ms`
                                : '-'}
                            </span>
                          </div>
                          <div className="status-row">
                            <span className="status-label">连续失败:</span>
                            <span className="status-value">
                              {currentTargets[selectedTarget].consecutive_failures} 次
                            </span>
                          </div>
                          <div className="status-row">
                            <span className="status-label">连续成功:</span>
                            <span className="status-value">
                              {currentTargets[selectedTarget].consecutive_successes} 次
                            </span>
                          </div>
                          {currentTargets[selectedTarget].error_message && (
                            <div className="status-row error">
                              <span className="status-label">错误:</span>
                              <span className="status-value">
                                {currentTargets[selectedTarget].error_message}
                              </span>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="no-data">该时刻无数据</div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="empty-detail">
                    <div className="empty-icon">📊</div>
                    <div className="empty-text">选择左侧目标查看详细数据</div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default SnapshotPlayer;
