import { useState, useEffect, useMemo } from 'react';
import MaintenanceWindowModal from './MaintenanceWindowModal';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

const STATUS_COLORS = {
  scheduled: '#3b82f6',
  active: '#f59e0b',
  completed: '#10b981',
  cancelled: '#6b7280',
  maintenance_timeout: '#ef4444',
};

const STATUS_LABELS = {
  scheduled: '已计划',
  active: '进行中',
  completed: '已完成',
  cancelled: '已取消',
};

function MaintenanceCalendar({ windows = [], targets = [], groups = [], onRefresh }) {
  const [viewMode, setViewMode] = useState('week');
  const [currentDate, setCurrentDate] = useState(new Date());
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedWindow, setSelectedWindow] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showExtendModal, setShowExtendModal] = useState(false);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [extendEndTime, setExtendEndTime] = useState('');
  const [extendReason, setExtendReason] = useState('');
  const [cancelReason, setCancelReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [selectedTargetId, setSelectedTargetId] = useState('');

  const filteredTargets = useMemo(() => {
    if (!selectedTargetId) return targets;
    return targets.filter(t => t.id === parseInt(selectedTargetId));
  }, [targets, selectedTargetId]);

  const filteredWindows = useMemo(() => {
    if (!selectedTargetId) return windows;
    return windows.filter(w => w.target_id === parseInt(selectedTargetId));
  }, [windows, selectedTargetId]);

  const getWeekRange = (date) => {
    const start = new Date(date);
    start.setDate(start.getDate() - start.getDay());
    start.setHours(0, 0, 0, 0);
    const end = new Date(start);
    end.setDate(end.getDate() + 6);
    end.setHours(23, 59, 59, 999);
    return { start, end };
  };

  const getMonthRange = (date) => {
    const start = new Date(date.getFullYear(), date.getMonth(), 1);
    start.setHours(0, 0, 0, 0);
    const end = new Date(date.getFullYear(), date.getMonth() + 1, 0);
    end.setHours(23, 59, 59, 999);
    return { start, end };
  };

  const { start: viewStart, end: viewEnd } = viewMode === 'week' 
    ? getWeekRange(currentDate) 
    : getMonthRange(currentDate);

  const days = useMemo(() => {
    const result = [];
    let current = new Date(viewStart);
    while (current <= viewEnd) {
      result.push(new Date(current));
      current.setDate(current.getDate() + 1);
    }
    return result;
  }, [viewStart, viewEnd]);

  const navigatePrev = () => {
    const newDate = new Date(currentDate);
    if (viewMode === 'week') {
      newDate.setDate(newDate.getDate() - 7);
    } else {
      newDate.setMonth(newDate.getMonth() - 1);
    }
    setCurrentDate(newDate);
  };

  const navigateNext = () => {
    const newDate = new Date(currentDate);
    if (viewMode === 'week') {
      newDate.setDate(newDate.getDate() + 7);
    } else {
      newDate.setMonth(newDate.getMonth() + 1);
    }
    setCurrentDate(newDate);
  };

  const navigateToday = () => {
    setCurrentDate(new Date());
  };

  const getWindowPosition = (window) => {
    const windowStart = new Date(window.start_time);
    const windowEnd = new Date(window.end_time);
    
    const visibleStart = windowStart < viewStart ? viewStart : windowStart;
    const visibleEnd = windowEnd > viewEnd ? viewEnd : windowEnd;
    
    const totalDuration = viewEnd.getTime() - viewStart.getTime();
    const startOffset = (visibleStart.getTime() - viewStart.getTime()) / totalDuration * 100;
    const width = (visibleEnd.getTime() - visibleStart.getTime()) / totalDuration * 100;
    
    return { left: `${startOffset}%`, width: `${width}%` };
  };

  const handleWindowClick = (window) => {
    setSelectedWindow(window);
    setShowDetailModal(true);
  };

  const handleExtend = async () => {
    if (!selectedWindow || !extendEndTime || !extendReason.trim()) return;
    
    setActionLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/maintenance-windows/${selectedWindow.id}/extend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          end_time: new Date(extendEndTime).toISOString(),
          extension_reason: extendReason,
        }),
      });
      
      if (response.ok) {
        setShowExtendModal(false);
        setShowDetailModal(false);
        onRefresh && onRefresh();
      } else {
        const error = await response.json();
        alert(error.detail || '延期失败');
      }
    } catch (err) {
      alert('网络错误，请重试');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!selectedWindow) return;
    
    setActionLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/maintenance-windows/${selectedWindow.id}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cancelled_reason: cancelReason }),
      });
      
      if (response.ok) {
        setShowCancelModal(false);
        setShowDetailModal(false);
        onRefresh && onRefresh();
      } else {
        const error = await response.json();
        alert(error.detail || '取消失败');
      }
    } catch (err) {
      alert('网络错误，请重试');
    } finally {
      setActionLoading(false);
    }
  };

  const formatDateTime = (dateStr) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatTime = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  };

  const isToday = (date) => {
    const today = new Date();
    return date.getDate() === today.getDate() &&
           date.getMonth() === today.getMonth() &&
           date.getFullYear() === today.getFullYear();
  };

  const getDayLabel = (date) => {
    const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
    return {
      weekday: weekdays[date.getDay()],
      day: date.getDate(),
      month: date.getMonth() + 1,
    };
  };

  const getHeaderTitle = () => {
    if (viewMode === 'week') {
      const start = days[0];
      const end = days[days.length - 1];
      return `${start.getFullYear()}年${start.getMonth() + 1}月${start.getDate()}日 - ${end.getMonth() + 1}月${end.getDate()}日`;
    } else {
      return `${currentDate.getFullYear()}年${currentDate.getMonth() + 1}月`;
    }
  };

  const formatDateTimeLocal = (date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  };

  const activeWindows = windows.filter(w => w.status === 'active').length;
  const scheduledWindows = windows.filter(w => w.status === 'scheduled').length;

  return (
    <div className="maintenance-calendar">
      <div className="calendar-header">
        <div className="calendar-title-section">
          <h2>📅 维护日历</h2>
          <div className="calendar-stats">
            <span className="stat-badge scheduled">
              <span className="stat-dot"></span>
              计划中 {scheduledWindows}
            </span>
            <span className="stat-badge active">
              <span className="stat-dot"></span>
              进行中 {activeWindows}
            </span>
          </div>
        </div>

        <div className="calendar-controls">
          <div className="view-toggle">
            <button 
              className={`view-btn ${viewMode === 'week' ? 'active' : ''}`}
              onClick={() => setViewMode('week')}
            >
              周视图
            </button>
            <button 
              className={`view-btn ${viewMode === 'month' ? 'active' : ''}`}
              onClick={() => setViewMode('month')}
            >
              月视图
            </button>
          </div>

          <div className="target-filter">
            <select
              value={selectedTargetId}
              onChange={(e) => setSelectedTargetId(e.target.value)}
            >
              <option value="">全部目标</option>
              {targets.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>

          <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
            + 新建维护窗口
          </button>
        </div>
      </div>

      <div className="calendar-nav">
        <button className="nav-btn" onClick={navigatePrev}>‹</button>
        <button className="nav-btn today-btn" onClick={navigateToday}>今天</button>
        <button className="nav-btn" onClick={navigateNext}>›</button>
        <span className="current-period">{getHeaderTitle()}</span>
      </div>

      <div className="calendar-grid">
        <div className="timeline-header">
          <div className="target-col-header">目标</div>
          <div className="time-col-header">
            {days.map((day, idx) => {
              const label = getDayLabel(day);
              return (
                <div 
                  key={idx} 
                  className={`day-header ${isToday(day) ? 'today' : ''}`}
                  style={{ width: `${100 / days.length}%` }}
                >
                  <div className="day-weekday">{label.weekday}</div>
                  <div className="day-date">{label.month}/{label.day}</div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="timeline-body">
          {filteredTargets.length === 0 ? (
            <div className="no-targets">
              <p>暂无目标数据</p>
            </div>
          ) : (
            filteredTargets.map(target => {
              const targetWindows = filteredWindows.filter(w => w.target_id === target.id);
              
              return (
                <div key={target.id} className="timeline-row">
                  <div className="target-cell">
                    <div className="target-indicator" style={{ backgroundColor: target.color }}></div>
                    <span className="target-name">{target.name}</span>
                    <span className={`target-status status-${target.status}`}>
                      {target.paused ? '⏸ 暂停' : (target.status === 'healthy' ? '✓ 正常' : 
                       target.status === 'degraded' ? '⚠ 降级' : 
                       target.status === 'down' ? '✗ 故障' : target.status)}
                    </span>
                  </div>
                  <div className="time-cell">
                    <div className="time-track">
                      {targetWindows.filter(w => !w.is_cancelled).map(window => {
                        const position = getWindowPosition(window);
                        const color = STATUS_COLORS[window.status] || STATUS_COLORS.scheduled;
                        
                        return (
                          <div
                            key={window.id}
                            className={`maintenance-bar status-${window.status}`}
                            style={{ 
                              left: position.left, 
                              width: position.width,
                              backgroundColor: color,
                            }}
                            onClick={() => handleWindowClick(window)}
                            title={`${window.title}\n${formatDateTime(window.start_time)} - ${formatDateTime(window.end_time)}`}
                          >
                            <span className="bar-title">{window.title}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div className="calendar-legend">
        <span className="legend-item">
          <span className="legend-color" style={{ backgroundColor: STATUS_COLORS.scheduled }}></span>
          已计划
        </span>
        <span className="legend-item">
          <span className="legend-color" style={{ backgroundColor: STATUS_COLORS.active }}></span>
          进行中
        </span>
        <span className="legend-item">
          <span className="legend-color" style={{ backgroundColor: STATUS_COLORS.completed }}></span>
          已完成
        </span>
        <span className="legend-item">
          <span className="legend-color" style={{ backgroundColor: STATUS_COLORS.cancelled }}></span>
          已取消
        </span>
      </div>

      {showCreateModal && (
        <MaintenanceWindowModal
          onClose={() => setShowCreateModal(false)}
          onSubmit={() => onRefresh && onRefresh()}
          targets={targets}
          groups={groups}
        />
      )}

      {showDetailModal && selectedWindow && (
        <div className="modal-overlay" onClick={() => setShowDetailModal(false)}>
          <div className="modal-content maintenance-detail-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>维护窗口详情</h3>
              <button className="close-btn" onClick={() => setShowDetailModal(false)}>×</button>
            </div>

            <div className="modal-body">
              <div className="detail-status-bar" style={{ backgroundColor: STATUS_COLORS[selectedWindow.status] }}>
                <span className="status-label">{STATUS_LABELS[selectedWindow.status] || selectedWindow.status}</span>
              </div>

              <div className="detail-section">
                <h4>基本信息</h4>
                <div className="detail-grid">
                  <div className="detail-item">
                    <label>标题</label>
                    <span>{selectedWindow.title}</span>
                  </div>
                  <div className="detail-item">
                    <label>目标</label>
                    <span>{selectedWindow.target_name}</span>
                  </div>
                  <div className="detail-item">
                    <label>负责人</label>
                    <span>{selectedWindow.owner || '-'}</span>
                  </div>
                  <div className="detail-item">
                    <label>维护原因</label>
                    <span>{selectedWindow.reason || '-'}</span>
                  </div>
                </div>
              </div>

              <div className="detail-section">
                <h4>时间信息</h4>
                <div className="detail-grid">
                  <div className="detail-item">
                    <label>计划开始</label>
                    <span>{formatDateTime(selectedWindow.start_time)}</span>
                  </div>
                  <div className="detail-item">
                    <label>计划结束</label>
                    <span>{formatDateTime(selectedWindow.end_time)}</span>
                  </div>
                  {selectedWindow.actual_start_time && (
                    <div className="detail-item">
                      <label>实际开始</label>
                      <span>{formatDateTime(selectedWindow.actual_start_time)}</span>
                    </div>
                  )}
                  {selectedWindow.actual_end_time && (
                    <div className="detail-item">
                      <label>实际结束</label>
                      <span>{formatDateTime(selectedWindow.actual_end_time)}</span>
                    </div>
                  )}
                </div>
              </div>

              {selectedWindow.description && (
                <div className="detail-section">
                  <h4>详细描述</h4>
                  <p className="detail-description">{selectedWindow.description}</p>
                </div>
              )}

              {selectedWindow.extension_reason && (
                <div className="detail-section">
                  <h4>延期原因</h4>
                  <p className="detail-description">{selectedWindow.extension_reason}</p>
                </div>
              )}

              {selectedWindow.is_cancelled && selectedWindow.cancelled_reason && (
                <div className="detail-section">
                  <h4>取消原因</h4>
                  <p className="detail-description">{selectedWindow.cancelled_reason}</p>
                </div>
              )}

              {selectedWindow.timeout_alert_sent && (
                <div className="timeout-warning">
                  ⚠️ 维护窗口已超时，超过计划结束时间
                </div>
              )}

              <div className="detail-actions">
                {(selectedWindow.status === 'scheduled' || selectedWindow.status === 'active') && !selectedWindow.is_cancelled && (
                  <>
                    <button 
                      className="btn-warning"
                      onClick={() => {
                        const defaultEnd = new Date(selectedWindow.end_time);
                        defaultEnd.setHours(defaultEnd.getHours() + 2);
                        setExtendEndTime(formatDateTimeLocal(defaultEnd));
                        setExtendReason('');
                        setShowExtendModal(true);
                      }}
                    >
                      延期
                    </button>
                    <button 
                      className="btn-danger"
                      onClick={() => {
                        setCancelReason('');
                        setShowCancelModal(true);
                      }}
                    >
                      取消
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {showExtendModal && selectedWindow && (
        <div className="modal-overlay" onClick={() => setShowExtendModal(false)}>
          <div className="modal-content small-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>延期维护窗口</h3>
              <button className="close-btn" onClick={() => setShowExtendModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>新的结束时间 *</label>
                <input
                  type="datetime-local"
                  value={extendEndTime}
                  onChange={(e) => setExtendEndTime(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>延期原因 *</label>
                <textarea
                  value={extendReason}
                  onChange={(e) => setExtendReason(e.target.value)}
                  rows="3"
                  placeholder="请填写延期原因..."
                />
              </div>
              <div className="modal-footer">
                <button className="btn-secondary" onClick={() => setShowExtendModal(false)} disabled={actionLoading}>
                  取消
                </button>
                <button 
                  className="btn-primary" 
                  onClick={handleExtend} 
                  disabled={actionLoading || !extendEndTime || !extendReason.trim()}
                >
                  {actionLoading ? '提交中...' : '确认延期'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showCancelModal && selectedWindow && (
        <div className="modal-overlay" onClick={() => setShowCancelModal(false)}>
          <div className="modal-content small-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>取消维护窗口</h3>
              <button className="close-btn" onClick={() => setShowCancelModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <p className="confirm-text">
                确定要取消这个维护窗口吗？
                {selectedWindow.status === 'active' && (
                  <span className="warning-text">
                    <br />注意：当前维护窗口正在进行中，取消后将立即恢复目标探测。
                  </span>
                )}
              </p>
              <div className="form-group">
                <label>取消原因</label>
                <textarea
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  rows="3"
                  placeholder="请填写取消原因（可选）..."
                />
              </div>
              <div className="modal-footer">
                <button className="btn-secondary" onClick={() => setShowCancelModal(false)} disabled={actionLoading}>
                  返回
                </button>
                <button 
                  className="btn-danger" 
                  onClick={handleCancel} 
                  disabled={actionLoading}
                >
                  {actionLoading ? '取消中...' : '确认取消'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MaintenanceCalendar;
