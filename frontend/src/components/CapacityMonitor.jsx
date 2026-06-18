import { useState, useEffect, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function WaterLevelBar({ value, status }) {
  const pct = Math.min(value, 100);
  const colorMap = { green: '#22c55e', yellow: '#eab308', red: '#ef4444' };
  const bgColorMap = { green: '#166534', yellow: '#854d0e', red: '#991b1b' };
  const color = colorMap[status] || '#64748b';
  const bg = bgColorMap[status] || '#1e293b';
  return (
    <div className="water-level-bar-container">
      <div className="water-level-bar-track" style={{ background: bg }}>
        <div
          className="water-level-bar-fill"
          style={{
            width: `${pct}%`,
            background: color,
            transition: 'width 0.6s ease, background 0.3s',
          }}
        />
        <div className="water-level-bar-markers">
          <div className="water-level-marker" style={{ left: '60%' }} />
          <div className="water-level-marker" style={{ left: '85%' }} />
        </div>
      </div>
      <span className="water-level-bar-label" style={{ color }}>
        {value.toFixed(1)}%
      </span>
    </div>
  );
}

function TrendChart({ trend, predictionPoints, expansionPlan }) {
  if (!trend || trend.length === 0) {
    return <div className="capacity-empty">暂无趋势数据</div>;
  }

  const w = 800, h = 260, pad = { t: 20, r: 20, b: 40, l: 50 };
  const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;

  const allPoints = [...trend];
  const predPoints = predictionPoints || [];
  const totalLen = allPoints.length + predPoints.length;
  if (totalLen < 2) return null;

  const maxVal = Math.max(
    ...allPoints.map(p => p.overall_utilization),
    ...predPoints.map(p => p.overall_utilization),
    100
  );
  const yMax = Math.max(maxVal * 1.2, 110);

  const getX = (i) => pad.l + (i / Math.max(totalLen - 1, 1)) * iw;
  const getY = (v) => pad.t + ih - (v / yMax) * ih;

  const actualPts = allPoints.map((p, i) => ({
    x: getX(i),
    y: getY(p.overall_utilization),
    val: p.overall_utilization,
    ts: p.hour,
  }));

  const predPts = predPoints.map((p, i) => ({
    x: getX(allPoints.length + i),
    y: getY(p.overall_utilization),
    val: p.overall_utilization,
    ts: p.hour,
  }));

  const actualLine = actualPts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
  const predLine = predPts.length > 0
    ? `M${actualPts[actualPts.length - 1].x},${actualPts[actualPts.length - 1].y} ` +
      predPts.map(p => `L${p.x},${p.y}`).join(' ')
    : '';

  const y85 = getY(85);
  const y100 = getY(100);

  const expansionX = expansionPlan
    ? getX(allPoints.length - 1 + (new Date(expansionPlan.planned_expansion_at) - new Date(allPoints[allPoints.length - 1].ts)) / 3600000)
    : null;

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="capacity-trend-chart">
      <defs>
        <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {[0, 0.25, 0.5, 0.75, 1].map(f => (
        <g key={f}>
          <line x1={pad.l} y1={pad.t + ih * (1 - f)} x2={w - pad.r} y2={pad.t + ih * (1 - f)}
            stroke="#334155" strokeWidth="0.5" />
          <text x={pad.l - 6} y={pad.t + ih * (1 - f) + 4} textAnchor="end" fill="#64748b" fontSize="10">
            {(yMax * f).toFixed(0)}%
          </text>
        </g>
      ))}
      <line x1={pad.l} y1={y85} x2={w - pad.r} y2={y85} stroke="#eab308" strokeWidth="1" strokeDasharray="6,3" />
      <text x={w - pad.r + 4} y={y85 + 4} fill="#eab308" fontSize="9">85%</text>
      <line x1={pad.l} y1={y100} x2={w - pad.r} y2={y100} stroke="#ef4444" strokeWidth="1" strokeDasharray="6,3" />
      <text x={w - pad.r + 4} y={y100 + 4} fill="#ef4444" fontSize="9">100%</text>

      {actualPts.length > 1 && (
        <path d={actualLine + ` L${actualPts[actualPts.length - 1].x},${pad.t + ih} L${actualPts[0].x},${pad.t + ih} Z`}
          fill="url(#trendGrad)" />
      )}
      <path d={actualLine} fill="none" stroke="#3b82f6" strokeWidth="2" />

      {predLine && (
        <path d={predLine} fill="none" stroke="#a855f7" strokeWidth="2" strokeDasharray="8,4" />
      )}

      {actualPts.filter((_, i) => i % Math.max(1, Math.floor(actualPts.length / 30)) === 0).map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="2.5" fill="#3b82f6" />
      ))}

      {predPts.filter((_, i) => i % Math.max(1, Math.floor(predPts.length / 20)) === 0).map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="2.5" fill="#a855f7" />
      ))}

      {expansionX && expansionX > pad.l && expansionX < w - pad.r && (
        <g>
          <line x1={expansionX} y1={pad.t} x2={expansionX} y2={pad.t + ih}
            stroke="#22c55e" strokeWidth="2" strokeDasharray="4,4" />
          <rect x={expansionX - 28} y={pad.t + 4} width="56" height="18" rx="3" fill="#22c55e" />
          <text x={expansionX} y={pad.t + 16} textAnchor="middle" fill="#fff" fontSize="10">扩容</text>
        </g>
      )}

      <text x={pad.l} y={h - 4} fill="#64748b" fontSize="10">
        {new Date(allPoints[0].hour).toLocaleDateString('zh-CN')}
      </text>
      {predPts.length > 0 && (
        <text x={w - pad.r} y={h - 4} textAnchor="end" fill="#64748b" fontSize="10">
          预测 → {new Date(predPts[predPts.length - 1].ts).toLocaleDateString('zh-CN')}
        </text>
      )}

      <g transform={`translate(${pad.l + 10}, ${pad.t + 10})`}>
        <line x1="0" y1="0" x2="20" y2="0" stroke="#3b82f6" strokeWidth="2" />
        <text x="24" y="4" fill="#94a3b8" fontSize="10">实际水位</text>
        <line x1="80" y1="0" x2="100" y2="0" stroke="#a855f7" strokeWidth="2" strokeDasharray="8,4" />
        <text x="104" y="4" fill="#94a3b8" fontSize="10">预测趋势</text>
      </g>
    </svg>
  );
}

function HeatmapChart({ heatmap }) {
  if (!heatmap || heatmap.length === 0) {
    return <div className="capacity-empty">暂无热力图数据</div>;
  }

  const dates = [...new Set(heatmap.map(c => c.date))].sort();
  const hours = Array.from({ length: 24 }, (_, i) => i);

  const cellW = 26, cellH = 22, padL = 70, padT = 25;
  const w = padL + 24 * cellW + 10;
  const h = padT + dates.length * cellH + 10;

  const getColor = (val) => {
    if (val < 60) return `rgba(34, 197, 94, ${0.2 + val / 100 * 0.8})`;
    if (val < 85) return `rgba(234, 179, 8, ${0.3 + (val - 60) / 25 * 0.7})`;
    return `rgba(239, 68, 68, ${0.4 + (val - 85) / 15 * 0.6})`;
  };

  const cellMap = {};
  heatmap.forEach(c => {
    cellMap[`${c.date}_${c.hour}`] = c.utilization;
  });

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="capacity-heatmap">
      {hours.map(hr => (
        <text key={hr} x={padL + hr * cellW + cellW / 2} y={padT - 6}
          textAnchor="middle" fill="#64748b" fontSize="8">
          {hr}时
        </text>
      ))}
      {dates.map((date, di) => (
        <g key={date}>
          <text x={padL - 4} y={padT + di * cellH + cellH / 2 + 4}
            textAnchor="end" fill="#64748b" fontSize="9">
            {date.slice(5)}
          </text>
          {hours.map(hr => {
            const val = cellMap[`${date}_${hr}`];
            if (val === undefined) return null;
            return (
              <rect key={hr} x={padL + hr * cellW + 1} y={padT + di * cellH + 1}
                width={cellW - 2} height={cellH - 2} rx="2"
                fill={getColor(val)} stroke="#1e293b" strokeWidth="0.5">
                <title>{`${date} ${hr}:00 - 利用率 ${val.toFixed(1)}%`}</title>
              </rect>
            );
          })}
        </g>
      ))}
    </svg>
  );
}

function CapacityConfigForm({ targetId, groupdId, existingConfig, onSave, onCancel }) {
  const [maxConnections, setMaxConnections] = useState(existingConfig?.max_connections || '');
  const [maxLatencyMs, setMaxLatencyMs] = useState(existingConfig?.max_latency_ms || 500);
  const [maxThroughputRps, setMaxThroughputRps] = useState(existingConfig?.max_throughput_rps || '');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        max_connections: maxConnections ? Number(maxConnections) : null,
        max_latency_ms: Number(maxLatencyMs),
        max_throughput_rps: maxThroughputRps ? Number(maxThroughputRps) : null,
        is_override: !!targetId,
      };
      if (targetId) payload.target_id = targetId;
      if (groupdId) payload.group_id = groupdId;

      const res = await fetch(`${API_BASE}/api/capacity/configs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        onSave?.();
      }
    } catch (e) {
      console.error('Failed to save capacity config:', e);
    }
  };

  return (
    <div className="capacity-config-form">
      <h4>配置容量阈值</h4>
      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <label>并发连接数上限</label>
          <input type="number" value={maxConnections} onChange={e => setMaxConnections(e.target.value)}
            placeholder="如 1000" />
        </div>
        <div className="form-row">
          <label>响应延迟天花板 (ms)</label>
          <input type="number" step="0.1" value={maxLatencyMs} onChange={e => setMaxLatencyMs(e.target.value)} />
        </div>
        <div className="form-row">
          <label>吞吐量峰值 (rps)</label>
          <input type="number" step="0.1" value={maxThroughputRps} onChange={e => setMaxThroughputRps(e.target.value)}
            placeholder="如 100" />
        </div>
        <div className="form-actions">
          <button type="submit" className="btn-primary">保存</button>
          <button type="button" className="btn-secondary" onClick={onCancel}>取消</button>
        </div>
      </form>
    </div>
  );
}

function CapacityPlanForm({ targetId, existingPlan, onSave, onCancel }) {
  const [expansionAt, setExpansionAt] = useState(
    existingPlan?.planned_expansion_at
      ? new Date(new Date(existingPlan.planned_expansion_at).getTime() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16)
      : ''
  );
  const [multiplier, setMultiplier] = useState(existingPlan?.target_capacity_multiplier || 2.0);
  const [notes, setNotes] = useState(existingPlan?.notes || '');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        target_id: targetId,
        planned_expansion_at: new Date(expansionAt).toISOString(),
        target_capacity_multiplier: Number(multiplier),
        notes,
      };
      const url = existingPlan
        ? `${API_BASE}/api/capacity/plans/${existingPlan.id}`
        : `${API_BASE}/api/capacity/plans`;
      const method = existingPlan ? 'PUT' : 'POST';
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        onSave?.();
      }
    } catch (e) {
      console.error('Failed to save capacity plan:', e);
    }
  };

  return (
    <div className="capacity-plan-form">
      <h4>容量规划方案</h4>
      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <label>计划扩容时间</label>
          <input type="datetime-local" value={expansionAt} onChange={e => setExpansionAt(e.target.value)} />
        </div>
        <div className="form-row">
          <label>扩容倍数</label>
          <input type="number" step="0.1" min="1.1" value={multiplier} onChange={e => setMultiplier(e.target.value)} />
        </div>
        <div className="form-row">
          <label>备注</label>
          <input type="text" value={notes} onChange={e => setNotes(e.target.value)} placeholder="扩容说明" />
        </div>
        <div className="form-actions">
          <button type="submit" className="btn-primary">保存</button>
          <button type="button" className="btn-secondary" onClick={onCancel}>取消</button>
        </div>
      </form>
    </div>
  );
}

function CapacityDetail({ targetId, onBack }) {
  const [detail, setDetail] = useState(null);
  const [showConfigForm, setShowConfigForm] = useState(false);
  const [showPlanForm, setShowPlanForm] = useState(false);

  const loadDetail = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/capacity/targets/${targetId}`);
      if (res.ok) {
        const data = await res.json();
        setDetail(data);
      }
    } catch (e) {
      console.error('Failed to load capacity detail:', e);
    }
  }, [targetId]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  if (!detail) return <div className="capacity-loading">加载中...</div>;

  const statusLabel = { green: '安全', yellow: '告警', red: '危险' };
  const statusIcon = { green: '✅', yellow: '⚠️', red: '🔴' };

  return (
    <div className="capacity-detail">
      <div className="capacity-detail-header">
        <button className="btn-back" onClick={onBack}>← 返回总览</button>
        <h3>{detail.target_name}</h3>
        <span className={`capacity-status-badge ${detail.water_level_status}`}>
          {statusIcon[detail.water_level_status]} {statusLabel[detail.water_level_status]}
        </span>
        <span className="capacity-water-level">
          当前水位: <strong>{detail.current_water_level}%</strong>
        </span>
        {detail.group_name && (
          <span className="capacity-group-tag">组: {detail.group_name}</span>
        )}
      </div>

      <div className="capacity-detail-metrics">
        <div className="capacity-metric-card">
          <span className="metric-label">延迟利用率</span>
          <span className="metric-value">{detail.trend?.length > 0 ? detail.trend[detail.trend.length - 1].latency_utilization : 0}%</span>
        </div>
        <div className="capacity-metric-card">
          <span className="metric-label">连接利用率</span>
          <span className="metric-value">{detail.trend?.length > 0 ? detail.trend[detail.trend.length - 1].connection_utilization : 0}%</span>
        </div>
        <div className="capacity-metric-card">
          <span className="metric-label">吞吐利用率</span>
          <span className="metric-value">{detail.trend?.length > 0 ? detail.trend[detail.trend.length - 1].throughput_utilization : 0}%</span>
        </div>
      </div>

      <div className="capacity-section">
        <div className="capacity-section-header">
          <h4>📊 7天水位趋势与预测</h4>
          {detail.prediction && (
            <div className="capacity-prediction-summary">
              <span className={`trend-badge ${detail.prediction.current_trend}`}>
                {detail.prediction.current_trend === 'rising' ? '📈 上升趋势' :
                 detail.prediction.current_trend === 'declining' ? '📉 下降趋势' : '➡️ 平稳'}
              </span>
              {detail.prediction.predicted_breach_85_at && (
                <span className="breach-predict">
                  预计突破85%: {new Date(detail.prediction.predicted_breach_85_at).toLocaleString('zh-CN')}
                </span>
              )}
              {detail.prediction.predicted_breach_100_at && (
                <span className="breach-predict danger">
                  预计突破100%: {new Date(detail.prediction.predicted_breach_100_at).toLocaleString('zh-CN')}
                </span>
              )}
            </div>
          )}
        </div>
        <TrendChart
          trend={detail.trend}
          predictionPoints={detail.prediction?.prediction_points}
          expansionPlan={detail.plans?.[0]}
        />
      </div>

      <div className="capacity-section">
        <h4>🗓️ 每小时利用率热力图</h4>
        <HeatmapChart heatmap={detail.heatmap} />
      </div>

      <div className="capacity-section">
        <div className="capacity-section-header">
          <h4>⚙️ 容量配置</h4>
          <button className="btn-sm" onClick={() => setShowConfigForm(!showConfigForm)}>
            {showConfigForm ? '收起' : '编辑'}
          </button>
        </div>
        {detail.config ? (
          <div className="capacity-config-info">
            <div className="config-item">
              <span>并发连接上限</span>
              <strong>{detail.config.max_connections || '未设置'}</strong>
            </div>
            <div className="config-item">
              <span>延迟天花板</span>
              <strong>{detail.config.max_latency_ms}ms</strong>
            </div>
            <div className="config-item">
              <span>吞吐峰值</span>
              <strong>{detail.config.max_throughput_rps || '未设置'} rps</strong>
            </div>
            {detail.config.is_override && (
              <span className="override-badge">单独覆盖</span>
            )}
          </div>
        ) : (
          <div className="capacity-no-config">未配置容量阈值，点击编辑按钮设置</div>
        )}
        {showConfigForm && (
          <CapacityConfigForm
            targetId={targetId}
            existingConfig={detail.config}
            onSave={() => { setShowConfigForm(false); loadDetail(); }}
            onCancel={() => setShowConfigForm(false)}
          />
        )}
      </div>

      <div className="capacity-section">
        <div className="capacity-section-header">
          <h4>📋 容量规划</h4>
          <button className="btn-sm" onClick={() => setShowPlanForm(!showPlanForm)}>
            {showPlanForm ? '收起' : (detail.plans?.length > 0 ? '编辑方案' : '新建方案')}
          </button>
        </div>
        {detail.plans?.length > 0 ? (
          <div className="capacity-plan-info">
            <div className="plan-item">
              <span>计划扩容时间</span>
              <strong>{new Date(detail.plans[0].planned_expansion_at).toLocaleString('zh-CN')}</strong>
            </div>
            <div className="plan-item">
              <span>扩容倍数</span>
              <strong>{detail.plans[0].target_capacity_multiplier}x</strong>
            </div>
            {detail.plans[0].notes && (
              <div className="plan-item">
                <span>备注</span>
                <span>{detail.plans[0].notes}</span>
              </div>
            )}
          </div>
        ) : (
          <div className="capacity-no-plan">暂无容量规划方案</div>
        )}
        {showPlanForm && (
          <CapacityPlanForm
            targetId={targetId}
            existingPlan={detail.plans?.[0]}
            onSave={() => { setShowPlanForm(false); loadDetail(); }}
            onCancel={() => setShowPlanForm(false)}
          />
        )}
      </div>

      {detail.alerts?.length > 0 && (
        <div className="capacity-section">
          <h4>🚨 容量预警</h4>
          {detail.alerts.map(alert => (
            <div key={alert.id} className="capacity-alert-card">
              <div className="alert-header">
                <span className="alert-target">{alert.target_name}</span>
                <span className="alert-level">水位 {alert.current_water_level}%</span>
              </div>
              <div className="alert-body">
                {alert.predicted_breach_85_at && (
                  <div>预计突破85%: {new Date(alert.predicted_breach_85_at).toLocaleString('zh-CN')}</div>
                )}
                {alert.predicted_breach_100_at && (
                  <div>预计突破100%: {new Date(alert.predicted_breach_100_at).toLocaleString('zh-CN')}</div>
                )}
                {alert.suggested_expansion && (
                  <div>建议扩容幅度: {alert.suggested_expansion}x</div>
                )}
              </div>
              <button className="btn-sm alert-resolve-btn" onClick={async () => {
                await fetch(`${API_BASE}/api/capacity/alerts/${alert.id}/resolve`, { method: 'POST' });
                loadDetail();
              }}>
                标记已处理
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CapacityMonitor() {
  const [overview, setOverview] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [selectedTarget, setSelectedTarget] = useState(null);
  const [showGroupConfig, setShowGroupConfig] = useState(false);
  const [selectedGroupId, setSelectedGroupId] = useState(null);

  const loadOverview = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/capacity/overview`);
      if (res.ok) {
        const data = await res.json();
        setOverview(data);
      }
    } catch (e) {
      console.error('Failed to load capacity overview:', e);
    }
  }, []);

  const loadAlerts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/capacity/alerts?active_only=true`);
      if (res.ok) {
        const data = await res.json();
        setAlerts(data);
      }
    } catch (e) {
      console.error('Failed to load capacity alerts:', e);
    }
  }, []);

  useEffect(() => {
    loadOverview();
    loadAlerts();
    const interval = setInterval(() => {
      loadOverview();
      loadAlerts();
    }, 30000);
    return () => clearInterval(interval);
  }, [loadOverview, loadAlerts]);

  if (selectedTarget) {
    return <CapacityDetail targetId={selectedTarget} onBack={() => { setSelectedTarget(null); loadOverview(); }} />;
  }

  if (!overview) return <div className="capacity-loading">加载容量数据...</div>;

  const configured = overview.targets.filter(t => t.has_capacity_config);
  const unconfigured = overview.targets.filter(t => !t.has_capacity_config);
  const sortedTargets = [
    ...configured.sort((a, b) => b.current_water_level - a.current_water_level),
    ...unconfigured,
  ];

  return (
    <div className="capacity-monitor">
      <div className="capacity-overview-header">
        <h2>📊 容量水位监控与资源瓶颈预测</h2>
        <div className="capacity-summary-stats">
          <div className="summary-stat">
            <span className="stat-value">{overview.total_targets}</span>
            <span className="stat-label">总目标</span>
          </div>
          <div className="summary-stat">
            <span className="stat-value">{overview.configured_targets}</span>
            <span className="stat-label">已配置</span>
          </div>
          <div className="summary-stat danger">
            <span className="stat-value">{overview.active_alerts}</span>
            <span className="stat-label">活跃预警</span>
          </div>
        </div>
      </div>

      {alerts.length > 0 && (
        <div className="capacity-alerts-banner">
          <h4>🚨 容量预警 ({alerts.length})</h4>
          <div className="alerts-scroll">
            {alerts.map(alert => (
              <div key={alert.id} className="capacity-alert-banner-item" onClick={() => setSelectedTarget(alert.target_id)}>
                <span className={`alert-status-dot ${alert.current_water_level >= 85 ? 'red' : 'yellow'}`}></span>
                <span className="alert-target-name">{alert.target_name}</span>
                <span className="alert-water-level">水位 {alert.current_water_level}%</span>
                {alert.predicted_breach_85_at && (
                  <span className="alert-breach-time">
                    预计 {new Date(alert.predicted_breach_85_at).toLocaleDateString('zh-CN')} 突破85%
                  </span>
                )}
                <span className="alert-suggestion">建议扩容 {alert.suggested_expansion}x</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="capacity-overview-grid">
        {sortedTargets.map(target => (
          <div
            key={target.target_id}
            className={`capacity-target-card ${target.water_level_status}`}
            onClick={() => setSelectedTarget(target.target_id)}
          >
            <div className="card-header">
              <span className="target-name">{target.target_name}</span>
              {target.group_name && <span className="group-tag">{target.group_name}</span>}
            </div>
            {target.has_capacity_config ? (
              <>
                <WaterLevelBar value={target.current_water_level} status={target.water_level_status} />
                <div className="card-metrics">
                  <div className="mini-metric">
                    <span className="mini-label">延迟</span>
                    <span className="mini-value">{target.latency_utilization}%</span>
                  </div>
                  <div className="mini-metric">
                    <span className="mini-label">连接</span>
                    <span className="mini-value">{target.connection_utilization}%</span>
                  </div>
                  <div className="mini-metric">
                    <span className="mini-label">吞吐</span>
                    <span className="mini-value">{target.throughput_utilization}%</span>
                  </div>
                </div>
                {(target.predicted_breach_85_at || target.predicted_breach_100_at) && (
                  <div className="card-prediction">
                    {target.predicted_breach_85_at && (
                      <span className="prediction-warning">
                        ⚠️ 预计 {new Date(target.predicted_breach_85_at).toLocaleDateString('zh-CN')} 突破85%
                      </span>
                    )}
                  </div>
                )}
              </>
            ) : (
              <div className="card-no-config">未配置容量阈值</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
