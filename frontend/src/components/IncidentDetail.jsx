import { useState, useEffect, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

const statusLabels = {
  active: '处置中',
  recovering: '观察中',
  resolved: '已解决',
};

const statusColors = {
  active: '#ef4444',
  recovering: '#f59e0b',
  resolved: '#10b981',
};

const severityColors = {
  warning: '#f59e0b',
  critical: '#ef4444',
  info: '#3b82f6',
};

const eventTypeLabels = {
  alert_triggered: '🚨 告警触发',
  alert: '🚨 告警',
  status_change: '📊 状态变更',
  severity_change: '⚠️ 等级变更',
  acknowledged: '👤 接管确认',
  owner_transfer: '🔄 负责人转交',
  mitigation: '🩹 止血操作',
  investigation: '🔍 排查进展',
  note_added: '📝 处置记录',
  cascade_detected: '🔗 级联扩散',
  observation_divergence: '🌐 观测分歧',
  observation_summary: '📡 观测汇总',
};

const targetStatusColors = {
  healthy: '#10b981',
  degraded: '#f59e0b',
  down: '#ef4444',
  partial: '#8b5cf6',
  paused: '#6b7280',
};

function formatDuration(seconds) {
  if (!seconds) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}时${m}分${s}秒`;
  if (m > 0) return `${m}分${s}秒`;
  return `${s}秒`;
}

function formatTime(isoStr) {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  return d.toLocaleString('zh-CN', { hour12: false });
}

function formatRelativeTime(isoStr) {
  if (!isoStr) return '—';
  const diff = Date.now() - new Date(isoStr).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}秒前`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}小时前`;
  const days = Math.floor(hours / 24);
  return `${days}天前`;
}

function IncidentDetail({ incidentId, targets, dependencies, onBack, onUpdate }) {
  const [incident, setIncident] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('timeline');
  const [showAckModal, setShowAckModal] = useState(false);
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [showNoteModal, setShowNoteModal] = useState(false);
  const [showResolveModal, setShowResolveModal] = useState(false);
  const [ackData, setAckData] = useState({ acknowledged_by: '', notes: '' });
  const [transferData, setTransferData] = useState({ new_owner: '', transferred_by: '', notes: '' });
  const [noteData, setNoteData] = useState({ author: '', content: '', action_type: 'note' });
  const [resolveData, setResolveData] = useState({ resolved_by: '', mark_for_review: true, review_notes: '' });

  const loadIncident = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/incidents/${incidentId}`);
      if (res.ok) {
        const data = await res.json();
        setIncident(data);
      }
    } catch (e) {
      console.error('Failed to load incident:', e);
    } finally {
      setLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    loadIncident();
  }, [loadIncident]);

  const handleAcknowledge = async () => {
    if (!ackData.acknowledged_by.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/api/incidents/${incidentId}/acknowledge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ackData),
      });
      if (res.ok) {
        setIncident(await res.json());
        setShowAckModal(false);
        if (onUpdate) onUpdate();
      }
    } catch (e) {
      console.error('Failed to acknowledge:', e);
    }
  };

  const handleTransfer = async () => {
    if (!transferData.new_owner.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/api/incidents/${incidentId}/transfer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(transferData),
      });
      if (res.ok) {
        setIncident(await res.json());
        setShowTransferModal(false);
        if (onUpdate) onUpdate();
      }
    } catch (e) {
      console.error('Failed to transfer:', e);
    }
  };

  const handleAddNote = async () => {
    if (!noteData.author.trim() || !noteData.content.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/api/incidents/${incidentId}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(noteData),
      });
      if (res.ok) {
        setIncident(await res.json());
        setShowNoteModal(false);
        setNoteData({ author: '', content: '', action_type: 'note' });
        if (onUpdate) onUpdate();
      }
    } catch (e) {
      console.error('Failed to add note:', e);
    }
  };

  const handleToggleMitigated = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/incidents/${incidentId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mitigated: !incident.mitigated }),
      });
      if (res.ok) {
        setIncident(await res.json());
        if (onUpdate) onUpdate();
      }
    } catch (e) {
      console.error('Failed to toggle mitigated:', e);
    }
  };

  const handleResolve = async () => {
    if (!resolveData.resolved_by.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/api/incidents/${incidentId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(resolveData),
      });
      if (res.ok) {
        setIncident(await res.json());
        setShowResolveModal(false);
        if (onUpdate) onUpdate();
      }
    } catch (e) {
      console.error('Failed to resolve:', e);
    }
  };

  if (loading) {
    return <div className="incident-detail"><div className="loading">加载中...</div></div>;
  }
  if (!incident) {
    return <div className="incident-detail"><div className="error">未找到故障事件</div></div>;
  }

  const sortedTimeline = [...(incident.timeline || [])].sort(
    (a, b) => new Date(a.timestamp) - new Date(b.timestamp)
  );
  const sortedNotes = [...(incident.notes || [])].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at)
  );
  const sortedAlerts = [...(incident.alerts || [])].sort(
    (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
  );

  return (
    <div className="incident-detail">
      <div className="detail-header">
        <button className="back-btn" onClick={onBack}>← 返回列表</button>
        <div className="detail-title-row">
          <span className="severity-badge" style={{ backgroundColor: severityColors[incident.severity] }}>
            {incident.severity === 'critical' ? '严重' : '警告'}
          </span>
          <h2>{incident.title}</h2>
          <span className="status-badge" style={{ backgroundColor: statusColors[incident.status] }}>
            {statusLabels[incident.status]}
          </span>
          {incident.mitigated && <span className="mitigated-badge">✓ 已止血</span>}
          {incident.needs_review && <span className="review-badge">📋 待复盘</span>}
        </div>
        <div className="detail-meta">
          <span>#{incident.id}</span>
          <span>首异常: {formatTime(incident.first_anomaly_at)} ({formatRelativeTime(incident.first_anomaly_at)})</span>
          <span>持续: {formatDuration(incident.duration_seconds)}</span>
          <span>负责人: {incident.owner || '未指派'}</span>
          {incident.acknowledged && (
            <span>已由 {incident.acknowledged_by} 接管</span>
          )}
        </div>
        {incident.description && <p className="detail-desc">{incident.description}</p>}

        <div className="detail-actions">
          {!incident.acknowledged && (
            <button className="action-btn primary" onClick={() => setShowAckModal(true)}>
              👤 手动接管
            </button>
          )}
          <button className="action-btn" onClick={() => setShowTransferModal(true)}>
            🔄 转交负责人
          </button>
          <button
            className={`action-btn ${incident.mitigated ? 'secondary' : 'warning'}`}
            onClick={handleToggleMitigated}
          >
            {incident.mitigated ? '↩️ 取消止血' : '🩹 标记止血'}
          </button>
          <button className="action-btn" onClick={() => setShowNoteModal(true)}>
            📝 添加处置记录
          </button>
          {incident.status !== 'resolved' && (
            <button className="action-btn success" onClick={() => setShowResolveModal(true)}>
              ✅ 标记已解决
            </button>
          )}
        </div>
      </div>

      <div className="detail-tabs">
        <button className={`tab ${activeTab === 'timeline' ? 'active' : ''}`} onClick={() => setActiveTab('timeline')}>
          ⏱️ 处置时间轴
        </button>
        <button className={`tab ${activeTab === 'targets' ? 'active' : ''}`} onClick={() => setActiveTab('targets')}>
          🎯 影响范围
        </button>
        <button className={`tab ${activeTab === 'alerts' ? 'active' : ''}`} onClick={() => setActiveTab('alerts')}>
          🚨 告警流
        </button>
        <button className={`tab ${activeTab === 'topology' ? 'active' : ''}`} onClick={() => setActiveTab('topology')}>
          🔗 拓扑扩散
        </button>
        <button className={`tab ${activeTab === 'context' ? 'active' : ''}`} onClick={() => setActiveTab('context')}>
          📊 变更&SLO
        </button>
        <button className={`tab ${activeTab === 'notes' ? 'active' : ''}`} onClick={() => setActiveTab('notes')}>
          📝 处置记录
        </button>
      </div>

      <div className="detail-content">
        {activeTab === 'timeline' && (
          <div className="timeline-panel">
            <h3>完整处置时间轴</h3>
            <div className="timeline-list">
              {sortedTimeline.length === 0 && <p className="empty-text">暂无时间轴记录</p>}
              {sortedTimeline.map((event, idx) => (
                <div key={event.id || idx} className="timeline-item">
                  <div
                    className="timeline-dot"
                    style={{ backgroundColor: severityColors[event.severity] || '#6b7280' }}
                  />
                  <div className="timeline-content">
                    <div className="timeline-header">
                      <span className="timeline-type">
                        {eventTypeLabels[event.event_type] || event.event_type}
                      </span>
                      <span className="timeline-time">{formatTime(event.timestamp)}</span>
                    </div>
                    <div className="timeline-title">{event.title}</div>
                    {event.description && <div className="timeline-desc">{event.description}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'targets' && (
          <div className="targets-panel">
            <h3>受影响目标</h3>
            <div className="targets-grid">
              {(incident.targets || []).map(t => (
                <div key={t.target_id} className="target-card">
                  <div className="target-card-header">
                    <span className={`status-dot`} style={{ backgroundColor: targetStatusColors[t.target_status] || '#6b7280' }} />
                    <span className="target-name">{t.target_name}</span>
                    {t.role === 'source' && <span className="role-tag source">故障源</span>}
                  </div>
                  <div className="target-card-meta">
                    <span>状态: <b style={{ color: targetStatusColors[t.target_status] }}>{t.target_status}</b></span>
                    <span>分组: {t.group_name || '—'}</span>
                    <span>最高等级: {t.max_severity}</span>
                  </div>
                  <div className="target-card-time">
                    <span>首告警: {formatTime(t.first_alert_at)}</span>
                    <span>末告警: {formatTime(t.last_alert_at)}</span>
                  </div>
                </div>
              ))}
            </div>

            {(incident.upstream_dependencies?.length > 0 || incident.downstream_dependencies?.length > 0) && (
              <>
                <h3 className="section-subtitle">上下游依赖</h3>
                {incident.upstream_dependencies?.length > 0 && (
                  <div className="deps-section">
                    <h4>↑ 上游依赖</h4>
                    <div className="deps-grid">
                      {incident.upstream_dependencies.map(d => (
                        <div key={`up-${d.target_id}`} className="dep-card upstream">
                          <span className="status-dot" style={{ backgroundColor: targetStatusColors[d.status] }} />
                          <span>{d.target_name}</span>
                          <span className={`dep-status status-${d.status}`}>{d.status}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {incident.downstream_dependencies?.length > 0 && (
                  <div className="deps-section">
                    <h4>↓ 下游依赖</h4>
                    <div className="deps-grid">
                      {incident.downstream_dependencies.map(d => (
                        <div key={`down-${d.target_id}`} className="dep-card downstream">
                          <span className="status-dot" style={{ backgroundColor: targetStatusColors[d.status] }} />
                          <span>{d.target_name}</span>
                          <span className={`dep-status status-${d.status}`}>{d.status}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {incident.region_divergence?.length > 0 && (
              <>
                <h3 className="section-subtitle">🌐 多地区观测分歧</h3>
                <div className="divergence-list">
                  {incident.region_divergence.map(div => (
                    <div key={div.target_id} className="divergence-item">
                      <div className="divergence-target">{div.target_name}</div>
                      <div className="divergence-regions">
                        {div.regions?.map(r => (
                          <span
                            key={r.name}
                            className={`region-tag status-${r.status}`}
                          >
                            {r.name}: {r.status}
                          </span>
                        ))}
                      </div>
                      <div className="divergence-summary" style={{ color: severityColors[div.severity] }}>
                        {div.summary}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === 'alerts' && (
          <div className="alerts-panel">
            <h3>告警流 ({sortedAlerts.length})</h3>
            <div className="alerts-list">
              {sortedAlerts.length === 0 && <p className="empty-text">暂无告警</p>}
              {sortedAlerts.map(a => (
                <div key={a.alert_id} className="alert-row">
                  <span className={`alert-severity ${a.to_status === 'down' ? 'critical' : 'warning'}`}>
                    {a.to_status === 'down' ? 'CRITICAL' : 'WARNING'}
                  </span>
                  <span className="alert-target">{a.target_name}</span>
                  <span className="alert-transition">{a.from_status} → {a.to_status}</span>
                  <span className="alert-time">{formatTime(a.timestamp)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'topology' && (
          <div className="topology-panel">
            <h3>拓扑扩散路径</h3>
            <div className="topology-viz">
              <div className="topo-node source">
                <div className="topo-label">故障源</div>
                <div className="topo-targets">
                  {(incident.targets || []).filter(t => t.role === 'source').map(t => (
                    <span key={t.target_id} className="topo-target-tag status-down">{t.target_name}</span>
                  ))}
                </div>
              </div>
              <div className="topo-arrow">↓ 扩散</div>
              <div className="topo-node affected">
                <div className="topo-label">受影响 ({incident.target_count || 0})</div>
                <div className="topo-targets">
                  {(incident.targets || []).map(t => (
                    <span
                      key={t.target_id}
                      className={`topo-target-tag status-${t.target_status}`}
                    >
                      {t.target_name}
                    </span>
                  ))}
                </div>
              </div>
              {incident.downstream_dependencies?.length > 0 && (
                <>
                  <div className="topo-arrow">↓ 下游级联</div>
                  <div className="topo-node downstream">
                    <div className="topo-label">下游依赖</div>
                    <div className="topo-targets">
                      {incident.downstream_dependencies.map(d => (
                        <span
                          key={d.target_id}
                          className={`topo-target-tag status-${d.status}`}
                        >
                          {d.target_name}
                        </span>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {activeTab === 'context' && (
          <div className="context-panel">
            <h3>🛡️ 关联变更</h3>
            <div className="changes-list">
              {(incident.active_changes || []).length === 0 && <p className="empty-text">未发现相关变更</p>}
              {(incident.active_changes || []).map(c => (
                <div key={c.change_id} className="change-row">
                  <span className={`change-status ${c.status}`}>{c.status}</span>
                  <span className="change-name">{c.name}</span>
                  <span className="change-creator">{c.created_by}</span>
                  <span className="change-time">计划: {formatTime(c.planned_time)}</span>
                </div>
              ))}
            </div>

            <h3 className="section-subtitle">📉 SLO 预算燃尽风险</h3>
            <div className="slo-list">
              {(incident.slo_budget_risks || []).length === 0 && <p className="empty-text">未关联SLO</p>}
              {(incident.slo_budget_risks || []).map(s => (
                <div key={s.slo_id} className={`slo-row status-${s.status}`}>
                  <span className="slo-name">{s.slo_name}</span>
                  <div className="slo-budget-bar">
                    <div
                      className="slo-budget-fill"
                      style={{
                        width: `${s.budget_remaining_pct || 0}%`,
                        backgroundColor: s.status === 'critical' ? '#ef4444' : s.status === 'warning' ? '#f59e0b' : '#10b981',
                      }}
                    />
                  </div>
                  <span className="slo-pct">{s.budget_remaining_pct?.toFixed(1)}%</span>
                  <span className="slo-burn">燃尽: {s.burn_rate?.toFixed(1)}x</span>
                  <span className={`slo-status status-${s.status}`}>{s.status}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'notes' && (
          <div className="notes-panel">
            <div className="notes-header">
              <h3>处置记录 ({sortedNotes.length})</h3>
              <button className="action-btn small" onClick={() => setShowNoteModal(true)}>
                + 添加记录
              </button>
            </div>
            <div className="notes-list">
              {sortedNotes.length === 0 && <p className="empty-text">暂无处置记录</p>}
              {sortedNotes.map(n => (
                <div key={n.id} className="note-card">
                  <div className="note-header">
                    <span className="note-author">👤 {n.author}</span>
                    <span className="note-type">{n.action_type === 'transfer' ? '转交备注' : '处置记录'}</span>
                    <span className="note-time">{formatTime(n.created_at)}</span>
                  </div>
                  <div className="note-content">{n.content}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {showAckModal && (
        <div className="modal-overlay" onClick={() => setShowAckModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>手动接管故障</h3>
            <div className="form-field">
              <label>您的姓名</label>
              <input
                type="text"
                value={ackData.acknowledged_by}
                onChange={e => setAckData({ ...ackData, acknowledged_by: e.target.value })}
                placeholder="输入姓名"
              />
            </div>
            <div className="form-field">
              <label>备注（可选）</label>
              <textarea
                value={ackData.notes}
                onChange={e => setAckData({ ...ackData, notes: e.target.value })}
                placeholder="接管说明..."
              />
            </div>
            <div className="modal-actions">
              <button className="btn secondary" onClick={() => setShowAckModal(false)}>取消</button>
              <button className="btn primary" onClick={handleAcknowledge}>确认接管</button>
            </div>
          </div>
        </div>
      )}

      {showTransferModal && (
        <div className="modal-overlay" onClick={() => setShowTransferModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>转交负责人</h3>
            <div className="form-field">
              <label>新负责人</label>
              <input
                type="text"
                value={transferData.new_owner}
                onChange={e => setTransferData({ ...transferData, new_owner: e.target.value })}
                placeholder="输入新负责人姓名"
              />
            </div>
            <div className="form-field">
              <label>转交人</label>
              <input
                type="text"
                value={transferData.transferred_by}
                onChange={e => setTransferData({ ...transferData, transferred_by: e.target.value })}
                placeholder="输入您的姓名"
              />
            </div>
            <div className="form-field">
              <label>备注（可选）</label>
              <textarea
                value={transferData.notes}
                onChange={e => setTransferData({ ...transferData, notes: e.target.value })}
                placeholder="转交说明..."
              />
            </div>
            <div className="modal-actions">
              <button className="btn secondary" onClick={() => setShowTransferModal(false)}>取消</button>
              <button className="btn primary" onClick={handleTransfer}>确认转交</button>
            </div>
          </div>
        </div>
      )}

      {showNoteModal && (
        <div className="modal-overlay" onClick={() => setShowNoteModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>添加处置记录</h3>
            <div className="form-field">
              <label>记录人</label>
              <input
                type="text"
                value={noteData.author}
                onChange={e => setNoteData({ ...noteData, author: e.target.value })}
                placeholder="输入姓名"
              />
            </div>
            <div className="form-field">
              <label>记录类型</label>
              <select
                value={noteData.action_type}
                onChange={e => setNoteData({ ...noteData, action_type: e.target.value })}
              >
                <option value="note">处置记录</option>
                <option value="investigation">排查进展</option>
                <option value="mitigation">止血操作</option>
                <option value="observation">观测记录</option>
              </select>
            </div>
            <div className="form-field">
              <label>记录内容</label>
              <textarea
                value={noteData.content}
                onChange={e => setNoteData({ ...noteData, content: e.target.value })}
                placeholder="请详细描述处置进展..."
                rows={4}
              />
            </div>
            <div className="modal-actions">
              <button className="btn secondary" onClick={() => setShowNoteModal(false)}>取消</button>
              <button className="btn primary" onClick={handleAddNote}>添加记录</button>
            </div>
          </div>
        </div>
      )}

      {showResolveModal && (
        <div className="modal-overlay" onClick={() => setShowResolveModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>标记故障已解决</h3>
            <div className="form-field">
              <label>确认人</label>
              <input
                type="text"
                value={resolveData.resolved_by}
                onChange={e => setResolveData({ ...resolveData, resolved_by: e.target.value })}
                placeholder="输入姓名"
              />
            </div>
            <div className="form-field checkbox-field">
              <label>
                <input
                  type="checkbox"
                  checked={resolveData.mark_for_review}
                  onChange={e => setResolveData({ ...resolveData, mark_for_review: e.target.checked })}
                />
                标记为待复盘
              </label>
            </div>
            {resolveData.mark_for_review && (
              <div className="form-field">
                <label>复盘要点</label>
                <textarea
                  value={resolveData.review_notes}
                  onChange={e => setResolveData({ ...resolveData, review_notes: e.target.value })}
                  placeholder="需要在复盘会上讨论的要点..."
                  rows={3}
                />
              </div>
            )}
            <div className="modal-actions">
              <button className="btn secondary" onClick={() => setShowResolveModal(false)}>取消</button>
              <button className="btn success" onClick={handleResolve}>确认解决</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default IncidentDetail;
