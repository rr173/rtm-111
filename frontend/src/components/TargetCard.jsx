import { useMemo, useState, useEffect } from 'react';
import StatusTimeline from './StatusTimeline';
import LatencyChart from './LatencyChart';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function TargetCard({ target, expanded, onToggleExpand, onDelete, onTogglePause, onToggleSilence, detailData, groups = [], onGroupChange }) {
  const [historyData, setHistoryData] = useState(null);
  const [alertsHistory, setAlertsHistory] = useState([]);
  const [selectedGroupId, setSelectedGroupId] = useState(target.group_id || '');

  useEffect(() => {
    if (expanded) {
      fetchHistory();
      fetchAlerts();
    }
  }, [expanded, target.id]);

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/targets/${target.id}/history?hours=24`);
      if (res.ok) {
        const data = await res.json();
        setHistoryData(data);
      }
    } catch (e) {
      console.error('Failed to fetch history:', e);
    }
  };

  const fetchAlerts = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/alerts?limit=50`);
      if (res.ok) {
        const data = await res.json();
        const targetAlerts = data.filter(a => a.target_id === target.id);
        setAlertsHistory(targetAlerts);
      }
    } catch (e) {
      console.error('Failed to fetch alerts:', e);
    }
  };

  const displayStatus = target.paused ? 'paused' : target.status;

  const statusLabel = useMemo(() => {
    if (target.paused) return '已暂停';
    switch (target.status) {
      case 'healthy': return '健康';
      case 'degraded': return '降级';
      case 'down': return '故障';
      default: return target.status;
    }
  }, [target.status, target.paused]);

  const formatTime = (isoString) => {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const handleGroupChange = async (e) => {
    const newGroupId = e.target.value === '' ? null : Number(e.target.value);
    setSelectedGroupId(e.target.value);

    try {
      const res = await fetch(`${API_BASE}/api/targets/${target.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group_id: newGroupId })
      });
      if (res.ok && onGroupChange) {
        onGroupChange(target.id, newGroupId);
      }
    } catch (e) {
      console.error('Failed to update target group:', e);
    }
  };

  return (
    <div className={`target-card ${expanded ? 'expanded' : ''}`}>
      <div className="target-header" onClick={onToggleExpand}>
        <div className="target-info">
          <div className="target-name">
            {target.name}
            <span className={`status-badge ${displayStatus}`}>
              {statusLabel}
            </span>
            {target.silenced && <span className="silenced-badge">已消声</span>}
          </div>
          <div className="target-address">
            {target.type.toUpperCase()} · {target.address}
            {target.expected_status && ` · 期望: ${target.expected_status}`}
          </div>
        </div>

        <div className="target-timeline">
          <StatusTimeline
            targetId={target.id}
            results={detailData?.results || target.recent_results || []}
            interval={target.interval}
          />
        </div>

        <div className="target-actions" onClick={(e) => e.stopPropagation()}>
          <button
            className="action-btn"
            onClick={() => onTogglePause(target.id, !target.paused)}
          >
            {target.paused ? '恢复' : '暂停'}
          </button>
          <button
            className={`action-btn ${target.silenced ? '' : 'silence'}`}
            onClick={() => onToggleSilence(target.id, !target.silenced)}
          >
            {target.silenced ? '取消消声' : '消声'}
          </button>
          <button
            className="action-btn danger"
            onClick={() => onDelete(target.id)}
          >
            删除
          </button>
        </div>

        <span className={`expand-icon ${expanded ? 'expanded' : ''}`}>▼</span>
      </div>

      {expanded && (
        <div className="target-details">
          <div className="detail-section">
            <h3>📊 统计数据 (24小时)</h3>
            {historyData ? (
              <>
                <div className="stats-grid">
                  <div className="stat-item">
                    <div className="stat-value">{historyData.availability?.toFixed(2)}%</div>
                    <div className="stat-label">可用率</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-value">{historyData.p50?.toFixed(0) || '-'} ms</div>
                    <div className="stat-label">P50 延迟</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-value">{historyData.p95?.toFixed(0) || '-'} ms</div>
                    <div className="stat-label">P95 延迟</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-value">{historyData.p99?.toFixed(0) || '-'} ms</div>
                    <div className="stat-label">P99 延迟</div>
                  </div>
                </div>
                <div className="chart-container">
                  <h4 style={{ fontSize: '13px', marginBottom: '12px', color: '#cbd5e1' }}>延迟趋势</h4>
                  <LatencyChart results={historyData.results || []} />
                </div>
              </>
            ) : (
              <div style={{ color: '#64748b', textAlign: 'center', padding: '20px' }}>
                加载中...
              </div>
            )}
          </div>

          <div className="detail-section">
            <h3>🔔 告警历史</h3>
            <div className="alerts-history-list">
              {alertsHistory.length > 0 ? (
                alertsHistory.slice(0, 20).map(alert => (
                  <div key={alert.id} className="alert-history-item">
                    <span className={`alert-level ${alert.to_status}`}></span>
                    <span>
                      {alert.from_status.toUpperCase()} → {alert.to_status.toUpperCase()}
                    </span>
                    <span style={{ color: '#64748b', marginLeft: 'auto', fontSize: '12px' }}>
                      {formatTime(alert.timestamp)}
                    </span>
                    {alert.acknowledged && (
                      <span style={{ color: '#64748b', fontSize: '11px' }}>[已确认]</span>
                    )}
                  </div>
                ))
              ) : (
                <div style={{ color: '#64748b', textAlign: 'center', padding: '20px' }}>
                  暂无告警记录
                </div>
              )}
            </div>
          </div>

          <div className="detail-section">
            <h3>ℹ️ 目标详情</h3>
            <div style={{ fontSize: '13px', color: '#94a3b8', lineHeight: '2' }}>
              <div className="detail-row">
                <span className="detail-label">所属分组:</span>
                <span className="detail-value">
                  <select
                    value={selectedGroupId}
                    onChange={handleGroupChange}
                    style={{
                      background: '#0f172a',
                      border: '1px solid #475569',
                      color: '#e2e8f0',
                      padding: '4px 8px',
                      borderRadius: '4px',
                      fontSize: '13px',
                      cursor: 'pointer'
                    }}
                  >
                    <option value="">未分组</option>
                    {groups.map(g => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                  </select>
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">探测间隔:</span>
                <span className="detail-value">{target.interval} 秒</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">超时时间:</span>
                <span className="detail-value">{target.timeout} 秒</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">连续失败:</span>
                <span className="detail-value">{target.consecutive_failures} 次</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">连续成功:</span>
                <span className="detail-value">{target.consecutive_successes} 次</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">最后探测:</span>
                <span className="detail-value">{formatTime(target.last_check)}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default TargetCard;
