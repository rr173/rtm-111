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

function getViolationTypeLabel(type) {
  const labels = {
    single_outage: '单次故障超时',
    monthly_outage: '月累计超时',
    availability: '可用率不达标',
  };
  return labels[type] || type;
}

function getViolationTypeClass(type) {
  switch (type) {
    case 'single_outage': return 'violation-single';
    case 'monthly_outage': return 'violation-monthly';
    case 'availability': return 'violation-availability';
    default: return '';
  }
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

function SLAContractDetail({ contractId, onBack }) {
  const [contract, setContract] = useState(null);
  const [loading, setLoading] = useState(false);
  const [violations, setViolations] = useState([]);
  const [monthlyStats, setMonthlyStats] = useState([]);
  const [acknowledgeNote, setAcknowledgeNote] = useState('');
  const [showAcknowledgeModal, setShowAcknowledgeModal] = useState(false);
  const [selectedViolation, setSelectedViolation] = useState(null);

  const loadContractDetail = useCallback(async () => {
    if (!contractId) return;
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/sla/contracts/${contractId}`);
      if (res.ok) {
        const data = await res.json();
        setContract(data);
        setViolations(data.recent_violations || []);
        setMonthlyStats(data.monthly_history || []);
      }
    } catch (e) {
      console.error('Failed to load contract detail:', e);
    } finally {
      setLoading(false);
    }
  }, [contractId]);

  useEffect(() => {
    loadContractDetail();
  }, [loadContractDetail]);

  const handleAcknowledge = async (violation) => {
    setSelectedViolation(violation);
    setAcknowledgeNote(violation.notes || '');
    setShowAcknowledgeModal(true);
  };

  const submitAcknowledge = async () => {
    if (!selectedViolation) return;

    try {
      const res = await fetch(`${API_BASE}/api/sla/violations/${selectedViolation.id}/acknowledge`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          acknowledged: !selectedViolation.acknowledged,
          notes: acknowledgeNote,
        }),
      });

      if (res.ok) {
        setShowAcknowledgeModal(false);
        loadContractDetail();
      }
    } catch (e) {
      console.error('Failed to acknowledge violation:', e);
    }
  };

  const renderAvailabilityChart = () => {
    if (!monthlyStats || monthlyStats.length === 0) {
      return (
        <div className="chart-placeholder">
          <p>暂无月度数据</p>
        </div>
      );
    }

    const maxAvailability = 100;
    const minAvailability = 99;

    const getY = (value) => {
      const range = maxAvailability - minAvailability;
      const pct = (value - minAvailability) / range;
      return 100 - (pct * 100);
    };

    const points = monthlyStats.map((stat, index) => {
      const x = (index / (monthlyStats.length - 1 || 1)) * 100;
      const y = getY(stat.availability_pct || 99.9);
      return `${x},${y}`;
    }).join(' ');

    return (
      <div className="availability-chart">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="chart-svg">
          <line x1="0" y1={getY(contract?.monthly_availability_target || 99.95)} x2="100" y2={getY(contract?.monthly_availability_target || 99.95)} stroke="#ef4444" strokeWidth="0.5" strokeDasharray="2,2" />
          <polyline
            points={points}
            fill="none"
            stroke="#3b82f6"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {monthlyStats.map((stat, index) => {
            const x = (index / (monthlyStats.length - 1 || 1)) * 100;
            const y = getY(stat.availability_pct || 99.9);
            const isViolated = stat.status === 'violated';
            return (
              <circle
                key={index}
                cx={x}
                cy={y}
                r="2"
                fill={isViolated ? '#ef4444' : '#10b981'}
              />
            );
          })}
        </svg>
        <div className="chart-labels">
          {monthlyStats.map((stat, index) => (
            <div key={index} className="chart-label">
              <span className="month-label">{stat.month}</span>
              <span className={`availability-value ${stat.status === 'violated' ? 'violated' : ''}`}>
                {stat.availability_pct?.toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
        <div className="chart-legend">
          <div className="legend-item">
            <span className="legend-line target"></span>
            <span>目标 {contract?.monthly_availability_target}%</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot compliant"></span>
            <span>达标</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot violated"></span>
            <span>违约</span>
          </div>
        </div>
      </div>
    );
  };

  const renderOutageChart = () => {
    if (!monthlyStats || monthlyStats.length === 0) {
      return (
        <div className="chart-placeholder">
          <p>暂无月度数据</p>
        </div>
      );
    }

    const maxOutage = Math.max(
      ...monthlyStats.map(s => s.total_outage_minutes || 0),
      contract?.max_monthly_outage_minutes || 30
    ) * 1.2;

    return (
      <div className="outage-chart">
        <div className="bars-container">
          {monthlyStats.map((stat, index) => {
            const pct = maxOutage > 0 ? ((stat.total_outage_minutes || 0) / maxOutage) * 100 : 0;
            const isViolated = stat.total_outage_minutes > (contract?.max_monthly_outage_minutes || 0);
            return (
              <div key={index} className="bar-wrapper">
                <div className="bar-value">{stat.total_outage_minutes?.toFixed(0)}分钟</div>
                <div className="bar-container">
                  <div
                    className={`bar-fill ${isViolated ? 'violated' : ''}`}
                    style={{ height: `${pct}%` }}
                  ></div>
                </div>
                <div className="bar-label">{stat.month}</div>
              </div>
            );
          })}
        </div>
        {contract && (
          <div
            className="threshold-line"
            style={{ bottom: `${(contract.max_monthly_outage_minutes / maxOutage) * 100}%` }}
          >
            <span className="threshold-label">上限 {contract.max_monthly_outage_minutes}分钟</span>
          </div>
        )}
      </div>
    );
  };

  if (loading && !contract) {
    return <div className="loading">加载中...</div>;
  }

  if (!contract) {
    return <div className="empty-state">未找到合同信息</div>;
  }

  const isExpiringSoon = () => {
    const now = new Date();
    const expiry = new Date(contract.expiry_date);
    const days = Math.ceil((expiry - now) / (1000 * 60 * 60 * 24));
    return days > 0 && days <= 30;
  };

  const getDaysRemaining = () => {
    const now = new Date();
    const expiry = new Date(contract.expiry_date);
    return Math.ceil((expiry - now) / (1000 * 60 * 60 * 24));
  };

  return (
    <div className="sla-detail-page">
      <div className="detail-header">
        <button className="back-btn" onClick={onBack}>
          ← 返回列表
        </button>
        <div className="detail-title-section">
          <div className="detail-title-row">
            <h2>{contract.name}</h2>
            <span className={`status-badge-large ${getStatusClass(contract.current_month_status)}`}>
              {getStatusLabel(contract.current_month_status)}
            </span>
          </div>
          <div className="detail-parties">
            <span className="party-badge">{contract.party_a}</span>
            <span className="party-separator">甲方 → 乙方</span>
            <span className="party-badge">{contract.party_b}</span>
          </div>
        </div>
      </div>

      {isExpiringSoon() && (
        <div className="renewal-banner">
          <div className="renewal-icon">⏰</div>
          <div className="renewal-content">
            <strong>合同即将到期</strong>
            <p>还有 {getDaysRemaining()} 天到期，请及时安排续约</p>
          </div>
          <button className="btn btn-warning">申请续约</button>
        </div>
      )}

      <div className="detail-grid">
        <div className="detail-main">
          <div className="detail-section">
            <h3>📊 本月履约概览</h3>
            <div className="monthly-metrics">
              <div className="metric-card metric-availability">
                <div className="metric-icon">📈</div>
                <div className="metric-content">
                  <div className="metric-value-large">
                    {contract.current_month_availability?.toFixed(2) || '--'}%
                  </div>
                  <div className="metric-label">当前月可用率</div>
                  <div className="metric-subtext">
                    目标: {contract.monthly_availability_target}%
                  </div>
                </div>
              </div>
              <div className="metric-card metric-outage">
                <div className="metric-icon">⏱️</div>
                <div className="metric-content">
                  <div className="metric-value-large">
                    {contract.monthly_outage_used || 0} 分钟
                  </div>
                  <div className="metric-label">本月累计故障</div>
                  <div className="metric-subtext">
                    上限: {contract.max_monthly_outage_minutes} 分钟
                  </div>
                </div>
              </div>
              <div className="metric-card metric-violations">
                <div className="metric-icon">⚠️</div>
                <div className="metric-content">
                  <div className="metric-value-large">
                    {contract.monthly_violation_count || 0} 次
                  </div>
                  <div className="metric-label">本月违约次数</div>
                  <div className="metric-subtext">
                    预估赔偿: ¥{contract.monthly_estimated_penalty?.toFixed(2) || 0}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="detail-section">
            <h3>📈 月度履约趋势</h3>
            <div className="chart-section">
              <h4>可用率趋势 (近6个月)</h4>
              {renderAvailabilityChart()}
            </div>
            <div className="chart-section">
              <h4>故障时长趋势 (近6个月)</h4>
              {renderOutageChart()}
            </div>
          </div>

          <div className="detail-section">
            <div className="section-header">
              <h3>📋 违约事件时间线</h3>
              <span className="violation-count">共 {violations.length} 条</span>
            </div>
            {violations.length === 0 ? (
              <div className="empty-state small">
                <p>暂无违约记录，保持得很好！</p>
              </div>
            ) : (
              <div className="violation-timeline">
                {violations.map((violation) => (
                  <div key={violation.id} className={`timeline-item ${violation.acknowledged ? 'acknowledged' : ''}`}>
                    <div className="timeline-dot">
                      {violation.acknowledged ? '✓' : '!'}
                    </div>
                    <div className="timeline-content">
                      <div className="timeline-header">
                        <span className={`violation-type-badge ${getViolationTypeClass(violation.violation_type)}`}>
                          {getViolationTypeLabel(violation.violation_type)}
                        </span>
                        <span className="violation-time">
                          {formatDateTime(violation.detected_at)}
                        </span>
                      </div>
                      <div className="violation-details">
                        <div className="violation-meta">
                          <span className="meta-item">
                            <strong>故障目标:</strong> {violation.target_name || '-'}
                          </span>
                          <span className="meta-item">
                            <strong>实际时长:</strong> {violation.actual_duration_minutes} 分钟
                          </span>
                          <span className="meta-item">
                            <strong>超出:</strong> {violation.exceeded_minutes} 分钟
                          </span>
                          <span className="meta-item penalty">
                            <strong>预估赔偿:</strong> ¥{violation.estimated_penalty?.toFixed(2)}
                          </span>
                        </div>
                        {violation.notes && (
                          <div className="violation-notes">
                            <strong>备注:</strong> {violation.notes}
                          </div>
                        )}
                        <div className="violation-actions">
                          {violation.alert_id && (
                            <span className="alert-reference">关联告警: #{violation.alert_id}</span>
                          )}
                          <button
                            className={`btn btn-sm ${violation.acknowledged ? 'btn-outline' : 'btn-primary'}`}
                            onClick={() => handleAcknowledge(violation)}
                          >
                            {violation.acknowledged ? '已确认' : '确认违约'}
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="detail-sidebar">
          <div className="detail-section">
            <h3>📄 合同信息</h3>
            <div className="info-list">
              <div className="info-item">
                <span className="info-label">合同状态</span>
                <span className={`info-value ${contract.status === 'active' ? 'status-active' : ''}`}>
                  {contract.status === 'active' ? '生效中' : contract.status}
                </span>
              </div>
              <div className="info-item">
                <span className="info-label">生效日期</span>
                <span className="info-value">{formatDate(contract.effective_date)}</span>
              </div>
              <div className="info-item">
                <span className="info-label">到期日期</span>
                <span className="info-value">{formatDate(contract.expiry_date)}</span>
              </div>
              <div className="info-item">
                <span className="info-label">合同期限</span>
                <span className="info-value">
                  {Math.round((new Date(contract.expiry_date) - new Date(contract.effective_date)) / (1000 * 60 * 60 * 24))} 天
                </span>
              </div>
            </div>
          </div>

          <div className="detail-section">
            <h3>📐 SLA条款</h3>
            <div className="info-list">
              <div className="info-item">
                <span className="info-label">月可用率目标</span>
                <span className="info-value highlight">{contract.monthly_availability_target}%</span>
              </div>
              <div className="info-item">
                <span className="info-label">单次最大容忍</span>
                <span className="info-value">{contract.max_single_outage_minutes} 分钟</span>
              </div>
              <div className="info-item">
                <span className="info-label">月累计故障上限</span>
                <span className="info-value">{contract.max_monthly_outage_minutes} 分钟</span>
              </div>
              <div className="info-item">
                <span className="info-label">违约赔偿比例</span>
                <span className="info-value">{(contract.penalty_rate * 100).toFixed(1)}%</span>
              </div>
            </div>
          </div>

          <div className="detail-section">
            <h3>🎯 覆盖目标</h3>
            <p className="section-hint">取最差的目标数据作为履约依据</p>
            <div className="target-list">
              {contract.targets && contract.targets.map((binding) => (
                <div key={binding.id} className="target-list-item">
                  <span className="target-name">{binding.target_name}</span>
                </div>
              ))}
            </div>
          </div>

          {contract.description && (
            <div className="detail-section">
              <h3>📝 备注</h3>
              <p className="description-text">{contract.description}</p>
            </div>
          )}

          <div className="detail-section">
            <h3>⚙️ 操作</h3>
            <div className="action-buttons">
              <button className="btn btn-secondary btn-block">编辑合同</button>
              <button className="btn btn-outline btn-block">导出报告</button>
              <button className="btn btn-danger btn-outline btn-block">删除合同</button>
            </div>
          </div>
        </div>
      </div>

      {showAcknowledgeModal && selectedViolation && (
        <div className="modal-overlay" onClick={() => setShowAcknowledgeModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{selectedViolation.acknowledged ? '取消确认违约' : '确认违约事件'}</h3>
              <button className="close-btn" onClick={() => setShowAcknowledgeModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="violation-summary">
                <p>
                  <strong>违约类型:</strong> {getViolationTypeLabel(selectedViolation.violation_type)}
                </p>
                <p>
                  <strong>发生时间:</strong> {formatDateTime(selectedViolation.detected_at)}
                </p>
                <p>
                  <strong>故障时长:</strong> {selectedViolation.actual_duration_minutes} 分钟
                  (超出 {selectedViolation.exceeded_minutes} 分钟)
                </p>
                <p className="penalty-amount">
                  <strong>预估赔偿:</strong> ¥{selectedViolation.estimated_penalty?.toFixed(2)}
                </p>
              </div>
              <div className="form-group">
                <label>备注说明</label>
                <textarea
                  value={acknowledgeNote}
                  onChange={(e) => setAcknowledgeNote(e.target.value)}
                  placeholder="请输入处理说明..."
                  rows={3}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowAcknowledgeModal(false)}>
                取消
              </button>
              <button className="btn btn-primary" onClick={submitAcknowledge}>
                {selectedViolation.acknowledged ? '取消确认' : '确认违约'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default SLAContractDetail;
