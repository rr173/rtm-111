import { useState, useEffect, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

const OPERATION_TYPE_LABELS = {
  target_create: '目标创建',
  target_update: '目标更新',
  target_delete: '目标删除',
  target_pause: '目标暂停',
  target_resume: '目标恢复',
  target_silence: '目标消声',
  target_unsilence: '目标取消消声',
  target_threshold_update: '阈值调整',
  group_create: '分组创建',
  group_update: '分组更新',
  group_delete: '分组删除',
  group_pause: '分组暂停',
  group_resume: '分组恢复',
  group_silence: '分组消声',
  group_unsilence: '分组取消消声',
  group_threshold_apply: '分组阈值应用',
  alert_acknowledge: '告警确认',
  maintenance_create: '维护窗口创建',
  maintenance_update: '维护窗口更新',
  maintenance_delete: '维护窗口删除',
  maintenance_extend: '维护窗口延期',
  maintenance_cancel: '维护窗口取消',
  duty_swap_create: '值班换班',
  duty_schedule_update: '值班调度更新',
  incident_acknowledge: '事件确认',
  incident_transfer: '事件转派',
  incident_resolve: '事件解决',
};

const TARGET_TYPE_LABELS = {
  target: '探测目标',
  group: '分组',
  alert: '告警',
  maintenance: '维护窗口',
  duty: '值班',
  incident: '事件',
};

function formatDateTime(dateStr) {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function AuditLogPage() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(false);

  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [operationType, setOperationType] = useState('');
  const [operator, setOperator] = useState('');
  const [targetName, setTargetName] = useState('');

  const [operationTypes, setOperationTypes] = useState({});
  const [operators, setOperators] = useState([]);

  const [expandedLogId, setExpandedLogId] = useState(null);

  const loadOperationTypes = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/audit-logs/operation-types`);
      if (res.ok) {
        const data = await res.json();
        setOperationTypes(data);
      }
    } catch (e) {
      console.error('Failed to load operation types:', e);
    }
  }, []);

  const loadOperators = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/audit-logs/operators`);
      if (res.ok) {
        const data = await res.json();
        setOperators(data.operators || []);
      }
    } catch (e) {
      console.error('Failed to load operators:', e);
    }
  }, []);

  const loadLogs = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (startTime) params.append('start_time', startTime);
      if (endTime) params.append('end_time', endTime);
      if (operationType) params.append('operation_type', operationType);
      if (operator) params.append('operator', operator);
      if (targetName) params.append('target_name', targetName);
      params.append('page', page);
      params.append('page_size', pageSize);

      const res = await fetch(`${API_BASE}/api/audit-logs?${params}`);
      if (res.ok) {
        const data = await res.json();
        setLogs(data.items || []);
        setTotal(data.total || 0);
        setTotalPages(data.total_pages || 0);
      }
    } catch (e) {
      console.error('Failed to load audit logs:', e);
    } finally {
      setLoading(false);
    }
  }, [startTime, endTime, operationType, operator, targetName, page, pageSize]);

  useEffect(() => {
    loadOperationTypes();
    loadOperators();
  }, [loadOperationTypes, loadOperators]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const handleSearch = () => {
    setPage(1);
  };

  const handleReset = () => {
    setStartTime('');
    setEndTime('');
    setOperationType('');
    setOperator('');
    setTargetName('');
    setPage(1);
  };

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setPage(newPage);
    }
  };

  const toggleExpand = (logId) => {
    setExpandedLogId(expandedLogId === logId ? null : logId);
  };

  const getOperationTypeLabel = (type) => {
    return OPERATION_TYPE_LABELS[type] || operationTypes[type] || type;
  };

  const getTargetTypeLabel = (type) => {
    return TARGET_TYPE_LABELS[type] || type;
  };

  const renderPageNumbers = () => {
    const pages = [];
    const maxVisiblePages = 5;
    let startPage = Math.max(1, page - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);

    if (endPage - startPage + 1 < maxVisiblePages) {
      startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
      pages.push(
        <button
          key={i}
          className={`page-btn ${page === i ? 'active' : ''}`}
          onClick={() => handlePageChange(i)}
        >
          {i}
        </button>
      );
    }
    return pages;
  };

  return (
    <div className="audit-log-page">
      <div className="page-header">
        <h2>📋 审计日志</h2>
        <p className="page-subtitle">记录所有关键操作的审计追踪</p>
      </div>

      <div className="filter-section">
        <div className="filter-row">
          <div className="filter-item">
            <label>开始时间</label>
            <input
              type="datetime-local"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
            />
          </div>
          <div className="filter-item">
            <label>结束时间</label>
            <input
              type="datetime-local"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
            />
          </div>
          <div className="filter-item">
            <label>操作类型</label>
            <select
              value={operationType}
              onChange={(e) => setOperationType(e.target.value)}
            >
              <option value="">全部</option>
              {Object.entries(OPERATION_TYPE_LABELS).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="filter-row">
          <div className="filter-item">
            <label>操作人</label>
            <input
              type="text"
              placeholder="输入操作人名称"
              value={operator}
              onChange={(e) => setOperator(e.target.value)}
              list="operator-list"
            />
            <datalist id="operator-list">
              {operators.map((op, idx) => (
                <option key={idx} value={op} />
              ))}
            </datalist>
          </div>
          <div className="filter-item">
            <label>目标名称</label>
            <input
              type="text"
              placeholder="输入目标名称"
              value={targetName}
              onChange={(e) => setTargetName(e.target.value)}
            />
          </div>
          <div className="filter-actions">
            <button className="btn btn-primary" onClick={handleSearch}>
              🔍 查询
            </button>
            <button className="btn btn-secondary" onClick={handleReset}>
              🔄 重置
            </button>
          </div>
        </div>
      </div>

      <div className="results-info">
        <span>共 {total} 条记录</span>
        <span>第 {page} / {totalPages || 1} 页</span>
      </div>

      <div className="audit-log-list">
        {loading ? (
          <div className="loading">加载中...</div>
        ) : logs.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📭</div>
            <p>暂无审计日志记录</p>
          </div>
        ) : (
          <div className="log-list">
            {logs.map((log) => (
              <div
                key={log.id}
                className={`log-item ${expandedLogId === log.id ? 'expanded' : ''}`}
                onClick={() => toggleExpand(log.id)}
              >
                <div className="log-header">
                  <div className="log-main-info">
                    <span className={`log-type-badge type-${log.target_type}`}>
                      {getTargetTypeLabel(log.target_type)}
                    </span>
                    <span className="log-operation">
                      {getOperationTypeLabel(log.operation_type)}
                    </span>
                    <span className="log-target-name">
                      {log.target_name || `#${log.target_id}`}
                    </span>
                  </div>
                  <div className="log-meta">
                    <span className="log-operator">👤 {log.operator || '系统'}</span>
                    <span className="log-time">{formatDateTime(log.created_at)}</span>
                    <span className="expand-icon">{expandedLogId === log.id ? '▲' : '▼'}</span>
                  </div>
                </div>

                {expandedLogId === log.id && (
                  <div className="log-detail">
                    <div className="log-description">
                      <strong>描述：</strong>{log.description || '-'}
                    </div>
                    {log.ip_address && (
                      <div className="log-ip">
                        <strong>IP 地址：</strong>{log.ip_address}
                      </div>
                    )}
                    <div className="log-values">
                      {log.old_value && (
                        <div className="value-box old-value">
                          <h4>变更前</h4>
                          <pre>{JSON.stringify(log.old_value, null, 2)}</pre>
                        </div>
                      )}
                      {log.new_value && (
                        <div className="value-box new-value">
                          <h4>变更后</h4>
                          <pre>{JSON.stringify(log.new_value, null, 2)}</pre>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          <button
            className="page-btn"
            onClick={() => handlePageChange(1)}
            disabled={page === 1}
          >
            首页
          </button>
          <button
            className="page-btn"
            onClick={() => handlePageChange(page - 1)}
            disabled={page === 1}
          >
            上一页
          </button>
          {renderPageNumbers()}
          <button
            className="page-btn"
            onClick={() => handlePageChange(page + 1)}
            disabled={page === totalPages}
          >
            下一页
          </button>
          <button
            className="page-btn"
            onClick={() => handlePageChange(totalPages)}
            disabled={page === totalPages}
          >
            末页
          </button>
        </div>
      )}
    </div>
  );
}

export default AuditLogPage;
