import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function StepHistoryModal({ step, onClose }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHistory();
  }, [step?.id]);

  const fetchHistory = async () => {
    if (step?.id == null) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/steps/${step.id}/history?limit=10`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data.executions || []);
      }
    } catch (e) {
        console.error('Failed to fetch step history:', e);
      } finally {
        setLoading(false);
      }
  };

  const formatTime = (iso) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal step-history-modal" onClick={e => e.stopPropagation()}>
        <div className="rule-editor-header">
          <h2>📊 步骤执行历史</h2>
          <button className="btn btn-secondary" onClick={onClose}>关闭</button>
        </div>

        <div className="step-history-info">
          <h3 style={{ marginBottom: '8px' }}>{step?.name}</h3>
          <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '20px' }}>
            类型: {step?.step_type} · 最近 10 次执行
          </p>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
            加载中...
          </div>
        ) : history.length === 0 ? (
          <div className="empty-text">暂无执行记录</div>
        ) : (
          <div className="step-history-list">
            {history.map((exec, idx) => (
              <div key={exec.id || idx} className="step-history-item">
              <div className="step-history-item-left">
                <span className={'status-dot-inline ' + (exec.success ? 'success' : 'failed')}></span>
                <div className="step-history-meta">
                  <div className="step-history-time">{formatTime(exec.timestamp)}</div>
                  <div className="step-history-latency">
                    耗时: {exec.latency_ms ? exec.latency_ms.toFixed(0) + ' ms' : '—'}
                  </div>
                </div>
              </div>
              <div className="step-history-item-right">
                <span className={'step-result-label ' + (exec.success ? 'success' : 'failed')}>
                  {exec.success ? '✓ 通过' : '✕ 失败'}
                </span>
              </div>
              {exec.error_message && (
                <div className="step-history-error">
                  {exec.error_message}
                </div>
              )}
              {exec.raw_response && exec.success && (
                  <div className="step-history-raw">
                    <details>
                      <summary>原始响应</summary>
                      <pre>{typeof exec.raw_response}</pre>
                    </details>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default StepHistoryModal;
