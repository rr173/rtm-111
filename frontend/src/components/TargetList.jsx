import { useMemo } from 'react';
import GroupCard from './GroupCard';
import TargetCard from './TargetCard';

function TargetList({
  targets,
  groups,
  expandedTarget,
  onToggleExpand,
  onDelete,
  onTogglePause,
  onToggleSilence,
  detailData,
  onRefreshGroups,
  onRefreshTargets,
  onTargetGroupChange
}) {
  const groupedTargets = useMemo(() => {
    const result = {};
    for (const group of groups) {
      result[group.id] = [];
    }
    result['_ungrouped'] = [];

    for (const target of targets) {
      if (target.group_id && result[target.group_id]) {
        result[target.group_id].push(target);
      } else {
        result['_ungrouped'].push(target);
      }
    }

    return result;
  }, [targets, groups]);

  const groupWithStats = useMemo(() => {
    return groups.map(group => {
      const groupTargets = groupedTargets[group.id] || [];
      const activeTargets = groupTargets.filter(t => !t.paused);

      let status = 'healthy';
      if (activeTargets.length === 0) {
        status = groupTargets.length > 0 ? 'paused' : 'healthy';
      } else {
        const hasDown = activeTargets.some(t => t.status === 'down');
        const hasDegraded = activeTargets.some(t => t.status === 'degraded');
        if (hasDown) status = 'down';
        else if (hasDegraded) status = 'degraded';
      }

      return {
        ...group,
        status,
        target_count: groupTargets.length,
        paused_count: groupTargets.filter(t => t.paused).length,
        healthy_count: activeTargets.filter(t => t.status === 'healthy').length,
        degraded_count: activeTargets.filter(t => t.status === 'degraded').length,
        down_count: activeTargets.filter(t => t.status === 'down').length
      };
    });
  }, [groups, groupedTargets]);

  const ungroupedTargets = groupedTargets['_ungrouped'] || [];

  const hasGroups = groups.length > 0;
  const hasUngrouped = ungroupedTargets.length > 0;

  if (targets.length === 0) {
    return (
      <div className="target-list">
        <div style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}>
          暂无探测目标，点击右下角 + 添加
        </div>
      </div>
    );
  }

  return (
    <div className="target-list">
      {groupWithStats.map(group => (
        <GroupCard
          key={group.id}
          group={group}
          targets={groupedTargets[group.id] || []}
          allGroups={groups}
          expandedTarget={expandedTarget}
          onToggleExpand={onToggleExpand}
          onDeleteTarget={onDelete}
          onTogglePause={onTogglePause}
          onToggleSilence={onToggleSilence}
          detailData={detailData}
          onRefreshGroups={onRefreshGroups}
          onRefreshTargets={onRefreshTargets}
          onTargetGroupChange={onTargetGroupChange}
        />
      ))}

      {hasUngrouped && (
        <div className="group-card">
          <div className="group-header ungrouped-header">
            <div className="group-header-left">
              <span className="expand-icon expanded">▶</span>
              <div className="group-info">
                <div className="group-name">
                  未分组
                  <span className="group-count-badge">
                    {ungroupedTargets.length} 个目标
                  </span>
                </div>
                <div className="group-description">未分配到任何分组的目标</div>
              </div>
            </div>
          </div>
          <div className="group-targets">
            {ungroupedTargets.map(target => (
              <TargetCard
                key={target.id}
                target={target}
                groups={groups}
                onGroupChange={onTargetGroupChange}
                expanded={expandedTarget === target.id}
                onToggleExpand={() => onToggleExpand(expandedTarget === target.id ? null : target.id)}
                onDelete={onDelete}
                onTogglePause={onTogglePause}
                onToggleSilence={onToggleSilence}
                detailData={detailData}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default TargetList;
