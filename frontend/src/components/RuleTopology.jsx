import { useState } from 'react';
import StepHistoryModal from './StepHistoryModal';

const STEP_TYPE_META = {
  http_status: { icon: '📡', label: 'HTTP状态码', color: '#3b82f6' },
  http_body_match: { icon: '📝', label: '响应体匹配', color: '#8b5cf6' },
  tcp_connect: { icon: '🔌', label: 'TCP连通', color: '#22c55e' },
  dns_resolve: { icon: '🌐', label: 'DNS解析', color: '#f59e0b' },
  latency_threshold: { icon: '⏱️', label: '延迟检查', color: '#ef4444' },
};

function RuleTopology({ steps, execution_mode, ruleExecutions = [], onStepClick }) {
  const [selectedStep, setSelectedStep] = useState(null);
  const [showStepHistory, setShowStepHistory] = useState(false);

  if (!steps || steps.length === 0) {
    return (
      <div style={{
        textAlign: 'center',
        padding: '30px',
        color: '#64748b',
        fontSize: '13px'
      }}>
        此目标未绑定探测规则
      </div>
    );
  }

  const getStepStatus = (step) => {
    const lastExec = step.last_execution;
    if (!lastExec) return 'pending';
    if (lastExec.success) return 'success';
    if (lastExec.success === false) return 'failed';
    return 'pending';
  };

  const handleStepClick = (step) => {
    setSelectedStep(step);
    setShowStepHistory(true);
    if (onStepClick) onStepClick(step);
  };

  const statusClass = (status) => {
    switch (status) {
      case 'success': return 'step-node-success';
      case 'failed': return 'step-node-failed';
      default: return 'step-node-pending';
    }
  };

  return (
    <div className="rule-topology-container">
      <div className="rule-topology-header">
        <span className="topology-mode-badge">
          {execution_mode === 'sequence' ? '🔗 顺序模式' : '⚡ 并行模式'}
        </span>
        <span style={{ fontSize: '12px', color: '#64748b' }}>
          点击步骤查看最近10次执行历史
        </span>
      </div>

      {execution_mode === 'sequence' ? (
        <div className="topology-sequence">
          {steps.map((step, idx) => {
            const meta = STEP_TYPE_META[step.step_type] || { icon: '⚙️', label: step.step_type, color: '#64748b' };
            const status = getStepStatus(step);
            return (
              <div key={step.id} className="topology-sequence-item">
                <div
                  className={`step-node ${statusClass(status)}`}
                  onClick={() => handleStepClick(step)}
                  style={{ borderColor: meta.color }}
                >
                  <div className="step-node-icon" style={{ backgroundColor: meta.color }}>
                    {meta.icon}
                  </div>
                  <div className="step-node-info">
                    <div className="step-node-name">{step.name}</div>
                    <div className="step-node-type" style={{ color: meta.color }}>
                      {meta.label}
                    </div>
                    {step.last_execution && (
                      <div className="step-node-latency">
                        {step.last_execution.latency_ms
                          ? `${step.last_execution.latency_ms.toFixed(0)} ms`
                          : '—'}
                      </div>
                    )}
                  </div>
                  <div className="step-node-status">
                    {status === 'success' && <span style={{ color: '#22c55e', fontSize: '18px' }}>✓</span>}
                    {status === 'failed' && <span style={{ color: '#ef4444', fontSize: '18px' }}>✕</span>}
                    {status === 'pending' && <span style={{ color: '#64748b', fontSize: '18px' }}>○</span>}
                  </div>
                </div>
                {idx < steps.length - 1 && (
                  <div className="topology-arrow-sequence">
                    <div className="arrow-line"></div>
                    <div className="arrow-label">然后</div>
                    <div className="arrow-head">▼</div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="topology-parallel">
          <div className="topology-parallel-start">
            <div className="parallel-fork-icon">⚡</div>
            <div className="parallel-label">并行开始</div>
          </div>
          <div className="topology-parallel-branches">
            {steps.map((step) => {
              const meta = STEP_TYPE_META[step.step_type] || { icon: '⚙️', label: step.step_type, color: '#64748b' };
              const status = getStepStatus(step);
              return (
                <div key={step.id} className="topology-parallel-branch">
                  <div className="branch-line-top"></div>
                  <div
                    className={`step-node ${statusClass(status)}`}
                    onClick={() => handleStepClick(step)}
                    style={{ borderColor: meta.color }}
                  >
                    <div className="step-node-icon" style={{ backgroundColor: meta.color }}>
                      {meta.icon}
                    </div>
                    <div className="step-node-info">
                      <div className="step-node-name">{step.name}</div>
                      <div className="step-node-type" style={{ color: meta.color }}>
                        {meta.label}
                      </div>
                      {step.last_execution && (
                        <div className="step-node-latency">
                          {step.last_execution.latency_ms
                            ? `${step.last_execution.latency_ms.toFixed(0)} ms`
                            : '—'}
                        </div>
                      )}
                    </div>
                    <div className="step-node-status">
                      {status === 'success' && <span style={{ color: '#22c55e', fontSize: '18px' }}>✓</span>}
                      {status === 'failed' && <span style={{ color: '#ef4444', fontSize: '18px' }}>✕</span>}
                      {status === 'pending' && <span style={{ color: '#64748b', fontSize: '18px' }}>○</span>}
                    </div>
                  </div>
                  <div className="branch-line-bottom"></div>
                </div>
              );
            })}
          </div>
          <div className="topology-parallel-end">
            <div className="parallel-join-icon">⤴</div>
            <div className="parallel-label">任一通过即成功</div>
          </div>
        </div>
      )}

      {showStepHistory && selectedStep && (
        <StepHistoryModal
          step={selectedStep}
          onClose={() => {
            setShowStepHistory(false);
            setSelectedStep(null);
          }}
        />
      )}
    </div>
  );
}

export default RuleTopology;
