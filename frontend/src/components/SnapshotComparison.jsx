import { useState, useEffect, useMemo } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function SnapshotComparison({ snapshotA, snapshotB, onClose }) {
  const [comparisonData, setComparisonData] = useState(null);
  const [selectedTarget, setSelectedTarget] = useState(null);
  const [filterDegraded, setFilterDegraded] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadComparison();
  }, [snapshotA.id, snapshotB.id]);

  const loadComparison = async () => {
    try {
      setLoading(true);
      const res = await fetch(
        `${API_BASE}/api/snapshots/compare/${snapshotA.id}/${snapshotB.id}`
      );
      if (res.ok) {
        const data = await res.json();
        setComparisonData(data);
        if (data.common_targets && data.common_targets.length > 0) {
          setSelectedTarget(data.common_targets[0]);
        }
      }
    } catch (e) {
      console.error('Failed to load comparison:', e);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (isoString) => {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatDiff = (value, isBetterWhenPositive = true) => {
    if (value === null || value === undefined) return '—';
    const sign = value > 0 ? '+' : '';
    const formatted = `${sign}${value.toFixed(1)}`;
    let className = 'diff-neutral';
    if (value > 0) {
      className = isBetterWhenPositive ? 'diff-better' : 'diff-worse';
    } else if (value < 0) {
      className = isBetterWhenPositive ? 'diff-worse' : 'diff-better';
    }
    return <span className={className}>{formatted}</span>;
  };

  const filteredComparisons = useMemo(() => {
    if (!comparisonData?.comparisons) return [];
    let result = comparisonData.comparisons;
    if (filterDegraded) {
      result = result.filter(c => c.degraded);
    }
    return result;
  }, [comparisonData, filterDegraded]);

  const selectedComparison = useMemo(() => {
    if (!comparisonData?.comparisons || !selectedTarget) return null;
    return comparisonData.comparisons.find(c => c.target_name === selectedTarget);
  }, [comparisonData, selectedTarget]);

  const summaryStats = useMemo(() => {
    if (!comparisonData?.comparisons) return null;
    const comparisons = comparisonData.comparisons;
    const degraded = comparisons.filter(c => c.degraded).length;
    const improved = comparisons.filter(c =>
      c.diff.availability > 5 || c.diff.p95 < -100
    ).length;
    const unchanged = comparisons.length - degraded - improved;

    return {
      total: comparisons.length,
      degraded,
      improved,
      unchanged
    };
  }, [comparisonData]);

  const LatencyComparisonChart = ({ resultsA, resultsB }) => {
    const width = 500;
    const height = 180;
    const padding = { top: 20, right: 20, bottom: 30, left: 50 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    const allResults = [...(resultsA || []), ...(resultsB || [])];
    const validResults = allResults.filter(r => r.success && r.latency_ms != null);

    if (validResults.length === 0) {
      return (
        <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
          无有效数据
        </div>
      );
    }

    const maxLat = Math.max(...validResults.map(r => r.latency_ms)) * 1.1;
    const minLat = Math.min(...validResults.map(r => r.latency_ms)) * 0.9;
    const range = maxLat - minLat || 1;

    const createPath = (results) => {
      const valid = results.filter(r => r.success && r.latency_ms != null);
      if (valid.length === 0) return '';

      const n = valid.length;
      const pts = valid.map((r, i) => {
        const x = padding.left + (i / (n - 1 || 1)) * chartWidth;
        const y = padding.top + chartHeight - ((r.latency_ms - minLat) / range) * chartHeight;
        return { x, y };
      });

      let path = `M ${pts[0].x} ${pts[0].y}`;
      for (let i = 1; i < pts.length; i++) {
        path += ` L ${pts[i].x} ${pts[i].y}`;
      }
      return path;
    };

    const pathA = createPath(resultsA);
    const pathB = createPath(resultsB);

    const yTicks = [];
    for (let i = 0; i <= 4; i++) {
      const value = minLat + (range * i) / 4;
      const y = padding.top + chartHeight - (i / 4) * chartHeight;
      yTicks.push({ value: value.toFixed(0), y });
    }

    return (
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        {yTicks.map((tick, i) => (
          <g key={i}>
            <line
              x1={padding.left}
              y1={tick.y}
              x2={width - padding.right}
              y2={tick.y}
              stroke="#334155"
              strokeWidth="1"
              strokeDasharray="3,3"
            />
            <text
              x={padding.left - 8}
              y={tick.y + 4}
              textAnchor="end"
              fill="#64748b"
              fontSize="11"
            >
              {tick.value}ms
            </text>
          </g>
        ))}

        {pathA && (
          <path
            d={pathA}
            fill="none"
            stroke="#3b82f6"
            strokeWidth="2"
            strokeLinecap="round"
            opacity="0.8"
          />
        )}

        {pathB && (
          <path
            d={pathB}
            fill="none"
            stroke="#f59e0b"
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray="5,5"
            opacity="0.8"
          />
        )}

        <line
          x1={padding.left}
          y1={padding.top + chartHeight}
          x2={width - padding.right}
          y2={padding.top + chartHeight}
          stroke="#475569"
          strokeWidth="1"
        />

        <text x={padding.left + 10} y={30} fill="#3b82f6" fontSize="11">
          ── A: {snapshotA.name}
        </text>
        <text x={padding.left + 10} y={45} fill="#f59e0b" fontSize="11">
          ─ ─ B: {snapshotB.name}
        </text>
      </svg>
    );
  };

  return (
    <div className="modal-overlay comparison-overlay" onClick={onClose}>
      <div className="modal-content comparison-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2>📊 快照对比分析</h2>
            <div className="comparison-header-info">
              <span className="snapshot-label a">A: {snapshotA.name}</span>
              <span className="vs">VS</span>
              <span className="snapshot-label b">B: {snapshotB.name}</span>
            </div>
          </div>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        {loading ? (
          <div className="loading-state">加载对比数据...</div>
        ) : !comparisonData ? (
          <div className="empty-state">无法加载对比数据</div>
        ) : (
          <>
            <div className="comparison-summary">
              <div className="summary-card">
                <div className="summary-value">{summaryStats?.total || 0}</div>
                <div className="summary-label">共同目标数</div>
              </div>
              <div className="summary-card degraded">
                <div className="summary-value">{summaryStats?.degraded || 0}</div>
                <div className="summary-label">性能变差</div>
              </div>
              <div className="summary-card improved">
                <div className="summary-value">{summaryStats?.improved || 0}</div>
                <div className="summary-label">性能提升</div>
              </div>
              <div className="summary-card">
                <div className="summary-value">{summaryStats?.unchanged || 0}</div>
                <div className="summary-label">基本一致</div>
              </div>
            </div>

            <div className="comparison-snapshot-info">
              <div className="snapshot-info-card a">
                <h4>A: {snapshotA.name}</h4>
                <p>{snapshotA.description || '无备注'}</p>
                <p className="time-range">
                  {formatTime(snapshotA.start_time)} ~ {formatTime(snapshotA.end_time)}
                </p>
              </div>
              <div className="arrow">→</div>
              <div className="snapshot-info-card b">
                <h4>B: {snapshotB.name}</h4>
                <p>{snapshotB.description || '无备注'}</p>
                <p className="time-range">
                  {formatTime(snapshotB.start_time)} ~ {formatTime(snapshotB.end_time)}
                </p>
              </div>
            </div>

            <div className="comparison-content">
              <div className="targets-comparison-panel">
                <div className="panel-header">
                  <h3>目标对比列表</h3>
                  <label className="filter-toggle">
                    <input
                      type="checkbox"
                      checked={filterDegraded}
                      onChange={(e) => setFilterDegraded(e.target.checked)}
                    />
                    只看变差的目标
                  </label>
                </div>
                <div className="comparison-table-container">
                  <table className="comparison-table">
                    <thead>
                      <tr>
                        <th>目标名称</th>
                        <th className="text-center">状态变化</th>
                        <th className="text-right">A 可用率</th>
                        <th className="text-right">B 可用率</th>
                        <th className="text-right">可用率差</th>
                        <th className="text-right">A P95</th>
                        <th className="text-right">B P95</th>
                        <th className="text-right">P95 差</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredComparisons.map((comp) => (
                        <tr
                          key={comp.target_name}
                          className={`${selectedTarget === comp.target_name ? 'selected' : ''} ${comp.degraded ? 'degraded-row' : ''}`}
                          onClick={() => setSelectedTarget(comp.target_name)}
                        >
                          <td>
                            {comp.degraded && <span className="degrade-indicator">⚠️</span>}
                            {comp.target_name}
                          </td>
                          <td className="text-center">
                            {comp.degraded ? (
                              <span className="status-badge worse">变差</span>
                            ) : comp.diff.availability > 0 ? (
                              <span className="status-badge better">提升</span>
                            ) : (
                              <span className="status-badge neutral">一致</span>
                            )}
                          </td>
                          <td className="text-right">
                            {comp.snapshot_a.stats.availability?.toFixed(2)}%
                          </td>
                          <td className="text-right">
                            {comp.snapshot_b.stats.availability?.toFixed(2)}%
                          </td>
                          <td className="text-right">
                            {formatDiff(comp.diff.availability, true)}
                          </td>
                          <td className="text-right">
                            {comp.snapshot_a.stats.p95?.toFixed(0) || '-'} ms
                          </td>
                          <td className="text-right">
                            {comp.snapshot_b.stats.p95?.toFixed(0) || '-'} ms
                          </td>
                          <td className="text-right">
                            {formatDiff(comp.diff.p95, false)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="detail-comparison-panel">
                {selectedComparison ? (
                  <>
                    <h3>{selectedComparison.target_name} - 详细对比</h3>

                    <div className="comparison-metrics-grid">
                      <div className="metric-card a">
                        <div className="metric-header">
                          <span className="metric-source">A</span>
                          <span className="metric-name">可用率</span>
                        </div>
                        <div className="metric-value">
                          {selectedComparison.snapshot_a.stats.availability?.toFixed(2)}%
                        </div>
                      </div>
                      <div className="metric-card diff-card">
                        <div className="metric-header">
                          <span className="metric-name">差值</span>
                        </div>
                        <div className="metric-value">
                          {formatDiff(selectedComparison.diff.availability, true)}
                        </div>
                      </div>
                      <div className="metric-card b">
                        <div className="metric-header">
                          <span className="metric-source">B</span>
                          <span className="metric-name">可用率</span>
                        </div>
                        <div className="metric-value">
                          {selectedComparison.snapshot_b.stats.availability?.toFixed(2)}%
                        </div>
                      </div>

                      <div className="metric-card a">
                        <div className="metric-header">
                          <span className="metric-source">A</span>
                          <span className="metric-name">P50 延迟</span>
                        </div>
                        <div className="metric-value">
                          {selectedComparison.snapshot_a.stats.p50?.toFixed(0) || '-'} ms
                        </div>
                      </div>
                      <div className="metric-card diff-card">
                        <div className="metric-header">
                          <span className="metric-name">差值</span>
                        </div>
                        <div className="metric-value">
                          {formatDiff(selectedComparison.diff.p50, false)}
                        </div>
                      </div>
                      <div className="metric-card b">
                        <div className="metric-header">
                          <span className="metric-source">B</span>
                          <span className="metric-name">P50 延迟</span>
                        </div>
                        <div className="metric-value">
                          {selectedComparison.snapshot_b.stats.p50?.toFixed(0) || '-'} ms
                        </div>
                      </div>

                      <div className="metric-card a">
                        <div className="metric-header">
                          <span className="metric-source">A</span>
                          <span className="metric-name">P95 延迟</span>
                        </div>
                        <div className="metric-value">
                          {selectedComparison.snapshot_a.stats.p95?.toFixed(0) || '-'} ms
                        </div>
                      </div>
                      <div className="metric-card diff-card">
                        <div className="metric-header">
                          <span className="metric-name">差值</span>
                        </div>
                        <div className="metric-value">
                          {formatDiff(selectedComparison.diff.p95, false)}
                        </div>
                      </div>
                      <div className="metric-card b">
                        <div className="metric-header">
                          <span className="metric-source">B</span>
                          <span className="metric-name">P95 延迟</span>
                        </div>
                        <div className="metric-value">
                          {selectedComparison.snapshot_b.stats.p95?.toFixed(0) || '-'} ms
                        </div>
                      </div>

                      <div className="metric-card a">
                        <div className="metric-header">
                          <span className="metric-source">A</span>
                          <span className="metric-name">P99 延迟</span>
                        </div>
                        <div className="metric-value">
                          {selectedComparison.snapshot_a.stats.p99?.toFixed(0) || '-'} ms
                        </div>
                      </div>
                      <div className="metric-card diff-card">
                        <div className="metric-header">
                          <span className="metric-name">差值</span>
                        </div>
                        <div className="metric-value">
                          {formatDiff(selectedComparison.diff.p99, false)}
                        </div>
                      </div>
                      <div className="metric-card b">
                        <div className="metric-header">
                          <span className="metric-source">B</span>
                          <span className="metric-name">P99 延迟</span>
                        </div>
                        <div className="metric-value">
                          {selectedComparison.snapshot_b.stats.p99?.toFixed(0) || '-'} ms
                        </div>
                      </div>
                    </div>

                    <div className="chart-container">
                      <h4>延迟曲线对比</h4>
                      <LatencyComparisonChart
                        resultsA={selectedComparison.snapshot_a.results}
                        resultsB={selectedComparison.snapshot_b.results}
                      />
                      <div className="chart-legend">
                        <span className="legend-item">
                          <span className="legend-dot" style={{ backgroundColor: '#3b82f6' }}></span>
                          A: {snapshotA.name}
                        </span>
                        <span className="legend-item">
                          <span className="legend-dot" style={{ backgroundColor: '#f59e0b' }}></span>
                          B: {snapshotB.name}
                        </span>
                      </div>
                    </div>

                    <div className="data-points-info">
                      <div>
                        <strong>A 数据点:</strong> {selectedComparison.snapshot_a.data_points} 个
                      </div>
                      <div>
                        <strong>B 数据点:</strong> {selectedComparison.snapshot_b.data_points} 个
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="empty-detail">
                    <div className="empty-icon">📊</div>
                    <div className="empty-text">选择左侧目标查看详细对比</div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default SnapshotComparison;
