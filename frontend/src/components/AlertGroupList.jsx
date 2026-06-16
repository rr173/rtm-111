import { useState } from 'react';
import { getSeverityLevel } from '../utils/alertNoiseReduction';

function formatDuration(startTime, endTime) {
  const start = new Date(startTime).getTime();
  const end = new Date(endTime).getTime();
  const diffMs = end - start;
  const diffMins = Math.floor(diffMs / 60000);
  
  if (diffMins < 60) return `${diffMins} 分钟`;
  const hours = Math.floor(diffMins / 60);
  const mins = diffMins % 60;
  return `${hours} 小时 ${mins} 分`;
}

function formatTime(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
}

function AlertTimeline({ alerts }) {
  const sorted = [...alerts].sort(
    (a, b) => new Date(a.timestamp) - new Date(b.timestamp)
  );

  return (
    <div className="alert-timeline">
      <div className="timeline-title">告警时间线</div>
      <div className="timeline-events">
        {sorted.map((alert, idx) => {
          const levelClass = alert.to_status === 'down' ? 'down' 
            : alert.to_status === 'degraded' ? 'degraded' 
            : alert.to_status === 'partial' ? 'partial' : 'healthy';
          return (
            <div key={alert.id} className="timeline-event">
              <div className="timeline-connector">
                <div className={`timeline-dot ${levelClass}`}></div>
                {idx < sorted.length - 1 && <div className="timeline-line"></div>}
              </div>
              <div className="timeline-content">
                <div className="timeline-header">
                  <span className={`alert-level ${levelClass}`}></span>
                  <span className="timeline-target">{alert.target_name}</span>
                  <span className="timeline-time">{formatTime(alert.timestamp)}</span>
                </div>
                <div className="timeline-status">
                  {alert.from_status.toUpperCase()} → {alert.to_status.toUpperCase()}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AlertRelationGraph({ group, targets, dependencies }) {
  const targetIds = group.affected_target_ids;
  const relatedTargets = targets.filter(t => targetIds.includes(t.id));

  const nodePositions = {};
  const centerX = 300;
  const centerY = 200;
  const radius = 130;

  relatedTargets.forEach((t, idx) => {
    const angle = (idx / Math.max(relatedTargets.length, 1)) * 2 * Math.PI - Math.PI / 2;
    nodePositions[t.id] = {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle)
    };
  });

  const edges = [];
  dependencies.forEach(dep => {
    if (targetIds.includes(dep.upstream_id) && targetIds.includes(dep.downstream_id)) {
      edges.push(dep);
    }
  });

  return (
    <div className="relation-graph">
      <div className="timeline-title">关联关系图</div>
      <div className="relation-graph-container">
        <svg width="600" height="400" className="relation-svg">
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="7"
              refX="9"
              refY="3.5"
              orient="auto"
            >
              <polygon points="0 0, 10 3.5, 0 7" fill="#475569" />
            </marker>
          </defs>

          {edges.map((edge, idx) => {
            const from = nodePositions[edge.upstream_id];
            const to = nodePositions[edge.downstream_id];
            if (!from || !to) return null;

            const dx = to.x - from.x;
            const dy = to.y - from.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const offsetX = (dx / dist) * 40;
            const offsetY = (dy / dist) * 40;

            return (
              <line
                key={idx}
                x1={from.x + offsetX}
                y1={from.y + offsetY}
                x2={to.x - offsetX}
                y2={to.y - offsetY}
                stroke="#475569"
                strokeWidth="2"
                markerEnd="url(#arrowhead)"
              />
            );
          })}

          {relatedTargets.map(target => {
            const pos = nodePositions[target.id];
            const statusClass = target.status;
            const sev = getSeverityLevel(group.severity_score);
            const isCenter = relatedTargets.indexOf(target) === 0;

            return (
              <g key={target.id}>
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={isCenter ? 42 : 36}
                  fill="#1e293b"
                  stroke={isCenter ? sev.color : '#334155'}
                  strokeWidth={isCenter ? 3 : 2}
                />
                <text
                  x={pos.x}
                  y={pos.y - 6}
                  textAnchor="middle"
                  fill="#e2e8f0"
                  fontSize="12"
                  fontWeight="500"
                >
                  {target.name.length > 10 ? target.name.slice(0, 10) + '...' : target.name}
                </text>
                <circle
                  cx={pos.x + 24}
                  cy={pos.y - 24}
                  r="8"
                  className={`status-circle status-${statusClass}`}
                />
              </g>
            );
          })}
        </svg>
      </div>
      <div className="relation-legend">
        <span className="legend-item">
          <span className="legend-dot legend-down"></span>
          故障
        </span>
        <span className="legend-item">
          <span className="legend-dot legend-degraded"></span>
          降级
        </span>
        <span className="legend-item">
          <span className="legend-dot legend-healthy"></span>
          正常
        </span>
        <span className="legend-item">
          → 依赖方向
        </span>
      </div>
    </div>
  );
}

function AlertGroupCard({ group, targets, dependencies, expanded, onToggle, onAcknowledge }) {
  const sev = getSeverityLevel(group.severity_score);
  const now = new Date();

  return (
    <div className={`alert-group-card ${expanded ? 'expanded' : ''}`}>
      <div 
        className="alert-group-header"
        onClick={onToggle}
      >
        <div className="group-severity-bar" style={{ backgroundColor: sev.color }}></div>
        
        <div className="group-main-info">
          <div className="group-title-row">
            <span 
              className="group-severity-badge"
              style={{ backgroundColor: `${sev.color}20`, color: sev.color }}
            >
              {sev.label}
            </span>
            <h3 className="group-name">{group.name}</h3>
            <span className="group-score-badge">
              评分 {group.severity_score}
            </span>
          </div>
          <div className="group-meta-row">
            <span className="meta-item">
              📦 {group.alert_count} 条告警
            </span>
            <span className="meta-item">
              🎯 {group.target_count} 个目标
            </span>
            <span className="meta-item">
              ⏱ 持续 {formatDuration(group.started_at, group.last_updated_at || now)}
            </span>
            <span className="meta-item">
              🕐 {formatTime(group.started_at)} 开始
            </span>
          </div>
        </div>

        <div className="group-actions">
          <button
            className="action-btn"
            onClick={(e) => {
              e.stopPropagation();
              onAcknowledge(group.id, !group.acknowledged);
            }}
          >
            {group.acknowledged ? '✓ 已确认' : '确认'}
          </button>
          <span className={`expand-icon ${expanded ? 'expanded' : ''}`}>▼</span>
        </div>
      </div>

      {expanded && (
        <div className="alert-group-details">
          <div className="details-grid">
            <div className="details-col">
              <AlertTimeline alerts={group.alerts} />
            </div>
            <div className="details-col">
              <AlertRelationGraph 
                group={group} 
                targets={targets} 
                dependencies={dependencies} 
              />
            </div>
          </div>
          
          <div className="affected-targets">
            <div className="timeline-title">受影响目标</div>
            <div className="targets-row">
              {group.affected_targets?.map(target => (
                <div key={target.id} className="affected-target-chip">
                  <span className={`target-status-dot status-${target.status}`}></span>
                  {target.name}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AlertGroupList({ groups, targets, dependencies, onAcknowledgeGroup }) {
  const [expandedId, setExpandedId] = useState(null);

  if (groups.length === 0) {
    return (
      <div className="nr-empty-state big">
        <div className="empty-icon">🎉</div>
        <div className="empty-text">暂无告警组</div>
        <div className="empty-hint">所有系统运行正常，告警已全部归并或抑制</div>
      </div>
    );
  }

  return (
    <div className="alert-group-list">
      <div className="nr-header">
        <div className="nr-header-title">
          <h2>🚨 告警组列表</h2>
          <p className="nr-subtitle">按综合严重度评分排序 · 共 {groups.length} 个告警组</p>
        </div>
      </div>
      <div className="groups-container">
        {groups.map(group => (
          <AlertGroupCard
            key={group.id}
            group={group}
            targets={targets}
            dependencies={dependencies}
            expanded={expandedId === group.id}
            onToggle={() => setExpandedId(expandedId === group.id ? null : group.id)}
            onAcknowledge={onAcknowledgeGroup}
          />
        ))}
      </div>
    </div>
  );
}

export default AlertGroupList;
