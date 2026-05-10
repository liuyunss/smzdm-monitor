"""
评分算法模块
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Scorer:
    """商品评分器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self._load_config()
    
    def _load_config(self):
        """加载评分配置"""
        weights = self.config.get('weights', {})
        self.weight_historical_low = weights.get('historical_low', 0.4)
        self.weight_comment_growth = weights.get('comment_growth', 0.3)
        self.weight_popularity = weights.get('popularity', 0.3)
        
        self.min_total_engagement = self.config.get('min_total_engagement', 15)
        self.min_composite_score = self.config.get('min_composite_score', 45)
        self.min_score_rate = self.config.get('min_score_rate', 70)
    
    def calculate_score(self, product: Dict, price_history: List[Dict] = None) -> float:
        """计算商品综合评分"""
        # 计算各维度得分
        historical_low_score = self._calc_historical_low_score(product, price_history)
        comment_growth_score = self._calc_comment_growth_score(product)
        popularity_score = self._calc_popularity_score(product)
        
        # 加权计算总分
        total_score = (
            historical_low_score * self.weight_historical_low +
            comment_growth_score * self.weight_comment_growth +
            popularity_score * self.weight_popularity
        )
        
        # 基础门槛检查
        total_engagement = product.get('comments', 0) + product.get('collection', 0) + product.get('worthy', 0)
        if total_engagement < self.min_total_engagement:
            total_score *= 0.5  # 降低分数
        
        # 好评率检查
        score_rate = self._calc_score_rate(product)
        if score_rate < self.min_score_rate:
            total_score *= 0.7  # 降低分数
        
        return round(total_score, 2)
    
    def _calc_historical_low_score(self, product: Dict, price_history: List[Dict] = None) -> float:
        """计算历史低价得分"""
        if not price_history:
            return 0
        
        try:
            # 获取当前价格
            current_price = self._parse_price(product.get('price', ''))
            if current_price is None:
                return 0
            
            # 获取历史最低价
            history_prices = [self._parse_price(p.get('price', '')) for p in price_history]
            history_prices = [p for p in history_prices if p is not None]
            
            if not history_prices:
                return 100  # 没有历史数据，给满分
            
            min_price = min(history_prices)
            
            # 计算折扣率
            if min_price > 0:
                discount_rate = current_price / min_price
                # 越接近历史最低价，得分越高
                if discount_rate <= 1.0:
                    return 100  # 历史最低
                elif discount_rate <= 1.1:
                    return 80  # 接近历史最低
                elif discount_rate <= 1.2:
                    return 60
                elif discount_rate <= 1.5:
                    return 40
                else:
                    return 20
            
            return 0
            
        except Exception as e:
            logger.warning(f"计算历史低价得分失败: {e}")
            return 0
    
    def _calc_comment_growth_score(self, product: Dict) -> float:
        """计算评论增速得分"""
        comments = product.get('comments', 0)
        age_hours = product.get('age_hours', 0)
        
        if age_hours <= 0 or comments <= 0:
            return 0
        
        # 计算每小时评论数
        comments_per_hour = comments / age_hours
        
        # 评分标准（基于经验）
        if comments_per_hour >= 10:
            return 100
        elif comments_per_hour >= 5:
            return 80
        elif comments_per_hour >= 2:
            return 60
        elif comments_per_hour >= 1:
            return 40
        elif comments_per_hour >= 0.5:
            return 20
        else:
            return 10
    
    def _calc_popularity_score(self, product: Dict) -> float:
        """计算热度得分"""
        comments = product.get('comments', 0)
        collection = product.get('collection', 0)
        worthy = product.get('worthy', 0)
        unworthy = product.get('unworthy', 0)
        
        # 热度公式：评论*2 + 收藏*1.5 + 值*1 - 不值*0.5
        popularity = comments * 2 + collection * 1.5 + worthy * 1 - unworthy * 0.5
        
        # 归一化到0-100分
        if popularity >= 500:
            return 100
        elif popularity >= 200:
            return 80
        elif popularity >= 100:
            return 60
        elif popularity >= 50:
            return 40
        elif popularity >= 20:
            return 20
        else:
            return 10
    
    def _calc_score_rate(self, product: Dict) -> float:
        """计算好评率"""
        worthy = product.get('worthy', 0)
        unworthy = product.get('unworthy', 0)
        total = worthy + unworthy
        
        if total == 0:
            return 100  # 没有评价，默认好评
        
        return (worthy / total) * 100
    
    def _parse_price(self, price_str: str) -> Optional[float]:
        """解析价格字符串"""
        if not price_str or price_str == '未知':
            return None
        
        try:
            # 移除货币符号和空格
            price_str = price_str.replace('¥', '').replace('￥', '').replace(' ', '')
            
            # 处理范围价格（如 "99-199"）
            if '-' in price_str:
                parts = price_str.split('-')
                # 取最低价
                return float(parts[0])
            
            return float(price_str)
            
        except (ValueError, IndexError):
            return None
    
    def filter_products(self, products: List[Dict], filter_config: Dict = None) -> List[Dict]:
        """过滤商品"""
        if filter_config is None:
            filter_config = {}
        
        # 获取过滤规则
        blacklist_keywords = filter_config.get('blacklist_keywords', [])
        blacklist_ids = filter_config.get('blacklist_ids', [])
        blacklist_malls = filter_config.get('blacklist_malls', [])
        whitelist_keywords = filter_config.get('whitelist_keywords', [])
        whitelist_ids = filter_config.get('whitelist_ids', [])
        
        filtered = []
        
        for product in products:
            # 白名单优先
            if self._is_whitelisted(product, whitelist_keywords, whitelist_ids):
                filtered.append(product)
                continue
            
            # 黑名单过滤
            if self._is_blacklisted(product, blacklist_keywords, blacklist_ids, blacklist_malls):
                continue
            
            filtered.append(product)
        
        return filtered
    
    def _is_whitelisted(self, product: Dict, keywords: List[str], ids: List[str]) -> bool:
        """检查是否白名单"""
        # 检查ID
        if product.get('id') in ids:
            return True
        
        # 检查关键词
        title = product.get('title', '').lower()
        for keyword in keywords:
            if keyword.lower() in title:
                return True
        
        return False
    
    def _is_blacklisted(self, product: Dict, keywords: List[str], ids: List[str], malls: List[str]) -> bool:
        """检查是否黑名单"""
        # 检查ID
        if product.get('id') in ids:
            return True
        
        # 检查店铺
        if product.get('mall') in malls:
            return True
        
        # 检查关键词
        title = product.get('title', '').lower()
        for keyword in keywords:
            if keyword.lower() in title:
                return True
        
        return False

# 全局评分器实例
_scorer_instance = None

def get_scorer(config: Dict) -> Scorer:
    """获取全局评分器"""
    global _scorer_instance
    if _scorer_instance is None:
        _scorer_instance = Scorer(config)
    return _scorer_instance
