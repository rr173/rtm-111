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

function TrendChart({ trend, predictionPoints, expansionPlan, baselineBand }) {
  if (!trend || trend.length === 0) {
    return <div className="capacity-empty">暂无趋势数据</div>;
  }

  const w = 800, h = 260, pad = { t: 20, r: 20, b: 40, l: 50 };
  const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;

  const allPoints = [...trend];
  const predPoints = predictionPoints || [];
  const totalLen = allPoints.length + predPoints.length;
  if (totalLen < 2) return null;

  const baselineData = baselineBand || [];

  const maxVal = Math.max(
    ...allPoints.map(p => p.overall_utilization),
    ...predPoints.map(p => p.overall_utilization),
    ...baselineData.map(b => b.upper_bound || 0),
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
    idx: i,
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

  const bandPts = baselineData.slice(0, allPoints.length).map((b, i) => ({
    x: getX(i),
    lower: getY(b.lower_bound || b.baseline_lower || 0),
    upper: getY(b.upper_bound || b.baseline_upper || 0),
    mean: getY(b.baseline_mean || 0),
  }));

  let baselineBandPath = '';
  let baselineMeanPath = '';
  if (bandPts.length >= 2) {
    const upperPart = bandPts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.upper}`).join(' ');
    const lowerPart = bandPts.slice().reverse().map(p => `L${p.x},${p.lower}`).join(' ');
    baselineBandPath = `${upperPart} ${lowerPart} Z`;
    baselineMeanPath = bandPts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.mean}`).join(' ');
  }

  const anomalySegments = [];
  if (baselineData.length >= 2) {
    let currentAnomaly = null;
    for (let i = 0; i < allPoints.length; i++) {
      const baseline = baselineData[i];
      const util = allPoints[i].overall_utilization;
      if (!baseline) { currentAnomaly = null; continue; }
      const lower = baseline.lower_bound || baseline.baseline_lower || 0;
      const upper = baseline.upper_bound || baseline.baseline_upper || 100;
      let type = null;
      if (util > upper) type = 'high';
      else if (util < lower) type = 'low';

      if (type) {
        if (currentAnomaly && currentAnomaly.type === type) {
          currentAnomaly.endIdx = i;
        } else {
          if (currentAnomaly) anomalySegments.push(currentAnomaly);
          currentAnomaly = { type, startIdx: i, endIdx: i };
        }
      } else {
        if (currentAnomaly) {
          anomalySegments.push(currentAnomaly);
          currentAnomaly = null;
        }
      }
    }
    if (currentAnomaly) anomalySegments.push(currentAnomaly);
  }

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="capacity-trend-chart">
      <defs>
        <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.02" />
        </linearGradient>
        <linearGradient id="baselineGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.08" />
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

      {baselineBandPath && (
        <path d={baselineBandPath} fill="url(#baselineGrad)" />
      )}
      {baselineMeanPath && (
        <path d={baselineMeanPath} fill="none" stroke="#06b6d4" strokeWidth="1.2" strokeDasharray="4,3" opacity="0.8" />
      )}

      {actualPts.length > 1 && (
        <path d={actualLine + ` L${actualPts[actualPts.length - 1].x},${pad.t + ih} L${actualPts[0].x},${pad.t + ih} Z`}
          fill="url(#trendGrad)" />
      )}
      <path d={actualLine} fill="none" stroke="#3b82f6" strokeWidth="2" />

      {anomalySegments.map((seg, si) => {
        const segPts = [];
        for (let i = seg.startIdx; i <= seg.endIdx; i++) {
          if (actualPts[i]) segPts.push(actualPts[i]);
        }
        if (segPts.length < 1) return null;
        const segPath = segPts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
        const strokeColor = seg.type === 'high' ? '#f97316' : '#a855f7';
        return (
          <g key={`anomaly-${si}`}>
            <path d={segPath} fill="none" stroke={strokeColor} strokeWidth="3.5" strokeLinecap="round" />
            {segPts.filter((_, i) => i % Math.max(1, Math.floor(segPts.length / 6)) === 0).map((p, i) => (
              <circle key={i} cx={p.x} cy={p.y} r="4" fill={strokeColor} stroke="#fff" strokeWidth="1" />
            ))}
          </g>
        );
      })}

      {predLine && (
        <path d={predLine} fill="none" stroke="#a855f7" strokeWidth="2" strokeDasharray="8,4" />
      )}

      {actualPts.filter((_, i) => i % Math.max(1, Math.floor(actualPts.length / 30)) === 0).map((p, i) => {
        const baseline = baselineData[p.idx];
        let isAnomaly = false;
        if (baseline) {
          const lower = baseline.lower_bound || baseline.baseline_lower || 0;
          const upper = baseline.upper_bound || baseline.baseline_upper || 100;
          isAnomaly = p.val > upper || p.val < lower;
        }
        if (isAnomaly) return null;
        return <circle key={i} cx={p.x} cy={p.y} r="2.5" fill="#3b82f6" />;
      })}

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

      <g transform={`translate(${pad.l + 10}, ${pad.t + 8})`}>
        <line x1="0" y1="0" x2="20" y2="0" stroke="#3b82f6" strokeWidth="2" />
        <text x="24" y="4" fill="#94a3b8" fontSize="10">实际水位</text>
        {baselineBandPath && (
          <>
            <rect x="80" y="-6" width="20" height="12" fill="url(#baselineGrad)" stroke="#06b6d4" strokeWidth="0.5" />
            <text x="104" y="4" fill="#94a3b8" fontSize="10">基线范围</text>
            <line x1="176" y1="0" x2="196" y2="0" stroke="#f97316" strokeWidth="3" />
            <text x="200" y="4" fill="#94a3b8" fontSize="10">异常偏离</text>
          </>
        )}
        <line x1={baselineBandPath ? 266 : 176} y1="0" x2={baselineBandPath ? 286 : 196} y2="0" stroke="#a855f7" strokeWidth="2" strokeDasharray="8,4" />
        <text x={baselineBandPath ? 290 : 200} y="4" fill="#94a3b8" fontSize="10">预测趋势</text>
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
  const [deviationThresholdPct, setDeviationThresholdPct] = useState(existingConfig?.deviation_threshold_pct ?? 30);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        max_connections: maxConnections ? Number(maxConnections) : null,
        max_latency_ms: Number(maxLatencyMs),
        max_throughput_rps: maxThroughputRps ? Number(maxThroughputRps) : null,
        deviation_threshold_pct: deviationThresholdPct ? Number(deviationThresholdPct) : null,
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
        <div className="form-row">
          <label>偏离告警阈值 (%)</label>
          <input type="number" step="1" min="5" max="200" value={deviationThresholdPct}
            onChange={e => setDeviationThresholdPct(e.target.value)}
            placeholder="默认 30%" />
          <small style={{ color: '#64748b', fontSize: '11px' }}>
            当前水位相对基线偏离超过此百分比时触发告警（双向检测：高于和低于都检测）
          </small>
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

function DeviationAnalysis({ analysis, onResolveAlert }) {
  if (!analysis) return null;
  const {
    effective_threshold_pct,
    current_deviation_pct,
    current_deviation_direction,
    is_current_anomaly,
    current_baseline_mean,
    current_utilization,
    events_24h,
    anomaly_count_24h,
    high_anomaly_count_24h,
    low_anomaly_count_24h,
    active_deviation_alerts,
  } = analysis;

  const dirLabel = current_deviation_direction === 'high' ? '高于基线' : current_deviation_direction === 'low' ? '低于基线' : '正常范围';
  const dirColor = current_deviation_direction === 'high' ? '#f97316' : current_deviation_direction === 'low' ? '#a855f7' : '#22c55e';

  return (
    <div className="deviation-analysis">
      <div className="deviation-metrics-grid">
        <div className="capacity-metric-card">
          <span className="metric-label">有效偏离阈值</span>
          <span className="metric-value">±{effective_threshold_pct}%</span>
        </div>
        <div className="capacity-metric-card">
          <span className="metric-label">当前偏离程度</span>
          <span className="metric-value" style={{ color: dirColor }}>
            {current_deviation_pct > 0 ? '+' : ''}{current_deviation_pct}%
          </span>
        </div>
        <div className="capacity-metric-card">
          <span className="metric-label">偏离方向</span>
          <span className="metric-value" style={{ color: dirColor }}>
            {is_current_anomaly ? '⚠️ ' : ''}{dirLabel}
          </span>
        </div>
        <div className="capacity-metric-card">
          <span className="metric-label">基线均值 / 当前值</span>
          <span className="metric-value">
            {current_baseline_mean.toFixed(1)}% / {current_utilization.toFixed(1)}%
          </span>
        </div>
      </div>

      <div className="deviation-summary-bar">
        <div className="deviation-count-total">
          近24小时异常偏离: <strong style={{ color: '#ef4444' }}>{anomaly_count_24h}</strong> 次
        </div>
        <div className="deviation-count-split">
          <span style={{ color: '#f97316' }}>↑ 高于 {high_anomaly_count_24h}</span>
          <span style={{ color: '#a855f7' }}>↓ 低于 {low_anomaly_count_24h}</span>
        </div>
      </div>

      {events_24h && events_24h.length > 0 && (
        <div className="deviation-events-list">
          <h5>近24小时偏离事件</h5>
          <div className="events-scroll">
            {events_24h.map((ev, i) => {
              const color = ev.deviation_direction === 'high' ? '#f97316' : '#a855f7';
              const arrow = ev.deviation_direction === 'high' ? '↑' : '↓';
              return (
                <div key={i} className="deviation-event-row">
                  <span className="event-time">{new Date(ev.hour).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}</span>
                  <span className="event-direction" style={{ color }}>{arrow} {ev.deviation_direction === 'high' ? '偏高' : '偏低'}</span>
                  <span className="event-values">
                    {ev.current_utilization.toFixed(1)}% vs 基线 {ev.baseline_mean.toFixed(1)}%
                  </span>
                  <span className="event-deviation" style={{ color }}>
                    {ev.deviation_pct > 0 ? '+' : ''}{ev.deviation_pct}%
                  </span>
                  {ev.is_anomaly && <span className="event-anomaly-tag">异常</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {active_deviation_alerts && active_deviation_alerts.length > 0 && (
        <div className="deviation-alerts-list">
          <h5>活跃偏离告警</h5>
          {active_deviation_alerts.map(alert => {
            const color = alert.deviation_direction === 'high' ? '#f97316' : '#a855f7';
            const arrow = alert.deviation_direction === 'high' ? '↑' : '↓';
            return (
              <div key={alert.id} className="capacity-alert-card deviation-alert-card">
                <div className="alert-header">
                  <span className="alert-target" style={{ color }}>
                    {arrow} 偏离告警 · {alert.deviation_direction === 'high' ? '高于基线' : '低于基线'}
                  </span>
                  <span className="alert-level" style={{ color }}>
                    偏离 {alert.deviation_pct > 0 ? '+' : ''}{alert.deviation_pct}%
                  </span>
                </div>
                <div className="alert-body">
                  <div>时段: {new Date(alert.hour).toLocaleString('zh-CN')}</div>
                  <div>当前水位: {alert.current_utilization}% / 基线均值: {alert.baseline_mean}% (阈值: ±{alert.threshold_pct}%)</div>
                </div>
                <button className="btn-sm alert-resolve-btn" onClick={() => onResolveAlert?.(alert.id)}>
                  标记已处理
                </button>
              </div>
            );
          })}
        </div>
      )}
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

  const resolveDeviationAlert = async (alertId) => {
    await fetch(`${API_BASE}/api/capacity/deviation-alerts/${alertId}/resolve`, { method: 'POST' });
    loadDetail();
  };

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
        {detail.deviation_analysis?.is_current_anomaly && (
          <div className="capacity-metric-card anomaly-card" style={{
            borderColor: detail.deviation_analysis.current_deviation_direction === 'high' ? '#f97316' : '#a855f7',
          }}>
            <span className="metric-label">
              ⚠️ 异常偏离 {detail.deviation_analysis.current_deviation_direction === 'high' ? '↑' : '↓'}
            </span>
            <span className="metric-value" style={{
              color: detail.deviation_analysis.current_deviation_direction === 'high' ? '#f97316' : '#a855f7'
            }}>
              {detail.deviation_analysis.current_deviation_pct > 0 ? '+' : ''}{detail.deviation_analysis.current_deviation_pct}%
            </span>
          </div>
        )}
      </div>

      <div className="capacity-section">
        <div className="capacity-section-header">
          <h4>📊 7天水位趋势与基线对比</h4>
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
          baselineBand={detail.baseline_band}
        />
      </div>

      {detail.deviation_analysis && (
        <div className="capacity-section">
          <h4>📐 基线偏离分析</h4>
          <DeviationAnalysis
            analysis={detail.deviation_analysis}
            onResolveAlert={resolveDeviationAlert}
          />
        </div>
      )}

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
            <div className="config-item">
              <span>偏离告警阈值</span>
              <strong>
                {detail.config.deviation_threshold_pct != null
                  ? `±${detail.config.deviation_threshold_pct}%`
                  : '未设置 (继承默认)'}
              </strong>
            </div>
            {detail.deviation_analysis?.effective_threshold_pct != null && (
              <div className="config-item" style={{ background: '#1e293b', borderRadius: '6px', padding: '6px 10px' }}>
                <span style={{ color: '#06b6d4' }}>实际生效阈值</span>
                <strong style={{ color: '#06b6d4' }}>±{detail.deviation_analysis.effective_threshold_pct}%</strong>
              </div>
            )}
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
  const [deviationAlerts, setDeviationAlerts] = useState([]);
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

  const loadDeviationAlerts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/capacity/deviation-alerts?active_only=true`);
      if (res.ok) {
        const data = await res.json();
        setDeviationAlerts(data);
      }
    } catch (e) {
      console.error('Failed to load deviation alerts:', e);
    }
  }, []);

  useEffect(() => {
    loadOverview();
    loadAlerts();
    loadDeviationAlerts();
    const interval = setInterval(() => {
      loadOverview();
      loadAlerts();
      loadDeviationAlerts();
    }, 30000);
    return () => clearInterval(interval);
  }, [loadOverview, loadAlerts, loadDeviationAlerts]);

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

  const totalActiveAnomalies = overview.targets.reduce((sum, t) => sum + (t.deviation_anomaly_count_24h || 0), 0);

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
          {totalActiveAnomalies > 0 && (
            <div className="summary-stat" style={{ borderColor: '#f97316' }}>
              <span className="stat-value" style={{ color: '#f97316' }}>{totalActiveAnomalies}</span>
              <span className="stat-label">偏离异常</span>
            </div>
          )}
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

      {deviationAlerts.length > 0 && (
        <div className="capacity-alerts-banner deviation-banner">
          <h4>⚠️ 基线偏离告警 ({deviationAlerts.length})</h4>
          <div className="alerts-scroll">
            {deviationAlerts.map(alert => {
              const color = alert.deviation_direction === 'high' ? '#f97316' : '#a855f7';
              return (
                <div key={alert.id} className="capacity-alert-banner-item" onClick={() => setSelectedTarget(alert.target_id)}
                  style={{ borderLeftColor: color }}>
                  <span className="alert-status-dot" style={{ background: color }}></span>
                  <span className="alert-target-name">{alert.target_name}</span>
                  <span style={{ color }}>
                    {alert.deviation_direction === 'high' ? '↑ 高于基线' : '↓ 低于基线'} {alert.deviation_pct > 0 ? '+' : ''}{alert.deviation_pct}%
                  </span>
                  <span className="alert-water-level">水位 {alert.current_utilization}% vs 基线 {alert.baseline_mean}%</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="capacity-overview-grid">
        {sortedTargets.map(target => (
          <div
            key={target.target_id}
            className={`capacity-target-card ${target.water_level_status} ${target.has_deviation_anomaly_24h ? 'has-anomaly' : ''}`}
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
                {(target.current_deviation_pct != null) && (
                  <div className={`card-deviation ${target.current_deviation_pct > 0 ? 'high' : 'low'}`}>
                    <span>
                      {target.current_deviation_direction === 'high' ? '↑' : '↓'}
                      偏离基线 {target.current_deviation_pct > 0 ? '+' : ''}{target.current_deviation_pct}%
                    </span>
                    {target.is_current_anomaly && <span className="anomaly-flag">异常</span>}
                  </div>
                )}
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
