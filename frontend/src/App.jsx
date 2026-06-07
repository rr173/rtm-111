import { useState, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import StatsBar from './components/StatsBar';
import TargetList from './components/TargetList';
import AlertPanel from './components/AlertPanel';
import AddTargetModal from './components/AddTargetModal';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || 'http://localhost:8000';

function App() {
  const { connected, targets, alerts, setTargets, setAlerts } = useWebSocket();
  const [expandedTarget, setExpandedTarget] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [detailData, setDetailData] = useState({});

  useEffect(() => {
    if (expandedTarget) {
      fetchTargetHistory(expandedTarget);
    }
  }, [expandedTarget]);

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
  const degradedCount = targets.filter(t => t.status === 'degraded' && !t.paused).length;
  const downCount = targets.filter(t => t.status === 'down' && !t.paused).length;

  return (
    <div className="app">
      <header className="header">
        <h1>🔍 服务探活与告警仪表台</h1>
        <div className="connection-status">
          <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`}></span>
          <span>{connected ? '实时连接' : '连接断开'}</span>
        </div>
      </header>

      <div className="main-content">
        <div className="left-panel">
          <StatsBar
            healthy={healthyCount}
            degraded={degradedCount}
            down={downCount}
          />
          <TargetList
            targets={targets}
            expandedTarget={expandedTarget}
            onToggleExpand={setExpandedTarget}
            onDelete={deleteTarget}
            onTogglePause={togglePause}
            onToggleSilence={toggleSilence}
            detailData={detailData}
          />
        </div>

        <div className="right-panel">
          <AlertPanel
            alerts={alerts}
            onAcknowledge={acknowledgeAlert}
          />
        </div>
      </div>

      <button className="add-target-btn" onClick={() => setShowAddModal(true)}>
        +
      </button>

      {showAddModal && (
        <AddTargetModal
          onClose={() => setShowAddModal(false)}
          onSubmit={addTarget}
        />
      )}
    </div>
  );
}

export default App;
