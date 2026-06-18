import { useState, useEffect, useCallback } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import StatsBar from './components/StatsBar';
import TargetList from './components/TargetList';
import AlertPanel from './components/AlertPanel';
import AddTargetModal from './components/AddTargetModal';
import AddGroupModal from './components/AddGroupModal';
import TopologyPage from './components/TopologyPage';
import RuleEditor from './components/RuleEditor';
import SnapshotList from './components/SnapshotList';
import ObservationMatrix from './components/ObservationMatrix';
import ChangeGuardianPanel from './components/ChangeGuardianPanel';
import SLOBudgetPanel from './components/SLOBudgetPanel';
import CommandRoom from './components/CommandRoom';
import NoiseReductionPage from './components/NoiseReductionPage';
import AutoDiscoveryPanel from './components/AutoDiscoveryPanel';
import RecordingControlPanel from './components/RecordingControlPanel';
import PlaybackControlPanel from './components/PlaybackControlPanel';
import MaintenanceCalendar from './components/MaintenanceCalendar';
import DutyDispatchCenter from './components/DutyDispatchCenter';
import CapacityMonitor from './components/CapacityMonitor';
import AuditLogPage from './components/AuditLogPage';
import ComplianceReportPage from './components/ComplianceReportPage';
import HealthRankingPanel from './components/HealthRankingPanel';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function App() {
  const {
    connected,
    targets,
    groups,
    alerts,
    dependencies,
    setTargets,
    setGroups,
    setAlerts,
    setDependencies,
    loadInitialData,
    observers,
    observationMatrix,
    targetRoundResultsMap,
    activeChanges,
    targetChangesMap,
    incidents,
    incidentStats,
    setIncidents,
    recordingStatus,
    playbackStatus,
    playbackFinished,
    setPlaybackFinished,
    maintenanceWindows,
    maintenanceTargets,
    loadMaintenanceData,
    healthScores,
  } = useWebSocket();
  const [activeTab, setActiveTab] = useState('list');
  const [expandedTarget, setExpandedTarget] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showAddGroupModal, setShowAddGroupModal] = useState(false);
  const [showRuleEditor, setShowRuleEditor] = useState(false);
  const [detailData, setDetailData] = useState({});
  const [rules, setRules] = useState([]);

  const loadRules = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/rules`);
      if (res.ok) {
        const data = await res.json();
        setRules(data);
      }
    } catch (e) {
      console.error('Failed to load rules:', e);
    }
  }, []);

  const refreshGroups = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/groups`);
      if (res.ok) {
        const data = await res.json();
        setGroups(data);
      }
    } catch (e) {
      console.error('Failed to refresh groups:', e);
    }
  }, [setGroups]);

  const refreshTargets = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/targets`);
      if (res.ok) {
        const data = await res.json();
        setTargets(data);
      }
    } catch (e) {
      console.error('Failed to refresh targets:', e);
    }
  }, [setTargets]);

  useEffect(() => {
    if (expandedTarget) {
      fetchTargetHistory(expandedTarget);
    }
  }, [expandedTarget]);

  useEffect(() => {
    loadRules();
  }, [loadRules]);

  const fetchTargetHistory = async (targetId) => {
    try {
      const res = await fetch(`${API_BASE}/api/targets/${targetId}/history?hours=24`);
      if (res.ok) {
        const data = await res.json();
        setDetailData(prev => ({ ...prev, [targetId]: data }));
      }
    } catch (e) {
      console.error('Failed to fetch history:', e);
    }
  };

  const addTarget = async (targetData) => {
    try {
      const res = await fetch(`${API_BASE}/api/targets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(targetData)
      });
      if (res.ok) {
        const newTarget = await res.json();
        setTargets(prev => [...prev, newTarget]);
        setShowAddModal(false);
      }
    } catch (e) {
      console.error('Failed to add target:', e);
    }
  };

  const deleteTarget = async (targetId) => {
    if (!confirm('确定要删除这个探测目标吗？')) return;
    try {
      const res = await fetch(`${API_BASE}/api/targets/${targetId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setTargets(prev => prev.filter(t => t.id !== targetId));
        if (expandedTarget === targetId) {
          setExpandedTarget(null);
        }
      }
    } catch (e) {
      console.error('Failed to delete target:', e);
    }
  };

  const togglePause = async (targetId, paused) => {
    try {
      const endpoint = paused ? 'pause' : 'resume';
      const res = await fetch(`${API_BASE}/api/targets/${targetId}/${endpoint}`, {
        method: 'POST'
      });
      if (res.ok) {
        setTargets(prev => prev.map(t =>
          t.id === targetId ? { ...t, paused } : t
        ));
      }
    } catch (e) {
      console.error('Failed to toggle pause:', e);
    }
  };

  const toggleSilence = async (targetId, silenced) => {
    try {
      const endpoint = silenced ? 'silence' : 'unsilence';
      const res = await fetch(`${API_BASE}/api/targets/${targetId}/${endpoint}`, {
        method: 'POST'
      });
      if (res.ok) {
        setTargets(prev => prev.map(t =>
          t.id === targetId ? { ...t, silenced } : t
        ));
      }
    } catch (e) {
      console.error('Failed to toggle silence:', e);
    }
  };

  const handleTargetGroupChange = useCallback((targetId, newGroupId) => {
    setTargets(prev => prev.map(t =>
      t.id === targetId ? { ...t, group_id: newGroupId } : t
    ));
  }, [setTargets]);

  const acknowledgeAlert = async (alertId, acknowledged) => {
    try {
      const res = await fetch(`${API_BASE}/api/alerts/${alertId}/acknowledge`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ acknowledged })
      });
      if (res.ok) {
        setAlerts(prev => prev.map(a =>
          a.id === alertId ? { ...a, acknowledged } : a
        ));
      }
    } catch (e) {
      console.error('Failed to acknowledge alert:', e);
    }
  };

  const healthyCount = targets.filter(t => t.status === 'healthy' && !t.paused).length;
  const partialCount = targets.filter(t => t.status === 'partial' && !t.paused).length;
  const degradedCount = targets.filter(t => t.status === 'degraded' && !t.paused).length;
  const downCount = targets.filter(t => t.status === 'down' && !t.paused).length;

  return (
    <div className="app">
      <header className="header">
        <h1>🔍 服务探活与告警仪表台</h1>
        <div className="header-tabs">
          <button
            className={`tab-btn ${activeTab === 'list' ? 'active' : ''}`}
            onClick={() => setActiveTab('list')}
          >
            📋 目标列表
          </button>
          <button
            className={`tab-btn ${activeTab === 'topology' ? 'active' : ''}`}
            onClick={() => setActiveTab('topology')}
          >
            🔗 依赖拓扑
          </button>
          <button
            className={`tab-btn ${activeTab === 'snapshots' ? 'active' : ''}`}
            onClick={() => setActiveTab('snapshots')}
          >
            📸 快照对比
          </button>
          <button
            className={`tab-btn ${activeTab === 'matrix' ? 'active' : ''}`}
            onClick={() => setActiveTab('matrix')}
          >
            🌐 观测矩阵
          </button>
          <button
            className={`tab-btn ${activeTab === 'changes' ? 'active' : ''}`}
            onClick={() => setActiveTab('changes')}
          >
            🛡️ 变更守护
          </button>
          <button
            className={`tab-btn ${activeTab === 'slo' ? 'active' : ''}`}
            onClick={() => setActiveTab('slo')}
          >
            📉 SLO预算
          </button>
          <button
            className={`tab-btn ${activeTab === 'command' ? 'active' : ''}`}
            onClick={() => setActiveTab('command')}
          >
            🚨 指挥室
          </button>
          <button
            className={`tab-btn ${activeTab === 'noise' ? 'active' : ''}`}
            onClick={() => setActiveTab('noise')}
          >
            🔕 智能降噪
          </button>
          <button
            className={`tab-btn ${activeTab === 'discovery' ? 'active' : ''}`}
            onClick={() => setActiveTab('discovery')}
          >
            🔍 自动发现
          </button>
          <button
            className={`tab-btn ${activeTab === 'maintenance' ? 'active' : ''}`}
            onClick={() => setActiveTab('maintenance')}
          >
            📅 维护日历
          </button>
          <button
            className={`tab-btn ${activeTab === 'duty' ? 'active' : ''}`}
            onClick={() => setActiveTab('duty')}
          >
            📟 值班调度
          </button>
          <button
            className={`tab-btn ${activeTab === 'capacity' ? 'active' : ''}`}
            onClick={() => setActiveTab('capacity')}
          >
            📊 容量水位
          </button>
          <button
            className={`tab-btn ${activeTab === 'replay' ? 'active' : ''}`}
            onClick={() => setActiveTab('replay')}
          >
            🎬 录制回放
          </button>
          <button
            className={`tab-btn ${activeTab === 'audit' ? 'active' : ''}`}
            onClick={() => setActiveTab('audit')}
          >
            📋 审计日志
          </button>
          <button
            className={`tab-btn ${activeTab === 'compliance' ? 'active' : ''}`}
            onClick={() => setActiveTab('compliance')}
          >
            📊 合规报告
          </button>
          <button
            className={`tab-btn`}
            onClick={() => setShowRuleEditor(true)}
          >
            📋 规则管理
          </button>
        </div>
        <div className="header-right">
          {(recordingStatus?.is_recording || playbackStatus?.is_playing || playbackStatus?.is_paused) && (
            <div className="global-status-bar">
              {recordingStatus?.is_recording && (
                <div className="global-indicator recording" onClick={() => setActiveTab('replay')}>
                  <span className="rec-dot"></span>
                  <span>🎬 录制中 {Math.floor(recordingStatus.duration_seconds || 0)}s</span>
                </div>
              )}
              {(playbackStatus?.is_playing || playbackStatus?.is_paused) && (
                <div
                  className={`global-indicator playback ${playbackStatus?.is_paused ? 'paused' : ''}`}
                  onClick={() => setActiveTab('replay')}
                >
                  <span className="play-dot"></span>
                  <span>
                    {playbackStatus?.is_paused ? '⏸️' : '▶️'} 回放 {playbackStatus.speed}x {(playbackStatus.progress || 0).toFixed(0)}%
                  </span>
                </div>
              )}
            </div>
          )}
          <div className="connection-status">
            <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`}></span>
            <span>{connected ? '实时连接' : '连接断开'}</span>
          </div>
        </div>
      </header>

      <div className="main-content">
        <div className="left-panel">
          {activeTab === 'list' ? (
            <>
              <StatsBar
                healthy={healthyCount}
                partial={partialCount}
                degraded={degradedCount}
                down={downCount}
              />
              <HealthRankingPanel
                scores={healthScores}
                groups={groups}
              />
              <TargetList
                targets={targets}
                groups={groups}
                expandedTarget={expandedTarget}
                onToggleExpand={setExpandedTarget}
                onDelete={deleteTarget}
                onTogglePause={togglePause}
                onToggleSilence={toggleSilence}
                detailData={detailData}
                onRefreshGroups={refreshGroups}
                onRefreshTargets={refreshTargets}
                onTargetGroupChange={handleTargetGroupChange}
                targetRoundResultsMap={targetRoundResultsMap || {}}
                targetChangesMap={targetChangesMap}
              />
            </>
          ) : activeTab === 'matrix' ? (
            <ObservationMatrix
              matrixData={observationMatrix}
              observers={observers}
              targets={targets}
            />
          ) : activeTab === 'topology' ? (
            <TopologyPage
              targets={targets}
              dependencies={dependencies}
              setDependencies={setDependencies}
            />
          ) : activeTab === 'changes' ? (
            <ChangeGuardianPanel
              targets={targets}
              activeChanges={activeChanges}
              targetChangesMap={targetChangesMap}
            />
          ) : activeTab === 'slo' ? (
            <SLOBudgetPanel targets={targets} groups={groups} />
          ) : activeTab === 'command' ? (
            <CommandRoom
              incidents={incidents}
              incidentStats={incidentStats}
              targets={targets}
              dependencies={dependencies}
              onIncidentUpdate={loadInitialData}
            />
          ) : activeTab === 'noise' ? (
            <NoiseReductionPage
              realAlerts={alerts}
              realTargets={targets}
              realDependencies={dependencies}
              realGroups={groups}
            />
          ) : activeTab === 'discovery' ? (
            <AutoDiscoveryPanel targets={targets} groups={groups} />
          ) : activeTab === 'maintenance' ? (
            <MaintenanceCalendar
              windows={maintenanceWindows}
              targets={maintenanceTargets.length > 0 ? maintenanceTargets : targets}
              groups={groups}
              onRefresh={loadMaintenanceData}
            />
          ) : activeTab === 'duty' ? (
            <DutyDispatchCenter />
          ) : activeTab === 'capacity' ? (
            <CapacityMonitor />
          ) : activeTab === 'audit' ? (
            <AuditLogPage />
          ) : activeTab === 'compliance' ? (
            <ComplianceReportPage />
          ) : activeTab === 'replay' ? (
            <div className="replay-page">
              <div className="replay-panels">
                <RecordingControlPanel
                  recordingStatus={recordingStatus}
                  targets={targets}
                  groups={groups}
                />
                <PlaybackControlPanel
                  playbackStatus={playbackStatus}
                  playbackFinished={playbackFinished}
                  setPlaybackFinished={setPlaybackFinished}
                  onPlaybackEnd={() => loadInitialData()}
                />
              </div>
              <div className="replay-visualization">
                <h3 className="replay-section-title">📊 实时状态概览</h3>
                <StatsBar
                  healthy={healthyCount}
                  partial={partialCount}
                  degraded={degradedCount}
                  down={downCount}
                />
                <TargetList
                  targets={targets}
                  groups={groups}
                  expandedTarget={expandedTarget}
                  onToggleExpand={setExpandedTarget}
                  onDelete={deleteTarget}
                  onTogglePause={togglePause}
                  onToggleSilence={toggleSilence}
                  detailData={detailData}
                  onRefreshGroups={refreshGroups}
                  onRefreshTargets={refreshTargets}
                  onTargetGroupChange={handleTargetGroupChange}
                  targetRoundResultsMap={targetRoundResultsMap || {}}
                  targetChangesMap={targetChangesMap}
                  compact={true}
                />
              </div>
            </div>
          ) : (
            <SnapshotList />
          )}
        </div>

        {activeTab !== 'slo' && activeTab !== 'command' && activeTab !== 'noise' && activeTab !== 'discovery' && activeTab !== 'replay' && activeTab !== 'duty' && activeTab !== 'capacity' && activeTab !== 'audit' && activeTab !== 'compliance' ? (
          <div className="right-panel">
            <AlertPanel
              alerts={alerts}
              onAcknowledge={acknowledgeAlert}
            />
          </div>
        ) : activeTab === 'replay' ? (
          <div className="right-panel replay-right-panel">
            <AlertPanel
              alerts={alerts}
              onAcknowledge={acknowledgeAlert}
            />
          </div>
        ) : null}
      </div>

      {activeTab === 'list' && (
        <div className="fab-container">
          <button className="add-group-btn" onClick={() => setShowAddGroupModal(true)}>
            + 分组
          </button>
          <button
            className="add-group-btn"
            onClick={() => setShowRuleEditor(true)}
            style={{ background: '#7c3aed' }}
          >
            📋 规则
          </button>
          <button className="add-target-btn" onClick={() => setShowAddModal(true)}>
            + 目标
          </button>
        </div>
      )}

      {showAddModal && (
        <AddTargetModal
          onClose={() => setShowAddModal(false)}
          onSubmit={addTarget}
          groups={groups}
          rules={rules}
        />
      )}

      {showAddGroupModal && (
        <AddGroupModal
          onClose={() => setShowAddGroupModal(false)}
          onSubmit={(newGroup) => {
            setGroups(prev => [...prev, newGroup]);
          }}
        />
      )}

      {showRuleEditor && (
        <RuleEditor
          onClose={() => {
            setShowRuleEditor(false);
            loadRules();
          }}
        />
      )}
    </div>
  );
}

export default App;
