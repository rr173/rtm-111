import { useState } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

export default function CreateChangeModal({ onClose, onSubmit, targets }) {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    planned_time: new Date().toISOString().slice(0, 16),
    target_ids: [],
    notes: '',
    created_by: ''
  });
  const [searchTerm, setSearchTerm] = useState('');

  const filteredTargets = targets.filter(t =>
    t.name.toLowerCase().includes(searchTerm.toLowerCase()) && !t.paused
  );

  const handleTargetToggle = (targetId) => {
    setFormData(prev => ({
      ...prev,
      target_ids: prev.target_ids.includes(targetId)
        ? prev.target_ids.filter(id => id !== targetId)
        : [...prev.target_ids, targetId]
    }));
  };

  const handleSelectAll = () => {
    if (formData.target_ids.length === filteredTargets.length) {
      setFormData(prev => ({ ...prev, target_ids: [] }));
    } else {
      setFormData(prev => ({ ...prev, target_ids: filteredTargets.map(t => t.id) }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      alert('请输入变更名称');
      return;
    }
    if (formData.target_ids.length === 0) {
      alert('请至少选择一个目标');
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/changes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          planned_time: new Date(formData.planned_time).toISOString()
        })
      });
      if (res.ok) {
        const newChange = await res.json();
        onSubmit?.(newChange);
        onClose();
      } else {
        const error = await res.json();
        alert(error.detail || '创建失败');
      }
    } catch (e) {
      console.error('Failed to create change:', e);
      alert('创建失败');
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content large-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>📝 创建发布变更</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          <div className="form-group">
            <label>变更名称 *</label>
            <input
              type="text"
              value={formData.name}
              onChange={e => setFormData(prev => ({ ...prev, name: e.target.value }))}
              placeholder="例如：核心服务版本 v2.3.1 发布"
              className="form-input"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>计划时间 *</label>
              <input
                type="datetime-local"
                value={formData.planned_time}
                onChange={e => setFormData(prev => ({ ...prev, planned_time: e.target.value }))}
                className="form-input"
              />
            </div>
            <div className="form-group">
              <label>创建人</label>
              <input
                type="text"
                value={formData.created_by}
                onChange={e => setFormData(prev => ({ ...prev, created_by: e.target.value }))}
                placeholder="您的姓名或团队"
                className="form-input"
              />
            </div>
          </div>

          <div className="form-group">
            <label>变更描述</label>
            <textarea
              value={formData.description}
              onChange={e => setFormData(prev => ({ ...prev, description: e.target.value }))}
              placeholder="简要描述本次变更的内容、目的..."
              className="form-textarea"
              rows={2}
            />
          </div>

          <div className="form-group">
            <label>涉及目标 * ({formData.target_ids.length} 个已选)</label>
            <div className="target-search-box">
              <input
                type="text"
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                placeholder="搜索目标..."
                className="form-input"
              />
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleSelectAll}
              >
                {formData.target_ids.length === filteredTargets.length ? '取消全选' : '全选'}
              </button>
            </div>
            <div className="target-selection-list">
              {filteredTargets.map(target => (
                <label
                  key={target.id}
                  className={`target-select-item ${formData.target_ids.includes(target.id) ? 'selected' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={formData.target_ids.includes(target.id)}
                    onChange={() => handleTargetToggle(target.id)}
                  />
                  <span className={`status-indicator status-${target.status}`}></span>
                  <span className="target-name">{target.name}</span>
                  <span className="target-type-badge">{target.type}</span>
                </label>
              ))}
              {filteredTargets.length === 0 && (
                <div className="empty-state">没有找到匹配的目标</div>
              )}
            </div>
          </div>

          <div className="form-group">
            <label>备注</label>
            <textarea
              value={formData.notes}
              onChange={e => setFormData(prev => ({ ...prev, notes: e.target.value }))}
              placeholder="其他需要记录的信息..."
              className="form-textarea"
              rows={2}
            />
          </div>

          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="btn btn-primary">
              创建变更
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
