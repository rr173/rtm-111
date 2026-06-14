import { useMemo, useState, useEffect } from 'react';
import StatusTimeline from './StatusTimeline';
import LatencyChart from './LatencyChart';
import RuleTopology from './RuleTopology';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function getFailureTypeLabel(type) {
  const labels = {
    all_healthy: { text: '全部正常', color: '#22c55e' },
    service_failure: { text: '服务故障', color: '#ef4444' },
    regional_failure: { text: '区域故障', color: '#f59e0b' },
    partial_failure: { text: '局部异常', color: '#f59e0b' },
    observer_offline: { text: '观测点离线', color: '#6b7280' },
    all_observers_offline: { text: '观测点全部离线', color: '#6b7280' },
  };
  return labels[type] || { text: type, color: '#9ca3af' };
}

function TargetCard({ target, expanded, onToggleExpand, onDelete, onTogglePause, onToggleSilence, detailData, groups = [], onGroupChange, roundResults = [], activeChanges = [] }) {
  const [historyData, setHistoryData] = useState(null);
  const [alertsHistory, setAlertsHistory] = useState([]);
  const [selectedGroupId, setSelectedGroupId] = useState(target.group_id || '');
  const [nextProbeCountdown, setNextProbeCountdown] = useState(null);
  const [ruleData, setRuleData] = useState(null);
  const [observerRoundHistory, setObserverRoundHistory] = useState([]);
  const [targetObservers, setTargetObservers] = useState([]);

  useEffect(() => {
    if (expanded) {
      fetchHistory();
      fetchAlerts();
      fetchObserverRoundHistory();
      fetchTargetObservers();
      if (target.rule_id) {
        fetchRuleDetails();
      }
    }
  }, [expanded, target.id]);

  useEffect(() => {
    if (roundResults && roundResults.length > 0) {
      setObserverRoundHistory(prev => {
        const existingIds = new Set(prev.map(r => r.round_id));
        const newRounds = roundResults.filter(r => !existingIds.has(r.round_id));
        return [...newRounds, ...prev].slice(0, 50);
      });
    }
  }, [roundResults]);

  useEffect(() => {
    if (!target.next_probe_at) {
      setNextProbeCountdown(null);
      return;
    }

    const updateCountdown = () => {
      const now = Date.now();
      const next = new Date(target.next_probe_at).getTime();
      const diff = Math.max(0, Math.ceil((next - now) / 1000));
      setNextProbeCountdown(diff);
    };

    updateCountdown();
    const timer = setInterval(updateCountdown, 1000);
    return () => clearInterval(timer);
  }, [target.next_probe_at]);

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

  const fetchRuleDetails = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/rules/${target.rule_id}/execution?target_id=${target.id}`);
      if (res.ok) {
        const data = await res.json();
        setRuleData(data);
      }
    } catch (e) {
      console.error('Failed to fetch rule details:', e);
    }
  };

  const fetchObserverRoundHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/targets/${target.id}/round-history?limit=30`);
      if (res.ok) {
        const data = await res.json();
        setObserverRoundHistory(data);
      }
    } catch (e) {
      console.error('Failed to fetch observer round history:', e);
    }
  };

  const fetchTargetObservers = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/targets/${target.id}/observers`);
      if (res.ok) {
        const data = await res.json();
        setTargetObservers(data);
      }
    } catch (e) {
      console.error('Failed to fetch target observers:', e);
    }
  };

  const displayStatus = target.cascade_affected ? 'cascade' : (target.paused ? 'paused' : target.status);

  const statusLabel = useMemo(() => {
    if (target.cascade_affected) return '级联受损';
    if (target.paused) return '已暂停';
    switch (target.status) {
      case 'healthy': return '健康';
      case 'partial': return '局部异常';
      case 'degraded': return '降级';
      case 'down': return '故障';
      default: return target.status;
    }
  }, [target.status, target.paused, target.cascade_affected]);

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

  const formatCountdown = (seconds) => {
    if (seconds === null || seconds === undefined) return '—';
    if (seconds < 60) return `${seconds}秒`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}分${secs}秒`;
  };

  const hasSilentWindow = target.silent_start && target.silent_end;

  return (
    <div className={`target-card ${expanded ? 'expanded' : ''}`}>
      <div className="target-header" onClick={onToggleExpand}>
        <div className="target-info">
          <div className="target-name">
            {target.name}
            <span className={`status-badge ${displayStatus}`}>
              {statusLabel}
            </span>
            {target.cascade_affected && <span className="cascade-badge">级联受损</span>}
            {target.silenced && <span className="silenced-badge">已消声</span>}
            {target.in_silent_window && <span className="silent-window-badge">静默中</span>}
            {target.adaptive_enabled && <span className="adaptive-badge">自适应</span>}
            {target.rule_id && <span className="rule-badge" title={`绑定规则 #${target.rule_id}`}>📋 规则编排</span>}
            {activeChanges.length > 0 && activeChanges.map((change, idx) => (
              <span
                key={idx}
                className={`change-badge ${change.change_status}`}
                title={`变更 #${change.change_id}: ${change.change_name}`}
              >
                🛡️ {change.change_name}
              </span>
            ))}
          </div>
          {target.cascade_affected && target.cascade_source_name && (
            <div className="cascade-source-info">
              <span className="cascade-source-label">级联源:</span>
              <span className="cascade-source-name">{target.cascade_source_name}</span>
            </div>
          )}
          <div className="target-address">
            {target.type.toUpperCase()} · {target.address}
            {target.expected_status && ` · 期望: ${target.expected_status}`}
          </div>
          <div className="target-strategy-info">
            <span className="strategy-item">
              <span className="strategy-label">当前间隔:</span>
              <span className="strategy-value">{target.current_interval || target.interval}秒</span>
            </span>
            <span className="strategy-item">
              <span className="strategy-label">下次探测:</span>
              <span className="strategy-value">{formatCountdown(nextProbeCountdown)}</span>
            </span>
            {hasSilentWindow && (
              <span className="strategy-item">
                <span className="strategy-label">静默时段:</span>
                <span className="strategy-value">{target.silent_start} - {target.silent_end}</span>
              </span>
            )}
          </div>
        </div>

        <div className="target-timeline">
          <StatusTimeline
            targetId={target.id}
            results={detailData?.results || target.recent_results || []}
            interval={target.interval}
            silentStart={target.silent_start}
            silentEnd={target.silent_end}
            inSilentWindow={target.in_silent_window}
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
          {target.rule_id && (
            <div className="detail-section">
              <h3>
                📋 规则步骤拓扑
                {ruleData?.rule_name && (
                  <span style={{ fontSize: '13px', color: '#94a3b8', marginLeft: '8px', fontWeight: 'normal' }}>
                    {ruleData.rule_name} (v{ruleData.version || 1})
                  </span>
                )}
              </h3>
              {ruleData ? (
                <RuleTopology
                  steps={ruleData.steps || []}
                  execution_mode={ruleData.execution_mode}
                />
              ) : (
                <div style={{ color: '#64748b', textAlign: 'center', padding: '20px' }}>
                  加载中...
                </div>
              )}
            </div>
          )}

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
            <h3>🌐 多观测点协同探测</h3>
            <div className="observers-summary">
              <div className="observers-stats">
                <div className="stat-mini">
                  <span className="stat-mini-label">配置观测点:</span>
                  <span className="stat-mini-value">{targetObservers.length}</span>
                </div>
                <div className="stat-mini">
                  <span className="stat-mini-label">在线观测点:</span>
                  <span className="stat-mini-value" style={{ color: '#22c55e' }}>
                    {targetObservers.filter(o => o.status === 'online').length}
                  </span>
                </div>
                <div className="stat-mini">
                  <span className="stat-mini-label">离线观测点:</span>
                  <span className="stat-mini-value" style={{ color: '#ef4444' }}>
                    {targetObservers.filter(o => o.status === 'offline').length}
                  </span>
                </div>
              </div>
              <div className="observers-list">
                {targetObservers.map(obs => (
                  <div key={obs.id} className={`observer-tag obs-${obs.status}`}>
                    <span className="obs-dot"></span>
                    {obs.name}
                    <span className="obs-region">({obs.region})</span>
                  </div>
                ))}
              </div>
            </div>

            {observerRoundHistory.length > 0 ? (
              <div className="round-history">
                <h4 style={{ fontSize: '13px', marginBottom: '10px', color: '#cbd5e1' }}>
                  最近探测轮次（各观测点结果分歧）
                </h4>
                <div className="round-list">
                  {observerRoundHistory.slice(0, 10).map((round, idx) => {
                    const failureInfo = getFailureTypeLabel(round.failure_type);
                    return (
                      <div key={round.round_id || idx} className="round-item">
                        <div className="round-header">
                          <span className="round-time">{formatTime(round.timestamp)}</span>
                          <span
                            className="round-failure-type"
                            style={{ background: failureInfo.color, color: '#fff' }}
                          >
                            {failureInfo.text}
                          </span>
                          <span className="round-summary">
                            <span style={{ color: '#22c55e' }}>✓ {round.success_count}</span>
                            <span style={{ color: '#94a3b8', margin: '0 4px' }}>/</span>
                            <span style={{ color: '#ef4444' }}>✗ {round.failure_count}</span>
                            <span style={{ color: '#94a3b8', margin: '0 4px' }}>/</span>
                            <span style={{ color: '#6b7280' }}>离线 {round.offline_count || 0}</span>
                          </span>
                        </div>
                        <div className="round-observer-results">
                          {round.results && round.results.map((r, ridx) => (
                            <div
                              key={ridx}
                              className={`observer-result ${r.success ? 'success' : 'fail'} ${r.observer_status === 'offline' ? 'offline' : ''}`}
                              title={r.error_message || ''}
                            >
                              <div className="observer-result-header">
                                <span className="obs-result-name">{r.observer_name}</span>
                                <span className="obs-result-region">{r.observer_region}</span>
                              </div>
                              <div className="observer-result-status">
                                {r.observer_status === 'offline' ? (
                                  <span style={{ color: '#6b7280' }}>⬤ 离线</span>
                                ) : r.success ? (
                                  <span style={{ color: '#22c55e' }}>✓ 成功</span>
                                ) : (
                                  <span style={{ color: '#ef4444' }}>✗ 失败</span>
                                )}
                              </div>
                              {r.latency_ms != null && (
                                <div className="obs-result-latency">
                                  {r.latency_ms >= 1000
                                    ? `${(r.latency_ms / 1000).toFixed(1)}s`
                                    : `${r.latency_ms.toFixed(0)}ms`}
                                </div>
                              )}
                              {r.error_message && (
                                <div className="obs-result-error">{r.error_message}</div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div style={{ color: '#64748b', textAlign: 'center', padding: '20px' }}>
                暂无多观测点探测历史
              </div>
            )}
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
                <span className="detail-label">基准间隔:</span>
                <span className="detail-value">{target.interval} 秒</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">当前间隔:</span>
                <span className="detail-value" style={{ color: '#22c55e', fontWeight: 'bold' }}>
                  {target.current_interval || target.interval} 秒
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">下次探测:</span>
                <span className="detail-value">{formatCountdown(nextProbeCountdown)}</span>
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

          <div className="detail-section">
            <h3>⚙️ 探测策略</h3>
            <div style={{ fontSize: '13px', color: '#94a3b8', lineHeight: '2' }}>
              <div className="detail-row">
                <span className="detail-label">自适应间隔:</span>
                <span className="detail-value">
                  <span className={target.adaptive_enabled ? 'status-enabled' : 'status-disabled'}>
                    {target.adaptive_enabled ? '已启用' : '未启用'}
                  </span>
                </span>
              </div>
              {target.adaptive_enabled && (
                <>
                  <div className="detail-row">
                    <span className="detail-label">慢速间隔:</span>
                    <span className="detail-value">{target.slow_interval} 秒 (健康/故障时)</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">快速间隔:</span>
                    <span className="detail-value">{target.fast_interval} 秒 (异常检测时)</span>
                  </div>
                </>
              )}
              <div className="detail-row">
                <span className="detail-label">静默时段:</span>
                <span className="detail-value">
                  {target.silent_start && target.silent_end
                    ? `${target.silent_start} - ${target.silent_end}`
                    : '未设置'}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">当前状态:</span>
                <span className="detail-value">
                  {target.in_silent_window ? (
                    <span style={{ color: '#f59e0b' }}>静默中 - 暂停探测</span>
                  ) : (
                    <span style={{ color: '#22c55e' }}>正常探测中</span>
                  )}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default TargetCard;
