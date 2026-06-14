import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

export default function ChangeObservationPanel({ changeId, onClose }) {
  const [observationData, setObservationData] = useState(null);
  const [comparisonData, setComparisonData] = useState(null);
  const [topologyData, setTopologyData] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (changeId) {
      loadData();
      const interval = setInterval(loadData, 5000);
      return () => clearInterval(interval);
    }
  }, [changeId]);

  const loadData = async () => {
    try {
      const [obsRes, compRes, topoRes] = await Promise.all([
        fetch(`${API_BASE}/api/changes/${changeId}/observation`),
        fetch(`${API_BASE}/api/changes/${changeId}/comparison`),
        fetch(`${API_BASE}/api/changes/${changeId}/topology`)
      ]);

      if (obsRes.ok) {
        const data = await obsRes.json();
        setObservationData(data);
      }
      if (compRes.ok) {
        const data = await compRes.json();
        setComparisonData(data);
      }
      if (topoRes.ok) {
        const data = await topoRes.json();
        setTopologyData(data);
      }
    } catch (e) {
      console.error('Failed to load observation data:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleStartChange = async () => {
    if (!confirm('确定要开始这个变更吗？开始后将自动创建基线快照并进入守护模式。')) return;
    try {
      const res = await fetch(`${API_BASE}/api/changes/${changeId}/start`, { method: 'POST' });
      if (res.ok) {
        loadData();
      }
    } catch (e) {
      console.error('Failed to start change:', e);
    }
  };

  const handleEndChange = async () => {
    if (!confirm('确定要结束这个变更吗？结束后将自动创建结果快照并进行对比分析。')) return;
    try {
      const res = await fetch(`${API_BASE}/api/changes/${changeId}/end`, { method: 'POST' });
      if (res.ok) {
        loadData();
      }
    } catch (e) {
      console.error('Failed to end change:', e);
    }
  };

  const handleCancelChange = async () => {
    if (!confirm('确定要取消这个变更吗？')) return;
    try {
      const res = await fetch(`${API_BASE}/api/changes/${changeId}/cancel`, { method: 'POST' });
      if (res.ok) {
        loadData();
      }
    } catch (e) {
      console.error('Failed to cancel change:', e);
    }
  };

  if (loading && !observationData) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content extra-large-modal" onClick={e => e.stopPropagation()}>
          <div className="modal-header">
            <h2>🔍 变更观察面板</h2>
            <button className="close-btn" onClick={onClose}>×</button>
          </div>
          <div className="modal-body">
            <div className="loading-state">加载中...</div>
          </div>
        </div>
      </div>
    );
  }

  if (!observationData) return null;

  const { change, status_diff, alert_stats, region_divergence, baseline_metrics, current_metrics, alerts_timeline } = observationData;

  const getStatusColor = (status) => {
    const colors = {
      pending: '#f59e0b',
      running: '#3b82f6',
      completed: '#10b981',
      cancelled: '#6b7280'
    };
    return colors[status] || '#6b7280';
  };

  const getConclusionBadge = (conclusion) => {
    if (!conclusion) return null;
    const config = {
      pass: { label: '✅ 通过', color: '#10b981' },
      observe: { label: '⚠️ 需观察', color: '#f59e0b' },
      rollback: { label: '🔴 建议回滚', color: '#ef4444' }
    };
    const cfg = config[conclusion] || { label: conclusion, color: '#6b7280' };
    return <span className="conclusion-badge" style={{ background: cfg.color }}>{cfg.label}</span>;
  };

  const formatTime = (time) => {
    if (!time) return '-';
    return new Date(time).toLocaleString('zh-CN');
  };

  const getStatusBadge = (status) => {
    const colors = {
      healthy: '#10b981',
      degraded: '#f59e0b',
      down: '#ef4444',
      partial: '#8b5cf6'
    };
    return (
      <span className="status-badge" style={{ background: colors[status] || '#6b7280' }}>
        {status}
      </span>
    );
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content extra-large-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="header-title-section">
            <h2>🔍 变更观察面板</h2>
            <span className="change-status-chip" style={{ background: getStatusColor(change.status) }}>
              {change.status === 'pending' ? '⏳ 待开始' :
               change.status === 'running' ? '🚀 进行中' :
               change.status === 'completed' ? '✅ 已完成' : '❌ 已取消'}
            </span>
            {getConclusionBadge(change.conclusion)}
          </div>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <div className="change-info-bar">
          <div className="info-item">
            <span className="info-label">变更名称</span>
            <span className="info-value">{change.name}</span>
          </div>
          <div className="info-item">
            <span className="info-label">计划时间</span>
            <span className="info-value">{formatTime(change.planned_time)}</span>
          </div>
          <div className="info-item">
            <span className="info-label">开始时间</span>
            <span className="info-value">{formatTime(change.start_time)}</span>
          </div>
          <div className="info-item">
            <span className="info-label">创建人</span>
            <span className="info-value">{change.created_by || '-'}</span>
          </div>
          <div className="change-actions">
            {change.status === 'pending' && (
              <>
                <button className="btn btn-primary" onClick={handleStartChange}>
                  ▶ 开始变更
                </button>
                <button className="btn btn-danger" onClick={handleCancelChange}>
                  取消
                </button>
              </>
            )}
            {change.status === 'running' && (
              <>
                <button className="btn btn-success" onClick={handleEndChange}>
                  ✓ 结束变更
                </button>
                <button className="btn btn-danger" onClick={handleCancelChange}>
                  取消
                </button>
              </>
            )}
          </div>
        </div>

        {change.description && (
          <div className="description-box">
            <strong>变更描述：</strong>{change.description}
          </div>
        )}

        <div className="observation-tabs">
          <button
            className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            📊 总览
          </button>
          <button
            className={`tab-btn ${activeTab === 'status' ? 'active' : ''}`}
            onClick={() => setActiveTab('status')}
          >
            🟢 状态对比
          </button>
          <button
            className={`tab-btn ${activeTab === 'alerts' ? 'active' : ''}`}
            onClick={() => setActiveTab('alerts')}
          >
            ⚠️ 告警分析
          </button>
          <button
            className={`tab-btn ${activeTab === 'regions' ? 'active' : ''}`}
            onClick={() => setActiveTab('regions')}
          >
            🌍 地区分歧
          </button>
          <button
            className={`tab-btn ${activeTab === 'comparison' ? 'active' : ''}`}
            onClick={() => setActiveTab('comparison')}
          >
            📸 快照对比
          </button>
          <button
            className={`tab-btn ${activeTab === 'topology' ? 'active' : ''}`}
            onClick={() => setActiveTab('topology')}
          >
            🔗 影响范围
          </button>
          <button
            className={`tab-btn ${activeTab === 'events' ? 'active' : ''}`}
            onClick={() => setActiveTab('events')}
          >
            📝 事件时间线
          </button>
        </div>

        <div className="observation-content">
          {activeTab === 'overview' && (
            <div className="overview-section">
              <div className="metrics-grid">
                <div className="metric-card baseline">
                  <div className="metric-title">📊 基线指标 (变更前10分钟)</div>
                  <div className="metric-value">{baseline_metrics.availability}%</div>
                  <div className="metric-subtitle">可用性</div>
                  <div className="metric-details">
                    <div>P50: {baseline_metrics.avg_latency}ms</div>
                    <div>P95: {baseline_metrics.p95_latency}ms</div>
                    <div>健康: {baseline_metrics.healthy_count}/{baseline_metrics.total}</div>
                  </div>
                </div>

                <div className="metric-card current">
                  <div className="metric-title">📈 当前指标 (最近10分钟)</div>
                  <div className={`metric-value ${current_metrics.availability < baseline_metrics.availability ? 'negative' : 'positive'}`}>
                    {current_metrics.availability}%
                    <span className="diff-indicator">
                      {current_metrics.availability - baseline_metrics.availability >= 0 ? '+' : ''}
                      {(current_metrics.availability - baseline_metrics.availability).toFixed(1)}%
                    </span>
                  </div>
                  <div className="metric-subtitle">可用性</div>
                  <div className="metric-details">
                    <div>P50: {current_metrics.avg_latency}ms</div>
                    <div>P95: {current_metrics.p95_latency}ms</div>
                    <div>健康: {current_metrics.healthy_count}/{current_metrics.total}</div>
                  </div>
                </div>

                <div className="metric-card alerts">
                  <div className="metric-title">⚠️ 告警统计</div>
                  <div className="metric-value">{alert_stats.new_alerts}</div>
                  <div className="metric-subtitle">新增告警</div>
                  <div className="metric-details">
                    <div>基线期: {alert_stats.baseline_count}</div>
                    <div>当前: {alert_stats.current_count}</div>
                    <div>已解决: {alert_stats.resolved_alerts}</div>
                  </div>
                </div>

                <div className="metric-card targets">
                  <div className="metric-title">🎯 影响范围</div>
                  <div className="metric-value">{observationData.target_ids.length}</div>
                  <div className="metric-subtitle">直接目标</div>
                  <div className="metric-details">
                    <div>下游依赖: {observationData.downstream_target_ids.length} 个</div>
                    <div>总计影响: {observationData.all_target_ids.length} 个</div>
                    <div>状态变化: {status_diff.filter(s => s.status_changed).length} 个</div>
                  </div>
                </div>
              </div>

              {change.conclusion_reason && (
                <div className={`conclusion-box ${change.conclusion}`}>
                  <strong>结论：</strong>{change.conclusion_reason}
                </div>
              )}

              <div className="quick-stats">
                <h4>📋 涉及目标</h4>
                <div className="target-chips">
                  {observationData.target_names.map((name, idx) => (
                    <span key={idx} className="target-chip direct">{name} (直接)</span>
                  ))}
                  {observationData.downstream_target_names.map((name, idx) => (
                    <span key={`ds-${idx}`} className="target-chip downstream">{name} (下游)</span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'status' && (
            <div className="status-section">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>目标名称</th>
                    <th>类型</th>
                    <th>基线状态</th>
                    <th>当前状态</th>
                    <th>状态变化</th>
                  </tr>
                </thead>
                <tbody>
                  {status_diff.map((diff, idx) => (
                    <tr key={idx} className={diff.status_changed ? 'row-alert' : ''}>
                      <td>{diff.target_name}</td>
                      <td>
                        {observationData.target_ids.includes(diff.target_id) ? (
                          <span className="badge direct-badge">直接</span>
                        ) : (
                          <span className="badge downstream-badge">下游</span>
                        )}
                      </td>
                      <td>{getStatusBadge(diff.baseline_status)}</td>
                      <td>{getStatusBadge(diff.current_status)}</td>
                      <td>
                        {diff.status_changed ? (
                          <span className="change-indicator negative">
                            ↓ {diff.baseline_status} → {diff.current_status}
                          </span>
                        ) : (
                          <span className="change-indicator positive">→ 无变化</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === 'alerts' && (
            <div className="alerts-section">
              <div className="alert-summary">
                <div className="alert-stat">
                  <span className="stat-label">基线期告警</span>
                  <span className="stat-value">{alert_stats.baseline_count}</span>
                </div>
                <div className="alert-stat">
                  <span className="stat-label">当前告警</span>
                  <span className="stat-value">{alert_stats.current_count}</span>
                </div>
                <div className="alert-stat highlight">
                  <span className="stat-label">新增告警</span>
                  <span className="stat-value">{alert_stats.new_alerts}</span>
                </div>
                <div className="alert-stat">
                  <span className="stat-label">已解决</span>
                  <span className="stat-value">{alert_stats.resolved_alerts}</span>
                </div>
              </div>

              <h4>按目标统计</h4>
              <div className="target-alert-bars">
                {Object.entries(alert_stats.target_alerts).map(([name, count]) => (
                  <div key={name} className="target-alert-bar">
                    <span className="target-name">{name}</span>
                    <div className="bar-container">
                      <div
                        className="bar-fill"
                        style={{ width: `${Math.min(count * 20, 100)}%`, background: count > 2 ? '#ef4444' : count > 0 ? '#f59e0b' : '#10b981' }}
                      ></div>
                    </div>
                    <span className="alert-count">{count}</span>
                  </div>
                ))}
              </div>

              <h4>告警时间线</h4>
              <div className="alerts-timeline">
                {alerts_timeline.length === 0 ? (
                  <div className="empty-state">暂无告警</div>
                ) : (
                  alerts_timeline.map((alert, idx) => (
                    <div key={idx} className="timeline-item">
                      <div className="timeline-dot"></div>
                      <div className="timeline-content">
                        <div className="timeline-header">
                          <span className={`alert-type ${alert.to_status}`}>{alert.to_status.toUpperCase()}</span>
                          <span className="timeline-time">{formatTime(alert.timestamp)}</span>
                        </div>
                        <div className="timeline-target">{alert.target_name}</div>
                        <div className="timeline-desc">
                          {alert.from_status} → {alert.to_status}
                          {alert.acknowledged && <span className="acked-badge">已确认</span>}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {activeTab === 'regions' && (
            <div className="regions-section">
              <h4>🌍 各地区观测结果分歧分析</h4>
              {region_divergence.length === 0 ? (
                <div className="empty-state">暂无地区观测数据</div>
              ) : (
                region_divergence.map((rd, idx) => (
                  <div key={idx} className={`region-card ${rd.has_divergence ? 'has-divergence' : ''}`}>
                    <div className="region-header">
                      <span className="region-target-name">{rd.target_name}</span>
                      {rd.has_divergence && (
                        <span className="divergence-badge">⚠️ 检测到地区分歧</span>
                      )}
                    </div>
                    <div className="region-grid">
                      {Object.entries(rd.regions).map(([region, data]) => (
                        <div
                          key={region}
                          className={`region-cell ${data.success_rate < 70 ? 'region-fail' : data.success_rate < 90 ? 'region-warning' : 'region-ok'}`}
                        >
                          <div className="region-name">{region}</div>
                          <div className="region-rate">{data.success_rate.toFixed(0)}%</div>
                          <div className="region-latency">{data.avg_latency.toFixed(0)}ms</div>
                          <div className="region-count">{data.success}/{data.total}</div>
                        </div>
                      ))}
                    </div>
                    {rd.has_divergence && (
                      <div className="divergent-regions">
                        <strong>异常地区：</strong>{rd.divergent_regions.join(', ')}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'comparison' && comparisonData && (
            <div className="comparison-section">
              {comparisonData.baseline_snapshot && comparisonData.result_snapshot ? (
                <>
                  <div className="snapshot-info-row">
                    <div className="snapshot-info">
                      <strong>基线快照：</strong>
                      {comparisonData.baseline_snapshot.name}
                      <span className="snapshot-time">
                        {formatTime(comparisonData.baseline_snapshot.start_time)} - {formatTime(comparisonData.baseline_snapshot.end_time)}
                      </span>
                    </div>
                    <div className="vs-badge">VS</div>
                    <div className="snapshot-info">
                      <strong>结果快照：</strong>
                      {comparisonData.result_snapshot.name}
                      <span className="snapshot-time">
                        {formatTime(comparisonData.result_snapshot.start_time)} - {formatTime(comparisonData.result_snapshot.end_time)}
                      </span>
                    </div>
                  </div>

                  <div className="comparison-summary">
                    <div className="summary-item">
                      <span className="summary-label">对比目标</span>
                      <span className="summary-value">{comparisonData.overall_summary.total_targets}</span>
                    </div>
                    <div className="summary-item degraded">
                      <span className="summary-label">性能下降</span>
                      <span className="summary-value">{comparisonData.overall_summary.degraded_count}</span>
                    </div>
                    <div className="summary-item improved">
                      <span className="summary-label">性能提升</span>
                      <span className="summary-value">{comparisonData.overall_summary.improved_count}</span>
                    </div>
                    <div className="summary-item">
                      <span className="summary-label">无变化</span>
                      <span className="summary-value">{comparisonData.overall_summary.unchanged_count}</span>
                    </div>
                    <div className="summary-item">
                      <span className="summary-label">平均可用性变化</span>
                      <span className={`summary-value ${comparisonData.overall_summary.avg_availability_change < 0 ? 'negative' : 'positive'}`}>
                        {comparisonData.overall_summary.avg_availability_change >= 0 ? '+' : ''}
                        {comparisonData.overall_summary.avg_availability_change.toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>目标名称</th>
                        <th>基线可用性</th>
                        <th>结果可用性</th>
                        <th>可用性变化</th>
                        <th>基线P95</th>
                        <th>结果P95</th>
                        <th>P95变化</th>
                        <th>状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {comparisonData.target_comparisons.map((comp, idx) => (
                        <tr key={idx} className={comp.degraded ? 'row-alert' : ''}>
                          <td>{comp.target_name}</td>
                          <td>{comp.snapshot_a.stats.availability.toFixed(1)}%</td>
                          <td>{comp.snapshot_b.stats.availability.toFixed(1)}%</td>
                          <td className={comp.diff.availability < 0 ? 'negative' : 'positive'}>
                            {comp.diff.availability >= 0 ? '+' : ''}{comp.diff.availability.toFixed(1)}%
                          </td>
                          <td>{comp.snapshot_a.stats.p95.toFixed(0)}ms</td>
                          <td>{comp.snapshot_b.stats.p95.toFixed(0)}ms</td>
                          <td className={comp.diff.p95 > 0 ? 'negative' : 'positive'}>
                            {comp.diff.p95 >= 0 ? '+' : ''}{comp.diff.p95.toFixed(0)}ms
                          </td>
                          <td>
                            {comp.degraded ? (
                              <span className="status-badge" style={{ background: '#ef4444' }}>降级</span>
                            ) : comp.diff.availability > 0 ? (
                              <span className="status-badge" style={{ background: '#10b981' }}>提升</span>
                            ) : (
                              <span className="status-badge" style={{ background: '#6b7280' }}>正常</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              ) : (
                <div className="empty-state">
                  快照数据不完整，无法进行对比。
                  {change.status === 'running' && <p>请等待变更结束后自动创建结果快照。</p>}
                </div>
              )}
            </div>
          )}

          {activeTab === 'topology' && topologyData && (
            <div className="topology-section">
              <div className="topology-summary">
                <div className="summary-item">
                  <span className="summary-label">直接目标</span>
                  <span className="summary-value">{topologyData.direct_target_count}</span>
                </div>
                <div className="summary-item">
                  <span className="summary-label">下游依赖</span>
                  <span className="summary-value">{topologyData.downstream_target_count}</span>
                </div>
                <div className="summary-item highlight">
                  <span className="summary-label">总影响</span>
                  <span className="summary-value">{topologyData.targets.length}</span>
                </div>
              </div>

              <div className="topology-nodes">
                <h4>🎯 直接变更目标</h4>
                <div className="nodes-grid">
                  {topologyData.targets.filter(t => t.is_direct).map((t, idx) => (
                    <div key={idx} className={`topology-node direct status-${t.status}`}>
                      <span className="node-status"></span>
                      <span className="node-name">{t.name}</span>
                      <span className="node-type">{t.type}</span>
                    </div>
                  ))}
                </div>

                {topologyData.targets.filter(t => t.is_downstream).length > 0 && (
                  <>
                    <h4>🔗 下游受影响目标</h4>
                    <div className="nodes-grid">
                      {topologyData.targets.filter(t => t.is_downstream).map((t, idx) => (
                        <div key={idx} className={`topology-node downstream status-${t.status}`}>
                          <span className="node-status"></span>
                          <span className="node-name">{t.name}</span>
                          <span className="node-type">{t.type}</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>

              <div className="dependencies-list">
                <h4>📋 依赖关系</h4>
                {topologyData.dependencies.length === 0 ? (
                  <div className="empty-state">暂无依赖关系</div>
                ) : (
                  <ul className="dependency-list">
                    {topologyData.dependencies.map((d, idx) => {
                      const up = topologyData.targets.find(t => t.id === d.upstream_id);
                      const down = topologyData.targets.find(t => t.id === d.downstream_id);
                      return (
                        <li key={idx} className="dependency-item">
                          <span className={`dep-status status-${up?.status || 'unknown'}`}></span>
                          <span className="dep-name">{up?.name || d.upstream_id}</span>
                          <span className="dep-arrow">→</span>
                          <span className={`dep-status status-${down?.status || 'unknown'}`}></span>
                          <span className="dep-name">{down?.name || d.downstream_id}</span>
                          {d.description && <span className="dep-desc">({d.description})</span>}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </div>
          )}

          {activeTab === 'events' && (
            <div className="events-section">
              <div className="events-timeline">
                {change.events.length === 0 ? (
                  <div className="empty-state">暂无事件记录</div>
                ) : (
                  change.events.map((event, idx) => (
                    <div key={idx} className={`timeline-item event-${event.event_type}`}>
                      <div className="timeline-dot"></div>
                      <div className="timeline-content">
                        <div className="timeline-header">
                          <span className="event-type-badge">{event.event_type}</span>
                          <span className="timeline-time">{formatTime(event.timestamp)}</span>
                        </div>
                        <div className="timeline-message">{event.message}</div>
                        {event.data && (
                          <div className="event-data">
                            <pre>{JSON.stringify(event.data, null, 2)}</pre>
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
