function StatsBar({ healthy, partial, degraded, down }) {
  return (
    <div className="stats-bar">
      <div className="stat-card">
        <div className="stat-icon healthy">
          ✓
        </div>
        <div className="stat-info">
          <div className="stat-number">{healthy}</div>
          <div className="stat-label">健康</div>
        </div>
      </div>
      {partial > 0 && (
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(139, 92, 246, 0.15)', color: '#8b5cf6' }}>
            ◐
          </div>
          <div className="stat-info">
            <div className="stat-number">{partial}</div>
            <div className="stat-label">局部异常</div>
          </div>
        </div>
      )}
      <div className="stat-card">
        <div className="stat-icon degraded">
          !
        </div>
        <div className="stat-info">
          <div className="stat-number">{degraded}</div>
          <div className="stat-label">降级</div>
        </div>
      </div>
      <div className="stat-card">
        <div className="stat-icon down">
          ✕
        </div>
        <div className="stat-info">
          <div className="stat-number">{down}</div>
          <div className="stat-label">故障</div>
        </div>
      </div>
    </div>
  );
}

export default StatsBar;
