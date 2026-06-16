import { useState, useEffect, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function formatTime(ts) {
  if (!ts) return '-';
  return new Date(ts).toLocaleString('zh-CN');
}

function timeAgo(ts) {
  if (!ts) return '-';
  const diff = (Date.now() - new Date(ts).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}秒前`;
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
  return `${Math.floor(diff / 86400)}天前`;
}

function AddSourceModal({ onClose, onSubmit, groups }) {
  const [formData, setFormData] = useState({
    name: '',
    url: '',
    pull_interval: 60,
    default_group_id: '',
    default_type: 'http',
    default_interval: 30,
    default_timeout: 5,
    deprecate_after_hours: 24,
    enabled: true,
  });
  const [headerKey, setHeaderKey] = useState('');
  const [headerValue, setHeaderValue] = useState('');
  const [headers, setHeaders] = useState({});

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    let parsedValue = value;
    if (type === 'checkbox') {
      parsedValue = checked;
    } else if (['pull_interval', 'default_interval', 'default_timeout', 'deprecate_after_hours'].includes(name)) {
      parsedValue = Number(value);
    } else if (name === 'default_group_id') {
      parsedValue = value === '' ? null : Number(value);
    }
    setFormData(prev => ({ ...prev, [name]: parsedValue }));
  };

  const addHeader = () => {
    if (headerKey.trim()) {
      setHeaders(prev => ({ ...prev, [headerKey.trim()]: headerValue }));
      setHeaderKey('');
      setHeaderValue('');
    }
  };

  const removeHeader = (key) => {
    setHeaders(prev => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name || !formData.url) return;
    const data = { ...formData };
    if (data.default_group_id === null || data.default_group_id === '') delete data.default_group_id;
    if (Object.keys(headers).length > 0) data.headers = headers;
    onSubmit(data);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 640 }}>
        <h2>添加注册源</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>名称</label>
            <input type="text" name="name" value={formData.name} onChange={handleChange} placeholder="例如：Consul生产集群" required />
          </div>
          <div className="form-group">
            <label>服务列表地址</label>
            <input type="text" name="url" value={formData.url} onChange={handleChange} placeholder="例如：http://consul.internal:8500/v1/catalog/services" required />
            <span className="form-hint">返回JSON数组或包含services/data/items字段的对象</span>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>拉取间隔 (秒)</label>
              <input type="number" name="pull_interval" min="10" max="3600" value={formData.pull_interval} onChange={handleChange} />
            </div>
            <div className="form-group">
              <label>废弃阈值 (小时)</label>
              <input type="number" name="deprecate_after_hours" min="1" max="720" value={formData.deprecate_after_hours} onChange={handleChange} />
              <span className="form-hint">服务消失多久后标记为废弃</span>
            </div>
          </div>

          <div className="form-group">
            <label>默认分组</label>
            <select name="default_group_id" value={formData.default_group_id || ''} onChange={handleChange}>
              <option value="">不指定分组</option>
              {groups.map(g => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>默认探测类型</label>
              <select name="default_type" value={formData.default_type} onChange={handleChange}>
                <option value="http">HTTP</option>
                <option value="tcp">TCP</option>
              </select>
            </div>
            <div className="form-group">
              <label>默认间隔 (秒)</label>
              <input type="number" name="default_interval" min="5" max="300" value={formData.default_interval} onChange={handleChange} />
            </div>
            <div className="form-group">
              <label>默认超时 (秒)</label>
              <input type="number" name="default_timeout" min="1" max="60" value={formData.default_timeout} onChange={handleChange} />
            </div>
          </div>

          <div className="form-group">
            <label>自定义请求头</label>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <input type="text" value={headerKey} onChange={e => setHeaderKey(e.target.value)} placeholder="Header名" style={{ flex: 1 }} />
              <input type="text" value={headerValue} onChange={e => setHeaderValue(e.target.value)} placeholder="Header值" style={{ flex: 1 }} />
              <button type="button" className="btn btn-secondary" onClick={addHeader} style={{ padding: '6px 12px' }}>+</button>
            </div>
            {Object.keys(headers).length > 0 && (
              <div className="discovery-headers-list">
                {Object.entries(headers).map(([k, v]) => (
                  <div key={k} className="discovery-header-item">
                    <span>{k}: {v}</span>
                    <button type="button" onClick={() => removeHeader(k)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}>✕</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="form-group">
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <input type="checkbox" name="enabled" checked={formData.enabled} onChange={handleChange} style={{ width: 'auto' }} />
              启用自动同步
            </label>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>取消</button>
            <button type="submit" className="btn btn-primary">创建</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function EditSourceModal({ onClose, onSubmit, groups, source }) {
  const [formData, setFormData] = useState({
    name: source.name || '',
    url: source.url || '',
    pull_interval: source.pull_interval || 60,
    default_group_id: source.default_group_id || '',
    default_type: source.default_type || 'http',
    default_interval: source.default_interval || 30,
    default_timeout: source.default_timeout || 5,
    deprecate_after_hours: source.deprecate_after_hours || 24,
    enabled: source.enabled !== false,
  });
  const [headerKey, setHeaderKey] = useState('');
  const [headerValue, setHeaderValue] = useState('');
  const [headers, setHeaders] = useState(source.headers || {});

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    let parsedValue = value;
    if (type === 'checkbox') {
      parsedValue = checked;
    } else if (['pull_interval', 'default_interval', 'default_timeout', 'deprecate_after_hours'].includes(name)) {
      parsedValue = Number(value);
    } else if (name === 'default_group_id') {
      parsedValue = value === '' ? null : Number(value);
    }
    setFormData(prev => ({ ...prev, [name]: parsedValue }));
  };

  const addHeader = () => {
    if (headerKey.trim()) {
      setHeaders(prev => ({ ...prev, [headerKey.trim()]: headerValue }));
      setHeaderKey('');
      setHeaderValue('');
    }
  };

  const removeHeader = (key) => {
    setHeaders(prev => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const data = { ...formData };
    if (data.default_group_id === null || data.default_group_id === '') delete data.default_group_id;
    data.headers = headers;
    onSubmit(data);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 640 }}>
        <h2>编辑注册源</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>名称</label>
            <input type="text" name="name" value={formData.name} onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>服务列表地址</label>
            <input type="text" name="url" value={formData.url} onChange={handleChange} required />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>拉取间隔 (秒)</label>
              <input type="number" name="pull_interval" min="10" max="3600" value={formData.pull_interval} onChange={handleChange} />
            </div>
            <div className="form-group">
              <label>废弃阈值 (小时)</label>
              <input type="number" name="deprecate_after_hours" min="1" max="720" value={formData.deprecate_after_hours} onChange={handleChange} />
            </div>
          </div>
          <div className="form-group">
            <label>默认分组</label>
            <select name="default_group_id" value={formData.default_group_id || ''} onChange={handleChange}>
              <option value="">不指定分组</option>
              {groups.map(g => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>默认探测类型</label>
              <select name="default_type" value={formData.default_type} onChange={handleChange}>
                <option value="http">HTTP</option>
                <option value="tcp">TCP</option>
              </select>
            </div>
            <div className="form-group">
              <label>默认间隔 (秒)</label>
              <input type="number" name="default_interval" min="5" max="300" value={formData.default_interval} onChange={handleChange} />
            </div>
            <div className="form-group">
              <label>默认超时 (秒)</label>
              <input type="number" name="default_timeout" min="1" max="60" value={formData.default_timeout} onChange={handleChange} />
            </div>
          </div>
          <div className="form-group">
            <label>自定义请求头</label>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <input type="text" value={headerKey} onChange={e => setHeaderKey(e.target.value)} placeholder="Header名" style={{ flex: 1 }} />
              <input type="text" value={headerValue} onChange={e => setHeaderValue(e.target.value)} placeholder="Header值" style={{ flex: 1 }} />
              <button type="button" className="btn btn-secondary" onClick={addHeader} style={{ padding: '6px 12px' }}>+</button>
            </div>
            {Object.keys(headers).length > 0 && (
              <div className="discovery-headers-list">
                {Object.entries(headers).map(([k, v]) => (
                  <div key={k} className="discovery-header-item">
                    <span>{k}: {v}</span>
                    <button type="button" onClick={() => removeHeader(k)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}>✕</button>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="form-group">
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <input type="checkbox" name="enabled" checked={formData.enabled} onChange={handleChange} style={{ width: 'auto' }} />
              启用自动同步
            </label>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>取消</button>
            <button type="submit" className="btn btn-primary">保存</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function SourceCard({ source, onSync, onEdit, onDelete, onViewHistory, syncing }) {
  const statusColor = source.last_sync_status === 'success' ? '#22c55e'
    : source.last_sync_status === 'failed' ? '#ef4444' : '#64748b';

  return (
    <div className={`discovery-source-card ${!source.enabled ? 'disabled' : ''}`}>
      <div className="discovery-source-header">
        <div className="discovery-source-title">
          <h3>{source.name}</h3>
          {!source.enabled && <span className="discovery-badge disabled-badge">已禁用</span>}
          {source.last_sync_status === 'success' && <span className="discovery-badge success-badge">正常</span>}
          {source.last_sync_status === 'failed' && <span className="discovery-badge error-badge">异常</span>}
        </div>
        <div className="discovery-source-actions">
          <button className="btn btn-sm btn-secondary" onClick={() => onViewHistory(source)} title="同步历史">
            📋
          </button>
          <button className="btn btn-sm btn-secondary" onClick={() => onEdit(source)} title="编辑">
            ✏️
          </button>
          <button className="btn btn-sm btn-primary" onClick={() => onSync(source.id)} disabled={syncing} title="立即同步">
            {syncing ? '⏳' : '🔄'}
          </button>
          <button className="btn btn-sm btn-danger" onClick={() => onDelete(source)} title="删除">
            🗑️
          </button>
        </div>
      </div>
      <div className="discovery-source-body">
        <div className="discovery-source-meta">
          <span className="discovery-meta-item">
            <span className="discovery-meta-label">地址</span>
            <span className="discovery-meta-value" title={source.url}>{source.url.length > 50 ? source.url.slice(0, 50) + '...' : source.url}</span>
          </span>
          <span className="discovery-meta-item">
            <span className="discovery-meta-label">拉取间隔</span>
            <span className="discovery-meta-value">{source.pull_interval}s</span>
          </span>
          <span className="discovery-meta-item">
            <span className="discovery-meta-label">默认类型</span>
            <span className="discovery-meta-value">{source.default_type.toUpperCase()}</span>
          </span>
          <span className="discovery-meta-item">
            <span className="discovery-meta-label">默认分组</span>
            <span className="discovery-meta-value">{source.default_group_name || '无'}</span>
          </span>
          <span className="discovery-meta-item">
            <span className="discovery-meta-label">废弃阈值</span>
            <span className="discovery-meta-value">{source.deprecate_after_hours}h</span>
          </span>
          <span className="discovery-meta-item">
            <span className="discovery-meta-label">目标数</span>
            <span className="discovery-meta-value">{source.target_count}</span>
          </span>
        </div>
        <div className="discovery-source-footer">
          <span className="discovery-sync-status">
            <span className="status-dot" style={{ backgroundColor: statusColor, width: 8, height: 8 }}></span>
            {source.last_sync_at ? `上次同步 ${timeAgo(source.last_sync_at)}` : '尚未同步'}
          </span>
          <span className="discovery-default-params">
            间隔{source.default_interval}s / 超时{source.default_timeout}s
          </span>
        </div>
      </div>
    </div>
  );
}

function SyncHistoryPanel({ source, onBack }) {
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [eventDetail, setEventDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadEvents();
  }, [source]);

  useEffect(() => {
    if (selectedEvent) loadEventDetail(selectedEvent.id);
  }, [selectedEvent]);

  const loadEvents = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/registry-sources/${source.id}/sync-events?limit=50`);
      if (res.ok) {
        const data = await res.json();
        setEvents(data.items || []);
      }
    } catch (e) {
      console.error('Failed to load sync events:', e);
    } finally {
      setLoading(false);
    }
  };

  const loadEventDetail = async (eventId) => {
    try {
      const res = await fetch(`${API_BASE}/api/sync-events/${eventId}`);
      if (res.ok) {
        const data = await res.json();
        setEventDetail(data);
      }
    } catch (e) {
      console.error('Failed to load event detail:', e);
    }
  };

  const actionColor = { created: '#22c55e', deprecated: '#f59e0b', restored: '#3b82f6', failed: '#ef4444' };
  const actionLabel = { created: '新增', deprecated: '废弃', restored: '恢复', failed: '失败' };

  return (
    <div className="discovery-history">
      <div className="discovery-history-header">
        <button className="btn btn-secondary" onClick={onBack}>← 返回</button>
        <h3>{source.name} - 同步历史</h3>
      </div>

      <div className="discovery-history-content">
        <div className="discovery-history-list">
          {loading ? (
            <div style={{ padding: 20, textAlign: 'center', color: '#64748b' }}>加载中...</div>
          ) : events.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', color: '#64748b' }}>暂无同步记录</div>
          ) : (
            events.map(ev => (
              <div
                key={ev.id}
                className={`discovery-history-item ${selectedEvent?.id === ev.id ? 'selected' : ''}`}
                onClick={() => setSelectedEvent(ev)}
              >
                <div className="discovery-history-item-header">
                  <span className={`discovery-status-tag ${ev.status}`}>{ev.status === 'success' ? '✅' : ev.status === 'failed' ? '❌' : '⏳'} {ev.status}</span>
                  <span className="discovery-history-time">{formatTime(ev.started_at)}</span>
                </div>
                <div className="discovery-history-item-stats">
                  <span className="discovery-stat new">+{ev.new_count}</span>
                  <span className="discovery-stat deprecated">-{ev.deprecated_count}</span>
                  <span className="discovery-stat unchanged">={ev.unchanged_count}</span>
                  {ev.failed_count > 0 && <span className="discovery-stat failed">!{ev.failed_count}</span>}
                  <span className="discovery-stat total">{ev.raw_service_count}个服务</span>
                </div>
                <div className="discovery-history-item-meta">
                  触发: {ev.triggered_by === 'manual' ? '手动' : '自动'}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="discovery-history-detail">
          {eventDetail ? (
            <>
              <h4>同步详情</h4>
              <div className="discovery-detail-summary">
                <span>发现 {eventDetail.discovered_count} 个服务</span>
                <span>新增 {eventDetail.new_count}</span>
                <span>废弃 {eventDetail.deprecated_count}</span>
                <span>不变 {eventDetail.unchanged_count}</span>
                {eventDetail.failed_count > 0 && <span style={{ color: '#ef4444' }}>失败 {eventDetail.failed_count}</span>}
              </div>
              {eventDetail.error_message && (
                <div className="discovery-detail-error">错误: {eventDetail.error_message}</div>
              )}
              <div className="discovery-detail-timeline">
                <h5>变更明细</h5>
                {eventDetail.details.length === 0 ? (
                  <div style={{ color: '#64748b', padding: 12 }}>本次同步无变更</div>
                ) : (
                  eventDetail.details.map((d, i) => (
                    <div key={i} className="discovery-detail-item">
                      <span className="discovery-detail-action" style={{ color: actionColor[d.action] || '#64748b' }}>
                        {actionLabel[d.action] || d.action}
                      </span>
                      <span className="discovery-detail-name">{d.service_name}</span>
                      <span className="discovery-detail-address">{d.service_address}</span>
                      {d.detail && <span className="discovery-detail-desc">{d.detail}</span>}
                    </div>
                  ))
                )}
              </div>
            </>
          ) : (
            <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>
              点击左侧同步记录查看详情
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DeprecatedTargetsPanel({ targets, onRestore }) {
  const [restoring, setRestoring] = useState(null);
  const deprecated = targets.filter(t => t.deprecated);

  const handleRestore = async (targetId) => {
    setRestoring(targetId);
    try {
      await onRestore(targetId);
    } finally {
      setRestoring(null);
    }
  };

  if (deprecated.length === 0) {
    return (
      <div className="discovery-deprecated-empty">
        暂无废弃目标
      </div>
    );
  }

  return (
    <div className="discovery-deprecated-list">
      {deprecated.map(t => (
        <div key={t.id} className="discovery-deprecated-item">
          <div className="discovery-deprecated-info">
            <span className="discovery-deprecated-name">{t.name}</span>
            <span className="discovery-deprecated-address">{t.address}</span>
            {t.source_name && <span className="discovery-deprecated-source">来自: {t.source_name}</span>}
            {t.deprecated_at && <span className="discovery-deprecated-time">废弃于 {formatTime(t.deprecated_at)}</span>}
          </div>
          <button
            className="btn btn-sm btn-primary"
            onClick={() => handleRestore(t.id)}
            disabled={restoring === t.id}
          >
            {restoring === t.id ? '恢复中...' : '🔄 恢复'}
          </button>
        </div>
      ))}
    </div>
  );
}

export default function AutoDiscoveryPanel({ targets, groups }) {
  const [sources, setSources] = useState([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editSource, setEditSource] = useState(null);
  const [historySource, setHistorySource] = useState(null);
  const [syncingIds, setSyncingIds] = useState(new Set());
  const [activeSubTab, setActiveSubTab] = useState('sources');

  const loadSources = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/registry-sources`);
      if (res.ok) {
        const data = await res.json();
        setSources(data);
      }
    } catch (e) {
      console.error('Failed to load sources:', e);
    }
  }, []);

  useEffect(() => {
    loadSources();
  }, [loadSources]);

  const handleAddSource = async (data) => {
    try {
      const res = await fetch(`${API_BASE}/api/registry-sources`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (res.ok) {
        setShowAddModal(false);
        loadSources();
      } else {
        const err = await res.json();
        alert(`创建失败: ${err.detail || JSON.stringify(err)}`);
      }
    } catch (e) {
      alert('创建失败: ' + e.message);
    }
  };

  const handleEditSource = async (data) => {
    try {
      const res = await fetch(`${API_BASE}/api/registry-sources/${editSource.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (res.ok) {
        setEditSource(null);
        loadSources();
      } else {
        const err = await res.json();
        alert(`更新失败: ${err.detail || JSON.stringify(err)}`);
      }
    } catch (e) {
      alert('更新失败: ' + e.message);
    }
  };

  const handleDeleteSource = async (source) => {
    if (!confirm(`确定删除注册源"${source.name}"吗？已创建的目标不会被删除。`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/registry-sources/${source.id}`, { method: 'DELETE' });
      if (res.ok) loadSources();
    } catch (e) {
      alert('删除失败: ' + e.message);
    }
  };

  const handleSync = async (sourceId) => {
    setSyncingIds(prev => new Set([...prev, sourceId]));
    try {
      const res = await fetch(`${API_BASE}/api/registry-sources/${sourceId}/sync`, { method: 'POST' });
      if (res.ok) {
        const result = await res.json();
        alert(`同步完成：新增 ${result.new_count}，废弃 ${result.deprecated_count}，不变 ${result.unchanged_count}`);
      } else {
        const err = await res.json();
        alert(`同步失败: ${err.detail || JSON.stringify(err)}`);
      }
      loadSources();
    } catch (e) {
      alert('同步失败: ' + e.message);
    } finally {
      setSyncingIds(prev => {
        const next = new Set(prev);
        next.delete(sourceId);
        return next;
      });
    }
  };

  const handleRestore = async (targetId) => {
    try {
      const res = await fetch(`${API_BASE}/api/targets/${targetId}/restore`, { method: 'POST' });
      if (res.ok) {
        alert('目标已恢复为活跃状态');
      } else {
        const err = await res.json();
        alert(`恢复失败: ${err.detail}`);
      }
    } catch (e) {
      alert('恢复失败: ' + e.message);
    }
  };

  if (historySource) {
    return <SyncHistoryPanel source={historySource} onBack={() => { setHistorySource(null); loadSources(); }} />;
  }

  return (
    <div className="discovery-panel">
      <div className="discovery-header">
        <h2>🔍 服务自动发现与注册</h2>
        <div className="discovery-subtabs">
          <button className={`discovery-subtab ${activeSubTab === 'sources' ? 'active' : ''}`} onClick={() => setActiveSubTab('sources')}>
            注册源管理
          </button>
          <button className={`discovery-subtab ${activeSubTab === 'deprecated' ? 'active' : ''}`} onClick={() => setActiveSubTab('deprecated')}>
            废弃目标 ({targets.filter(t => t.deprecated).length})
          </button>
        </div>
        {activeSubTab === 'sources' && (
          <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>
            + 注册源
          </button>
        )}
      </div>

      {activeSubTab === 'sources' && (
        <div className="discovery-sources">
          {sources.length === 0 ? (
            <div className="discovery-empty">
              <div className="discovery-empty-icon">📡</div>
              <h3>尚未配置服务注册源</h3>
              <p>添加一个服务注册源，系统将定期拉取服务列表并自动创建探测目标</p>
              <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>
                + 添加第一个注册源
              </button>
            </div>
          ) : (
            <div className="discovery-sources-grid">
              {sources.map(s => (
                <SourceCard
                  key={s.id}
                  source={s}
                  onSync={handleSync}
                  onEdit={setEditSource}
                  onDelete={handleDeleteSource}
                  onViewHistory={setHistorySource}
                  syncing={syncingIds.has(s.id)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {activeSubTab === 'deprecated' && (
        <DeprecatedTargetsPanel targets={targets} onRestore={handleRestore} />
      )}

      {showAddModal && (
        <AddSourceModal onClose={() => setShowAddModal(false)} onSubmit={handleAddSource} groups={groups} />
      )}

      {editSource && (
        <EditSourceModal onClose={() => setEditSource(null)} onSubmit={handleEditSource} groups={groups} source={editSource} />
      )}
    </div>
  );
}
