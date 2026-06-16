import { useState } from 'react';

function RuleCard({ rule, type, onToggle, onDelete, onEdit }) {
  return (
    <div className={`rule-card ${!rule.enabled ? 'disabled' : ''}`}>
      <div className="rule-card-header">
        <div className="rule-card-title">
          <span className="rule-icon">
            {type === 'merge' ? '🔗' : '🚫'}
          </span>
          <div>
            <h4>{rule.name}</h4>
            <p className="rule-desc">{rule.description}</p>
          </div>
        </div>
        <div className="rule-card-actions">
          <span className="rule-priority-badge">
            优先级 {rule.priority}
          </span>
          <label className="toggle-switch">
            <input
              type="checkbox"
              checked={rule.enabled}
              onChange={() => onToggle(rule.id)}
            />
            <span className="toggle-slider"></span>
          </label>
          <button className="icon-btn" onClick={() => onEdit(rule)}>✏️</button>
          <button className="icon-btn danger" onClick={() => onDelete(rule.id)}>🗑️</button>
        </div>
      </div>
      
      <div className="rule-card-body">
        {type === 'merge' ? (
          <div className="merge-rule-info">
            <span className="info-chip">
              类型: {rule.type === 'target' ? '同一目标' : 
                     rule.type === 'group' ? '同一分组' : 
                     rule.type === 'dependency' ? '依赖链路' : '自定义'}
            </span>
            <span className="info-chip">
              时间窗口: {rule.windowSeconds}s
            </span>
          </div>
        ) : (
          <div className="suppress-conditions">
            {rule.conditions?.map((cond, idx) => (
              <span key={idx} className="condition-chip">
                {cond.field} {cond.operator} {JSON.stringify(cond.value)}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function NoiseReductionRules({ 
  mergeRules, 
  suppressionRules, 
  onUpdateMergeRules, 
  onUpdateSuppressionRules 
}) {
  const [activeTab, setActiveTab] = useState('merge');
  const [showModal, setShowModal] = useState(false);
  const [editingRule, setEditingRule] = useState(null);

  const toggleMergeRule = (ruleId) => {
    const updated = mergeRules.map(r => 
      r.id === ruleId ? { ...r, enabled: !r.enabled } : r
    );
    onUpdateMergeRules(updated);
  };

  const toggleSuppressionRule = (ruleId) => {
    const updated = suppressionRules.map(r => 
      r.id === ruleId ? { ...r, enabled: !r.enabled } : r
    );
    onUpdateSuppressionRules(updated);
  };

  const deleteMergeRule = (ruleId) => {
    if (confirm('确定删除此归并规则？')) {
      onUpdateMergeRules(mergeRules.filter(r => r.id !== ruleId));
    }
  };

  const deleteSuppressionRule = (ruleId) => {
    if (confirm('确定删除此抑制规则？')) {
      onUpdateSuppressionRules(suppressionRules.filter(r => r.id !== ruleId));
    }
  };

  const handleEdit = (rule) => {
    setEditingRule(rule);
    setShowModal(true);
  };

  const handleAddNew = () => {
    setEditingRule(null);
    setShowModal(true);
  };

  const handleSave = (rule) => {
    if (activeTab === 'merge') {
      if (editingRule) {
        onUpdateMergeRules(mergeRules.map(r => r.id === rule.id ? rule : r));
      } else {
        onUpdateMergeRules([...mergeRules, { ...rule, id: `rule-${Date.now()}` }]);
      }
    } else {
      if (editingRule) {
        onUpdateSuppressionRules(suppressionRules.map(r => r.id === rule.id ? rule : r));
      } else {
        onUpdateSuppressionRules([...suppressionRules, { ...rule, id: `suppress-${Date.now()}` }]);
      }
    }
    setShowModal(false);
    setEditingRule(null);
  };

  return (
    <div className="nr-rules">
      <div className="nr-header">
        <div className="nr-header-title">
          <h2>⚙️ 降噪规则配置</h2>
          <p className="nr-subtitle">管理告警归并和抑制规则，优先级高的规则先执行</p>
        </div>
        <button className="btn btn-primary" onClick={handleAddNew}>
          + 新建规则
        </button>
      </div>

      <div className="rules-tabs">
        <button 
          className={`rules-tab ${activeTab === 'merge' ? 'active' : ''}`}
          onClick={() => setActiveTab('merge')}
        >
          🔗 归并规则 ({mergeRules.filter(r => r.enabled).length}/{mergeRules.length})
        </button>
        <button 
          className={`rules-tab ${activeTab === 'suppress' ? 'active' : ''}`}
          onClick={() => setActiveTab('suppress')}
        >
          🚫 抑制规则 ({suppressionRules.filter(r => r.enabled).length}/{suppressionRules.length})
        </button>
      </div>

      <div className="rules-list">
        {activeTab === 'merge' ? (
          mergeRules
            .sort((a, b) => b.priority - a.priority)
            .map(rule => (
              <RuleCard
                key={rule.id}
                rule={rule}
                type="merge"
                onToggle={toggleMergeRule}
                onDelete={deleteMergeRule}
                onEdit={handleEdit}
              />
            ))
        ) : (
          suppressionRules
            .sort((a, b) => b.priority - a.priority)
            .map(rule => (
              <RuleCard
                key={rule.id}
                rule={rule}
                type="suppress"
                onToggle={toggleSuppressionRule}
                onDelete={deleteSuppressionRule}
                onEdit={handleEdit}
              />
            ))
        )}
      </div>

      {showModal && (
        <RuleEditorModal
          type={activeTab}
          rule={editingRule}
          onClose={() => { setShowModal(false); setEditingRule(null); }}
          onSave={handleSave}
        />
      )}
    </div>
  );
}

function RuleEditorModal({ type, rule, onClose, onSave }) {
  const [formData, setFormData] = useState(rule || {
    name: '',
    description: '',
    enabled: true,
    priority: 50,
    ...(type === 'merge' 
      ? { type: 'target', windowSeconds: 300 }
      : { conditions: [{ field: 'to_status', operator: 'equals', value: 'healthy' }] }
    )
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(formData);
  };

  const addCondition = () => {
    setFormData({
      ...formData,
      conditions: [...(formData.conditions || []), { field: '', operator: 'equals', value: '' }]
    });
  };

  const updateCondition = (idx, field, value) => {
    const newConditions = [...formData.conditions];
    newConditions[idx] = { ...newConditions[idx], [field]: value };
    setFormData({ ...formData, conditions: newConditions });
  };

  const removeCondition = (idx) => {
    const newConditions = formData.conditions.filter((_, i) => i !== idx);
    setFormData({ ...formData, conditions: newConditions });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal rule-editor-modal" onClick={e => e.stopPropagation()}>
        <h2>{rule ? '编辑' : '新建'}{type === 'merge' ? '归并' : '抑制'}规则</h2>
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>规则名称</label>
            <input
              type="text"
              value={formData.name}
              onChange={e => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>

          <div className="form-group">
            <label>规则描述</label>
            <input
              type="text"
              value={formData.description}
              onChange={e => setFormData({ ...formData, description: e.target.value })}
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>优先级（数值越高考前）</label>
              <input
                type="number"
                value={formData.priority}
                onChange={e => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                min="0"
                max="100"
              />
            </div>
            <div className="form-group">
              <label>启用状态</label>
              <select
                value={formData.enabled}
                onChange={e => setFormData({ ...formData, enabled: e.target.value === 'true' })}
              >
                <option value="true">启用</option>
                <option value="false">禁用</option>
              </select>
            </div>
          </div>

          {type === 'merge' ? (
            <>
              <div className="form-row">
                <div className="form-group">
                  <label>归并类型</label>
                  <select
                    value={formData.type}
                    onChange={e => setFormData({ ...formData, type: e.target.value })}
                  >
                    <option value="target">同一目标</option>
                    <option value="group">同一分组</option>
                    <option value="dependency">依赖链路</option>
                    <option value="custom">自定义</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>时间窗口（秒）</label>
                  <input
                    type="number"
                    value={formData.windowSeconds}
                    onChange={e => setFormData({ ...formData, windowSeconds: parseInt(e.target.value) })}
                    min="10"
                    max="86400"
                  />
                </div>
              </div>
            </>
          ) : (
            <div className="form-group">
              <label>
                抑制条件（全部满足时生效）
                <button 
                  type="button" 
                  className="btn btn-secondary"
                  style={{ marginLeft: '10px', padding: '2px 10px', fontSize: '12px' }}
                  onClick={addCondition}
                >
                  + 添加条件
                </button>
              </label>
              {formData.conditions?.map((cond, idx) => (
                <div key={idx} className="condition-row">
                  <select
                    value={cond.field}
                    onChange={e => updateCondition(idx, 'field', e.target.value)}
                  >
                    <option value="to_status">目标状态(to_status)</option>
                    <option value="from_status">源状态(from_status)</option>
                    <option value="target_paused">目标暂停中</option>
                    <option value="target_silenced">目标静默中</option>
                    <option value="target_group_id">目标分组ID</option>
                    <option value="target_id">目标ID</option>
                  </select>
                  <select
                    value={cond.operator}
                    onChange={e => updateCondition(idx, 'operator', e.target.value)}
                  >
                    <option value="equals">等于</option>
                    <option value="not_equals">不等于</option>
                    <option value="contains">包含</option>
                    <option value="in">在列表中</option>
                    <option value="greater_than">大于</option>
                    <option value="less_than">小于</option>
                  </select>
                  <input
                    type="text"
                    value={cond.value}
                    onChange={e => updateCondition(idx, 'value', 
                      ['true', 'false'].includes(e.target.value) 
                        ? e.target.value === 'true' 
                        : e.target.value
                    )}
                    placeholder="值 (true/false/字符串)"
                  />
                  <button 
                    type="button"
                    className="icon-btn danger"
                    onClick={() => removeCondition(idx)}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="btn btn-primary">
              保存
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default NoiseReductionRules;
