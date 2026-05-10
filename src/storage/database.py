"""
SQLite数据库存储模块
"""
import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager

class Database:
    """SQLite数据库管理器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_dir()
        self._init_tables()
    
    def _ensure_dir(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    
    @contextmanager
    def _get_conn(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_tables(self):
        """初始化数据库表"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # 商品表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    price TEXT,
                    mall TEXT,
                    url TEXT,
                    channel_type TEXT,
                    comments INTEGER DEFAULT 0,
                    collection INTEGER DEFAULT 0,
                    worthy INTEGER DEFAULT 0,
                    unworthy INTEGER DEFAULT 0,
                    score REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 价格历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    price TEXT,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            ''')
            
            # 通知记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notification_count INTEGER DEFAULT 1,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            ''')
            
            # 反馈记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,
                    category TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            ''')
            
            # 代理使用记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS proxy_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proxy TEXT NOT NULL,
                    success BOOLEAN DEFAULT 1,
                    response_time REAL,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
    
    def product_exists(self, product_id: str) -> bool:
        """检查商品是否存在"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM products WHERE id = ?', (product_id,))
            return cursor.fetchone() is not None
    
    def save_product(self, product: Dict) -> bool:
        """保存商品信息"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO products 
                (id, title, price, mall, url, channel_type, comments, collection, worthy, unworthy, score, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                product['id'],
                product['title'],
                product.get('price', ''),
                product.get('mall', ''),
                product.get('url', ''),
                product.get('channel_type', ''),
                product.get('comments', 0),
                product.get('collection', 0),
                product.get('worthy', 0),
                product.get('unworthy', 0),
                product.get('score', 0)
            ))
            
            # 记录价格历史
            if product.get('price'):
                cursor.execute('''
                    INSERT INTO price_history (product_id, price)
                    VALUES (?, ?)
                ''', (product['id'], product['price']))
            
            return True
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        """获取商品信息"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_price_history(self, product_id: str, days: int = 30) -> List[Dict]:
        """获取价格历史"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            since = datetime.now() - timedelta(days=days)
            cursor.execute('''
                SELECT * FROM price_history 
                WHERE product_id = ? AND recorded_at >= ?
                ORDER BY recorded_at DESC
            ''', (product_id, since))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_lowest_price(self, product_id: str) -> Optional[str]:
        """获取历史最低价"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT MIN(CAST(price AS REAL)) as lowest_price
                FROM price_history 
                WHERE product_id = ? AND price != ''
            ''', (product_id,))
            row = cursor.fetchone()
            return str(row['lowest_price']) if row and row['lowest_price'] else None
    
    def save_notification(self, product_id: str) -> bool:
        """保存通知记录"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # 检查已通知次数
            cursor.execute('''
                SELECT COUNT(*) as count
                FROM notifications 
                WHERE product_id = ?
            ''', (product_id,))
            count = cursor.fetchone()['count']
            
            if count >= 2:  # 最多通知2次
                return False
            
            cursor.execute('''
                INSERT INTO notifications (product_id, notification_count)
                VALUES (?, ?)
            ''', (product_id, count + 1))
            
            return True
    
    def get_notification_count(self, product_id: str) -> int:
        """获取已通知次数"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COALESCE(MAX(notification_count), 0) as count
                FROM notifications 
                WHERE product_id = ?
            ''', (product_id,))
            return cursor.fetchone()['count']
    
    def save_feedback(self, product_id: str, feedback_type: str, category: str = None) -> bool:
        """保存反馈记录"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO feedback (product_id, feedback_type, category)
                VALUES (?, ?, ?)
            ''', (product_id, feedback_type, category))
            return True
    
    def get_feedback_stats(self, category: str = None) -> Dict:
        """获取反馈统计"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            if category:
                cursor.execute('''
                    SELECT 
                        feedback_type,
                        COUNT(*) as count
                    FROM feedback 
                    WHERE category = ?
                    GROUP BY feedback_type
                ''', (category,))
            else:
                cursor.execute('''
                    SELECT 
                        feedback_type,
                        COUNT(*) as count
                    FROM feedback 
                    GROUP BY feedback_type
                ''')
            
            return {row['feedback_type']: row['count'] for row in cursor.fetchall()}
    
    def save_proxy_usage(self, proxy: str, success: bool, response_time: float = 0):
        """保存代理使用记录"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO proxy_usage (proxy, success, response_time)
                VALUES (?, ?, ?)
            ''', (proxy, success, response_time))
    
    def get_proxy_stats(self, proxy: str) -> Dict:
        """获取代理统计"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as fail_count,
                    AVG(response_time) as avg_response_time
                FROM proxy_usage 
                WHERE proxy = ?
            ''', (proxy,))
            row = cursor.fetchone()
            return {
                'success': row['success_count'] or 0,
                'fail': row['fail_count'] or 0,
                'avg_time': row['avg_response_time'] or 0
            }
    
    def cleanup_old_data(self, days: int = 30):
        """清理旧数据"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            since = datetime.now() - timedelta(days=days)
            
            # 清理旧价格历史
            cursor.execute('''
                DELETE FROM price_history 
                WHERE recorded_at < ?
            ''', (since,))
            
            # 清理旧通知记录
            cursor.execute('''
                DELETE FROM notifications 
                WHERE notified_at < ?
            ''', (since,))
            
            # 清理旧代理使用记录
            cursor.execute('''
                DELETE FROM proxy_usage 
                WHERE used_at < ?
            ''', (since,))

# 全局数据库实例
_db_instance = None

def get_db(db_path: str = None) -> Database:
    """获取全局数据库实例"""
    global _db_instance
    if _db_instance is None:
        if db_path is None:
            from src.config.loader import get_config
            config = get_config()
            db_path = config.get('storage', 'db_path', default='./data/smzdm.db')
        _db_instance = Database(db_path)
    return _db_instance
