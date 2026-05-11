"""清理30天以上的旧数据"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.loader import get_config
from src.storage.database import get_db

config = get_config()
db_path = config.get('storage', 'db_path', default='./data/smzdm.db')
db = get_db(db_path)

retention = config.get('storage', 'retention_days', default=30)
db.cleanup_old_data(retention)
print(f"已清理 {retention} 天前的旧数据")
