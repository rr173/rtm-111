import { getSeverityLevel } from '../utils/alertNoiseReduction';

function NoiseReductionDashboard({ stats, hourlyStats, groups, suppressedAlerts }) {
  const formatNumber = (num) => {
    if (num >= 10000) return (num / 10000).toFixed(1) + '万';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
    return num.toString();
  };

  const maxBarValue = Math.max(
    ...hourlyStats.map(h => Math.max(h.raw_count, h.group_count, h.suppressed_count)),
    1
  );

  const reductionColor = (ratio) => {
    if (ratio >= 70) return '#22c55e';
    if (ratio >= 40) return '#3b82f6';
    if (ratio >= 20) return '#eab308';
    return '#ef4444';
  };

  return (
    <div className="nr-dashboard">
      <div className="nr-header">
        <div className="nr-header-title">
          <h2>📊 降噪效果仪表盘</h2>
          <p className="nr-subtitle">过去 24 小时告警降噪统计</p>
        </div>
      </div>

      <div className="nr-stats-grid">
        <div className="nr-stat-card nr-stat-raw">
          <div className="nr-stat-icon">📨</div>
          <div className="nr-stat-content">
            <div className="nr-stat-value">{formatNumber(stats.total_raw)}</div>
            <div className="nr-stat-label">原始告警数</div>
          </div>
        </div>

        <div className="nr-stat-card nr-stat-groups">
          <div className="nr-stat-icon">📦</div>
          <div className="nr-stat-content">
            <div className="nr-stat-value">{formatNumber(stats.total_groups)}</div>
            <div className="nr-stat-label">归并后告警组</div>
          </div>
        </div>

        <div className="nr-stat-card nr-stat-suppressed">
          <div className="nr-stat-icon">🚫</div>
          <div className="nr-stat-content">
            <div className="nr-stat-value">{formatNumber(stats.total_suppressed)}</div>
            <div className="nr-stat-label">抑制告警数</div>
          </div>
        </div>

        <div className="nr-stat-card nr-stat-reduction">
          <div className="nr-stat-icon">✨</div>
          <div className="nr-stat-content">
            <div 
              className="nr-stat-value" 
              style={{ color: reductionColor(stats.noise_reduction_ratio) }}
            >
              {stats.noise_reduction_ratio}%
            </div>
            <div className="nr-stat-label">综合降噪比</div>
          </div>
        </div>
      </div>

      <div className="nr-chart-card">
        <div className="nr-chart-header">
          <h3>📈 24小时告警趋势</h3>
          <div className="nr-chart-legend">
            <span className="legend-item">
              <span className="legend-dot legend-raw"></span>
              原始告警
            </span>
            <span className="legend-item">
              <span className="legend-dot legend-group"></span>
              归并后组
            </span>
            <span className="legend-item">
              <span className="legend-dot legend-suppressed"></span>
              抑制数
            </span>
          </div>
        </div>
        <div className="nr-chart-container">
          <div className="nr-chart-bars">
            {hourlyStats.map((hour, idx) => (
              <div key={idx} className="nr-chart-bar-group">
                <div className="nr-chart-bar-wrapper">
                  <div 
                    className="nr-chart-bar bar-raw" 
                    style={{ height: `${(hour.raw_count / maxBarValue) * 100}%` }}
                    title={`原始告警: ${hour.raw_count}`}
                  ></div>
                  <div 
                    className="nr-chart-bar bar-suppressed" 
                    style={{ height: `${(hour.suppressed_count / maxBarValue) * 100}%` }}
                    title={`抑制: ${hour.suppressed_count}`}
                  ></div>
                  <div 
                    className="nr-chart-bar bar-group" 
                    style={{ height: `${(hour.group_count / maxBarValue) * 100}%` }}
                    title={`归并组: ${hour.group_count}`}
                  ></div>
                </div>
                <div className="nr-chart-label">{hour.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="nr-bottom-grid">
        <div className="nr-section-card">
          <div className="nr-section-header">
            <h3>🔥 告警组严重度分布</h3>
          </div>
          <div className="nr-severity-dist">
            {['critical', 'high', 'medium', 'low', 'info'].map(level => {
              const levelInfo = getSeverityLevel(
                level === 'critical' ? 500 : 
                level === 'high' ? 300 : 
                level === 'medium' ? 150 : 
                level === 'low' ? 75 : 25
              );
              const count = groups.filter(g => {
                const gLevel = getSeverityLevel(g.severity_score).level;
                return gLevel === level;
              }).length;
              const pct = groups.length > 0 ? (count / groups.length) * 100 : 0;
              
              return (
                <div key={level} className="severity-row">
                  <div className="severity-row-left">
                    <span 
                      className="severity-indicator" 
                      style={{ backgroundColor: levelInfo.color }}
                    ></span>
                    <span className="severity-label">{levelInfo.label}</span>
                  </div>
                  <div className="severity-bar-wrapper">
                    <div 
                      className="severity-bar" 
                      style={{ 
                        width: `${pct}%`,
                        backgroundColor: levelInfo.color 
                      }}
                    ></div>
                  </div>
                  <div className="severity-count">{count}</div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="nr-section-card">
          <div className="nr-section-header">
            <h3>🔇 最近抑制告警</h3>
            <span className="nr-badge">{suppressedAlerts.length} 条</span>
          </div>
          <div className="nr-suppressed-list">
            {suppressedAlerts.length > 0 ? (
              suppressedAlerts.slice(0, 5).map(alert => (
                <div key={alert.id} className="suppressed-item">
                  <div className="suppressed-icon">🚫</div>
                  <div className="suppressed-content">
                    <div className="suppressed-name">{alert.target_name}</div>
                    <div className="suppressed-meta">
                      {alert.from_status} → {alert.to_status}
                      <span className="suppressed-rule">
                        · {alert.suppressed_by?.name || '未知规则'}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="nr-empty-state">暂无抑制告警</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default NoiseReductionDashboard;
