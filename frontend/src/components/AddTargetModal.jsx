import { useState } from 'react';

function AddTargetModal({ onClose, onSubmit, groups = [] }) {
  const [formData, setFormData] = useState({
    name: '',
    type: 'http',
    address: '',
    group_id: '',
    interval: 30,
    timeout: 5,
    expected_status: '200'
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    let parsedValue = value;
    if (name === 'interval' || name === 'timeout') {
      parsedValue = Number(value);
    } else if (name === 'group_id') {
      parsedValue = value === '' ? null : Number(value);
    }
    setFormData(prev => ({
      ...prev,
      [name]: parsedValue
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name || !formData.address) return;

    const data = { ...formData };
    if (formData.type === 'tcp') {
      delete data.expected_status;
    }
    if (data.group_id === null) {
      delete data.group_id;
    }
    onSubmit(data);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2>添加探测目标</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>目标名称</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              placeholder="例如：网站首页"
              required
            />
          </div>

          {groups.length > 0 && (
            <div className="form-group">
              <label>所属分组</label>
              <select
                name="group_id"
                value={formData.group_id === null ? '' : formData.group_id}
                onChange={handleChange}
              >
                <option value="">未分组</option>
                {groups.map(group => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="form-row">
            <div className="form-group">
              <label>类型</label>
              <select
                name="type"
                value={formData.type}
                onChange={handleChange}
              >
                <option value="http">HTTP</option>
                <option value="tcp">TCP</option>
              </select>
            </div>
            <div className="form-group">
              <label>超时时间 (秒)</label>
              <input
                type="number"
                name="timeout"
                min="1"
                max="60"
                value={formData.timeout}
                onChange={handleChange}
              />
            </div>
          </div>

          <div className="form-group">
            <label>{formData.type === 'http' ? 'URL 地址' : '地址 (host:port)'}</label>
            <input
              type="text"
              name="address"
              value={formData.address}
              placeholder={formData.type === 'http' ? 'https://example.com' : 'example.com:80'}
              required
            />
          </div>

          {formData.type === 'http' && (
            <div className="form-group">
              <label>期望状态码</label>
              <input
                type="text"
                name="expected_status"
                value={formData.expected_status}
                onChange={handleChange}
                placeholder="200,201 或 200-399"
              />
            </div>
          )}

          <div className="form-group">
            <label>探测间隔 (秒)</label>
            <input
              type="range"
              name="interval"
              min="5"
              max="300"
              value={formData.interval}
              onChange={handleChange}
              style={{ width: '100%' }}
            />
            <div style={{ fontSize: '12px', color: '#64748b', textAlign: 'center' }}>
              {formData.interval} 秒
            </div>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="btn btn-primary">
              添加
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default AddTargetModal;
