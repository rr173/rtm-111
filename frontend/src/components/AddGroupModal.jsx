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
    success_threshold: 3,
    adaptive_enabled: false,
    slow_interval: 60,
    fast_interval: 5,
    silent_start: '',
    silent_end: ''
  });
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      alert('请输入分组名称');
      return;
    }

    const submitData = { ...formData };
    if (!submitData.silent_start || !submitData.silent_end) {
      delete submitData.silent_start;
      delete submitData.silent_end;
    }
    if (!submitData.adaptive_enabled) {
      delete submitData.slow_interval;
      delete submitData.fast_interval;
    }

    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/groups`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(submitData)
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

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    let parsedValue = value;
    if (type === 'checkbox') {
      parsedValue = checked;
    } else if (['degrade_threshold', 'down_threshold', 'success_threshold', 'slow_interval', 'fast_interval'].includes(name)) {
      parsedValue = parseInt(value) || 1;
    }
    setFormData(prev => ({ ...prev, [name]: parsedValue }));
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
              name="name"
              value={formData.name}
              onChange={handleChange}
              placeholder="例如：生产环境"
              autoFocus
            />
          </div>

          <div className="form-group">
            <label>描述</label>
            <input
              type="text"
              name="description"
              value={formData.description}
              onChange={handleChange}
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
                name="degrade_threshold"
                min="1"
                max="100"
                value={formData.degrade_threshold}
                onChange={handleChange}
              />
              <span className="form-hint">连续失败次数</span>
            </div>
            <div className="form-group">
              <label>故障阈值</label>
              <input
                type="number"
                name="down_threshold"
                min="1"
                max="100"
                value={formData.down_threshold}
                onChange={handleChange}
              />
              <span className="form-hint">连续失败次数</span>
            </div>
          </div>

          <div className="form-group">
            <label>恢复阈值</label>
            <input
              type="number"
              name="success_threshold"
              min="1"
              max="100"
              value={formData.success_threshold}
              onChange={handleChange}
            />
            <span className="form-hint">连续成功次数后恢复健康</span>
          </div>

          <h3 style={{ fontSize: '14px', marginTop: '20px', marginBottom: '12px', color: '#cbd5e1' }}>
            探测策略
          </h3>

          <div className="form-group">
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                name="adaptive_enabled"
                checked={formData.adaptive_enabled}
                onChange={handleChange}
                style={{ width: 'auto' }}
              />
              启用自适应探测间隔
            </label>
            <span className="form-hint">健康时慢速探测节省资源，异常时快速探测确认故障</span>
          </div>

          {formData.adaptive_enabled && (
            <div className="form-row">
              <div className="form-group">
                <label>慢速间隔 (秒)</label>
                <input
                  type="number"
                  name="slow_interval"
                  min="5"
                  max="600"
                  value={formData.slow_interval}
                  onChange={handleChange}
                />
                <span className="form-hint">健康/故障确认后使用</span>
              </div>
              <div className="form-group">
                <label>快速间隔 (秒)</label>
                <input
                  type="number"
                  name="fast_interval"
                  min="1"
                  max="120"
                  value={formData.fast_interval}
                  onChange={handleChange}
                />
                <span className="form-hint">异常检测时使用</span>
              </div>
            </div>
          )}

          <div className="form-group">
            <label>静默时段</label>
            <div className="form-row">
              <div className="form-group" style={{ marginBottom: 0 }}>
                <input
                  type="time"
                  name="silent_start"
                  value={formData.silent_start}
                  onChange={handleChange}
                />
                <span className="form-hint">开始时间 (UTC)</span>
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <input
                  type="time"
                  name="silent_end"
                  value={formData.silent_end}
                  onChange={handleChange}
                />
                <span className="form-hint">结束时间 (UTC)</span>
              </div>
            </div>
            <span className="form-hint">静默时段内暂停探测且不产生告警</span>
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
