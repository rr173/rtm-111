import { useState, useCallback } from 'react';
import TopologyGraph from './TopologyGraph';
import DependencyModal from './DependencyModal';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

export default function TopologyPage({ targets, dependencies, setDependencies }) {
  const [showDepModal, setShowDepModal] = useState(false);
  const [simulationTargetId, setSimulationTargetId] = useState(null);
  const [simulatedAffectedIds, setSimulatedAffectedIds] = useState([]);
  const [simulatedAffectedNames, setSimulatedAffectedNames] = useState([]);
  const [isSimulating, setIsSimulating] = useState(false);

  const handleNodeDoubleClick = useCallback(async (node) => {
    if (!isSimulating) {
      setIsSimulating(true);
      setSimulationTargetId(node.id);

      try {
        const res = await fetch(`${API_BASE}/api/dependencies/simulate/${node.id}`);
        if (res.ok) {
          const data = await res.json();
          setSimulatedAffectedIds(data.affected_target_ids);
          setSimulatedAffectedNames(data.affected_target_names);
        }
      } catch (e) {
        console.error('Failed to simulate cascade:', e);
      }
    }
  }, [isSimulating]);

  const handleClearSimulation = () => {
    setSimulationTargetId(null);
    setSimulatedAffectedIds([]);
    setSimulatedAffectedNames([]);
    setIsSimulating(false);
  };

  const handleNodeClick = useCallback((node) => {
    console.log('Node clicked:', node);
  }, []);

  const cascadeCount = targets.filter(t => t.cascade_affected).length;
  const healthyCount = targets.filter(t => t.status === 'healthy' && !t.paused).length;
  const degradedCount = targets.filter(t => t.status === 'degraded' && !t.paused).length;
  const downCount = targets.filter(t => t.status === 'down' && !t.paused).length;

  return (
    <div className="topology-page">
      <div className="topology-header">
        <div className="topology-title">
          <h2>🔗 服务依赖拓扑</h2>
          <p className="topology-subtitle">
            展示服务之间的依赖关系与健康状态分布
          </p>
        </div>
        <div className="topology-actions">
          {isSimulating && (
            <button className="btn btn-secondary" onClick={handleClearSimulation}>
              清除模拟
            </button>
          )}
          <button
            className="btn btn-primary"
            onClick={() => setShowDepModal(true)}
          >
            管理依赖关系
          </button>
        </div>
      </div>

      <div className="topology-stats">
        <div className="topo-stat-card">
          <span className="topo-stat-label">总目标数</span>
          <span className="topo-stat-value">{targets.length}</span>
        </div>
        <div className="topo-stat-card healthy">
          <span className="topo-stat-label">健康</span>
          <span className="topo-stat-value">{healthyCount}</span>
        </div>
        <div className="topo-stat-card degraded">
          <span className="topo-stat-label">降级</span>
          <span className="topo-stat-value">{degradedCount}</span>
        </div>
        <div className="topo-stat-card down">
          <span className="topo-stat-label">故障</span>
          <span className="topo-stat-value">{downCount}</span>
        </div>
        <div className="topo-stat-card cascade">
          <span className="topo-stat-label">级联受损</span>
          <span className="topo-stat-value">{cascadeCount}</span>
        </div>
        <div className="topo-stat-card deps">
          <span className="topo-stat-label">依赖关系</span>
          <span className="topo-stat-value">{dependencies.length}</span>
        </div>
      </div>

      {isSimulating && (
        <div className="simulation-banner">
          <div className="simulation-info">
            <span className="simulation-icon">⚠️</span>
            <span>
              <strong>故障模拟中：</strong>
              假设「{targets.find(t => t.id === simulationTargetId)?.name}」故障
            </span>
          </div>
          <div className="simulation-result">
            将级联影响 <strong>{simulatedAffectedIds.length}</strong> 个下游目标
            {simulatedAffectedNames.length > 0 && (
              <span className="simulation-names">
                （{simulatedAffectedNames.slice(0, 3).join('、')}
                {simulatedAffectedNames.length > 3 ? ` 等${simulatedAffectedNames.length}个` : ''}）
              </span>
            )}
          </div>
        </div>
      )}

      <div className="topology-graph-wrapper">
        <TopologyGraph
          targets={targets}
          dependencies={dependencies}
          simulationTargetId={simulationTargetId}
          simulatedAffectedIds={simulatedAffectedIds}
          onNodeClick={handleNodeClick}
          onNodeDoubleClick={handleNodeDoubleClick}
        />
      </div>

      <div className="topology-tips">
        <p>💡 <strong>提示：</strong>双击任意节点可模拟该节点故障的级联影响范围；拖拽可平移画布</p>
      </div>

      {showDepModal && (
        <DependencyModal
          isOpen={showDepModal}
          onClose={() => setShowDepModal(false)}
          targets={targets}
          dependencies={dependencies}
          onDependenciesChange={setDependencies}
        />
      )}
    </div>
  );
}
