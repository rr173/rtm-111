function AlertPanel({ alerts = [], onAcknowledge }) {
  const formatTime = (isoString) => {
    if (!isoString) return '';
    const d = new Date(isoString);
    const now = new Date();
    const diff = now - d;

    if (diff < 60000) return '刚刚';
    if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
    return d.toLocaleDateString('zh-CN');
  };

  const getAlertLevel = (alert) => {
    if (alert.to_status === 'down') return 'down';
    if (alert.to_status === 'degraded') return 'degraded';
    return 'healthy';
  };

  const getAlertText = (alert) => {
    const toLabel = {
      healthy: '恢复正常',
      degraded: '降级',
      down: '故障'
    };
    return `${alert.target_name} - ${toLabel[alert.to_status] || alert.to_status}`;
  };

  return (
    <div className="alert-panel">
      <div className="alert-panel-header">
        <h2>🔔 实时告警流</h2>
        <span style={{ fontSize: '12px', color: '#64748b' }}>
          {alerts.length} 条
        </span>
      </div>
      <div className="alert-list">
        {alerts.length > 0 ? (
          alerts.map(alert => (
            <div
              key={alert.id}
              className={`alert-item ${alert.acknowledged ? 'acknowledged' : ''}`}
            >
              <div className="alert-title">
                <span className={`alert-level ${getAlertLevel(alert)}`}></span>
                <span>{getAlertText(alert)}</span>
              </div>
              <div className="alert-time">
                {formatTime(alert.timestamp)} · {alert.from_status.toUpperCase()} → {alert.to_status.toUpperCase()}
              </div>
              <div className="alert-action">
                <button onClick={() => onAcknowledge(alert.id, !alert.acknowledged)}>
                  {alert.acknowledged ? '取消确认' : '确认告警'}
                </button>
              </div>
            </div>
          ))
        ) : (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: '#64748b' }}>
            暂无告警
          </div>
        )}
      </div>
    </div>
  );
}

export default AlertPanel;
