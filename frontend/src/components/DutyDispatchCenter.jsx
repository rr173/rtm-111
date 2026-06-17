import { useState, useEffect, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';
const DAY_NAMES = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

function formatTime(dt) {
  if (!dt) return '-';
  const d = new Date(dt);
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return '-';
  if (seconds < 60) return `${Math.round(seconds)}秒`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分${Math.round(seconds % 60)}秒`;
  return `${Math.floor(seconds / 3600)}时${Math.floor((seconds % 3600) / 60)}分`;
}

function StatusBadge({ status }) {
  const config = {
    dispatched: { label: '待接手', cls: 'dispatched' },
    primary_escalated: { label: '已升级', cls: 'escalated' },
    acknowledged: { label: '已接手', cls: 'acknowledged' },
    resolved: { label: '已结案', cls: 'resolved' },
    unattended: { label: '无人接手', cls: 'unattended' },
  };
  const c = config[status] || { label: status, cls: '' };
  return <span className={`duty-status-badge duty-status-${c.cls}`}>{c.label}</span>;
}

function OverviewTab({ overview, dispatchedAlerts, onAcknowledge, onResolve, schedules }) {
  const [resolveId, setResolveId] = useState(null);
  const [resolveSummary, setResolveSummary] = useState('');
  const [resolveBy, setResolveBy] = useState('');

  const pending = dispatchedAlerts.filter(a => a.dispatch_status === 'dispatched' || a.dispatch_status === 'primary_escalated');
  const unattended = dispatchedAlerts.filter(a => a.dispatch_status === 'unattended');

  return (
    <div className="duty-overview">
      <div className="duty-overview-cards">
        <div className="duty-overview-card current-duty">
          <div className="duty-card-icon">👤</div>
          <div className="duty-card-content">
            <div className="duty-card-label">当前值班</div>
            <div className="duty-card-value primary">{overview.current_primary || '-'}</div>
            <div className="duty-card-sub">备班: {overview.current_backup || '-'}</div>
            {overview.current_schedule_name && <div className="duty-card-schedule">{overview.current_schedule_name}</div>}
          </div>
        </div>
        <div className="duty-overview-card pending-card">
          <div className="duty-card-icon">🔔</div>
          <div className="duty-card-content">
            <div className="duty-card-label">待处理告警</div>
            <div className="duty-card-value">{overview.pending_alert_count + overview.escalated_alert_count}</div>
            <div className="duty-card-sub">已升级: {overview.escalated_alert_count}</div>
          </div>
        </div>
        <div className="duty-overview-card unattended-card">
          <div className="duty-card-icon">⚠️</div>
          <div className="duty-card-content">
            <div className="duty-card-label">无人接手</div>
            <div className="duty-card-value alert">{overview.unattended_alert_count}</div>
          </div>
        </div>
        <div className="duty-overview-card response-card">
          <div className="duty-card-icon">⏱️</div>
          <div className="duty-card-content">
            <div className="duty-card-label">平均响应时长</div>
            <div className="duty-card-value">{formatDuration(overview.avg_response_seconds)}</div>
          </div>
        </div>
      </div>

      {unattended.length > 0 && (
        <div className="duty-unattended-banner">
          <span className="unattended-icon">🚨</span>
          <span>有 {unattended.length} 条告警无人接手！请尽快处理！</span>
        </div>
      )}

      <div className="duty-alerts-section">
        <h3>待处理告警</h3>
        {pending.length === 0 && unattended.length === 0 ? (
          <div className="duty-empty">暂无待处理告警</div>
        ) : (
          <div className="duty-alerts-list">
            {[...unattended, ...pending].map(da => (
              <div key={da.id} className={`duty-alert-item duty-alert-${da.dispatch_status}`}>
                <div className="duty-alert-header">
                  <StatusBadge status={da.dispatch_status} />
                  <span className="duty-alert-target">{da.alert_target_name || `目标#${da.alert_id}`}</span>
                  <span className="duty-alert-time">{formatTime(da.dispatched_at)}</span>
                </div>
                <div className="duty-alert-body">
                  <span className="duty-alert-change">{da.alert_from_status} → {da.alert_to_status}</span>
                  {da.group_name && <span className="duty-alert-group">[{da.group_name}]</span>}
                  <span className="duty-alert-assignee">
                    主: {da.primary_person} | 备: {da.backup_person}
                  </span>
                  {da.assigned_to && <span className="duty-alert-current">当前: {da.assigned_to}</span>}
                </div>
                <div className="duty-alert-actions">
                  {da.dispatch_status !== 'acknowledged' && da.dispatch_status !== 'resolved' && (
                    <button className="duty-btn duty-btn-ack" onClick={() => {
                      const person = prompt('请输入你的姓名以确认接手:');
                      if (person) onAcknowledge(da.id, person);
                    }}>
                      确认接手
                    </button>
                  )}
                  {da.dispatch_status === 'acknowledged' && !da.resolved_at && (
                    resolveId === da.id ? (
                      <div className="duty-resolve-form">
                        <input placeholder="处理人" value={resolveBy} onChange={e => setResolveBy(e.target.value)} />
                        <textarea placeholder="处理摘要" value={resolveSummary} onChange={e => setResolveSummary(e.target.value)} />
                        <button className="duty-btn duty-btn-resolve" onClick={() => {
                          if (resolveBy && resolveSummary) {
                            onResolve(da.id, resolveBy, resolveSummary);
                            setResolveId(null);
                            setResolveSummary('');
                            setResolveBy('');
                          }
                        }}>确认结案</button>
                        <button className="duty-btn duty-btn-cancel" onClick={() => setResolveId(null)}>取消</button>
                      </div>
                    ) : (
                      <button className="duty-btn duty-btn-resolve-start" onClick={() => setResolveId(da.id)}>
                        结案
                      </button>
                    )
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="duty-alerts-section">
        <h3>已处理告警</h3>
        {dispatchedAlerts.filter(a => a.dispatch_status === 'resolved').length === 0 ? (
          <div className="duty-empty">暂无已处理告警</div>
        ) : (
          <div className="duty-alerts-list">
            {dispatchedAlerts.filter(a => a.dispatch_status === 'resolved').map(da => (
              <div key={da.id} className="duty-alert-item duty-alert-resolved">
                <div className="duty-alert-header">
                  <StatusBadge status={da.dispatch_status} />
                  <span className="duty-alert-target">{da.alert_target_name || `目标#${da.alert_id}`}</span>
                  <span className="duty-alert-time">{formatTime(da.dispatched_at)}</span>
                </div>
                <div className="duty-alert-body">
                  <span className="duty-alert-change">{da.alert_from_status} → {da.alert_to_status}</span>
                  <span className="duty-alert-assignee">处理人: {da.resolved_by}</span>
                  <span className="duty-alert-response">响应: {formatDuration(da.response_seconds)}</span>
                </div>
                {da.resolution_summary && (
                  <div className="duty-alert-summary">摘要: {da.resolution_summary}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function CalendarTab({ schedules, selectedScheduleId, onSelectSchedule }) {
  const [weekOffset, setWeekOffset] = useState(0);
  const [calendar, setCalendar] = useState(null);
  const [dragSlot, setDragSlot] = useState(null);
  const [showSwapModal, setShowSwapModal] = useState(null);

  const loadCalendar = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (selectedScheduleId) params.set('schedule_id', selectedScheduleId);
      params.set('week_offset', weekOffset);
      const res = await fetch(`${API_BASE}/api/duty/calendar?${params}`);
      if (res.ok) {
        const data = await res.json();
        setCalendar(data);
      }
    } catch (e) {
      console.error('Failed to load calendar:', e);
    }
  }, [selectedScheduleId, weekOffset]);

  useEffect(() => {
    loadCalendar();
  }, [loadCalendar]);

  const handleDragStart = (e, dayIdx, slotIdx, person, role) => {
    setDragSlot({ dayIdx, slotIdx, person, role });
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDrop = (e, targetDayIdx, targetSlotIdx, targetRole) => {
    e.preventDefault();
    if (!dragSlot) return;
    if (dragSlot.dayIdx === targetDayIdx && dragSlot.slotIdx === targetSlotIdx && dragSlot.role === targetRole) return;

    setShowSwapModal({
      scheduleId: selectedScheduleId || (schedules.find(s => s.is_default)?.id),
      source: dragSlot,
      target: { dayIdx: targetDayIdx, slotIdx: targetSlotIdx, role: targetRole },
    });
    setDragSlot(null);
  };

  const handleSwapSubmit = async (reason) => {
    if (!showSwapModal || !calendar) return;
    const { source, target, scheduleId } = showSwapModal;
    const sourceDay = calendar.days[source.dayIdx];
    const targetDay = calendar.days[target.dayIdx];
    const sourceSlot = sourceDay.slots[source.slotIdx];
    const targetSlot = targetDay.slots[target.slotIdx];

    const sourcePerson = source.role === 'primary' ? sourceSlot.primary_person : sourceSlot.backup_person;
    const targetPerson = target.role === 'primary' ? targetSlot.primary_person : targetSlot.backup_person;

    try {
      await fetch(`${API_BASE}/api/duty/schedules/${scheduleId}/swaps`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          swap_date: sourceDay.date + 'T00:00:00',
          start_hour: sourceSlot.start_hour,
          end_hour: sourceSlot.end_hour,
          original_person: sourcePerson,
          new_person: targetPerson,
          role: source.role,
          reason: reason,
        }),
      });
      await fetch(`${API_BASE}/api/duty/schedules/${scheduleId}/swaps`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          swap_date: targetDay.date + 'T00:00:00',
          start_hour: targetSlot.start_hour,
          end_hour: targetSlot.end_hour,
          original_person: targetPerson,
          new_person: sourcePerson,
          role: target.role,
          reason: reason,
        }),
      });
      setShowSwapModal(null);
      loadCalendar();
    } catch (e) {
      console.error('Swap failed:', e);
    }
  };

  const weekStart = calendar?.week_start ? new Date(calendar.week_start) : null;

  return (
    <div className="duty-calendar">
      <div className="duty-calendar-controls">
        <select value={selectedScheduleId || ''} onChange={e => onSelectSchedule(e.target.value ? Number(e.target.value) : null)}>
          {schedules.map(s => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        <button className="duty-btn" onClick={() => setWeekOffset(w => w - 1)}>◀ 上周</button>
        <span className="duty-week-label">{weekStart ? `${weekStart.toLocaleDateString('zh-CN')} 起` : ''}</span>
        <button className="duty-btn" onClick={() => setWeekOffset(w => w + 1)}>下周 ▶</button>
        <button className="duty-btn" onClick={() => setWeekOffset(0)}>本周</button>
      </div>

      {calendar && calendar.days && (
        <div className="duty-calendar-grid">
          <div className="duty-calendar-header-row">
            <div className="duty-calendar-time-col">时段</div>
            {calendar.days.map((day, idx) => (
              <div key={idx} className="duty-calendar-day-col">
                <div className="duty-day-name">{DAY_NAMES[day.day_of_week]}</div>
                <div className="duty-day-date">{day.date.slice(5)}</div>
              </div>
            ))}
          </div>
          {[0, 8, 18].map(hourStart => {
            const rangeLabel = hourStart === 0 ? '0:00-8:00 夜班' : hourStart === 8 ? '8:00-18:00 白班' : '18:00-24:00 晚班';
            return (
              <div key={hourStart} className="duty-calendar-row">
                <div className="duty-calendar-time-col">{rangeLabel}</div>
                {calendar.days.map((day, dayIdx) => {
                  const slot = day.slots.find(s => s.start_hour === hourStart) || day.slots[0];
                  if (!slot) return <div key={dayIdx} className="duty-calendar-cell empty" />;
                  return (
                    <div key={dayIdx}
                      className={`duty-calendar-cell ${slot.is_swapped ? 'swapped' : ''}`}
                      onDragOver={e => e.preventDefault()}
                      onDrop={e => handleDrop(e, dayIdx, day.slots.indexOf(slot), 'primary')}
                    >
                      <div className="duty-cell-primary"
                        draggable
                        onDragStart={e => handleDragStart(e, dayIdx, day.slots.indexOf(slot), slot.primary_person, 'primary')}
                      >
                        <span className="duty-cell-role">主</span>
                        <span className="duty-cell-name">{slot.primary_person}</span>
                      </div>
                      <div className="duty-cell-backup"
                        draggable
                        onDragStart={e => handleDragStart(e, dayIdx, day.slots.indexOf(slot), slot.backup_person, 'backup')}
                      >
                        <span className="duty-cell-role">备</span>
                        <span className="duty-cell-name">{slot.backup_person}</span>
                      </div>
                      {slot.is_swapped && <div className="duty-cell-swap-tag" title={slot.swap_reason}>🔄</div>}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}

      {showSwapModal && (
        <div className="duty-modal-overlay">
          <div className="duty-modal">
            <h3>换班确认</h3>
            <p>将 <strong>{showSwapModal.source.person}</strong> 与目标时段人员互换</p>
            <textarea
              id="swap-reason-input"
              placeholder="请输入换班原因"
              defaultValue=""
            />
            <div className="duty-modal-actions">
              <button className="duty-btn duty-btn-primary" onClick={() => {
                const reason = document.getElementById('swap-reason-input')?.value;
                if (reason?.trim()) handleSwapSubmit(reason.trim());
              }}>确认换班</button>
              <button className="duty-btn duty-btn-cancel" onClick={() => setShowSwapModal(null)}>取消</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function HistoryTab() {
  const [person, setPerson] = useState('');
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(false);

  const searchHistory = useCallback(async () => {
    if (!person.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/duty/person-history?person=${encodeURIComponent(person.trim())}`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (e) {
      console.error('Failed to search history:', e);
    } finally {
      setLoading(false);
    }
  }, [person]);

  return (
    <div className="duty-history">
      <div className="duty-history-search">
        <input
          placeholder="输入值班人姓名查询"
          value={person}
          onChange={e => setPerson(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && searchHistory()}
        />
        <button className="duty-btn duty-btn-primary" onClick={searchHistory} disabled={loading}>
          {loading ? '查询中...' : '查询'}
        </button>
      </div>

      {history && (
        <div className="duty-history-result">
          <div className="duty-history-stats">
            <div className="duty-stat-item">
              <div className="duty-stat-value">{history.total_dispatched}</div>
              <div className="duty-stat-label">分配总数</div>
            </div>
            <div className="duty-stat-item">
              <div className="duty-stat-value">{history.total_acknowledged}</div>
              <div className="duty-stat-label">已接手</div>
            </div>
            <div className="duty-stat-item">
              <div className="duty-stat-value">{history.total_resolved}</div>
              <div className="duty-stat-label">已结案</div>
            </div>
            <div className="duty-stat-item">
              <div className="duty-stat-value">{formatDuration(history.avg_response_seconds)}</div>
              <div className="duty-stat-label">平均响应</div>
            </div>
          </div>

          <div className="duty-history-list">
            {history.alerts.length === 0 ? (
              <div className="duty-empty">无记录</div>
            ) : (
              history.alerts.map(da => (
                <div key={da.id} className={`duty-alert-item duty-alert-${da.dispatch_status}`}>
                  <div className="duty-alert-header">
                    <StatusBadge status={da.dispatch_status} />
                    <span className="duty-alert-target">{da.alert_target_name || `目标#${da.alert_id}`}</span>
                    <span className="duty-alert-time">{formatTime(da.dispatched_at)}</span>
                  </div>
                  <div className="duty-alert-body">
                    <span className="duty-alert-change">{da.alert_from_status} → {da.alert_to_status}</span>
                    {da.response_seconds != null && <span className="duty-alert-response">响应: {formatDuration(da.response_seconds)}</span>}
                    {da.resolved_by && <span className="duty-alert-assignee">处理人: {da.resolved_by}</span>}
                  </div>
                  {da.resolution_summary && <div className="duty-alert-summary">摘要: {da.resolution_summary}</div>}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function DutyDispatchCenter() {
  const [activeTab, setActiveTab] = useState('overview');
  const [overview, setOverview] = useState({});
  const [dispatchedAlerts, setDispatchedAlerts] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [selectedScheduleId, setSelectedScheduleId] = useState(null);

  const loadOverview = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/duty/overview`);
      if (res.ok) {
        const data = await res.json();
        setOverview(data);
      }
    } catch (e) {
      console.error('Failed to load overview:', e);
    }
  }, []);

  const loadDispatched = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/duty/dispatched`);
      if (res.ok) {
        const data = await res.json();
        setDispatchedAlerts(data);
      }
    } catch (e) {
      console.error('Failed to load dispatched:', e);
    }
  }, []);

  const loadSchedules = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/duty/schedules`);
      if (res.ok) {
        const data = await res.json();
        setSchedules(data);
        if (!selectedScheduleId && data.length > 0) {
          const def = data.find(s => s.is_default);
          setSelectedScheduleId(def ? def.id : data[0].id);
        }
      }
    } catch (e) {
      console.error('Failed to load schedules:', e);
    }
  }, [selectedScheduleId]);

  useEffect(() => {
    loadOverview();
    loadDispatched();
    loadSchedules();
    const interval = setInterval(() => {
      loadOverview();
      loadDispatched();
    }, 10000);
    return () => clearInterval(interval);
  }, [loadOverview, loadDispatched, loadSchedules]);

  const handleAcknowledge = async (dispatchId, person) => {
    try {
      const res = await fetch(`${API_BASE}/api/duty/dispatched/${dispatchId}/acknowledge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ acknowledged_by: person }),
      });
      if (res.ok) {
        loadOverview();
        loadDispatched();
      }
    } catch (e) {
      console.error('Acknowledge failed:', e);
    }
  };

  const handleResolve = async (dispatchId, resolvedBy, summary) => {
    try {
      const res = await fetch(`${API_BASE}/api/duty/dispatched/${dispatchId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resolved_by: resolvedBy, resolution_summary: summary }),
      });
      if (res.ok) {
        loadOverview();
        loadDispatched();
      }
    } catch (e) {
      console.error('Resolve failed:', e);
    }
  };

  return (
    <div className="duty-dispatch-center">
      <div className="duty-header">
        <h2>📟 值班排班与告警分派调度中心</h2>
        <div className="duty-tabs">
          <button className={`duty-tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
            📊 值班总览
          </button>
          <button className={`duty-tab-btn ${activeTab === 'calendar' ? 'active' : ''}`} onClick={() => setActiveTab('calendar')}>
            📅 排班日历
          </button>
          <button className={`duty-tab-btn ${activeTab === 'history' ? 'active' : ''}`} onClick={() => setActiveTab('history')}>
            📋 历史记录
          </button>
        </div>
      </div>

      <div className="duty-content">
        {activeTab === 'overview' && (
          <OverviewTab
            overview={overview}
            dispatchedAlerts={dispatchedAlerts}
            onAcknowledge={handleAcknowledge}
            onResolve={handleResolve}
            schedules={schedules}
          />
        )}
        {activeTab === 'calendar' && (
          <CalendarTab
            schedules={schedules}
            selectedScheduleId={selectedScheduleId}
            onSelectSchedule={setSelectedScheduleId}
          />
        )}
        {activeTab === 'history' && (
          <HistoryTab />
        )}
      </div>
    </div>
  );
}
