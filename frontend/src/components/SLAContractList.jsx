import { useState, useEffect, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function formatDate(dateStr) {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
}

function formatDateTime(dateStr) {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getStatusLabel(status) {
  const labels = {
    compliant: '达标',
    at_risk: '风险',
    violated: '违约',
  };
  return labels[status] || status;
}

function getStatusClass(status) {
  switch (status) {
    case 'compliant': return 'status-compliant';
    case 'at_risk': return 'status-at-risk';
    case 'violated': return 'status-violated';
    default: return '';
  }
}

function getDaysRemaining(expiryDate) {
  const now = new Date();
  const expiry = new Date(expiryDate);
  const diff = expiry - now;
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function SLAContractList({ onViewDetail }) {
  const [contracts, setContracts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sortBy, setSortBy] = useState('expiry_date');
  const [sortOrder, setSortOrder] = useState('asc');
  const [statusFilter, setStatusFilter] = useState('');
  const [overview, setOverview] = useState(null);

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    party_a: '',
    party_b: '',
    effective_date: '',
    expiry_date: '',
    monthly_availability_target: 99.95,
    max_single_outage_minutes: 30,
    max_monthly_outage_minutes: 22,
    penalty_rate: 0.1,
    status: 'active',
    description: '',
    target_ids: [],
  });

  const [targets, setTargets] = useState([]);
  const [creating, setCreating] = useState(false);

  const loadOverview = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/sla/overview`);
      if (res.ok) {
        const data = await res.json();
        setOverview(data);
      }
    } catch (e) {
      console.error('Failed to load SLA overview:', e);
    }
  }, []);

  const loadContracts = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (statusFilter) params.append('status', statusFilter);
      params.append('sort_by', sortBy);
      params.append('sort_order', sortOrder);

      const res = await fetch(`${API_BASE}/api/sla/contracts?${params}`);
      if (res.ok) {
        const data = await res.json();
        setContracts(data.items || []);
      }
    } catch (e) {
      console.error('Failed to load SLA contracts:', e);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, sortBy, sortOrder]);

  const loadTargets = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/targets`);
      if (res.ok) {
        const data = await res.json();
        setTargets(data || []);
      }
    } catch (e) {
      console.error('Failed to load targets:', e);
    }
  }, []);

  useEffect(() => {
    loadOverview();
    loadContracts();
    loadTargets();
  }, [loadOverview, loadContracts, loadTargets]);

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
  };

  const handleTargetToggle = (targetId) => {
    setFormData(prev => {
      const newIds = prev.target_ids.includes(targetId)
        ? prev.target_ids.filter(id => id !== targetId)
        : [...prev.target_ids, targetId];
      return { ...prev, target_ids: newIds };
    });
  };

  const handleCreateContract = async () => {
    if (!formData.name || !formData.party_a || !formData.party_b || !formData.effective_date || !formData.expiry_date) {
      alert('请填写必填项');
      return;
    }

    try {
      setCreating(true);
      const res = await fetch(`${API_BASE}/api/sla/contracts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          effective_date: `${formData.effective_date}T00:00:00Z`,
          expiry_date: `${formData.expiry_date}T23:59:59Z`,
        }),
      });

      if (res.ok) {
        setShowCreateModal(false);
        loadContracts();
        loadOverview();
        setFormData({
          name: '',
          party_a: '',
          party_b: '',
          effective_date: '',
          expiry_date: '',
          monthly_availability_target: 99.95,
          max_single_outage_minutes: 30,
          max_monthly_outage_minutes: 22,
          penalty_rate: 0.1,
          status: 'active',
          description: '',
          target_ids: [],
        });
      } else {
        const err = await res.json();
        alert(`创建失败: ${err.detail || '未知错误'}`);
      }
    } catch (e) {
      console.error('Failed to create contract:', e);
      alert('创建失败，请稍后重试');
    } finally {
      setCreating(false);
    }
  };

  const getContractStatus = (contract) => {
    return contract.current_month_status || 'compliant';
  };

  const getProgressBarColor = (pct) => {
    if (pct >= 100) return '#ef4444';
    if (pct >= 80) return '#f59e0b';
    return '#10b981';
  };

  return (
    <div className="sla-contract-page">
      <div className="page-header">
        <div>
          <h2>📄 SLA合同管理</h2>
          <p className="page-subtitle">服务级别协议合同管理与违约追踪</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
          ➕ 新建合同
        </button>
      </div>

      {overview && (
        <div className="overview-cards">
          <div className="overview-card">
            <div className="overview-icon">📄</div>
            <div className="overview-content">
              <div className="overview-value">{overview.total_contracts}</div>
              <div className="overview-label">合同总数</div>
            </div>
          </div>
          <div className="overview-card">
            <div className="overview-icon">✅</div>
            <div className="overview-content">
              <div className="overview-value">{overview.active_contracts}</div>
              <div className="overview-label">活跃合同</div>
            </div>
          </div>
          <div className="overview-card warning">
            <div className="overview-icon">⏰</div>
            <div className="overview-content">
              <div className="overview-value">{overview.expiring_soon}</div>
              <div className="overview-label">即将到期</div>
            </div>
          </div>
          <div className="overview-card danger">
            <div className="overview-icon">⚠️</div>
            <div className="overview-content">
              <div className="overview-value">{overview.current_violations}</div>
              <div className="overview-label">本月违约</div>
            </div>
          </div>
        </div>
      )}

      <div className="filter-section">
        <div className="filter-row">
          <div className="filter-item">
            <label>合同状态</label>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">全部</option>
              <option value="active">生效中</option>
              <option value="expired">已过期</option>
              <option value="draft">草稿</option>
            </select>
          </div>
          <div className="filter-item">
            <label>排序方式</label>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
              <option value="expiry_date">到期时间</option>
              <option value="created_at">创建时间</option>
              <option value="name">合同名称</option>
            </select>
          </div>
          <div className="filter-item">
            <label>排序顺序</label>
            <button
              className="sort-toggle-btn"
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
            >
              {sortOrder === 'asc' ? '↑ 升序' : '↓ 降序'}
            </button>
          </div>
        </div>
      </div>

      <div className="results-info">
        <span>共 {contracts.length} 份合同</span>
      </div>

      <div className="contract-list">
        {loading ? (
          <div className="loading">加载中...</div>
        ) : contracts.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📄</div>
            <p>暂无SLA合同</p>
            <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
              创建第一份合同
            </button>
          </div>
        ) : (
          <div className="contract-cards">
            {contracts.map((contract) => {
              const daysRemaining = getDaysRemaining(contract.expiry_date);
              const isExpiringSoon = daysRemaining > 0 && daysRemaining <= 30;
              const isExpired = daysRemaining <= 0;
              const status = getContractStatus(contract);
              const usedPct = contract.monthly_outage_used_pct || 0;

              return (
                <div
                  key={contract.id}
                  className={`contract-card ${isExpiringSoon ? 'expiring-soon' : ''} ${isExpired ? 'expired' : ''}`}
                  onClick={() => onViewDetail && onViewDetail(contract.id)}
                >
                  <div className="contract-card-header">
                    <div className="contract-title-row">
                      <h3 className="contract-name">{contract.name}</h3>
                      <span className={`contract-status-badge ${getStatusClass(status)}`}>
                        {getStatusLabel(status)}
                      </span>
                    </div>
                    <div className="contract-parties">
                      <span className="party-tag">{contract.party_a}</span>
                      <span className="party-arrow">→</span>
                      <span className="party-tag">{contract.party_b}</span>
                    </div>
                  </div>

                  <div className="contract-card-body">
                    <div className="contract-date-range">
                      <span className="date-label">📅 合同期限</span>
                      <span className="date-value">
                        {formatDate(contract.effective_date)} ~ {formatDate(contract.expiry_date)}
                      </span>
                    </div>

                    {isExpiringSoon && (
                      <div className="expiring-warning">
                        ⏰ 还有 {daysRemaining} 天到期
                      </div>
                    )}

                    {isExpired && (
                      <div className="expired-badge">
                        📴 已过期 {Math.abs(daysRemaining)} 天
                      </div>
                    )}

                    <div className="contract-targets">
                      <span className="targets-label">🎯 覆盖目标 ({contract.target_count || 0})</span>
                      <div className="targets-preview">
                        {contract.targets && contract.targets.slice(0, 3).map((t, idx) => (
                          <span key={idx} className="target-chip">
                            {t.target_name}
                          </span>
                        ))}
                        {contract.target_count > 3 && (
                          <span className="target-chip more">
                            +{contract.target_count - 3}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="contract-metrics">
                      <div className="contract-metric">
                        <span className="metric-label">月可用率目标</span>
                        <span className="metric-value">{contract.monthly_availability_target}%</span>
                      </div>
                      <div className="contract-metric">
                        <span className="metric-label">单次最大容忍</span>
                        <span className="metric-value">{contract.max_single_outage_minutes}分钟</span>
                      </div>
                    </div>

                    <div className="outage-progress">
                      <div className="progress-header">
                        <span className="progress-label">本月故障时长</span>
                        <span className="progress-value">
                          {contract.monthly_outage_used || 0} / {contract.max_monthly_outage_minutes} 分钟
                          ({usedPct.toFixed(1)}%)
                        </span>
                      </div>
                      <div className="progress-bar">
                        <div
                          className="progress-fill"
                          style={{
                            width: `${Math.min(usedPct, 100)}%`,
                            backgroundColor: getProgressBarColor(usedPct),
                          }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="contract-card-footer">
                    <span className="contract-id">#{contract.id}</span>
                    <button className="btn btn-sm btn-outline" onClick={(e) => {
                      e.stopPropagation();
                      onViewDetail && onViewDetail(contract.id);
                    }}>
                      查看详情 →
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>新建SLA合同</h3>
              <button className="close-btn" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>
            <div className="modal-body modal-scrollable">
              <div className="form-section">
                <h4>基本信息</h4>
                <div className="form-row">
                  <div className="form-group">
                    <label>合同名称 *</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      placeholder="请输入合同名称"
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>甲方 *</label>
                    <input
                      type="text"
                      value={formData.party_a}
                      onChange={(e) => setFormData({ ...formData, party_a: e.target.value })}
                      placeholder="甲方名称"
                    />
                  </div>
                  <div className="form-group">
                    <label>乙方 *</label>
                    <input
                      type="text"
                      value={formData.party_b}
                      onChange={(e) => setFormData({ ...formData, party_b: e.target.value })}
                      placeholder="乙方名称"
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>生效日期 *</label>
                    <input
                      type="date"
                      value={formData.effective_date}
                      onChange={(e) => setFormData({ ...formData, effective_date: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>到期日期 *</label>
                    <input
                      type="date"
                      value={formData.expiry_date}
                      onChange={(e) => setFormData({ ...formData, expiry_date: e.target.value })}
                    />
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h4>SLA条款</h4>
                <div className="form-row">
                  <div className="form-group">
                    <label>月可用率目标 (%)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={formData.monthly_availability_target}
                      onChange={(e) => setFormData({ ...formData, monthly_availability_target: parseFloat(e.target.value) })}
                    />
                  </div>
                  <div className="form-group">
                    <label>单次最大容忍故障 (分钟)</label>
                    <input
                      type="number"
                      value={formData.max_single_outage_minutes}
                      onChange={(e) => setFormData({ ...formData, max_single_outage_minutes: parseInt(e.target.value) })}
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>月累计故障上限 (分钟)</label>
                    <input
                      type="number"
                      value={formData.max_monthly_outage_minutes}
                      onChange={(e) => setFormData({ ...formData, max_monthly_outage_minutes: parseInt(e.target.value) })}
                    />
                  </div>
                  <div className="form-group">
                    <label>违约赔偿比例 (%)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={formData.penalty_rate * 100}
                      onChange={(e) => setFormData({ ...formData, penalty_rate: parseFloat(e.target.value) / 100 })}
                    />
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h4>覆盖目标</h4>
                <p className="form-hint">选择该合同覆盖的探测目标，取最差的目标数据作为履约依据</p>
                <div className="target-select-list">
                  {targets.map((target) => (
                    <label key={target.id} className="target-select-item">
                      <input
                        type="checkbox"
                        checked={formData.target_ids.includes(target.id)}
                        onChange={() => handleTargetToggle(target.id)}
                      />
                      <span className="target-name">{target.name}</span>
                      <span className={`target-status status-${target.status}`}>{target.status}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="form-section">
                <h4>备注</h4>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="合同备注信息"
                  rows={3}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>
                取消
              </button>
              <button
                className="btn btn-primary"
                onClick={handleCreateContract}
                disabled={creating}
              >
                {creating ? '创建中...' : '创建合同'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default SLAContractList;
