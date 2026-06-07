import { useState } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

const COLOR_OPTIONS = [
  '#ef4444',
  '#f97316',
  '#eab308',
  '#22c55e',
  '#06b6d4',
  '#3b82f6',
  '#8b5cf6',
  '#ec4899',
  '#64748b'
];

function AddGroupModal({ onClose, onSubmit }) {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    color: '#3b82f6',
    degrade_threshold: 2,
    down_threshold: 5,
    success_threshold: 3
  });
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      alert('请输入分组名称');
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/groups`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
      if (res.ok) {
        const newGroup = await res.json();
        if (onSubmit) onSubmit(newGroup);
        onClose();
      } else {
        alert('创建分组失败');
      }
    } catch (e) {
      console.error('Failed to create group:', e);
      alert('创建分组失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>添加分组</h2>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>分组名称 *</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              placeholder="例如：生产环境"
              autoFocus
            />
          </div>

          <div className="form-group">
            <label>描述</label>
            <input
              type="text"
              value={formData.description}
              onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
              placeholder="可选，分组说明"
            />
          </div>

          <div className="form-group">
            <label>标识颜色</label>
            <div className="color-picker">
              {COLOR_OPTIONS.map(color => (
                <button
                  key={color}
                  type="button"
                  className={`color-option ${formData.color === color ? 'selected' : ''}`}
                  style={{ backgroundColor: color }}
                  onClick={() => setFormData(prev => ({ ...prev, color }))}
                />
              ))}
            </div>
          </div>

          <h3 style={{ fontSize: '14px', marginTop: '20px', marginBottom: '12px', color: '#cbd5e1' }}>
            告警阈值
          </h3>

          <div className="form-row">
            <div className="form-group">
              <label>降级阈值</label>
              <input
                type="number"
                min="1"
                max="100"
                value={formData.degrade_threshold}
                onChange={(e) => setFormData(prev => ({
                  ...prev,
                  degrade_threshold: parseInt(e.target.value) || 1
                }))}
              />
              <span className="form-hint">连续失败次数</span>
            </div>
            <div className="form-group">
              <label>故障阈值</label>
              <input
                type="number"
                min="1"
                max="100"
                value={formData.down_threshold}
                onChange={(e) => setFormData(prev => ({
                  ...prev,
                  down_threshold: parseInt(e.target.value) || 1
                }))}
              />
              <span className="form-hint">连续失败次数</span>
            </div>
          </div>

          <div className="form-group">
            <label>恢复阈值</label>
            <input
              type="number"
              min="1"
              max="100"
              value={formData.success_threshold}
              onChange={(e) => setFormData(prev => ({
                ...prev,
                success_threshold: parseInt(e.target.value) || 1
              }))}
            />
            <span className="form-hint">连续成功次数后恢复健康</span>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? '创建中...' : '创建分组'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default AddGroupModal;
