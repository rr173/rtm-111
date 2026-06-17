import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function MaintenanceWindowModal({ onClose, onSubmit, targets, initialData = null }) {
  const [formData, setFormData] = useState({
    target_id: '',
    title: '',
    description: '',
    start_time: '',
    end_time: '',
    reason: '',
    owner: '',
  });
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (initialData) {
      setFormData({
        target_id: initialData.target_id || '',
        title: initialData.title || '',
        description: initialData.description || '',
        start_time: formatDateTimeLocal(initialData.start_time),
        end_time: formatDateTimeLocal(initialData.end_time),
        reason: initialData.reason || '',
        owner: initialData.owner || '',
      });
    }
  }, [initialData]);

  const formatDateTimeLocal = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  const validate = () => {
    const newErrors = {};
    if (!formData.target_id) newErrors.target_id = '请选择目标';
    if (!formData.title.trim()) newErrors.title = '请输入标题';
    if (!formData.start_time) newErrors.start_time = '请选择开始时间';
    if (!formData.end_time) newErrors.end_time = '请选择结束时间';
    if (formData.start_time && formData.end_time && 
        new Date(formData.start_time) >= new Date(formData.end_time)) {
      newErrors.end_time = '结束时间必须晚于开始时间';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    setSubmitting(true);
    try {
      const payload = {
        ...formData,
        target_id: parseInt(formData.target_id),
        start_time: new Date(formData.start_time).toISOString(),
        end_time: new Date(formData.end_time).toISOString(),
        created_by: formData.owner || 'unknown',
      };

      let response;
      if (initialData && initialData.id) {
        response = await fetch(`${API_BASE}/api/maintenance-windows/${initialData.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } else {
        response = await fetch(`${API_BASE}/api/maintenance-windows`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      }

      if (response.ok) {
        const data = await response.json();
        onSubmit && onSubmit(data);
        onClose();
      } else {
        const errorData = await response.json();
        if (response.status === 409) {
          setErrors({ general: '该目标在所选时间段已有维护窗口，时间不能重叠' });
        } else {
          setErrors({ general: errorData.detail || '操作失败，请重试' });
        }
      }
    } catch (err) {
      setErrors({ general: '网络错误，请重试' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content maintenance-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{initialData ? '编辑维护窗口' : '创建维护窗口'}</h3>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          {errors.general && (
            <div className="form-error">{errors.general}</div>
          )}

          <div className="form-group">
            <label>探测目标 *</label>
            <select
              name="target_id"
              value={formData.target_id}
              onChange={handleChange}
              disabled={!!initialData}
            >
              <option value="">请选择目标</option>
              {targets.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
            {errors.target_id && <span className="field-error">{errors.target_id}</span>}
          </div>

          <div className="form-group">
            <label>标题 *</label>
            <input
              type="text"
              name="title"
              value={formData.title}
              onChange={handleChange}
              placeholder="例如：版本升级维护"
            />
            {errors.title && <span className="field-error">{errors.title}</span>}
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>开始时间 *</label>
              <input
                type="datetime-local"
                name="start_time"
                value={formData.start_time}
                onChange={handleChange}
              />
              {errors.start_time && <span className="field-error">{errors.start_time}</span>}
            </div>
            <div className="form-group">
              <label>结束时间 *</label>
              <input
                type="datetime-local"
                name="end_time"
                value={formData.end_time}
                onChange={handleChange}
              />
              {errors.end_time && <span className="field-error">{errors.end_time}</span>}
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>维护原因</label>
              <input
                type="text"
                name="reason"
                value={formData.reason}
                onChange={handleChange}
                placeholder="例如：版本发布、硬件维修"
              />
            </div>
            <div className="form-group">
              <label>负责人</label>
              <input
                type="text"
                name="owner"
                value={formData.owner}
                onChange={handleChange}
                placeholder="负责人姓名"
              />
            </div>
          </div>

          <div className="form-group">
            <label>详细描述</label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleChange}
              rows="3"
              placeholder="维护窗口的详细描述..."
            />
          </div>

          <div className="form-info">
            <p>ℹ️ 维护窗口开始后，系统将自动：</p>
            <ul>
              <li>暂停目标探测</li>
              <li>抑制该目标的所有告警</li>
            </ul>
            <p>维护窗口结束后，系统将自动：</p>
            <ul>
              <li>恢复目标探测</li>
              <li>恢复告警通知</li>
            </ul>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={submitting}>
              取消
            </button>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? '提交中...' : (initialData ? '保存修改' : '创建')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default MaintenanceWindowModal;
