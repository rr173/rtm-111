import { useState, useEffect } from 'react';
import CreateChangeModal from './CreateChangeModal';
import ChangeObservationPanel from './ChangeObservationPanel';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

export default function ChangeGuardianPanel({ activeChanges, targetChangesMap, targets }) {
  const [allChanges, setAllChanges] = useState([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedChangeId, setSelectedChangeId] = useState(null);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [dateRange, setDateRange] = useState({ start: '', end: '' });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadChanges();
  }, [filter, search, dateRange.start, dateRange.end]);

  const loadChanges = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter !== 'all') {
        params.append('status', filter);
      }
      if (search) {
        params.append('search', search);
      }
      if (dateRange.start) {
        params.append('start_date', new Date(dateRange.start).toISOString());
      }
      if (dateRange.end) {
        const endDate = new Date(dateRange.end);
        endDate.setHours(23, 59, 59, 999);
        params.append('end_date', endDate.toISOString());
      }

      const res = await fetch(`${API_BASE}/api/changes?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setAllChanges(data);
      }
    } catch (e) {
      console.error('Failed to load changes:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteChange = async (changeId) => {
    if (!confirm('确定要删除这个变更吗？')) return;
    try {
      const res = await fetch(`${API_BASE}/api/changes/${changeId}`, { method: 'DELETE' });
      if (res.ok) {
        loadChanges();
      }
    } catch (e) {
      console.error('Failed to delete change:', e);
    }
  };

  const getStatusConfig = (status) => {
    const configs = {
      pending: { label: '⏳ 待开始', color: '#f59e0b', bg: '#fef3c7' },
      running: { label: '🚀 进行中', color: '#3b82f6', bg: '#dbeafe' },
      completed: { label: '✅ 已完成', color: '#10b981', bg: '#d1fae5' },
      cancelled: { label: '❌ 已取消', color: '#6b7280', bg: '#f3f4f6' }
    };
    return configs[status] || { label: status, color: '#6b7280', bg: '#f3f4f6' };
  };

  const getConclusionConfig = (conclusion) => {
    if (!conclusion) return null;
    const configs = {
      pass: { label: '✅ 通过', color: '#10b981' },
      observe: { label: '⚠️ 需观察', color: '#f59e0b' },
      rollback: { label: '🔴 建议回滚', color: '#ef4444' }
    };
    return configs[conclusion] || { label: conclusion, color: '#6b7280' };
  };

  const formatTime = (time) => {
    if (!time) return '-';
    return new Date(time).toLocaleString('zh-CN');
  };

  const formatDuration = (start, end) => {
    if (!start || !end) return '-';
    const diff = new Date(end) - new Date(start);
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (hours > 0) {
      return `${hours}小时${mins}分钟`;
    }
    return `${mins}分钟`;
  };

  const getTargetActiveChanges = (targetId) => {
    return targetChangesMap[targetId] || [];
  };

  const pendingChanges = allChanges.filter(c => c.status === 'pending');
  const runningChanges = allChanges.filter(c => c.status === 'running');
  const completedChanges = allChanges.filter(c => c.status === 'completed' || c.status === 'cancelled');

  return (
    <div className="change-guardian-panel">
      <div className="panel-header">
        <div className="header-left">
          <h2>🛡️ 发布变更守护</h2>
          <span className="panel-subtitle">实时监控发布变更对服务的影响</span>
        </div>
        <div className="header-right">
          <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
            + 登记变更
          </button>
        </div>
      </div>

      <div className="stats-cards">
        <div className="stat-card pending">
          <div className="stat-icon">⏳</div>
          <div className="stat-content">
            <div className="stat-label">待开始</div>
            <div className="stat-value">{pendingChanges.length}</div>
          </div>
        </div>
        <div className="stat-card running">
          <div className="stat-icon">🚀</div>
          <div className="stat-content">
            <div className="stat-label">进行中</div>
            <div className="stat-value">{runningChanges.length}</div>
          </div>
        </div>
        <div className="stat-card completed">
          <div className="stat-icon">✅</div>
          <div className="stat-content">
            <div className="stat-label">已完成</div>
            <div className="stat-value">{completedChanges.length}</div>
          </div>
        </div>
        <div className="stat-card total">
          <div className="stat-icon">📋</div>
          <div className="stat-content">
            <div className="stat-label">总计</div>
            <div className="stat-value">{allChanges.length}</div>
          </div>
        </div>
      </div>

      <div className="filter-bar">
        <div className="filter-group">
          <label>状态筛选</label>
          <div className="filter-tabs">
            <button
              className={`filter-tab ${filter === 'all' ? 'active' : ''}`}
              onClick={() => setFilter('all')}
            >
              全部
            </button>
            <button
              className={`filter-tab ${filter === 'pending' ? 'active' : ''}`}
              onClick={() => setFilter('pending')}
            >
              待开始
            </button>
            <button
              className={`filter-tab ${filter === 'running' ? 'active' : ''}`}
              onClick={() => setFilter('running')}
            >
              进行中
            </button>
            <button
              className={`filter-tab ${filter === 'completed' ? 'active' : ''}`}
              onClick={() => setFilter('completed')}
            >
              已完成
            </button>
          </div>
        </div>

        <div className="filter-group">
          <label>搜索</label>
          <input
            type="text"
            className="form-input"
            placeholder="搜索变更名称..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        <div className="filter-group">
          <label>开始日期</label>
          <input
            type="date"
            className="form-input"
            value={dateRange.start}
            onChange={e => setDateRange(prev => ({ ...prev, start: e.target.value }))}
          />
        </div>

        <div className="filter-group">
          <label>结束日期</label>
          <input
            type="date"
            className="form-input"
            value={dateRange.end}
            onChange={e => setDateRange(prev => ({ ...prev, end: e.target.value }))}
          />
        </div>
      </div>

      {runningChanges.length > 0 && (
        <div className="section">
          <h3>🚀 进行中的变更</h3>
          <div className="changes-grid">
            {runningChanges.map(change => {
              const statusCfg = getStatusConfig(change.status);
              const conclusionCfg = getConclusionConfig(change.conclusion);
              return (
                <div key={change.id} className="change-card running-card">
                  <div className="change-card-header">
                    <div className="change-title-section">
                      <h4 className="change-name">{change.name}</h4>
                      <span className="change-status" style={{ background: statusCfg.bg, color: statusCfg.color }}>
                        {statusCfg.label}
                      </span>
                      {conclusionCfg && (
                        <span className="change-conclusion" style={{ background: conclusionCfg.color }}>
                          {conclusionCfg.label}
                        </span>
                      )}
                    </div>
                    <div className="pulse-indicator"></div>
                  </div>

                  {change.description && (
                    <p className="change-desc">{change.description}</p>
                  )}

                  <div className="change-meta">
                    <div className="meta-item">
                      <span className="meta-label">计划时间</span>
                      <span className="meta-value">{formatTime(change.planned_time)}</span>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">开始时间</span>
                      <span className="meta-value">{formatTime(change.start_time)}</span>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">目标数</span>
                      <span className="meta-value">{change.target_count} 个</span>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">创建人</span>
                      <span className="meta-value">{change.created_by || '-'}</span>
                    </div>
                  </div>

                  <div className="change-targets">
                    <span className="targets-label">涉及目标：</span>
                    <div className="target-tags">
                      {change.targets.slice(0, 3).map(t => (
                        <span key={t.id} className="target-tag">
                          {t.target_name}
                          {getTargetActiveChanges(t.target_id).length > 1 && (
                            <span className="multi-change-warning" title={`同时被 ${getTargetActiveChanges(t.target_id).length} 个变更影响`}>
                              ⚠️{getTargetActiveChanges(t.target_id).length}
                            </span>
                          )}
                        </span>
                      ))}
                      {change.targets.length > 3 && (
                        <span className="target-tag more">+{change.targets.length - 3}</span>
                      )}
                    </div>
                  </div>

                  {Object.entries(targetChangesMap).some(([tid, changes]) =>
                    changes.some(c => change.targets.some(ct => ct.target_id === parseInt(tid))) && changes.length > 1
                  ) && (
                    <div className="multi-change-alert">
                      ⚠️ 部分目标同时处于多个变更中，请特别留意
                    </div>
                  )}

                  <div className="change-actions">
                    <button
                      className="btn btn-primary"
                      onClick={() => setSelectedChangeId(change.id)}
                    >
                      🔍 观察面板
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {pendingChanges.length > 0 && (
        <div className="section">
          <h3>⏳ 待开始的变更</h3>
          <div className="changes-grid">
            {pendingChanges.map(change => {
              const statusCfg = getStatusConfig(change.status);
              return (
                <div key={change.id} className="change-card pending-card">
                  <div className="change-card-header">
                    <div className="change-title-section">
                      <h4 className="change-name">{change.name}</h4>
                      <span className="change-status" style={{ background: statusCfg.bg, color: statusCfg.color }}>
                        {statusCfg.label}
                      </span>
                    </div>
                  </div>

                  {change.description && (
                    <p className="change-desc">{change.description}</p>
                  )}

                  <div className="change-meta">
                    <div className="meta-item">
                      <span className="meta-label">计划时间</span>
                      <span className="meta-value">{formatTime(change.planned_time)}</span>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">目标数</span>
                      <span className="meta-value">{change.target_count} 个</span>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">创建人</span>
                      <span className="meta-value">{change.created_by || '-'}</span>
                    </div>
                  </div>

                  <div className="change-targets">
                    <span className="targets-label">涉及目标：</span>
                    <div className="target-tags">
                      {change.targets.slice(0, 3).map(t => (
                        <span key={t.id} className="target-tag">{t.target_name}</span>
                      ))}
                      {change.targets.length > 3 && (
                        <span className="target-tag more">+{change.targets.length - 3}</span>
                      )}
                    </div>
                  </div>

                  <div className="change-actions">
                    <button
                      className="btn btn-primary"
                      onClick={() => setSelectedChangeId(change.id)}
                    >
                      查看详情
                    </button>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => handleDeleteChange(change.id)}
                    >
                      删除
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="section">
        <h3>📋 {filter === 'all' || filter === 'completed' ? '历史变更记录' : '变更列表'}</h3>
        {loading ? (
          <div className="loading-state">加载中...</div>
        ) : allChanges.length === 0 ? (
          <div className="empty-state">
            暂无变更记录
            <p>点击右上角"登记变更"按钮创建第一个变更</p>
          </div>
        ) : (
          <div className="changes-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>变更名称</th>
                  <th>状态</th>
                  <th>结论</th>
                  <th>计划时间</th>
                  <th>开始时间</th>
                  <th>结束时间</th>
                  <th>持续时间</th>
                  <th>目标数</th>
                  <th>创建人</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {allChanges.map(change => {
                  const statusCfg = getStatusConfig(change.status);
                  const conclusionCfg = getConclusionConfig(change.conclusion);
                  return (
                    <tr key={change.id} className={change.status === 'running' ? 'row-highlight' : ''}>
                      <td>
                        <div className="cell-change-name">
                          {change.name}
                          {change.status === 'running' && <span className="live-dot"></span>}
                        </div>
                      </td>
                      <td>
                        <span className="status-badge" style={{ background: statusCfg.bg, color: statusCfg.color }}>
                          {statusCfg.label}
                        </span>
                      </td>
                      <td>
                        {conclusionCfg ? (
                          <span className="status-badge" style={{ background: conclusionCfg.color, color: '#fff' }}>
                            {conclusionCfg.label}
                          </span>
                        ) : '-'}
                      </td>
                      <td>{formatTime(change.planned_time)}</td>
                      <td>{formatTime(change.start_time)}</td>
                      <td>{formatTime(change.end_time)}</td>
                      <td>{formatDuration(change.start_time, change.end_time)}</td>
                      <td>{change.target_count}</td>
                      <td>{change.created_by || '-'}</td>
                      <td>
                        <div className="row-actions">
                          <button
                            className="btn btn-link"
                            onClick={() => setSelectedChangeId(change.id)}
                          >
                            查看
                          </button>
                          {change.status !== 'running' && (
                            <button
                              className="btn btn-link danger"
                              onClick={() => handleDeleteChange(change.id)}
                            >
                              删除
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showCreateModal && (
        <CreateChangeModal
          onClose={() => setShowCreateModal(false)}
          onSubmit={() => {
            loadChanges();
          }}
          targets={targets}
        />
      )}

      {selectedChangeId && (
        <ChangeObservationPanel
          changeId={selectedChangeId}
          onClose={() => setSelectedChangeId(null)}
        />
      )}
    </div>
  );
}
