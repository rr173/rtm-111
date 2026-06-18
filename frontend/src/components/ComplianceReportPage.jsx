import { useState, useEffect, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

const REPORT_TYPE_LABELS = {
  weekly: '周报',
  monthly: '月报',
  custom: '自定义',
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
  });
}

function formatDate(dateStr) {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
}

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '-';
  if (seconds < 60) return `${Math.round(seconds)} 秒`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} 小时`;
  return `${Math.round(seconds / 86400)} 天`;
}

function ComplianceReportPage() {
  const [reports, setReports] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(false);

  const [reportType, setReportType] = useState('');
  const [selectedReport, setSelectedReport] = useState(null);
  const [showPreview, setShowPreview] = useState(false);

  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [generateStartDate, setGenerateStartDate] = useState('');
  const [generateEndDate, setGenerateEndDate] = useState('');
  const [generating, setGenerating] = useState(false);

  const loadReports = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (reportType) params.append('report_type', reportType);
      params.append('page', page);
      params.append('page_size', pageSize);

      const res = await fetch(`${API_BASE}/api/compliance-reports?${params}`);
      if (res.ok) {
        const data = await res.json();
        setReports(data.items || []);
        setTotal(data.total || 0);
        setTotalPages(data.total_pages || 0);
      }
    } catch (e) {
      console.error('Failed to load compliance reports:', e);
    } finally {
      setLoading(false);
    }
  }, [reportType, page, pageSize]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const loadReportDetail = async (reportId) => {
    try {
      const res = await fetch(`${API_BASE}/api/compliance-reports/${reportId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedReport(data);
        setShowPreview(true);
      }
    } catch (e) {
      console.error('Failed to load report detail:', e);
    }
  };

  const handleGenerateReport = async () => {
    if (!generateStartDate || !generateEndDate) {
      alert('请选择开始和结束时间');
      return;
    }

    try {
      setGenerating(true);
      const res = await fetch(`${API_BASE}/api/compliance-reports/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_time: generateStartDate,
          end_time: generateEndDate,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setShowGenerateModal(false);
        setSelectedReport(data);
        setShowPreview(true);
        loadReports();
      } else {
        const err = await res.json();
        alert(`生成失败: ${err.detail || '未知错误'}`);
      }
    } catch (e) {
      console.error('Failed to generate report:', e);
      alert('生成失败，请稍后重试');
    } finally {
      setGenerating(false);
    }
  };

  const handleDownloadReport = (report) => {
    const jsonStr = JSON.stringify(report, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `compliance-report-${report.report_type}-${report.id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setPage(newPage);
    }
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

  const getReportTypeBadgeClass = (type) => {
    switch (type) {
      case 'weekly': return 'badge-weekly';
      case 'monthly': return 'badge-monthly';
      default: return 'badge-custom';
    }
  };

  return (
    <div className="compliance-report-page">
      <div className="page-header">
        <h2>📊 合规报告</h2>
        <p className="page-subtitle">探测覆盖率、告警响应率、MTTR等合规指标分析</p>
        <button className="btn btn-primary" onClick={() => setShowGenerateModal(true)}>
          ➕ 生成报告
        </button>
      </div>

      <div className="filter-section">
        <div className="filter-row">
          <div className="filter-item">
            <label>报告类型</label>
            <select value={reportType} onChange={(e) => { setReportType(e.target.value); setPage(1); }}>
              <option value="">全部</option>
              <option value="weekly">周报</option>
              <option value="monthly">月报</option>
              <option value="custom">自定义</option>
            </select>
          </div>
        </div>
      </div>

      <div className="results-info">
        <span>共 {total} 份报告</span>
        <span>第 {page} / {totalPages || 1} 页</span>
      </div>

      <div className="report-list">
        {loading ? (
          <div className="loading">加载中...</div>
        ) : reports.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📊</div>
            <p>暂无合规报告</p>
            <button className="btn btn-primary" onClick={() => setShowGenerateModal(true)}>
              生成第一份报告
            </button>
          </div>
        ) : (
          <div className="report-cards">
            {reports.map((report) => (
              <div key={report.id} className="report-card">
                <div className="report-card-header">
                  <span className={`report-type-badge ${getReportTypeBadgeClass(report.report_type)}`}>
                    {REPORT_TYPE_LABELS[report.report_type] || report.report_type}
                  </span>
                  <h3>{report.title}</h3>
                </div>
                <div className="report-card-body">
                  <div className="report-period">
                    <span>📅 报告周期</span>
                    <span>{formatDate(report.period_start)} - {formatDate(report.period_end)}</span>
                  </div>
                  <div className="report-metrics">
                    <div className="metric-item">
                      <span className="metric-label">探测覆盖率</span>
                      <span className="metric-value coverage">
                        {report.summary?.probe_coverage_rate ? (report.summary.probe_coverage_rate * 100).toFixed(1) : 0}%
                      </span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">告警响应率</span>
                      <span className="metric-value response">
                        {report.summary?.alert_response_rate ? (report.summary.alert_response_rate * 100).toFixed(1) : 0}%
                      </span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">平均恢复时间</span>
                      <span className="metric-value mttr">
                        {formatDuration(report.summary?.avg_mttr_seconds)}
                      </span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">配置变更次数</span>
                      <span className="metric-value changes">
                        {report.summary?.total_changes || 0}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="report-card-footer">
                  <span className="report-generated">生成于 {formatDateTime(report.generated_at)}</span>
                  <div className="report-actions">
                    <button className="btn btn-sm btn-secondary" onClick={() => loadReportDetail(report.id)}>
                      👁 预览
                    </button>
                    <button className="btn btn-sm btn-primary" onClick={() => handleDownloadReport(report)}>
                      ⬇ 下载
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          <button className="page-btn" onClick={() => handlePageChange(1)} disabled={page === 1}>
            首页
          </button>
          <button className="page-btn" onClick={() => handlePageChange(page - 1)} disabled={page === 1}>
            上一页
          </button>
          {renderPageNumbers()}
          <button className="page-btn" onClick={() => handlePageChange(page + 1)} disabled={page === totalPages}>
            下一页
          </button>
          <button className="page-btn" onClick={() => handlePageChange(totalPages)} disabled={page === totalPages}>
            末页
          </button>
        </div>
      )}

      {showGenerateModal && (
        <div className="modal-overlay" onClick={() => setShowGenerateModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>生成合规报告</h3>
              <button className="close-btn" onClick={() => setShowGenerateModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>开始时间</label>
                <input
                  type="date"
                  value={generateStartDate}
                  onChange={(e) => setGenerateStartDate(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>结束时间</label>
                <input
                  type="date"
                  value={generateEndDate}
                  onChange={(e) => setGenerateEndDate(e.target.value)}
                />
              </div>
              <p className="form-hint">
                选择一个时间段，系统将自动生成该时间段内的合规报告，包括探测覆盖率、告警响应率、MTTR等指标。
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowGenerateModal(false)}>
                取消
              </button>
              <button
                className="btn btn-primary"
                onClick={handleGenerateReport}
                disabled={generating}
              >
                {generating ? '生成中...' : '生成报告'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showPreview && selectedReport && (
        <div className="modal-overlay modal-large" onClick={() => setShowPreview(false)}>
          <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{selectedReport.title}</h3>
              <button className="close-btn" onClick={() => setShowPreview(false)}>✕</button>
            </div>
            <div className="modal-body modal-scrollable">
              <div className="report-preview">
                <div className="preview-section">
                  <h4>📅 报告信息</h4>
                  <div className="info-grid">
                    <div className="info-item">
                      <span className="info-label">报告类型</span>
                      <span className="info-value">
                        {REPORT_TYPE_LABELS[selectedReport.report_type] || selectedReport.report_type}
                      </span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">报告周期</span>
                      <span className="info-value">
                        {formatDate(selectedReport.period_start)} - {formatDate(selectedReport.period_end)}
                      </span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">生成时间</span>
                      <span className="info-value">{formatDateTime(selectedReport.generated_at)}</span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">审计日志数</span>
                      <span className="info-value">{selectedReport.audit_log_count || 0}</span>
                    </div>
                  </div>
                </div>

                <div className="preview-section">
                  <h4>📊 核心指标概览</h4>
                  <div className="metrics-grid">
                    <div className="metric-card metric-coverage">
                      <div className="metric-icon">📡</div>
                      <div className="metric-content">
                        <div className="metric-value-large">
                          {selectedReport.probe_coverage?.coverage_rate
                            ? (selectedReport.probe_coverage.coverage_rate * 100).toFixed(1)
                            : 0}%
                        </div>
                        <div className="metric-label">探测覆盖率</div>
                        <div className="metric-subtext">
                          {selectedReport.probe_coverage?.total_targets || 0} 个目标中
                          {selectedReport.probe_coverage?.healthy_targets || 0} 个持续可用
                        </div>
                      </div>
                    </div>

                    <div className="metric-card metric-response">
                      <div className="metric-icon">⚡</div>
                      <div className="metric-content">
                        <div className="metric-value-large">
                          {selectedReport.alert_response?.response_rate
                            ? (selectedReport.alert_response.response_rate * 100).toFixed(1)
                            : 0}%
                        </div>
                        <div className="metric-label">告警响应率</div>
                        <div className="metric-subtext">
                          {selectedReport.alert_response?.acknowledged || 0} /
                          {selectedReport.alert_response?.total || 0} 条告警已确认
                        </div>
                      </div>
                    </div>

                    <div className="metric-card metric-mttr">
                      <div className="metric-icon">⏱️</div>
                      <div className="metric-content">
                        <div className="metric-value-large">
                          {formatDuration(selectedReport.mttr?.avg_mttr_seconds)}
                        </div>
                        <div className="metric-label">平均故障恢复时间</div>
                        <div className="metric-subtext">
                          基于 {selectedReport.mttr?.incident_count || 0} 个故障事件计算
                        </div>
                      </div>
                    </div>

                    <div className="metric-card metric-changes">
                      <div className="metric-icon">⚙️</div>
                      <div className="metric-content">
                        <div className="metric-value-large">
                          {selectedReport.config_changes?.total_changes || 0}
                        </div>
                        <div className="metric-label">配置变更次数</div>
                        <div className="metric-subtext">
                          涉及 {selectedReport.config_changes?.affected_targets || 0} 个目标
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="preview-section">
                  <h4>🔝 变更频率最高的目标</h4>
                  {selectedReport.top_changed_targets?.length > 0 ? (
                    <div className="top-targets-list">
                      {selectedReport.top_changed_targets.map((target, index) => (
                        <div key={index} className="top-target-item">
                          <span className="rank">{index + 1}</span>
                          <span className="target-name">{target.target_name}</span>
                          <span className="change-count">{target.change_count} 次变更</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="no-data">暂无数据</p>
                  )}
                </div>

                <div className="preview-section">
                  <h4>📋 详细数据 (JSON)</h4>
                  <details>
                    <summary>点击查看完整 JSON 数据</summary>
                    <pre className="json-preview">
                      {JSON.stringify(selectedReport, null, 2)}
                    </pre>
                  </details>
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowPreview(false)}>
                关闭
              </button>
              <button className="btn btn-primary" onClick={() => handleDownloadReport(selectedReport)}>
                ⬇ 下载报告
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ComplianceReportPage;
