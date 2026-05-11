"""
评分算法模块

核心逻辑：
1. 基于当前互动量直接评分（评论/收藏/值/不值）
2. 结合价格优势
3. 品类偏好加权（根据用户反馈学习）
"""
import logging
import math
import re
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class Scorer:
    """商品评分器（基于绝对互动量）"""
    
    def __init__(self, config: Dict, category_pref=None):
        self.config = config
        self.category_pref = category_pref
        self._load_config()
        self._load_filters()
    
    def _load_config(self):
        """加载评分配置"""
        weights = self.config.get('weights', {})
        self.weight_comments = weights.get('comments', 3)
        self.weight_collection = weights.get('collection', 2)
        self.weight_worthy = weights.get('worthy', 1)
        self.weight_unworthy = weights.get('unworthy', -0.5)
        self.weight_price = weights.get('price', 0.15)
        
        self.min_age_hours = self.config.get('min_age_hours', 1)
        self.scale = self.config.get('scale', 14) if self.config else 14
    
    def _load_filters(self):
        filters = self.config.get('filters', {}) if self.config else {}
        self.min_worthy = filters.get('min_worthy', 15)
    
    def calculate_score(self, product: Dict, price_history: List[Dict] = None) -> float:
        """计算商品综合评分（含品类偏好加权）"""
        # 太新的商品不评分
        age_hours = product.get('age_hours', 0)
        if age_hours < self.min_age_hours:
            return 0
        
        # 互动量得分（0-100）
        engagement_score = self._calc_engagement_score(product)
        
        # 价格优势得分（0-100）
        price_score = self._calc_price_score(product, price_history)
        
        # 综合分 = 互动量 * 85% + 价格 * 15%
        base_score = (
            engagement_score * (1 - self.weight_price) +
            price_score * self.weight_price
        )
        
        # 品类偏好加权
        if self.category_pref:
            category = product.get('category', '其他')
            weight = self.category_pref.get_pref_weight(category)
            base_score *= weight
        
        return round(base_score, 2)
    
    def _calc_engagement_score(self, product: Dict) -> float:
        """计算互动量得分（0-100）
        总互动<10 直接返回0（互动太少不可靠）
        """
        comments = product.get('comments', 0)
        collection = product.get('collection', 0)
        worthy = product.get('worthy', 0)
        unworthy = product.get('unworthy', 0)

        # 最低门槛：只看值（核心正向信号）
        if worthy < self.min_worthy:
            return 0

        # 值是核心正向信号，值比收藏或评论低说明有问题
        if worthy < collection or worthy < comments:
            return 0

        # 加权互动值
        value = (
            comments * self.weight_comments +
            collection * self.weight_collection +
            worthy * self.weight_worthy +
            unworthy * self.weight_unworthy
        )
        
        if value <= 0:
            return 0
        
        # 非线性映射：对数缩放，避免头部商品分太高
        log_val = math.log1p(value)
        # log_val 范围大约 0~8（value 0~3000）
        score = min(100, log_val * 14)
        return round(score, 1)
    
    def _calc_price_score(self, product: Dict, price_history: List[Dict] = None) -> float:
        """计算价格优势得分（0-100）
        没有历史价格时默认给 50 分（中性）
        """
        if not price_history or len(price_history) < 2:
            return 50
        
        try:
            current_price = self._parse_price(product.get('price', ''))
            if current_price is None:
                return 50
            
            history_prices = [self._parse_price(p.get('price', '')) for p in price_history]
            history_prices = [p for p in history_prices if p is not None]
            
            if not history_prices:
                return 50
            
            min_price = min(history_prices)
            if min_price > 0:
                ratio = current_price / min_price
                if ratio <= 1.0:
                    return 100
                elif ratio <= 1.05:
                    return 80
                elif ratio <= 1.1:
                    return 60
                elif ratio <= 1.2:
                    return 40
                else:
                    return 20
            
            return 50
            
        except Exception:
            return 50
    
    def _parse_price(self, price_str: str) -> Optional[float]:
        """解析价格字符串"""
        if not price_str or price_str == '未知':
            return None
        
        try:
            match = re.search(r'[\d]+\.?\d*', price_str)
            if match:
                return float(match.group())
            return None
        except (ValueError, IndexError):
            return None
    
    def filter_products(self, products: List[Dict], filter_config: Dict = None) -> List[Dict]:
        """过滤商品"""
        if filter_config is None:
            filter_config = {}
        
        blacklist_keywords = filter_config.get('blacklist_keywords', [])
        blacklist_ids = filter_config.get('blacklist_ids', [])
        blacklist_malls = filter_config.get('blacklist_malls', [])
        whitelist_keywords = filter_config.get('whitelist_keywords', [])
        whitelist_ids = filter_config.get('whitelist_ids', [])
        
        filtered = []
        
        for product in products:
            if self._is_whitelisted(product, whitelist_keywords, whitelist_ids):
                filtered.append(product)
                continue
            
            if self._is_blacklisted(product, blacklist_keywords, blacklist_ids, blacklist_malls):
                continue
            
            filtered.append(product)
        
        return filtered
    
    def _is_whitelisted(self, product: Dict, keywords: List[str], ids: List[str]) -> bool:
        if product.get('id') in ids:
            return True
        title = product.get('title', '').lower()
        for keyword in keywords:
            if keyword.lower() in title:
                return True
        return False
    
    def _is_blacklisted(self, product: Dict, keywords: List[str], ids: List[str], malls: List[str]) -> bool:
        if product.get('id') in ids:
            return True
        if product.get('mall') in malls:
            return True
        title = product.get('title', '').lower()
        for keyword in keywords:
            if keyword.lower() in title:
                return True
        return False

# 全局评分器实例
_scorer_instance = None

def get_scorer(config: Dict, category_pref=None) -> Scorer:
    global _scorer_instance
    if _scorer_instance is None:
        _scorer_instance = Scorer(config, category_pref)
    return _scorer_instance
