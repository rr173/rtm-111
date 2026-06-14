import { useState, useMemo } from 'react';
import IncidentDetail from './IncidentDetail';

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

const severityLabels = {
  warning: '警告',
  critical: '严重',
  info: '信息',
};

function formatDuration(seconds) {
  if (!seconds) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}时${m}分`;
  if (m > 0) return `${m}分${s}秒`;
  return `${s}秒`;
}

function formatTime(isoStr) {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  return d.toLocaleString('zh-CN', { hour12: false });
}

function CommandRoom({ incidents, incidentStats, targets, dependencies, onIncidentUpdate }) {
  const [selectedIncidentId, setSelectedIncidentId] = useState(null);
  const [filterStatus, setFilterStatus] = useState('all');

  const filteredIncidents = useMemo(() => {
    if (filterStatus === 'all') return incidents || [];
    if (filterStatus === 'active') {
      return (incidents || []).filter(i => i.status === 'active' || i.status === 'recovering');
    }
    if (filterStatus === 'review') {
      return (incidents || []).filter(i => i.needs_review);
    }
    return (incidents || []).filter(i => i.status === filterStatus);
  }, [incidents, filterStatus]);

  const activeIncidents = (incidents || []).filter(i => i.status === 'active' || i.status === 'recovering');
  const reviewIncidents = (incidents || []).filter(i => i.needs_review);

  if (selectedIncidentId) {
    return (
      <IncidentDetail
        incidentId={selectedIncidentId}
        targets={targets}
        dependencies={dependencies}
        onBack={() => setSelectedIncidentId(null)}
        onUpdate={onIncidentUpdate}
      />
    );
  }

  return (
    <div className="command-room">
      <div className="command-room-header">
        <h2>🚨 故障处置指挥室</h2>
        <div className="command-stats">
          <div className="stat-card stat-active">
            <span className="stat-label">进行中</span>
            <span className="stat-value">{incidentStats?.active_count || activeIncidents.length}</span>
          </div>
          <div className="stat-card stat-review">
            <span className="stat-label">待复盘</span>
            <span className="stat-value">{incidentStats?.review_count || reviewIncidents.length}</span>
          </div>
          <div className="stat-card stat-resolved">
            <span className="stat-label">已解决</span>
            <span className="stat-value">{incidentStats?.resolved_count || 0}</span>
          </div>
        </div>
      </div>

      <div className="command-filters">
        <button
          className={`filter-btn ${filterStatus === 'all' ? 'active' : ''}`}
          onClick={() => setFilterStatus('all')}
        >
          全部 ({incidents?.length || 0})
        </button>
        <button
          className={`filter-btn ${filterStatus === 'active' ? 'active' : ''}`}
          onClick={() => setFilterStatus('active')}
        >
          进行中 ({activeIncidents.length})
        </button>
        <button
          className={`filter-btn ${filterStatus === 'review' ? 'active' : ''}`}
          onClick={() => setFilterStatus('review')}
        >
          待复盘 ({reviewIncidents.length})
        </button>
        <button
          className={`filter-btn ${filterStatus === 'resolved' ? 'active' : ''}`}
          onClick={() => setFilterStatus('resolved')}
        >
          已解决
        </button>
      </div>

      <div className="incident-list">
        {filteredIncidents.length === 0 && (
          <div className="empty-state">
            <p>暂无故障事件</p>
          </div>
        )}
        {filteredIncidents.map(incident => (
          <div
            key={incident.id}
            className={`incident-card severity-${incident.severity} status-${incident.status}`}
            onClick={() => setSelectedIncidentId(incident.id)}
          >
            <div className="incident-header">
              <div className="incident-title-row">
                <span
                  className="severity-badge"
                  style={{ backgroundColor: severityColors[incident.severity] || '#6b7280' }}
                >
                  {severityLabels[incident.severity] || incident.severity}
                </span>
                <h3 className="incident-title">{incident.title}</h3>
                <span
                  className="status-badge"
                  style={{ backgroundColor: statusColors[incident.status] || '#6b7280' }}
                >
                  {statusLabels[incident.status] || incident.status}
                </span>
                {incident.mitigated && (
                  <span className="mitigated-badge">✓ 已止血</span>
                )}
                {incident.needs_review && (
                  <span className="review-badge">📋 待复盘</span>
                )}
              </div>
              <div className="incident-meta">
                <span>#{incident.id}</span>
                <span>负责人: {incident.owner || '未指派'}</span>
                <span>持续: {formatDuration(incident.duration_seconds)}</span>
                <span>首异常: {formatTime(incident.first_anomaly_at)}</span>
              </div>
            </div>

            {incident.description && (
              <p className="incident-desc">{incident.description}</p>
            )}

            <div className="incident-affected">
              <div className="affected-section">
                <span className="affected-label">🎯 受影响目标 ({incident.target_count || 0})</span>
                <div className="affected-targets">
                  {(incident.targets || []).slice(0, 4).map(t => (
                    <span key={t.target_id} className={`target-tag status-${t.target_status}`}>
                      {t.target_name}
                    </span>
                  ))}
                  {(incident.targets || []).length > 4 && (
                    <span className="target-tag more">+{(incident.targets || []).length - 4}</span>
                  )}
                </div>
              </div>

              {(incident.upstream_dependencies?.length > 0 || incident.downstream_dependencies?.length > 0) && (
                <div className="affected-section">
                  <span className="affected-label">🔗 依赖影响</span>
                  <div className="affected-deps">
                    {incident.upstream_dependencies?.slice(0, 2).map(d => (
                      <span key={`up-${d.target_id}`} className="dep-tag upstream">
                        ↑ {d.target_name}
                      </span>
                    ))}
                    {incident.downstream_dependencies?.slice(0, 2).map(d => (
                      <span key={`down-${d.target_id}`} className="dep-tag downstream">
                        ↓ {d.target_name}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="affected-section">
                <span className="affected-label">🚨 告警数: {incident.alert_count || 0}</span>
                {incident.region_divergence?.length > 0 && (
                  <span className="divergence-tag">⚠️ 多地区观测分歧</span>
                )}
                {incident.slo_budget_risks?.length > 0 && (
                  <span className="slo-tag">
                    📉 {incident.slo_budget_risks.filter(r => r.status === 'critical' || r.status === 'warning').length} 个SLO风险
                  </span>
                )}
                {incident.active_changes?.length > 0 && (
                  <span className="change-tag">🛡️ {incident.active_changes.length} 个进行中变更</span>
                )}
              </div>
            </div>

            <div className="incident-footer">
              <span className="click-hint">点击查看详情 →</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default CommandRoom;
