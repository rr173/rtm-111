import { useState, useMemo } from 'react';
import TargetCard from './TargetCard';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function GroupCard({
  group,
  targets,
  allGroups = [],
  expandedTarget,
  onToggleExpand,
  onDeleteTarget,
  onTogglePause,
  onToggleSilence,
  detailData,
  onRefreshGroups,
  onRefreshTargets,
  onTargetGroupChange,
  targetRoundResultsMap = {}
}) {
  const [expanded, setExpanded] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [editingThresholds, setEditingThresholds] = useState(false);
  const [thresholdForm, setThresholdForm] = useState({
    degrade_threshold: group.degrade_threshold,
    down_threshold: group.down_threshold,
    success_threshold: group.success_threshold
  });

  const statusLabel = useMemo(() => {
    switch (group.status) {
      case 'healthy': return '健康';
      case 'degraded': return '降级';
      case 'down': return '故障';
      case 'paused': return '已暂停';
      default: return group.status;
    }
  }, [group.status]);

  const allPaused = group.paused_count === group.target_count && group.target_count > 0;

  const handlePauseAll = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/groups/${group.id}/pause`, {
        method: 'POST'
      });
      if (res.ok) {
        if (onRefreshTargets) onRefreshTargets();
      }
    } catch (e) {
      console.error('Failed to pause group:', e);
    }
  };

  const handleResumeAll = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/groups/${group.id}/resume`, {
        method: 'POST'
      });
      if (res.ok) {
        if (onRefreshTargets) onRefreshTargets();
      }
    } catch (e) {
      console.error('Failed to resume group:', e);
    }
  };

  const handleSilenceAll = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/groups/${group.id}/silence`, {
        method: 'POST'
      });
      if (res.ok) {
        if (onRefreshTargets) onRefreshTargets();
      }
    } catch (e) {
      console.error('Failed to silence group:', e);
    }
  };

  const handleUnsilenceAll = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/groups/${group.id}/unsilence`, {
        method: 'POST'
      });
      if (res.ok) {
        if (onRefreshTargets) onRefreshTargets();
      }
    } catch (e) {
      console.error('Failed to unsilence group:', e);
    }
  };

  const handleApplyThresholds = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/groups/${group.id}/apply-thresholds`, {
        method: 'POST'
      });
      if (res.ok) {
        if (onRefreshTargets) onRefreshTargets();
        alert('阈值已应用到组内所有目标');
      }
    } catch (e) {
      console.error('Failed to apply thresholds:', e);
    }
  };

  const handleSaveThresholds = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/groups/${group.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(thresholdForm)
      });
      if (res.ok) {
        setEditingThresholds(false);
        if (onRefreshGroups) onRefreshGroups();
      }
    } catch (e) {
      console.error('Failed to update group thresholds:', e);
    }
  };

  const handleDeleteGroup = async () => {
    if (!confirm(`确定要删除分组"${group.name}"吗？组内目标将变为未分组状态。`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/groups/${group.id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        if (onRefreshGroups) onRefreshGroups();
        if (onRefreshTargets) onRefreshTargets();
      }
    } catch (e) {
      console.error('Failed to delete group:', e);
    }
  };

  const hasSilenced = targets.some(t => t.silenced);

  return (
    <div className={`group-card ${expanded ? 'expanded' : ''}`}>
      <div
        className="group-header"
        style={{ borderLeftColor: group.color }}
        onClick={() => setExpanded(!expanded)}
      >
        <div className="group-header-left">
          <span className={`expand-icon ${expanded ? 'expanded' : ''}`}>▶</span>
          <div className="group-info">
            <div className="group-name">
              {group.name}
              <span className={`status-badge ${group.status}`}>
                {statusLabel}
              </span>
              {group.target_count > 0 && (
                <span className="group-count-badge">
                  {group.target_count} 个目标
                </span>
              )}
            </div>
            {group.description && (
              <div className="group-description">{group.description}</div>
            )}
          </div>
        </div>

        <div className="group-stats">
          {group.healthy_count > 0 && (
            <span className="group-stat healthy">
              <span className="stat-dot"></span>
              {group.healthy_count}
            </span>
          )}
          {group.degraded_count > 0 && (
            <span className="group-stat degraded">
              <span className="stat-dot"></span>
              {group.degraded_count}
            </span>
          )}
          {group.down_count > 0 && (
            <span className="group-stat down">
              <span className="stat-dot"></span>
              {group.down_count}
            </span>
          )}
          {group.paused_count > 0 && (
            <span className="group-stat paused">
              <span className="stat-dot"></span>
              {group.paused_count} 暂停
            </span>
          )}
        </div>

        <div className="group-actions" onClick={(e) => e.stopPropagation()}>
          {allPaused ? (
            <button className="action-btn" onClick={handleResumeAll}>全部恢复</button>
          ) : (
            <button className="action-btn" onClick={handlePauseAll}>全部暂停</button>
          )}
          {hasSilenced ? (
            <button className="action-btn" onClick={handleUnsilenceAll}>全部取消消声</button>
          ) : (
            <button className="action-btn silence" onClick={handleSilenceAll}>全部消声</button>
          )}
          <button className="action-btn" onClick={() => setShowSettings(true)}>设置</button>
        </div>
      </div>

      {expanded && (
        <div className="group-targets">
          {targets.length > 0 ? (
            targets.map(target => (
              <TargetCard
                key={target.id}
                target={target}
                groups={allGroups}
                onGroupChange={onTargetGroupChange}
                expanded={expandedTarget === target.id}
                onToggleExpand={() => onToggleExpand(expandedTarget === target.id ? null : target.id)}
                onDelete={onDeleteTarget}
                onTogglePause={onTogglePause}
                onToggleSilence={onToggleSilence}
                detailData={detailData}
                roundResults={targetRoundResultsMap[target.id] || []}
              />
            ))
          ) : (
            <div className="group-empty">
              该分组暂无目标
            </div>
          )}
        </div>
      )}

      {showSettings && (
        <div className="modal-overlay" onClick={() => setShowSettings(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>分组设置 - {group.name}</h2>

            <div className="form-group">
              <label>分组名称</label>
              <input type="text" value={group.name} readOnly />
            </div>

            <div className="form-group">
              <label>描述</label>
              <input type="text" value={group.description || ''} readOnly />
            </div>

            <h3 style={{ fontSize: '14px', marginTop: '20px', marginBottom: '12px', color: '#cbd5e1' }}>
              告警阈值配置
            </h3>

            {editingThresholds ? (
              <>
                <div className="form-row">
                  <div className="form-group">
                    <label>降级阈值 (连续失败次数)</label>
                    <input
                      type="number"
                      min="1"
                      max="100"
                      value={thresholdForm.degrade_threshold}
                      onChange={(e) => setThresholdForm(prev => ({
                        ...prev,
                        degrade_threshold: parseInt(e.target.value) || 1
                      }))}
                    />
                  </div>
                  <div className="form-group">
                    <label>故障阈值 (连续失败次数)</label>
                    <input
                      type="number"
                      min="1"
                      max="100"
                      value={thresholdForm.down_threshold}
                      onChange={(e) => setThresholdForm(prev => ({
                        ...prev,
                        down_threshold: parseInt(e.target.value) || 1
                      }))}
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>恢复阈值 (连续成功次数)</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={thresholdForm.success_threshold}
                    onChange={(e) => setThresholdForm(prev => ({
                      ...prev,
                      success_threshold: parseInt(e.target.value) || 1
                    }))}
                  />
                </div>
                <div className="modal-actions">
                  <button className="btn btn-secondary" onClick={() => setEditingThresholds(false)}>
                    取消
                  </button>
                  <button className="btn btn-primary" onClick={handleSaveThresholds}>
                    保存
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="thresholds-display">
                  <div className="threshold-item">
                    <span className="threshold-label">降级阈值</span>
                    <span className="threshold-value">
                      连续失败 {group.degrade_threshold} 次
                    </span>
                  </div>
                  <div className="threshold-item">
                    <span className="threshold-label">故障阈值</span>
                    <span className="threshold-value">
                      连续失败 {group.down_threshold} 次
                    </span>
                  </div>
                  <div className="threshold-item">
                    <span className="threshold-label">恢复阈值</span>
                    <span className="threshold-value">
                      连续成功 {group.success_threshold} 次
                    </span>
                  </div>
                </div>

                <div style={{ marginTop: '16px', display: 'flex', gap: '8px' }}>
                  <button
                    className="btn btn-secondary"
                    style={{ flex: 1 }}
                    onClick={() => {
                      setThresholdForm({
                        degrade_threshold: group.degrade_threshold,
                        down_threshold: group.down_threshold,
                        success_threshold: group.success_threshold
                      });
                      setEditingThresholds(true);
                    }}
                  >
                    修改阈值
                  </button>
                  <button
                    className="btn btn-primary"
                    style={{ flex: 1 }}
                    onClick={handleApplyThresholds}
                  >
                    应用到所有目标
                  </button>
                </div>

                <div className="modal-actions">
                  <button
                    className="btn btn-secondary danger"
                    onClick={handleDeleteGroup}
                    style={{ marginRight: 'auto', color: '#f87171' }}
                  >
                    删除分组
                  </button>
                  <button className="btn btn-primary" onClick={() => setShowSettings(false)}>
                    关闭
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default GroupCard;
