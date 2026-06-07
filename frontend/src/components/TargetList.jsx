import TargetCard from './TargetCard';

function TargetList({ targets, expandedTarget, onToggleExpand, onDelete, onTogglePause, onToggleSilence, detailData }) {
  return (
    <div className="target-list">
      {targets.map(target => (
        <TargetCard
          key={target.id}
          target={target}
          expanded={expandedTarget === target.id}
          onToggleExpand={() => onToggleExpand(expandedTarget === target.id ? null : target.id)}
          onDelete={onDelete}
          onTogglePause={onTogglePause}
          onToggleSilence={onToggleSilence}
          detailData={detailData[target.id]}
        />
      ))}
      {targets.length === 0 && (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}>
          暂无探测目标，点击右下角 + 添加
        </div>
      )}
    </div>
  );
}

export default TargetList;
