import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function BudgetRing({ pct, status, size = 120 }) {
  const r = (size - 12) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;
  const colorMap = { safe: '#22c55e', fast_burn: '#eab308', critical: '#ef4444', breached: '#dc2626' };
  const color = colorMap[status] || '#64748b';
  return (
    <svg width={size} height={size} className="budget-ring-svg">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#334155" strokeWidth="6" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="6"
        strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset 0.6s ease, stroke 0.3s' }} />
      <text x={size / 2} y={size / 2 - 6} textAnchor="middle" fill="#f1f5f9" fontSize="20" fontWeight="700">
        {pct.toFixed(1)}%
      </text>
      <text x={size / 2} y={size / 2 + 14} textAnchor="middle" fill="#94a3b8" fontSize="11">
        剩余预算
      </text>
    </svg>
  );
}

function BurnDownChart({ timeline }) {
  if (!timeline || timeline.length < 2) return null;
  const w = 700, h = 200, pad = { t: 20, r: 20, b: 30, l: 50 };
  const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
  const maxBudget = Math.max(...timeline.map(p => p.total_budget), 0.01);
  const pts = timeline.map((p, i) => ({
    x: pad.l + (i / (timeline.length - 1)) * iw,
    y: pad.t + ih - (p.budget_remaining / maxBudget) * ih,
    consumed: p.budget_consumed,
    remaining: p.budget_remaining,
    ts: p.timestamp,
  }));
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
  const area = `${line} L${pts[pts.length - 1].x},${pad.t + ih} L${pts[0].x},${pad.t + ih} Z`;

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="burndown-chart">
      <defs>
        <linearGradient id="burnGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ef4444" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#ef4444" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {[0, 0.25, 0.5, 0.75, 1].map(f => (
        <g key={f}>
          <line x1={pad.l} y1={pad.t + ih * (1 - f)} x2={w - pad.r} y2={pad.t + ih * (1 - f)}
            stroke="#334155" strokeWidth="0.5" />
          <text x={pad.l - 6} y={pad.t + ih * (1 - f) + 4} textAnchor="end" fill="#64748b" fontSize="10">
            {(maxBudget * f).toFixed(2)}
          </text>
        </g>
      ))}
      <path d={area} fill="url(#burnGrad)" />
      <path d={line} fill="none" stroke="#ef4444" strokeWidth="2" />
      {pts.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="3" fill="#ef4444" stroke="#0f172a" strokeWidth="1.5" />
      ))}
      <text x={pad.l} y={h - 4} fill="#64748b" fontSize="10">
        {new Date(timeline[0].timestamp).toLocaleDateString('zh-CN')}
      </text>
      <text x={w - pad.r} y={h - 4} textAnchor="end" fill="#64748b" fontSize="10">
        {new Date(timeline[timeline.length - 1].timestamp).toLocaleDateString('zh-CN')}
      </text>
    </svg>
  );
}

function AttributionBar({ attribution, total }) {
  const segments = [
    { key: 'service_fault', label: '服务自身故障', color: '#ef4444' },
    { key: 'regional_anomaly', label: '局部区域异常', color: '#f59e0b' },
    { key: 'dependency_cascade', label: '依赖级联影响', color: '#a855f7' },
    { key: 'change_induced', label: '变更期间新增', color: '#3b82f6' },
  ];
  const sum = segments.reduce((s, seg) => s + (attribution[seg.key] || 0), 0);
  return (
    <div className="attribution-bar-container">
      <div className="attribution-bar">
        {segments.map(seg => {
          const val = attribution[seg.key] || 0;
          const pct = sum > 0 ? (val / sum) * 100 : 0;
          return (
            <div key={seg.key} className="attribution-segment"
              style={{ width: `${pct}%`, backgroundColor: seg.color, minWidth: pct > 0 ? '2px' : '0' }}
              title={`${seg.label}: ${val.toFixed(1)} (${pct.toFixed(1)}%)`} />
          );
        })}
      </div>
      <div className="attribution-legend">
        {segments.map(seg => {
          const val = attribution[seg.key] || 0;
          const pct = sum > 0 ? (val / sum) * 100 : 0;
          return (
            <div key={seg.key} className="attribution-legend-item">
              <span className="legend-dot" style={{ backgroundColor: seg.color }}></span>
              <span className="legend-label">{seg.label}</span>
              <span className="legend-value">{val.toFixed(1)}</span>
              <span className="legend-pct">({pct.toFixed(1)}%)</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  const cfg = {
    safe: { label: '安全', icon: '✅', cls: 'safe' },
    fast_burn: { label: '快速燃尽', icon: '⚠️', cls: 'fast-burn' },
    critical: { label: '即将违约', icon: '🔴', cls: 'critical' },
    breached: { label: '已违约', icon: '❌', cls: 'breached' },
  };
  const c = cfg[status] || { label: status, icon: '❓', cls: '' };
  return <span className={`slo-status-badge ${c.cls}`}>{c.icon} {c.label}</span>;
}

function AddSLOModal({ onClose, onSubmit, targets, groups }) {
  const [form, setForm] = useState({
    name: '', description: '', target_id: '', group_id: '',
    slo_type: 'availability', slo_target: 99.9, latency_threshold_ms: '', window_days: 30,
  });
  const handleSubmit = () => {
    const data = { ...form };
    if (!data.target_id) delete data.target_id;
    else data.target_id = parseInt(data.target_id);
    if (!data.group_id) delete data.group_id;
    else data.group_id = parseInt(data.group_id);
    if (!data.latency_threshold_ms) delete data.latency_threshold_ms;
    else data.latency_threshold_ms = parseFloat(data.latency_threshold_ms);
    data.slo_target = parseFloat(data.slo_target);
    data.window_days = parseInt(data.window_days);
    onSubmit(data);
  };
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal slo-modal" onClick={e => e.stopPropagation()}>
        <h2>新建 SLO 目标</h2>
        <div className="form-group">
          <label>名称</label>
          <input type="text" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="例: 核心API月可用性" />
        </div>
        <div className="form-group">
          <label>描述</label>
          <input type="text" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
        </div>
        <div className="form-row">
          <div className="form-group">
            <label>绑定目标</label>
            <select value={form.target_id} onChange={e => setForm(f => ({ ...f, target_id: e.target.value }))}>
              <option value="">不绑定</option>
              {targets.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>绑定分组</label>
            <select value={form.group_id} onChange={e => setForm(f => ({ ...f, group_id: e.target.value }))}>
              <option value="">不绑定</option>
              {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label>SLO 类型</label>
            <select value={form.slo_type} onChange={e => setForm(f => ({ ...f, slo_type: e.target.value }))}>
              <option value="availability">可用性</option>
              <option value="latency">延迟</option>
            </select>
          </div>
          <div className="form-group">
            <label>SLO 目标 (%)</label>
            <input type="number" step="0.01" value={form.slo_target} onChange={e => setForm(f => ({ ...f, slo_target: e.target.value }))} />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label>延迟阈值 (ms)</label>
            <input type="number" value={form.latency_threshold_ms} onChange={e => setForm(f => ({ ...f, latency_threshold_ms: e.target.value }))} placeholder="可选" />
          </div>
          <div className="form-group">
            <label>观测窗口 (天)</label>
            <input type="number" value={form.window_days} onChange={e => setForm(f => ({ ...f, window_days: e.target.value }))} />
          </div>
        </div>
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>取消</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={!form.name}>创建</button>
        </div>
      </div>
    </div>
  );
}

export default function SLOBudgetPanel({ targets, groups }) {
  const [overview, setOverview] = useState([]);
  const [selectedSloId, setSelectedSloId] = useState(null);
  const [budgetDetail, setBudgetDetail] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadOverview = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/slo/budget/overview`);
      if (res.ok) {
        const data = await res.json();
        setOverview(data);
      }
    } catch (e) {
      console.error('Failed to load SLO overview:', e);
    } finally {
      setLoading(false);
    }
  };

  const loadBudgetDetail = async (sloId) => {
    try {
      const [budgetRes, predRes] = await Promise.all([
        fetch(`${API_BASE}/api/slo/${sloId}/budget`),
        fetch(`${API_BASE}/api/slo/${sloId}/prediction`),
      ]);
      if (budgetRes.ok) {
        const data = await budgetRes.json();
        setBudgetDetail(data);
      }
      if (predRes.ok) {
        const data = await predRes.json();
        setPrediction(data);
      }
    } catch (e) {
      console.error('Failed to load budget detail:', e);
    }
  };

  const handleCreateSLO = async (data) => {
    try {
      const res = await fetch(`${API_BASE}/api/slo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (res.ok) {
        setShowAddModal(false);
        loadOverview();
      }
    } catch (e) {
      console.error('Failed to create SLO:', e);
    }
  };

  const handleDeleteSLO = async (sloId) => {
    if (!confirm('确定要删除此 SLO 目标吗？')) return;
    try {
      const res = await fetch(`${API_BASE}/api/slo/${sloId}`, { method: 'DELETE' });
      if (res.ok) {
        if (selectedSloId === sloId) {
          setSelectedSloId(null);
          setBudgetDetail(null);
          setPrediction(null);
        }
        loadOverview();
      }
    } catch (e) {
      console.error('Failed to delete SLO:', e);
    }
  };

  useEffect(() => {
    loadOverview();
    const interval = setInterval(loadOverview, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedSloId) {
      loadBudgetDetail(selectedSloId);
    } else {
      setBudgetDetail(null);
      setPrediction(null);
    }
  }, [selectedSloId]);

  const safeCount = overview.filter(s => s.status === 'safe').length;
  const fastBurnCount = overview.filter(s => s.status === 'fast_burn').length;
  const criticalCount = overview.filter(s => s.status === 'critical' || s.status === 'breached').length;

  const sortedOverview = [...overview].sort((a, b) => {
    const order = { breached: 0, critical: 1, fast_burn: 2, safe: 3 };
    return (order[a.status] ?? 4) - (order[b.status] ?? 4);
  });

  return (
    <div className="slo-budget-panel">
      <div className="slo-panel-header">
        <div className="slo-header-left">
          <h2>SLO 预算与燃尽中心</h2>
          <span className="slo-header-subtitle">实时追踪可用性预算消耗，定位预算烧掉的原因</span>
        </div>
        <div className="slo-header-right">
          <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>+ 新建 SLO</button>
        </div>
      </div>

      <div className="slo-summary-cards">
        <div className="slo-summary-card safe">
          <div className="slo-summary-icon">✅</div>
          <div className="slo-summary-info">
            <div className="slo-summary-value">{safeCount}</div>
            <div className="slo-summary-label">预算安全</div>
          </div>
        </div>
        <div className="slo-summary-card fast-burn">
          <div className="slo-summary-icon">⚠️</div>
          <div className="slo-summary-info">
            <div className="slo-summary-value">{fastBurnCount}</div>
            <div className="slo-summary-label">快速燃尽</div>
          </div>
        </div>
        <div className="slo-summary-card critical">
          <div className="slo-summary-icon">🔴</div>
          <div className="slo-summary-info">
            <div className="slo-summary-value">{criticalCount}</div>
            <div className="slo-summary-label">即将/已违约</div>
          </div>
        </div>
        <div className="slo-summary-card total">
          <div className="slo-summary-icon">📊</div>
          <div className="slo-summary-info">
            <div className="slo-summary-value">{overview.length}</div>
            <div className="slo-summary-label">SLO 目标总数</div>
          </div>
        </div>
      </div>

      <div className="slo-content">
        <div className="slo-list-section">
          <h3>预算总览</h3>
          {loading ? (
            <div className="loading-state">加载中...</div>
          ) : sortedOverview.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">📊</div>
              <p>暂无 SLO 目标</p>
              <p className="empty-hint">点击右上角"新建 SLO"按钮创建第一个目标</p>
            </div>
          ) : (
            <div className="slo-overview-grid">
              {sortedOverview.map(item => (
                <div key={item.slo_id}
                  className={`slo-overview-card ${item.status} ${selectedSloId === item.slo_id ? 'selected' : ''}`}
                  onClick={() => setSelectedSloId(item.slo_id)}>
                  <div className="slo-card-top">
                    <div className="slo-card-name">{item.slo_name}</div>
                    <StatusBadge status={item.status} />
                  </div>
                  <div className="slo-card-ring">
                    <BudgetRing pct={item.budget_remaining_pct} status={item.status} size={100} />
                  </div>
                  <div className="slo-card-meta">
                    <div className="slo-meta-row">
                      <span className="slo-meta-label">当前值</span>
                      <span className="slo-meta-value">{item.current_value.toFixed(3)}%</span>
                    </div>
                    <div className="slo-meta-row">
                      <span className="slo-meta-label">SLO 目标</span>
                      <span className="slo-meta-value">{item.slo_target}%</span>
                    </div>
                    <div className="slo-meta-row">
                      <span className="slo-meta-label">燃尽速率</span>
                      <span className={`slo-meta-value ${item.burn_rate > 0.5 ? 'burn-high' : ''}`}>{item.burn_rate.toFixed(2)}/天</span>
                    </div>
                    {item.target_name && (
                      <div className="slo-meta-row">
                        <span className="slo-meta-label">关联目标</span>
                        <span className="slo-meta-value slo-meta-target">{item.target_name}</span>
                      </div>
                    )}
                    {item.group_name && (
                      <div className="slo-meta-row">
                        <span className="slo-meta-label">关联分组</span>
                        <span className="slo-meta-value">{item.group_name}</span>
                      </div>
                    )}
                  </div>
                  <button className="slo-delete-btn" onClick={e => { e.stopPropagation(); handleDeleteSLO(item.slo_id); }}
                    title="删除">✕</button>
                </div>
              ))}
            </div>
          )}
        </div>

        {budgetDetail && (
          <div className="slo-detail-section">
            <div className="slo-detail-header">
              <h3>{budgetDetail.slo_name} - 预算详情</h3>
              <button className="btn btn-secondary" onClick={() => setSelectedSloId(null)}>关闭</button>
            </div>

            <div className="slo-detail-stats">
              <div className="slo-detail-stat-card">
                <div className="slo-detail-stat-label">当前可用性</div>
                <div className="slo-detail-stat-value">{budgetDetail.current_value.toFixed(3)}%</div>
              </div>
              <div className="slo-detail-stat-card">
                <div className="slo-detail-stat-label">SLO 目标</div>
                <div className="slo-detail-stat-value">{budgetDetail.slo_target}%</div>
              </div>
              <div className="slo-detail-stat-card">
                <div className="slo-detail-stat-label">预算已消耗</div>
                <div className="slo-detail-stat-value burn">{budgetDetail.budget_consumed.toFixed(4)}</div>
              </div>
              <div className="slo-detail-stat-card">
                <div className="slo-detail-stat-label">预算剩余</div>
                <div className={`slo-detail-stat-value ${budgetDetail.budget_remaining_pct <= 20 ? 'critical' : budgetDetail.budget_remaining_pct <= 50 ? 'warn' : 'good'}`}>
                  {budgetDetail.budget_remaining.toFixed(4)} ({budgetDetail.budget_remaining_pct.toFixed(1)}%)
                </div>
              </div>
            </div>

            <div className="slo-detail-section-block">
              <h4>预算消耗燃尽曲线</h4>
              <div className="chart-container">
                <BurnDownChart timeline={budgetDetail.timeline} />
              </div>
            </div>

            <div className="slo-detail-section-block">
              <h4>预算归因拆解</h4>
              <p className="slo-attribution-hint">展示预算是被哪些因素消耗的，合并计算避免重复</p>
              <AttributionBar attribution={budgetDetail.attribution} total={budgetDetail.budget_consumed} />
            </div>

            {prediction && (
              <div className="slo-detail-section-block">
                <h4>未来 24 小时预测</h4>
                <div className="slo-prediction-cards">
                  <div className="slo-pred-card">
                    <div className="slo-pred-label">燃尽速率</div>
                    <div className="slo-pred-value">{prediction.burn_rate.toFixed(2)}/天</div>
                  </div>
                  <div className="slo-pred-card">
                    <div className="slo-pred-label">24h 预测可用性</div>
                    <div className={`slo-pred-value ${prediction.will_breach_24h ? 'critical' : 'good'}`}>
                      {prediction.projected_value_24h.toFixed(3)}%
                    </div>
                  </div>
                  {prediction.hours_to_breach !== null && prediction.hours_to_breach > 0 ? (
                    <div className="slo-pred-card warn">
                      <div className="slo-pred-label">预计触线时间</div>
                      <div className="slo-pred-value">
                        {prediction.hours_to_breach.toFixed(1)} 小时后
                      </div>
                      <div className="slo-pred-sub">
                        约 {new Date(prediction.predicted_breach_time).toLocaleString('zh-CN')}
                      </div>
                    </div>
                  ) : prediction.hours_to_breach === 0 ? (
                    <div className="slo-pred-card critical">
                      <div className="slo-pred-label">触线状态</div>
                      <div className="slo-pred-value">已触线</div>
                    </div>
                  ) : (
                    <div className="slo-pred-card good">
                      <div className="slo-pred-label">触线风险</div>
                      <div className="slo-pred-value">暂无风险</div>
                    </div>
                  )}
                  <div className={`slo-pred-card ${prediction.will_breach_24h ? 'critical' : 'good'}`}>
                    <div className="slo-pred-label">24h 内是否触线</div>
                    <div className="slo-pred-value">{prediction.will_breach_24h ? '⚠️ 是' : '✅ 否'}</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {showAddModal && (
        <AddSLOModal
          onClose={() => setShowAddModal(false)}
          onSubmit={handleCreateSLO}
          targets={targets}
          groups={groups}
        />
      )}
    </div>
  );
}
