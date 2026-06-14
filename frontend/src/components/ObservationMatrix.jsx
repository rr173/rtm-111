import { useState, useEffect, useMemo } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

export default function ObservationMatrix({ matrixData, observers, targets }) {
  const [regionFilter, setRegionFilter] = useState('all');
  const [localMatrix, setLocalMatrix] = useState(matrixData);

  useEffect(() => {
    if (matrixData) {
      setLocalMatrix(matrixData);
    }
  }, [matrixData]);

  useEffect(() => {
    const fetchMatrix = async () => {
      try {
        const url = regionFilter === 'all'
          ? `${API_BASE}/api/observation-matrix`
          : `${API_BASE}/api/observation-matrix?region=${encodeURIComponent(regionFilter)}`;
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          setLocalMatrix(data);
        }
      } catch (e) {
        console.error('Failed to fetch observation matrix:', e);
      }
    };
    fetchMatrix();
    const interval = setInterval(fetchMatrix, 10000);
    return () => clearInterval(interval);
  }, [regionFilter]);

  const regions = useMemo(() => {
    if (localMatrix && localMatrix.regions) {
      return localMatrix.regions;
    }
    const regionSet = new Set(observers.map(o => o.region));
    return Array.from(regionSet).sort();
  }, [localMatrix, observers]);

  const displayObservers = useMemo(() => {
    if (localMatrix && localMatrix.observers) {
      return localMatrix.observers;
    }
    if (regionFilter === 'all') {
      return observers;
    }
    return observers.filter(o => o.region === regionFilter);
  }, [localMatrix, observers, regionFilter]);

  const displayTargets = useMemo(() => {
    if (localMatrix && localMatrix.targets) {
      return localMatrix.targets;
    }
    return targets;
  }, [localMatrix, targets]);

  const cellMap = useMemo(() => {
    const map = new Map();
    if (localMatrix && localMatrix.cells) {
      for (const cell of localMatrix.cells) {
        map.set(`${cell.target_id}-${cell.observer_id}`, cell);
      }
    }
    return map;
  }, [localMatrix]);

  const summaryStats = useMemo(() => {
    let healthy = 0, degraded = 0, down = 0, partial = 0;
    for (const t of displayTargets) {
      if (t.status === 'healthy') healthy++;
      else if (t.status === 'degraded') degraded++;
      else if (t.status === 'down') down++;
      else if (t.status === 'partial') partial++;
    }
    return {
      total: displayTargets.length,
      healthy,
      degraded,
      down,
      partial,
      observers: displayObservers.length,
      onlineObservers: displayObservers.filter(o => o.status === 'online').length,
      regions: regions.length
    };
  }, [displayTargets, displayObservers, regions]);

  const formatLatency = (latency) => {
    if (latency == null) return '-';
    if (latency >= 1000) return `${(latency / 1000).toFixed(1)}s`;
    return `${latency.toFixed(0)}ms`;
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const getCellStatus = (cell) => {
    if (!cell) {
      return { statusClass: 'status-unknown', statusText: '未知', latency: null, time: null };
    }
    if (cell.observer_status === 'offline') {
      return { statusClass: 'status-offline', statusText: '离线', latency: null, time: null };
    }
    const s = cell.latest_status;
    if (s === 'success' || s === 'healthy') {
      return { statusClass: 'status-healthy', statusText: '正常', latency: cell.latest_latency, time: cell.latest_timestamp };
    }
    if (s === 'degraded') {
      return { statusClass: 'status-degraded', statusText: '降级', latency: cell.latest_latency, time: cell.latest_timestamp };
    }
    if (s === 'failed' || s === 'down') {
      return { statusClass: 'status-down', statusText: '故障', latency: cell.latest_latency, time: cell.latest_timestamp, error: cell.error_message };
    }
    return { statusClass: 'status-unknown', statusText: '未知', latency: null, time: null };
  };

  const getTargetDisplayStatus = (status) => {
    switch (status) {
      case 'healthy': return 'healthy';
      case 'degraded': return 'degraded';
      case 'down': return 'down';
      case 'partial': return 'partial';
      case 'paused': return 'paused';
      default: return 'healthy';
    }
  };

  const getTargetStatusLabel = (status) => {
    switch (status) {
      case 'healthy': return '健康';
      case 'degraded': return '降级';
      case 'down': return '故障';
      case 'partial': return '局部异常';
      case 'paused': return '暂停';
      default: return status;
    }
  };

  return (
    <div>
      <div className="matrix-summary">
        <div className="matrix-stat-card">
          <div className="matrix-stat-label">观测点总数</div>
          <div className="matrix-stat-value">
            {summaryStats.observers}
            <span style={{ fontSize: '13px', color: '#22c55e', marginLeft: '8px' }}>
              在线 {summaryStats.onlineObservers}
            </span>
          </div>
        </div>
        <div className="matrix-stat-card">
          <div className="matrix-stat-label">探测目标</div>
          <div className="matrix-stat-value">{summaryStats.total}</div>
        </div>
        <div className="matrix-stat-card">
          <div className="matrix-stat-label">健康 / 降级 / 故障</div>
          <div className="matrix-stat-value">
            <span style={{ color: '#22c55e' }}>{summaryStats.healthy}</span>
            <span style={{ color: '#64748b', margin: '0 6px' }}>/</span>
            <span style={{ color: '#f59e0b' }}>{summaryStats.degraded}</span>
            <span style={{ color: '#64748b', margin: '0 6px' }}>/</span>
            <span style={{ color: '#ef4444' }}>{summaryStats.down}</span>
          </div>
        </div>
        <div className="matrix-stat-card">
          <div className="matrix-stat-label">覆盖地区</div>
          <div className="matrix-stat-value">{summaryStats.regions}</div>
        </div>
      </div>

      <div className="matrix-container">
        <div className="matrix-header">
          <h2>🌐 多观测点协同探测矩阵</h2>
          <div className="matrix-filters">
            <label className="matrix-filter-label">按地区筛选：</label>
            <select
              className="region-filter-select"
              value={regionFilter}
              onChange={(e) => setRegionFilter(e.target.value)}
            >
              <option value="all">全部地区</option>
              {regions.map(r => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="matrix-table-wrap">
          <table className="matrix-table">
            <thead>
              <tr>
                <th className="matrix-corner">目标 \ 观测点</th>
                {displayObservers.map(observer => (
                  <th key={observer.id} className={`observer-header observer-${observer.status}`}>
                    <div>
                      <span className="obs-status-dot"></span>
                      {observer.name}
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px', fontWeight: 'normal' }}>
                      {observer.region}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayTargets.map(target => (
                <tr key={target.id}>
                  <td className="target-cell">
                    <div className="target-name-cell">
                      <span className={`target-status-mini ${getTargetDisplayStatus(target.status)}`}></span>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span>{target.name}</span>
                        <span style={{ fontSize: '11px', color: '#64748b', fontWeight: 'normal' }}>
                          {getTargetStatusLabel(target.status)}
                        </span>
                      </div>
                    </div>
                  </td>
                  {displayObservers.map(observer => {
                    const cell = cellMap.get(`${target.id}-${observer.id}`);
                    const { statusClass, statusText, latency, time, error } = getCellStatus(cell);
                    return (
                      <td
                        key={`${target.id}-${observer.id}`}
                        className={`matrix-cell ${statusClass}`}
                        title={error ? `错误: ${error}` : `${statusText} | 延迟: ${formatLatency(latency)} | 时间: ${formatTime(time)}`}
                      >
                        <div className="matrix-cell-status">{statusText}</div>
                        {latency != null && (
                          <div className="matrix-cell-latency">{formatLatency(latency)}</div>
                        )}
                        {time && (
                          <div className="matrix-cell-time">{formatTime(time)}</div>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="matrix-legend">
          <div className="legend-item">
            <span className="legend-color healthy"></span>
            正常
          </div>
          <div className="legend-item">
            <span className="legend-color degraded"></span>
            降级
          </div>
          <div className="legend-item">
            <span className="legend-color down"></span>
            故障
          </div>
          <div className="legend-item">
            <span className="legend-color partial"></span>
            局部异常
          </div>
          <div className="legend-item">
            <span className="legend-color offline"></span>
            观测点离线
          </div>
          <div className="legend-item">
            <span className="legend-color unknown"></span>
            未知状态
          </div>
        </div>
      </div>
    </div>
  );
}
