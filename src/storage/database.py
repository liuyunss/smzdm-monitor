"""
SQLite数据库存储模块
"""
import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
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
                    category TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 兼容旧数据库：添加 category 列
            try:
                cursor.execute('ALTER TABLE products ADD COLUMN category TEXT DEFAULT ""')
            except Exception:
                pass  # 列已存在
            
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
            
            # 互动数据历史表（核心：记录每次运行的互动快照）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS engagement_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    comments INTEGER DEFAULT 0,
                    collection INTEGER DEFAULT 0,
                    worthy INTEGER DEFAULT 0,
                    unworthy INTEGER DEFAULT 0,
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
                    notified_score REAL DEFAULT 0,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            ''')

            # 兼容旧数据库：添加 notified_score 列
            try:
                cursor.execute('ALTER TABLE notifications ADD COLUMN notified_score REAL DEFAULT 0')
            except Exception:
                pass
            
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
    
    def _upsert_product(self, cursor, product: Dict):
        """单条商品 UPSERT + 价格历史 + 互动快照"""
        cursor.execute('''
            INSERT INTO products
            (id, title, price, mall, url, channel_type, comments, collection, worthy, unworthy, score, category, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, price=excluded.price, mall=excluded.mall,
                url=excluded.url, channel_type=excluded.channel_type,
                comments=excluded.comments, collection=excluded.collection,
                worthy=excluded.worthy, unworthy=excluded.unworthy,
                score=excluded.score, category=excluded.category,
                updated_at=CURRENT_TIMESTAMP
        ''', (
            product['id'], product['title'], product.get('price', ''),
            product.get('mall', ''), product.get('url', ''),
            product.get('channel_type', ''), product.get('comments', 0),
            product.get('collection', 0), product.get('worthy', 0),
            product.get('unworthy', 0), product.get('score', 0),
            product.get('category', '')
        ))
        if product.get('price'):
            cursor.execute('''
                INSERT INTO price_history (product_id, price)
                VALUES (?, ?)
            ''', (product['id'], product['price']))
        cursor.execute('''
            INSERT INTO engagement_history
            (product_id, comments, collection, worthy, unworthy)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            product['id'], product.get('comments', 0),
            product.get('collection', 0), product.get('worthy', 0),
            product.get('unworthy', 0)
        ))

    def get_product(self, product_id: str) -> Optional[Dict]:
        """获取商品信息"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_price_history_batch(self, product_ids: List[str], days: int = 30) -> Dict[str, List[Dict]]:
        """批量获取价格历史（一次连接）"""
        if not product_ids:
            return {}
        with self._get_conn() as conn:
            cursor = conn.cursor()
            since = datetime.now() - timedelta(days=days)
            placeholders = ','.join('?' * len(product_ids))
            cursor.execute(f'''
                SELECT * FROM price_history
                WHERE product_id IN ({placeholders}) AND recorded_at >= ?
                ORDER BY recorded_at DESC
            ''', (*product_ids, since))
            result = {}
            for row in cursor.fetchall():
                row_dict = dict(row)
                pid = row_dict.pop('product_id', None)
                if pid:
                    result.setdefault(pid, []).append(row_dict)
            return result

    def save_notification(self, product_id: str, current_score: float = 0) -> bool:
        """保存通知记录，返回是否成功（False=已达上限或分数未增长）"""
        with self._get_conn() as conn:
            conn.execute('BEGIN EXCLUSIVE')
            cursor = conn.cursor()

            # 获取最大通知次数和最新分数
            cursor.execute('''
                SELECT MAX(notification_count) as max_count,
                       notified_score
                FROM notifications
                WHERE product_id = ?
                AND notification_count = (SELECT MAX(notification_count) FROM notifications WHERE product_id = ?)
            ''', (product_id, product_id))
            row = cursor.fetchone()

            if row and row['max_count']:
                count = row['max_count']
                last_score = row['notified_score'] or 0
                if count >= 2:
                    return False  # 已达上限
                # 第二次推送：分数需增长 >=10 分
                if current_score < last_score + 10:
                    return False
                count += 1
            else:
                count = 1

            cursor.execute('''
                INSERT INTO notifications (product_id, notification_count, notified_score)
                VALUES (?, ?, ?)
            ''', (product_id, count, current_score))

            return True

    def save_feedback(self, product_id: str, feedback_type: str, category: str = None) -> bool:
        """保存反馈记录"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO feedback (product_id, feedback_type, category)
                VALUES (?, ?, ?)
            ''', (product_id, feedback_type, category))
            return True
    
    def save_products_batch(self, products: List[Dict]):
        """批量保存商品（单次连接）"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            for product in products:
                self._upsert_product(cursor, product)
    
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
            
            # 清理旧互动历史
            cursor.execute('''
                DELETE FROM engagement_history 
                WHERE recorded_at < ?
            ''', (since,))
            
            # 注意：不清理 notifications，避免重置推送计数
            
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
