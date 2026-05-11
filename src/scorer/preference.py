"""
品类偏好模块

记录每个品类的好评/差评次数，计算偏好系数。
偏好系数 = 1.0 + (好评数 - 差评数) * 0.1
范围: 0.0 ~ 3.0
"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class CategoryPreference:
    """品类偏好管理"""
    
    def __init__(self, database):
        self.db = database
        self._ensure_table()
    
    def _ensure_table(self):
        """确保偏好表存在"""
        with self.db._get_conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS category_pref (
                    category TEXT PRIMARY KEY,
                    good_count INTEGER DEFAULT 0,
                    bad_count INTEGER DEFAULT 0,
                    manual_value INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
    
    def record_feedback(self, category: str, feedback_type: str):
        """记录反馈到品类统计"""
        with self.db._get_conn() as conn:
            if feedback_type == 'helpful':
                conn.execute('''
                    INSERT INTO category_pref (category, good_count) VALUES (?, 1)
                    ON CONFLICT(category) DO UPDATE SET 
                        good_count = good_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                ''', (category,))
            elif feedback_type == 'not_helpful':
                conn.execute('''
                    INSERT INTO category_pref (category, bad_count) VALUES (?, 1)
                    ON CONFLICT(category) DO UPDATE SET 
                        bad_count = bad_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                ''', (category,))
    
    def set_manual_pref(self, category: str, value: int):
        """手动设置品类偏好值 (-100 ~ +100)"""
        value = max(-100, min(100, value))
        with self.db._get_conn() as conn:
            conn.execute('''
                INSERT INTO category_pref (category, manual_value) VALUES (?, ?)
                ON CONFLICT(category) DO UPDATE SET 
                    manual_value = ?,
                    updated_at = CURRENT_TIMESTAMP
            ''', (category, value, value))
        logger.info(f"手动设置偏好: {category} = {value}")
    
    def get_pref_weight(self, category: str) -> float:
        """获取品类偏好权重
        
        计算逻辑:
        1. 如果有手动设置值，使用手动值
        2. 否则根据好评/差评统计计算
        3. 最终权重范围 0.1 ~ 2.0
        """
        with self.db._get_conn() as conn:
            row = conn.execute(
                'SELECT good_count, bad_count, manual_value FROM category_pref WHERE category = ?',
                (category,)
            ).fetchone()
        
        if not row:
            return 1.0  # 无数据，中性
        
        good_count, bad_count, manual_value = row
        
        # 手动设置优先
        if manual_value != 0:
            # manual_value -100 ~ +100 → 0.1 ~ 2.0
            return max(0.1, min(2.0, 1.0 + manual_value / 100.0))
        
        # 根据统计计算
        total = good_count + bad_count
        if total == 0:
            return 1.0
        
        # 好评率 0~1 → 权重 0.3~1.5
        good_rate = good_count / total
        return max(0.3, min(1.5, 0.3 + good_rate * 1.2))
    
    def get_all_prefs(self) -> Dict[str, Dict]:
        """获取所有品类偏好"""
        with self.db._get_conn() as conn:
            rows = conn.execute(
                'SELECT category, good_count, bad_count, manual_value FROM category_pref'
            ).fetchall()
        
        result = {}
        for row in rows:
            category, good_count, bad_count, manual_value = row
            weight = self.get_pref_weight(category)
            result[category] = {
                'good_count': good_count,
                'bad_count': bad_count,
                'manual_value': manual_value,
                'weight': round(weight, 2),
            }
        return result


# 全局实例
_pref_instance = None

def get_category_pref(database) -> CategoryPreference:
    global _pref_instance
    if _pref_instance is None:
        _pref_instance = CategoryPreference(database)
    return _pref_instance
