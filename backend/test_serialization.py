from datetime import datetime
from app.database import SessionLocal
from app.models import ProbeTarget
from app.audit_engine import audit_engine

db = SessionLocal()

try:
    target = db.query(ProbeTarget).first()
    if target:
        print(f'Testing with target: {target.name} (id={target.id})')
        
        old_data = {c.name: getattr(target, c.name) for c in target.__table__.columns}
        print(f'Old data keys: {list(old_data.keys())}')
        
        try:
            serialized = audit_engine._serialize_value(old_data)
            print(f'Serialization successful!')
            print(f'Serialized keys: {list(serialized.keys())}')
            print(f'created_at type: {type(serialized.get("created_at"))}')
            print(f'created_at value: {serialized.get("created_at")}')
        except Exception as e:
            print(f'Serialization failed: {e}')
            import traceback
            traceback.print_exc()
    else:
        print('No target found')
finally:
    db.close()
