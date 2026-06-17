import { useState, useEffect, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function formatDuration(seconds) {
  if (!seconds || seconds < 0) return '00:00:00';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

export default function RecordingControlPanel({
  recordingStatus,
  targets = [],
  groups = [],
  onSessionCreated,
}) {
  const [showConfig, setShowConfig] = useState(false);
  const [sessionName, setSessionName] = useState('');
  const [description, setDescription] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [selectedTargetIds, setSelectedTargetIds] = useState([]);
  const [selectedGroupIds, setSelectedGroupIds] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [editingSession, setEditingSession] = useState(null);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editTags, setEditTags] = useState('');

  const loadSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/recording/sessions?limit=20`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data.items || []);
      }
    } catch (e) {
      console.error('Failed to load sessions:', e);
    }
  }, []);

  useEffect(() => {
    loadSessions();
    const timer = setInterval(loadSessions, 5000);
    return () => clearInterval(timer);
  }, [loadSessions]);

  useEffect(() => {
    if (recordingStatus?.last_session) {
      loadSessions();
    }
  }, [recordingStatus?.last_session, loadSessions]);

  const handleStartRecording = async () => {
    if (!sessionName.trim()) {
      setError('请输入会话名称');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const tags = tagsInput.split(/[,，\s]+/).map(t => t.trim()).filter(Boolean);
      const body = {
        name: sessionName.trim(),
        description: description.trim() || null,
        tags: tags.length > 0 ? tags : null,
      };
      if (selectedTargetIds.length > 0) {
        body.filter_target_ids = selectedTargetIds;
      }
      if (selectedGroupIds.length > 0) {
        body.filter_group_ids = selectedGroupIds;
      }
      const res = await fetch(`${API_BASE}/api/recording/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok) {
        setShowConfig(false);
        setSessionName('');
        setDescription('');
        setTagsInput('');
        setSelectedTargetIds([]);
        setSelectedGroupIds([]);
        if (onSessionCreated) onSessionCreated(data);
      } else {
        setError(data.detail || data.error || '启动录制失败');
      }
    } catch (e) {
      setError('网络错误，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleStopRecording = async () => {
    if (!confirm('确定要停止当前录制吗？')) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/recording/stop`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || data.error || '停止录制失败');
      } else {
        loadSessions();
      }
    } catch (e) {
      setError('网络错误，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSession = async (sessionId) => {
    if (!confirm('确定要删除这个录制会话吗？此操作不可恢复。')) return;
    try {
      const res = await fetch(`${API_BASE}/api/recording/sessions/${sessionId}`, { method: 'DELETE' });
      if (res.ok) {
        loadSessions();
      } else {
        const data = await res.json();
        alert(data.detail || data.error || '删除失败');
      }
    } catch (e) {
      alert('网络错误，请重试');
    }
  };

  const handleStartEdit = (session) => {
    setEditingSession(session.id);
    setEditName(session.name);
    setEditDescription(session.description || '');
    setEditTags((session.tags || []).join(', '));
  };

  const handleSaveEdit = async () => {
    if (!editName.trim()) {
      alert('会话名称不能为空');
      return;
    }
    try {
      const tags = editTags.split(/[,，\s]+/).map(t => t.trim()).filter(Boolean);
      const res = await fetch(`${API_BASE}/api/recording/sessions/${editingSession}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: editName.trim(),
          description: editDescription.trim() || null,
          tags,
        }),
      });
      if (res.ok) {
        setEditingSession(null);
        loadSessions();
      } else {
        const data = await res.json();
        alert(data.detail || data.error || '保存失败');
      }
    } catch (e) {
      alert('网络错误，请重试');
    }
  };

  const toggleTargetSelection = (targetId) => {
    setSelectedTargetIds(prev =>
      prev.includes(targetId)
        ? prev.filter(id => id !== targetId)
        : [...prev, targetId]
    );
  };

  const toggleGroupSelection = (groupId) => {
    setSelectedGroupIds(prev =>
      prev.includes(groupId)
        ? prev.filter(id => id !== groupId)
        : [...prev, groupId]
    );
  };

  const isRecording = recordingStatus?.is_recording;

  return (
    <div className="recording-panel">
      <div className="panel-header">
        <h3>🎬 录制控制</h3>
        {isRecording ? (
          <div className="recording-indicator active">
            <span className="recording-dot"></span>
            <span>录制中</span>
          </div>
        ) : (
          <div className="recording-indicator idle">
            <span className="recording-dot idle-dot"></span>
            <span>空闲</span>
          </div>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      {isRecording ? (
        <div className="recording-active">
          <div className="recording-info">
            <div className="info-row">
              <span className="info-label">会话名称:</span>
              <span className="info-value">{recordingStatus.session_name}</span>
            </div>
            <div className="info-row">
              <span className="info-label">持续时间:</span>
              <span className="info-value timer">{formatDuration(recordingStatus.duration_seconds)}</span>
            </div>
            <div className="info-row">
              <span className="info-label">已录事件:</span>
              <span className="info-value count">{recordingStatus.recorded_count || 0} 条</span>
            </div>
            <div className="info-row">
              <span className="info-label">涉及目标:</span>
              <span className="info-value count">{recordingStatus.target_count || 0} 个</span>
            </div>
          </div>
          <button
            className="btn btn-stop"
            onClick={handleStopRecording}
            disabled={loading}
          >
            {loading ? '处理中...' : '⏹ 停止录制'}
          </button>
        </div>
      ) : (
        <div className="recording-idle">
          {!showConfig ? (
            <button
              className="btn btn-start"
              onClick={() => {
                setShowConfig(true);
                const now = new Date();
                setSessionName(`录制会话_${now.getFullYear()}${(now.getMonth()+1).toString().padStart(2,'0')}${now.getDate().toString().padStart(2,'0')}_${now.getHours().toString().padStart(2,'0')}${now.getMinutes().toString().padStart(2,'0')}`);
              }}
            >
              ⏺ 开始新录制
            </button>
          ) : (
            <div className="recording-config">
              <div className="form-group">
                <label>会话名称 *</label>
                <input
                  type="text"
                  value={sessionName}
                  onChange={(e) => setSessionName(e.target.value)}
                  placeholder="请输入会话名称"
                  maxLength={255}
                />
              </div>
              <div className="form-group">
                <label>备注说明</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="可选：录制场景描述、备注等"
                  rows={2}
                  maxLength={1024}
                />
              </div>
              <div className="form-group">
                <label>标签（用逗号或空格分隔）</label>
                <input
                  type="text"
                  value={tagsInput}
                  onChange={(e) => setTagsInput(e.target.value)}
                  placeholder="如: 故障演练, 生产环境, 深夜维护"
                />
              </div>

              <div className="filter-section">
                <div className="filter-title">筛选录制范围（不选则录制全部）</div>

                <div className="filter-subtitle">按目标筛选：</div>
                <div className="filter-chips">
                  {targets.slice(0, 50).map(t => (
                    <label
                      key={t.id}
                      className={`chip ${selectedTargetIds.includes(t.id) ? 'selected' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedTargetIds.includes(t.id)}
                        onChange={() => toggleTargetSelection(t.id)}
                      />
                      <span>{t.name}</span>
                    </label>
                  ))}
                  {targets.length > 50 && (
                    <span className="chip-more">...还有 {targets.length - 50} 个目标</span>
                  )}
                </div>

                <div className="filter-subtitle">或按分组筛选：</div>
                <div className="filter-chips">
                  {groups.map(g => (
                    <label
                      key={g.id}
                      className={`chip group-chip ${selectedGroupIds.includes(g.id) ? 'selected' : ''}`}
                      style={{ borderLeftColor: g.color }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedGroupIds.includes(g.id)}
                        onChange={() => toggleGroupSelection(g.id)}
                      />
                      <span>{g.name}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="config-actions">
                <button
                  className="btn btn-cancel"
                  onClick={() => {
                    setShowConfig(false);
                    setError('');
                  }}
                >
                  取消
                </button>
                <button
                  className="btn btn-start"
                  onClick={handleStartRecording}
                  disabled={loading}
                >
                  {loading ? '启动中...' : '⏺ 开始录制'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="sessions-list-section">
        <div className="section-header">
          <h4>📼 录制会话历史</h4>
          <button className="btn-refresh" onClick={loadSessions}>🔄</button>
        </div>
        {sessions.length === 0 ? (
          <div className="empty-state">暂无录制会话</div>
        ) : (
          <div className="sessions-list">
            {sessions.map(s => (
              <div key={s.id} className="session-item">
                {editingSession === s.id ? (
                  <div className="session-edit-form">
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      placeholder="会话名称"
                    />
                    <textarea
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                      placeholder="备注"
                      rows={2}
                    />
                    <input
                      type="text"
                      value={editTags}
                      onChange={(e) => setEditTags(e.target.value)}
                      placeholder="标签（逗号分隔）"
                    />
                    <div className="edit-actions">
                      <button className="btn btn-cancel" onClick={() => setEditingSession(null)}>取消</button>
                      <button className="btn btn-save" onClick={handleSaveEdit}>保存</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="session-main">
                      <div className="session-name-row">
                        <span className="session-name">{s.name}</span>
                        <span className={`session-status status-${s.status}`}>
                          {s.status === 'completed' ? '✓ 已完成' : s.status === 'recording' ? '● 录制中' : s.status}
                        </span>
                      </div>
                      {s.description && (
                        <div className="session-desc">{s.description}</div>
                      )}
                      {s.tags && s.tags.length > 0 && (
                        <div className="session-tags">
                          {s.tags.map((tag, i) => (
                            <span key={i} className="tag">🏷 {tag}</span>
                          ))}
                        </div>
                      )}
                      <div className="session-meta">
                        <span>⏱ {formatDuration(s.duration_seconds)}</span>
                        <span>📊 {s.recorded_count || 0} 条事件</span>
                        <span>🎯 {s.target_count || 0} 个目标</span>
                        <span>📅 {new Date(s.created_at).toLocaleString('zh-CN')}</span>
                      </div>
                      {(s.filter_target_ids?.length > 0 || s.filter_group_ids?.length > 0) && (
                        <div className="session-filters">
                          {s.filter_target_ids?.length > 0 && (
                            <span className="filter-info">筛选目标: {s.filter_target_ids.length}个</span>
                          )}
                          {s.filter_group_ids?.length > 0 && (
                            <span className="filter-info">筛选分组: {s.filter_group_ids.length}个</span>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="session-actions">
                      <button
                        className="btn-icon"
                        onClick={() => handleStartEdit(s)}
                        title="编辑"
                      >
                        ✏️
                      </button>
                      <button
                        className="btn-icon danger"
                        onClick={() => handleDeleteSession(s.id)}
                        title="删除"
                        disabled={s.status === 'recording'}
                      >
                        🗑️
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
