"""
评分算法模块

核心逻辑：
1. 只对"有历史数据"的商品评分（至少运行过2次）
2. 用互动增长率而非绝对值
3. 太新的商品（<1h）不参与评分
4. 品类偏好加权（根据用户反馈学习）
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Scorer:
    """商品评分器"""
    
    def __init__(self, config: Dict, category_pref=None):
        self.config = config
        self.category_pref = category_pref
        self._load_config()
    
    def _load_config(self):
        """加载评分配置"""
        weights = self.config.get('weights', {})
        self.weight_engagement_growth = weights.get('engagement_growth', 0.5)
        self.weight_absolute_engagement = weights.get('absolute_engagement', 0.3)
        self.weight_price = weights.get('price', 0.2)
        
        self.min_engagement_growth = self.config.get('min_engagement_growth', 5)
        self.min_composite_score = self.config.get('min_composite_score', 45)
        self.min_age_hours = self.config.get('min_age_hours', 1)
        self.min_snapshots = self.config.get('min_snapshots', 2)
    
    def calculate_score(self, product: Dict, price_history: List[Dict] = None,
                        engagement_growth: Dict = None) -> float:
        """计算商品综合评分（含品类偏好加权）"""
        # 太新的商品不评分
        age_hours = product.get('age_hours', 0)
        if age_hours < self.min_age_hours:
            return 0
        
        # 没有增长数据的不评分
        if not engagement_growth or engagement_growth.get('snapshots', 0) < self.min_snapshots:
            return 0
        
        # 计算基础分
        growth_score = self._calc_growth_score(engagement_growth)
        absolute_score = self._calc_absolute_score(engagement_growth.get('curr', {}))
        price_score = self._calc_price_score(product, price_history)
        
        base_score = (
            growth_score * self.weight_engagement_growth +
            absolute_score * self.weight_absolute_engagement +
            price_score * self.weight_price
        )
        
        # 增长量门槛
        total_growth = engagement_growth.get('total_growth', 0)
        if total_growth < self.min_engagement_growth:
            base_score *= 0.3
        
        # 品类偏好加权
        if self.category_pref:
            category = product.get('category', '其他')
            weight = self.category_pref.get_pref_weight(category)
            base_score *= weight
            logger.debug(f"品类 {category} 权重: {weight}, 加权后: {base_score:.2f}")
        
        return round(base_score, 2)
    
    def _calc_growth_score(self, engagement_growth: Dict) -> float:
        """计算互动增长得分（0-100）"""
        growth = engagement_growth.get('growth', {})
        
        growth_value = (
            growth.get('comments', 0) * 2 +
            growth.get('collection', 0) * 1.5 +
            growth.get('worthy', 0) * 1 -
            growth.get('unworthy', 0) * 0.5
        )
        
        if growth_value >= 100:
            return 100
        elif growth_value >= 50:
            return 85
        elif growth_value >= 20:
            return 70
        elif growth_value >= 10:
            return 55
        elif growth_value >= 5:
            return 40
        elif growth_value >= 2:
            return 25
        elif growth_value >= 1:
            return 15
        else:
            return 0
    
    def _calc_absolute_score(self, curr: Dict) -> float:
        """计算绝对互动量得分（0-100）"""
        comments = curr.get('comments', 0)
        collection = curr.get('collection', 0)
        worthy = curr.get('worthy', 0)
        unworthy = curr.get('unworthy', 0)
        
        popularity = comments * 2 + collection * 1.5 + worthy * 1 - unworthy * 0.5
        
        if popularity >= 500:
            return 100
        elif popularity >= 200:
            return 80
        elif popularity >= 100:
            return 60
        elif popularity >= 50:
            return 40
        elif popularity >= 20:
            return 25
        elif popularity >= 5:
            return 15
        else:
            return 5
    
    def _calc_price_score(self, product: Dict, price_history: List[Dict] = None) -> float:
        """计算价格优势得分（0-100）"""
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
            import re
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
