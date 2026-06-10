import { useState, useEffect, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

const STEP_TYPES = [
  { value: 'http_status', label: 'HTTP状态码检查', icon: '📡' },
  { value: 'http_body_match', label: 'HTTP响应体匹配', icon: '📝' },
  { value: 'tcp_connect', label: 'TCP连通性', icon: '🔌' },
  { value: 'dns_resolve', label: 'DNS解析', icon: '🌐' },
  { value: 'latency_threshold', label: '延迟阈值检查', icon: '⏱️' },
];

const MATCH_MODES = [
  { value: 'contains', label: '包含所有关键词' },
  { value: 'contains_any', label: '包含任一关键词' },
  { value: 'regex', label: '正则匹配' },
  { value: 'not_contains', label: '不包含关键词' },
];

function StepEditor({ step, index, onUpdate, onDelete, onMoveUp, onMoveDown, isFirst, isLast }) {
  const stepType = STEP_TYPES.find(t => t.value === step.step_type);

  const handleFieldChange = (field, value) => {
    onUpdate(index, { ...step, [field]: value });
  };

  const handleConfigChange = (key, value) => {
    onUpdate(index, { ...step, config: { ...step.config, [key]: value } });
  };

  const handleConditionChange = (key, value) => {
    onUpdate(index, { ...step, pass_condition: { ...step.pass_condition, [key]: value } });
  };

  return (
    <div className="rule-step-card">
      <div className="rule-step-header">
        <div className="rule-step-header-left">
          <span className="step-order-badge">{index + 1}</span>
          <span className="step-type-icon">{stepType?.icon || '⚙️'}</span>
          <input
            type="text"
            className="step-name-input"
            value={step.name}
            onChange={(e) => handleFieldChange('name', e.target.value)}
            placeholder="步骤名称"
          />
        </div>
        <div className="rule-step-header-right">
          <button
            className="step-move-btn"
            onClick={onMoveUp}
            disabled={isFirst}
            title="上移"
          >
            ↑
          </button>
          <button
            className="step-move-btn"
            onClick={onMoveDown}
            disabled={isLast}
            title="下移"
          >
            ↓
          </button>
          <button
            className="step-delete-btn"
            onClick={onDelete}
            title="删除步骤"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="rule-step-body">
        <div className="form-row">
          <div className="form-group">
            <label>步骤类型</label>
            <select
              value={step.step_type}
              onChange={(e) => handleFieldChange('step_type', e.target.value)}
            >
              {STEP_TYPES.map(t => (
                <option key={t.value} value={t.value}>
                  {t.icon} {t.label}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>超时时间（秒）</label>
            <input
              type="number"
              min="1"
              max="120"
              value={step.timeout}
              onChange={(e) => handleFieldChange('timeout', Number(e.target.value))}
            />
          </div>
        </div>

        {step.step_type === 'http_status' && (
          <>
            <div className="form-row">
              <div className="form-group" style={{ flex: 2 }}>
                <label>URL 地址</label>
                <input
                  type="text"
                  placeholder="https://example.com/api/health"
                  value={step.config?.url || ''}
                  onChange={(e) => handleConfigChange('url', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>请求方法</label>
                <select
                  value={step.config?.method || 'GET'}
                  onChange={(e) => handleConfigChange('method', e.target.value)}
                >
                  <option value="GET">GET</option>
                  <option value="POST">POST</option>
                  <option value="HEAD">HEAD</option>
                </select>
              </div>
            </div>
            <div className="form-group">
              <label>期望状态码（多个用逗号分隔，支持范围如 200-399）</label>
              <input
                type="text"
                placeholder="200,201,200-399"
                value={(step.pass_condition?.expected_codes || []).join(',')}
                onChange={(e) => handleConditionChange('expected_codes', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
              />
            </div>
            <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <label style={{ marginBottom: 0 }}>
                <input
                  type="checkbox"
                  checked={step.config?.follow_redirects || false}
                  onChange={(e) => handleConfigChange('follow_redirects', e.target.checked)}
                  style={{ width: 'auto', marginRight: '6px' }}
                />
                跟随重定向
              </label>
            </div>
          </>
        )}

        {step.step_type === 'http_body_match' && (
          <>
            <div className="form-row">
              <div className="form-group" style={{ flex: 2 }}>
                <label>URL 地址</label>
                <input
                  type="text"
                  placeholder="https://example.com"
                  value={step.config?.url || ''}
                  onChange={(e) => handleConfigChange('url', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>请求方法</label>
                <select
                  value={step.config?.method || 'GET'}
                  onChange={(e) => handleConfigChange('method', e.target.value)}
                >
                  <option value="GET">GET</option>
                  <option value="POST">POST</option>
                </select>
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>匹配模式</label>
                <select
                  value={step.pass_condition?.mode || 'contains'}
                  onChange={(e) => handleConditionChange('mode', e.target.value)}
                >
                  {MATCH_MODES.map(m => (
                    <option key={m.value} value={m.value}>{m.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label>关键词/模式（多个用英文逗号分隔）</label>
              <input
                type="text"
                placeholder="关键词1,关键词2,正则表达式"
                value={(step.pass_condition?.patterns || []).join(',')}
                onChange={(e) => handleConditionChange('patterns', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
              />
            </div>
          </>
        )}

        {step.step_type === 'tcp_connect' && (
          <div className="form-group">
            <label>目标地址（host:port）</label>
            <input
              type="text"
              placeholder="example.com:3306"
              value={step.config?.address || ''}
              onChange={(e) => handleConfigChange('address', e.target.value)}
            />
          </div>
        )}

        {step.step_type === 'dns_resolve' && (
          <>
            <div className="form-group">
              <label>要解析的域名</label>
              <input
                type="text"
                placeholder="example.com"
                value={step.config?.domain || ''}
                onChange={(e) => handleConfigChange('domain', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>期望IP（可选，多个逗号分隔，留空则只要能解析成功）</label>
              <input
                type="text"
                placeholder="1.1.1.1,8.8.8.8"
                value={(step.pass_condition?.expected_ips || []).join(',')}
                onChange={(e) => handleConditionChange('expected_ips', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
              />
            </div>
          </>
        )}

        {step.step_type === 'latency_threshold' && (
          <>
            <div className="form-row">
              <div className="form-group">
                <label>内嵌探测类型</label>
                <select
                  value={step.config?.step_type || 'http_status'}
                  onChange={(e) => handleConfigChange('step_type', e.target.value)}
                >
                  <option value="http_status">HTTP状态码</option>
                  <option value="tcp_connect">TCP连通</option>
                </select>
              </div>
              <div className="form-group">
                <label>最大允许延迟（ms）</label>
                <input
                  type="number"
                  min="10"
                  max="60000"
                  value={step.pass_condition?.max_latency_ms || 1000}
                  onChange={(e) => handleConditionChange('max_latency_ms', Number(e.target.value))}
                />
              </div>
            </div>
            {step.config?.step_type === 'http_status' && (
              <div className="form-group">
                <label>URL 地址</label>
                <input
                  type="text"
                  placeholder="https://example.com/api"
                  value={step.config?.config?.url || ''}
                  onChange={(e) => {
                    const current = step.config?.config || {};
                    handleConfigChange('config', { ...current, url: e.target.value });
                  }}
                />
              </div>
            )}
            {step.config?.step_type === 'tcp_connect' && (
              <div className="form-group">
                <label>目标地址（host:port）</label>
                <input
                  type="text"
                  placeholder="example.com:443"
                  value={step.config?.config?.address || ''}
                  onChange={(e) => {
                    const current = step.config?.config || {};
                    handleConfigChange('config', { ...current, address: e.target.value });
                  }}
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function RuleEditor({ onClose }) {
  const [rules, setRules] = useState([]);
  const [selectedRule, setSelectedRule] = useState(null);
  const [editMode, setEditMode] = useState('list');
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    execution_mode: 'sequence',
    steps: [],
  });
  const [loading, setLoading] = useState(false);

  const loadRules = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/rules`);
      if (res.ok) {
        const data = await res.json();
        setRules(data);
      }
    } catch (e) {
      console.error('Failed to load rules:', e);
    }
  }, []);

  useEffect(() => {
    loadRules();
  }, [loadRules]);

  const startCreate = () => {
    setFormData({
      name: '',
      description: '',
      execution_mode: 'sequence',
      steps: [],
    });
    setSelectedRule(null);
    setEditMode('edit');
  };

  const startEdit = (rule) => {
    const currentVer = rule.versions?.[0];
    setFormData({
      name: rule.name,
      description: rule.description || '',
      execution_mode: currentVer?.execution_mode || 'sequence',
      steps: (currentVer?.steps || []).map(s => ({
        step_order: s.step_order,
        name: s.name,
        step_type: s.step_type,
        config: s.config || {},
        timeout: s.timeout,
        pass_condition: s.pass_condition || {},
      })),
    });
    setSelectedRule(rule);
    setEditMode('edit');
  };

  const backToList = () => {
    setEditMode('list');
    setSelectedRule(null);
  };

  const addStep = () => {
    const newStep = {
      step_order: formData.steps.length,
      name: `新步骤 ${formData.steps.length + 1}`,
      step_type: 'http_status',
      config: {},
      timeout: 5,
      pass_condition: {},
    };
    setFormData({ ...formData, steps: [...formData.steps, newStep] });
  };

  const updateStep = (index, updated) => {
    const steps = [...formData.steps];
    steps[index] = updated;
    setFormData({ ...formData, steps });
  };

  const deleteStep = (index) => {
    const steps = formData.steps.filter((_, i) => i !== index);
    steps.forEach((s, i) => s.step_order = i);
    setFormData({ ...formData, steps });
  };

  const moveStepUp = (index) => {
    if (index === 0) return;
    const steps = [...formData.steps];
    [steps[index - 1], steps[index]] = [steps[index], steps[index - 1]];
    steps.forEach((s, i) => s.step_order = i);
    setFormData({ ...formData, steps });
  };

  const moveStepDown = (index) => {
    if (index === formData.steps.length - 1) return;
    const steps = [...formData.steps];
    [steps[index], steps[index + 1]] = [steps[index + 1], steps[index]];
    steps.forEach((s, i) => s.step_order = i);
    setFormData({ ...formData, steps });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name.trim()) return;
    setLoading(true);

    try {
      const data = { ...formData };
      if (data.steps.length === 0) {
        delete data.steps;
      }

      let url, method;
      if (selectedRule) {
        url = `${API_BASE}/api/rules/${selectedRule.id}`;
        method = 'PUT';
      } else {
        url = `${API_BASE}/api/rules`;
        method = 'POST';
      }

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });

      if (res.ok) {
        await loadRules();
        backToList();
      }
    } catch (e) {
      console.error('Failed to save rule:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (rule) => {
    if (!confirm(`确定删除规则 "${rule.name}" 吗？绑定此规则的目标将解绑。`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/rules/${rule.id}`, { method: 'DELETE' });
      if (res.ok) {
        await loadRules();
      }
    } catch (e) {
      console.error('Failed to delete rule:', e);
    }
  };

  if (editMode === 'edit') {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal rule-editor-modal" onClick={e => e.stopPropagation()}>
          <div className="rule-editor-header">
            <button className="back-btn" onClick={backToList}>← 返回列表</button>
            <h2>{selectedRule ? '编辑规则' : '新建规则'}</h2>
            <div style={{ width: '100px' }}></div>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="rule-basic-info">
              <div className="form-row">
                <div className="form-group" style={{ flex: 2 }}>
                  <label>规则名称 *</label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="例如：Web应用完整健康检查"
                  />
                </div>
                <div className="form-group">
                  <label>编排模式</label>
                  <select
                    value={formData.execution_mode}
                    onChange={(e) => setFormData({ ...formData, execution_mode: e.target.value })}
                  >
                    <option value="sequence">🔗 顺序执行（全部通过）</option>
                    <option value="parallel">⚡ 并行执行（任一通过）</option>
                  </select>
                </div>
              </div>
              <div className="form-group">
                <label>规则描述</label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="描述此规则的用途"
                />
              </div>
              <div className="mode-hint">
                {formData.execution_mode === 'sequence' ? (
                  <span>🔗 <strong>顺序模式</strong>：步骤按顺序执行，前一步失败则立即终止并报错</span>
                ) : (
                  <span>⚡ <strong>并行模式</strong>：所有步骤同时执行，任一通过则判定为成功，否则失败</span>
                )}
              </div>
            </div>

            <div className="rule-steps-section">
              <div className="rule-steps-header">
                <h3>探测步骤 ({formData.steps.length})</h3>
                <button type="button" className="add-step-btn" onClick={addStep}>
                  + 添加步骤
                </button>
              </div>

              {formData.steps.length === 0 ? (
                <div className="empty-steps">
                  <div className="empty-steps-icon">📋</div>
                  <p>还没有步骤，点击上方按钮添加第一个步骤</p>
                </div>
              ) : (
                <div className="rule-steps-flow">
                  {formData.steps.map((step, idx) => (
                    <div key={idx} className="step-with-connector">
                      <StepEditor
                        step={step}
                        index={idx}
                        onUpdate={updateStep}
                        onDelete={() => deleteStep(idx)}
                        onMoveUp={() => moveStepUp(idx)}
                        onMoveDown={() => moveStepDown(idx)}
                        isFirst={idx === 0}
                        isLast={idx === formData.steps.length - 1}
                      />
                      {idx < formData.steps.length - 1 && (
                        <div className="step-connector">
                          {formData.execution_mode === 'sequence' ? '↓ 然后' : '⇅ 并行'}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={backToList}>
                取消
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading || !formData.name.trim()}
              >
                {loading ? '保存中...' : (selectedRule ? '保存（自动创建新版本）' : '创建规则')}
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal rule-list-modal" onClick={e => e.stopPropagation()}>
        <div className="rule-editor-header">
          <h2>📋 探测规则管理</h2>
          <div className="rule-list-actions">
            <button className="btn btn-primary" onClick={startCreate}>
              + 新建规则
            </button>
            <button className="btn btn-secondary" onClick={onClose}>
              关闭
            </button>
          </div>
        </div>

        <div className="rule-list">
          {rules.length === 0 ? (
            <div className="empty-text">
              还没有任何规则，点击"新建规则"开始创建
            </div>
          ) : (
            rules.map(rule => (
              <div key={rule.id} className="rule-list-card">
                <div className="rule-card-header">
                  <div className="rule-card-info">
                    <h3 className="rule-card-name">{rule.name}</h3>
                    {rule.description && (
                      <p className="rule-card-desc">{rule.description}</p>
                    )}
                  </div>
                  <div className="rule-card-tags">
                    <span className={`tag mode-tag ${rule.execution_mode}`}>
                      {rule.execution_mode === 'sequence' ? '🔗 顺序' : '⚡ 并行'}
                    </span>
                    <span className="tag version-tag">
                      v{rule.current_version || 1}
                    </span>
                    <span className="tag binding-tag">
                      🎯 {rule.bound_target_count} 个目标
                    </span>
                  </div>
                </div>
                <div className="rule-card-steps">
                  {(rule.versions?.[0]?.steps || []).map((s, i) => (
                    <span key={i} className={`step-chip ${STEP_TYPES.find(t => t.value === s.step_type) ? 'known' : 'unknown'}`}>
                      {s.name}
                      <span className="step-type-mini">
                        {STEP_TYPES.find(t => t.value === s.step_type)?.icon || '?'}
                      </span>
                    </span>
                  ))}
                  {(!rule.versions || !rule.versions[0]?.steps?.length) && (
                    <span className="empty-steps-mini">无步骤</span>
                  )}
                </div>
                <div className="rule-card-actions">
                  <button className="action-btn" onClick={() => startEdit(rule)}>
                    ✏️ 编辑
                  </button>
                  <button
                    className="action-btn danger"
                    onClick={() => handleDelete(rule)}
                  >
                    🗑️ 删除
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default RuleEditor;
