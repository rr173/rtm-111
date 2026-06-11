import { useState, useEffect, useMemo } from 'react';
import CreateSnapshotModal from './CreateSnapshotModal';
import SnapshotPlayer from './SnapshotPlayer';
import SnapshotComparison from './SnapshotComparison';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function SnapshotList() {
  const [snapshots, setSnapshots] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [playerSnapshot, setPlayerSnapshot] = useState(null);
  const [showComparison, setShowComparison] = useState(false);
  const [compareSnapshotA, setCompareSnapshotA] = useState(null);
  const [compareSnapshotB, setCompareSnapshotB] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadSnapshots = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        search: searchQuery,
        sort_by: sortBy,
        sort_order: sortOrder
      });
      const res = await fetch(`${API_BASE}/api/snapshots?${params}`);
      if (res.ok) {
        const data = await res.json();
        setSnapshots(data);
      }
    } catch (e) {
      console.error('Failed to load snapshots:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSnapshots();
  }, [searchQuery, sortBy, sortOrder]);

  const handleDelete = async (id) => {
    if (!confirm('确定要删除这个快照吗？此操作不可恢复。')) return;
    try {
      const res = await fetch(`${API_BASE}/api/snapshots/${id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        loadSnapshots();
      }
    } catch (e) {
      console.error('Failed to delete snapshot:', e);
    }
  };

  const handleEdit = (snapshot) => {
    setEditingId(snapshot.id);
    setEditName(snapshot.name);
    setEditDescription(snapshot.description || '');
  };

  const handleSaveEdit = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/api/snapshots/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: editName,
          description: editDescription
        })
      });
      if (res.ok) {
        setEditingId(null);
        loadSnapshots();
      }
    } catch (e) {
      console.error('Failed to update snapshot:', e);
    }
  };

  const handlePlay = (snapshot) => {
    setPlayerSnapshot(snapshot);
  };

  const handleSelectCompareA = (snapshot) => {
    setCompareSnapshotA(snapshot);
  };

  const handleSelectCompareB = (snapshot) => {
    setCompareSnapshotB(snapshot);
    if (compareSnapshotA) {
      setShowComparison(true);
    }
  };

  const formatDateTime = (isoString) => {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatDuration = (start, end) => {
    const diff = new Date(end) - new Date(start);
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (hours > 0) {
      return `${hours}小时${mins}分钟`;
    }
    return `${mins}分钟`;
  };

  const filteredSnapshots = useMemo(() => {
    if (!searchQuery) return snapshots;
    const query = searchQuery.toLowerCase();
    return snapshots.filter(s =>
      s.name.toLowerCase().includes(query) ||
      (s.description && s.description.toLowerCase().includes(query))
    );
  }, [snapshots, searchQuery]);

  return (
    <div className="snapshot-list-container">
      <div className="snapshot-header">
        <h2>📸 快照管理</h2>
        <div className="snapshot-header-actions">
          <div className="snapshot-search">
            <input
              type="text"
              placeholder="搜索快照名称或备注..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="search-input"
            />
          </div>
          <div className="snapshot-sort">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="sort-select"
            >
              <option value="created_at">创建时间</option>
              <option value="start_time">开始时间</option>
              <option value="name">名称</option>
            </select>
            <button
              className="sort-order-btn"
              onClick={() => setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc')}
            >
              {sortOrder === 'desc' ? '↓ 降序' : '↑ 升序'}
            </button>
          </div>
          <button
            className="create-snapshot-btn"
            onClick={() => setShowCreateModal(true)}
          >
            + 创建快照
          </button>
        </div>
      </div>

      {(compareSnapshotA || compareSnapshotB) && (
        <div className="compare-bar">
          <span>对比模式：</span>
          <span className={`compare-slot ${compareSnapshotA ? 'filled' : ''}`}>
            A: {compareSnapshotA ? compareSnapshotA.name : '请选择...'}
          </span>
          <span className="compare-arrow">→</span>
          <span className={`compare-slot ${compareSnapshotB ? 'filled' : ''}`}>
            B: {compareSnapshotB ? compareSnapshotB.name : '请选择...'}
          </span>
          {compareSnapshotA && compareSnapshotB && (
            <button
              className="compare-btn"
              onClick={() => setShowComparison(true)}
            >
              开始对比
            </button>
          )}
          <button
            className="clear-compare-btn"
            onClick={() => {
              setCompareSnapshotA(null);
              setCompareSnapshotB(null);
            }}
          >
            清除
          </button>
        </div>
      )}

      <div className="snapshot-grid">
        {loading ? (
          <div className="loading-state">加载中...</div>
        ) : filteredSnapshots.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📸</div>
            <div className="empty-text">暂无快照</div>
            <div className="empty-hint">点击"创建快照"按钮开始录制时间段数据</div>
          </div>
        ) : (
          filteredSnapshots.map(snapshot => (
            <div key={snapshot.id} className="snapshot-card">
              {editingId === snapshot.id ? (
                <div className="snapshot-edit-form">
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    placeholder="快照名称"
                    className="edit-input"
                  />
                  <textarea
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    placeholder="备注信息（如：上线前、上线后）"
                    className="edit-textarea"
                  />
                  <div className="edit-actions">
                    <button
                      className="save-btn"
                      onClick={() => handleSaveEdit(snapshot.id)}
                    >
                      保存
                    </button>
                    <button
                      className="cancel-btn"
                      onClick={() => setEditingId(null)}
                    >
                      取消
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="snapshot-card-header">
                    <h3 className="snapshot-name">{snapshot.name}</h3>
                    {snapshot.description && (
                      <div className="snapshot-description">{snapshot.description}</div>
                    )}
                  </div>
                  <div className="snapshot-meta">
                    <div className="meta-item">
                      <span className="meta-label">时间段:</span>
                      <span className="meta-value">
                        {formatDateTime(snapshot.start_time)} - {formatDateTime(snapshot.end_time)}
                      </span>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">时长:</span>
                      <span className="meta-value">
                        {formatDuration(snapshot.start_time, snapshot.end_time)}
                      </span>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">目标数:</span>
                      <span className="meta-value">{snapshot.target_count}</span>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">数据点:</span>
                      <span className="meta-value">{snapshot.data_point_count}</span>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">创建时间:</span>
                      <span className="meta-value">{formatDateTime(snapshot.created_at)}</span>
                    </div>
                  </div>
                  <div className="snapshot-actions">
                    <button
                      className="action-btn play"
                      onClick={() => handlePlay(snapshot)}
                    >
                      ▶ 回放
                    </button>
                    <button
                      className="action-btn compare-a"
                      onClick={() => handleSelectCompareA(snapshot)}
                      disabled={compareSnapshotA?.id === snapshot.id}
                    >
                      设为 A
                    </button>
                    <button
                      className="action-btn compare-b"
                      onClick={() => handleSelectCompareB(snapshot)}
                      disabled={compareSnapshotB?.id === snapshot.id}
                    >
                      设为 B
                    </button>
                    <button
                      className="action-btn edit"
                      onClick={() => handleEdit(snapshot)}
                    >
                      ✏️ 编辑
                    </button>
                    <button
                      className="action-btn delete"
                      onClick={() => handleDelete(snapshot.id)}
                    >
                      🗑️ 删除
                    </button>
                  </div>
                </>
              )}
            </div>
          ))
        )}
      </div>

      {showCreateModal && (
        <CreateSnapshotModal
          onClose={() => setShowCreateModal(false)}
          onCreated={() => {
            setShowCreateModal(false);
            loadSnapshots();
          }}
        />
      )}

      {playerSnapshot && (
        <SnapshotPlayer
          snapshot={playerSnapshot}
          onClose={() => setPlayerSnapshot(null)}
        />
      )}

      {showComparison && compareSnapshotA && compareSnapshotB && (
        <SnapshotComparison
          snapshotA={compareSnapshotA}
          snapshotB={compareSnapshotB}
          onClose={() => {
            setShowComparison(false);
          }}
        />
      )}
    </div>
  );
}

export default SnapshotList;
