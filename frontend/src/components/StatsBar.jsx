function StatsBar({ healthy, degraded, down }) {
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
