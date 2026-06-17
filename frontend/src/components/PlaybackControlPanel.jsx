import { useState, useEffect, useCallback, useMemo } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';
const SPEED_OPTIONS = [1, 2, 5, 10];

function formatDuration(seconds) {
  if (!seconds || seconds < 0) return '00:00:00';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function formatMsDuration(ms) {
  if (!ms || ms < 0) return '00:00:00';
  const totalSeconds = Math.floor(ms / 1000);
  return formatDuration(totalSeconds);
}

export default function PlaybackControlPanel({
  playbackStatus,
  playbackFinished,
  setPlaybackFinished,
  onPlaybackEnd,
}) {
  const [sessions, setSessions] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [selectedSessionDetail, setSelectedSessionDetail] = useState(null);
  const [selectedSpeed, setSelectedSpeed] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showSessionList, setShowSessionList] = useState(true);
  const [searchText, setSearchText] = useState('');
  const [filterTag, setFilterTag] = useState('');

  const isPlaying = playbackStatus?.is_playing;
  const isPaused = playbackStatus?.is_paused;

  const loadSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/recording/sessions?limit=100`);
      if (res.ok) {
        const data = await res.json();
        setSessions((data.items || []).filter(s => s.status === 'completed'));
      }
    } catch (e) {
      console.error('Failed to load sessions:', e);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (playbackFinished) {
      setError('');
      const timer = setTimeout(() => setPlaybackFinished(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [playbackFinished, setPlaybackFinished]);

  useEffect(() => {
    if (!selectedSessionId) return;
    const loadDetail = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/recording/sessions/${selectedSessionId}`);
        if (res.ok) {
          const data = await res.json();
          setSelectedSessionDetail(data);
        }
      } catch (e) {
        console.error('Failed to load session detail:', e);
      }
    };
    loadDetail();
  }, [selectedSessionId]);

  const allTags = useMemo(() => {
    const tagSet = new Set();
    sessions.forEach(s => {
      (s.tags || []).forEach(t => tagSet.add(t));
    });
    return Array.from(tagSet).sort();
  }, [sessions]);

  const filteredSessions = useMemo(() => {
    let result = sessions;
    if (searchText.trim()) {
      const q = searchText.toLowerCase();
      result = result.filter(s =>
        s.name.toLowerCase().includes(q) ||
        (s.description || '').toLowerCase().includes(q)
      );
    }
    if (filterTag) {
      result = result.filter(s => (s.tags || []).includes(filterTag));
    }
    return result;
  }, [sessions, searchText, filterTag]);

  const handleStartPlayback = async () => {
    if (!selectedSessionId) {
      setError('请先选择一个录制会话');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/playback/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: selectedSessionId,
          speed: selectedSpeed,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || data.error || '启动回放失败');
      } else {
        setShowSessionList(false);
      }
    } catch (e) {
      setError('网络错误，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handlePause = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/playback/pause`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || data.error || '暂停失败');
      }
    } catch (e) {
      setError('网络错误，请重试');
    }
  };

  const handleResume = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/playback/resume`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || data.error || '继续失败');
      }
    } catch (e) {
      setError('网络错误，请重试');
    }
  };

  const handleStop = async () => {
    if (!confirm('确定要停止回放吗？系统将恢复到回放前的状态。')) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/playback/stop?restore=true`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || data.error || '停止失败');
      } else {
        setShowSessionList(true);
        if (onPlaybackEnd) onPlaybackEnd();
      }
    } catch (e) {
      setError('网络错误，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleChangeSpeed = async (speed) => {
    if (isPlaying) {
      try {
        const res = await fetch(`${API_BASE}/api/playback/speed`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ speed }),
        });
        const data = await res.json();
        if (!res.ok) {
          setError(data.detail || data.error || '设置倍速失败');
          return;
        }
      } catch (e) {
        setError('网络错误，请重试');
        return;
      }
    }
    setSelectedSpeed(speed);
  };

  const progressPercent = playbackStatus?.progress || 0;
  const currentSpeed = playbackStatus?.speed || selectedSpeed;

  return (
    <div className="playback-panel">
      <div className="panel-header">
        <h3>⏯️ 场景回放</h3>
        {(isPlaying || isPaused) && (
          <div className={`playback-indicator ${isPaused ? 'paused' : 'playing'}`}>
            <span className="playback-dot"></span>
            <span>{isPaused ? '已暂停' : '回放中'}</span>
          </div>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      {playbackFinished && (
        <div className="success-message">
          ✅ 回放完成！系统已恢复到回放前状态
        </div>
      )}

      {(isPlaying || isPaused) && (
        <div className="playback-active">
          <div className="playback-session-info">
            <div className="info-row">
              <span className="info-label">当前会话:</span>
              <span className="info-value">
                {selectedSessionDetail?.name || sessions.find(s => s.id === playbackStatus.session_id)?.name || `#${playbackStatus.session_id}`}
              </span>
            </div>
            <div className="info-row">
              <span className="info-label">回放速度:</span>
              <div className="speed-buttons-inline">
                {SPEED_OPTIONS.map(s => (
                  <button
                    key={s}
                    className={`speed-btn-small ${currentSpeed === s ? 'active' : ''}`}
                    onClick={() => handleChangeSpeed(s)}
                  >
                    {s}x
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="playback-progress-section">
            <div className="progress-bar-container">
              <div
                className="progress-bar-fill"
                style={{ width: `${progressPercent}%` }}
              ></div>
            </div>
            <div className="progress-info">
              <span>
                {formatMsDuration(playbackStatus.virtual_time_ms || 0)} / {formatMsDuration(playbackStatus.total_duration_ms || 0)}
              </span>
              <span>
                {playbackStatus.current_index || 0} / {playbackStatus.total_events || 0} 事件
              </span>
              <span className="progress-percent">{progressPercent.toFixed(1)}%</span>
            </div>
          </div>

          <div className="playback-controls">
            {isPaused ? (
              <button
                className="btn btn-resume"
                onClick={handleResume}
                disabled={loading}
              >
                ▶️ 继续
              </button>
            ) : (
              <button
                className="btn btn-pause"
                onClick={handlePause}
                disabled={loading}
              >
                ⏸️ 暂停
              </button>
            )}
            <button
              className="btn btn-stop"
              onClick={handleStop}
              disabled={loading}
            >
              ⏹️ 停止并恢复
            </button>
          </div>

          {selectedSessionDetail && (
            <div className="playback-event-types">
              <div className="event-types-title">事件分布:</div>
              <div className="event-types-grid">
                {Object.entries(selectedSessionDetail.event_types_count || {}).map(([type, count]) => (
                  <div key={type} className="event-type-item">
                    <span className="event-type-name">{type}</span>
                    <span className="event-type-count">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {(!isPlaying && !isPaused) && showSessionList && (
        <div className="playback-setup">
          <div className="setup-section">
            <div className="section-title">选择回放速度</div>
            <div className="speed-buttons">
              {SPEED_OPTIONS.map(s => (
                <button
                  key={s}
                  className={`speed-btn ${selectedSpeed === s ? 'active' : ''}`}
                  onClick={() => handleChangeSpeed(s)}
                >
                  {s}x
                </button>
              ))}
            </div>
          </div>

          <div className="setup-section">
            <div className="section-title">选择录制会话</div>
            <div className="session-filters">
              <input
                type="text"
                className="search-input"
                placeholder="🔍 搜索会话名称或描述..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
              />
              {allTags.length > 0 && (
                <select
                  className="tag-filter"
                  value={filterTag}
                  onChange={(e) => setFilterTag(e.target.value)}
                >
                  <option value="">全部标签</option>
                  {allTags.map(t => (
                    <option key={t} value={t}>🏷 {t}</option>
                  ))}
                </select>
              )}
            </div>

            {filteredSessions.length === 0 ? (
              <div className="empty-state">
                {sessions.length === 0
                  ? '暂无已完成的录制会话，请先进行录制'
                  : '没有符合筛选条件的会话'}
              </div>
            ) : (
              <div className="session-select-list">
                {filteredSessions.map(s => (
                  <div
                    key={s.id}
                    className={`session-select-item ${selectedSessionId === s.id ? 'selected' : ''}`}
                    onClick={() => setSelectedSessionId(s.id)}
                  >
                    <div className="session-select-header">
                      <input
                        type="radio"
                        checked={selectedSessionId === s.id}
                        onChange={() => setSelectedSessionId(s.id)}
                        onClick={(e) => e.stopPropagation()}
                      />
                      <span className="session-name">{s.name}</span>
                      {s.has_playback_snapshot && (
                        <span className="badge badge-snapshot" title="存在回放快照">📸</span>
                      )}
                    </div>
                    {s.description && (
                      <div className="session-desc-small">{s.description}</div>
                    )}
                    {s.tags && s.tags.length > 0 && (
                      <div className="session-tags-small">
                        {s.tags.slice(0, 3).map((tag, i) => (
                          <span key={i} className="tag-small">{tag}</span>
                        ))}
                        {s.tags.length > 3 && <span className="tag-more">+{s.tags.length - 3}</span>}
                      </div>
                    )}
                    <div className="session-meta-small">
                      <span>⏱ {formatDuration(s.duration_seconds)}</span>
                      <span>📊 {s.recorded_count || 0}条</span>
                      <span>🎯 {s.target_count || 0}个</span>
                      <span>📅 {new Date(s.created_at).toLocaleString('zh-CN')}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {selectedSessionDetail && selectedSessionId && (
            <div className="selected-session-detail">
              <div className="detail-title">📋 会话详情</div>
              <div className="detail-grid">
                <div className="detail-item">
                  <span className="detail-label">目标数:</span>
                  <span className="detail-value">{selectedSessionDetail.target_count || 0}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">事件总数:</span>
                  <span className="detail-value">{selectedSessionDetail.recorded_count || 0}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">持续时间:</span>
                  <span className="detail-value">{formatDuration(selectedSessionDetail.duration_seconds)}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">涉及目标ID:</span>
                  <span className="detail-value small">
                    {(selectedSessionDetail.target_ids || []).slice(0, 10).join(', ')}
                    {(selectedSessionDetail.target_ids || []).length > 10 && '...'}
                  </span>
                </div>
              </div>
            </div>
          )}

          <div className="setup-warning">
            ⚠️ 回放开始后将暂停所有真实探测任务，回放结束后自动恢复
          </div>

          <button
            className="btn btn-start-playback"
            onClick={handleStartPlayback}
            disabled={!selectedSessionId || loading}
          >
            {loading ? '启动中...' : '▶️ 开始回放'}
          </button>
        </div>
      )}
    </div>
  );
}
