"""
什么值得买爬虫模块
"""
import requests
import time
import logging
import re
import random
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SmzdmCrawler:
    """什么值得买爬虫"""
    
    def __init__(self, config: Dict, proxy_manager=None):
        self.config = config
        self.proxy_manager = proxy_manager
        self.session = requests.Session()
        self._init_session()
    
    def _init_session(self):
        """初始化会话"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.smzdm.com/',
        })
    
    def fetch_deals(self, page: int = 1) -> Optional[List[Dict]]:
        """抓取好价商品"""
        # API端点
        api_url = f'https://api.smzdm.com/v1/list?limit=20&offset={(page-1)*20}'
        
        # 获取代理
        proxy = None
        if self.proxy_manager:
            proxy = self.proxy_manager.get_proxy()
        
        try:
            start_time = time.time()
            
            # 发送请求
            if proxy:
                response = self.session.get(
                    api_url,
                    proxies=proxy.dict,
                    timeout=30
                )
            else:
                response = self.session.get(api_url, timeout=30)
            
            response_time = time.time() - start_time
            
            # 代理成功
            if proxy and self.proxy_manager:
                self.proxy_manager.on_success(proxy)
            
            # 检查响应
            if response.status_code != 200:
                logger.warning(f"HTTP {response.status_code}: {api_url}")
                return None
            
            # 解析JSON
            data = response.json()
            if 'data' not in data:
                logger.warning(f"无效响应格式: {api_url}")
                return None
            
            # 解析商品列表
            products = []
            items = data['data'] if isinstance(data['data'], list) else []
            
            for item in items:
                product = self._parse_item(item)
                if product:
                    products.append(product)
            
            logger.info(f"第{page}页: 获取{len(products)}个商品")
            return products
            
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败: {e}")
            
            # 代理失败
            if proxy and self.proxy_manager:
                self.proxy_manager.on_failure(proxy)
            
            return None
    
    def _parse_item(self, item: Dict) -> Optional[Dict]:
        """解析商品数据"""
        try:
            # 基础字段
            article_id = item.get('article_id')
            title = item.get('article_title', '').strip()
            price = item.get('article_price', '').strip()
            mall = item.get('article_mall', '').strip()
            url = item.get('article_url', '').strip()
            channel_type = item.get('article_channel_type', '').strip()
            pub_time = item.get('article_format_date', '').strip()
            
            # 验证必要字段
            if not article_id or not title:
                return None
            
            # 解析互动数据
            worthy = max(0, int(item.get('article_worthy', 0)))
            unworthy = max(0, int(item.get('article_unworthy', 0)))
            comments = max(0, int(item.get('article_comment', 0)))
            
            # 解析 tongji_hudong 获取精确数据
            tongji = self._parse_tongji_hudong(item.get('tongji_hudong', ''))
            
            # 计算商品年龄（小时）
            age_hours = 0
            if pub_time:
                try:
                    pub_dt = datetime.strptime(pub_time, '%Y-%m-%d %H:%M')
                    age_hours = (datetime.now() - pub_dt).total_seconds() / 3600
                except Exception:
                    pass
            
            return {
                'id': str(article_id),
                'title': title,
                'price': price,
                'mall': mall,
                'url': url,
                'channel_type': channel_type,
                'pub_time': pub_time,
                'comments': tongji['comments'] or comments,
                'collection': tongji['collection'],
                'worthy': tongji['worthy'] or worthy,
                'unworthy': tongji['unworthy'] or unworthy,
                'age_hours': age_hours,
            }
            
        except Exception as e:
            logger.warning(f"解析商品失败: {e}")
            return None
    
    def _parse_tongji_hudong(self, tongji_str: str) -> Dict:
        """解析 tongji_hudong 字段：评论_5,收藏_3,值_10,不值_2"""
        result = {'comments': 0, 'collection': 0, 'worthy': 0, 'unworthy': 0}
        if not tongji_str:
            return result
        
        mapping = {'评论': 'comments', '收藏': 'collection', '值': 'worthy', '不值': 'unworthy'}
        for part in tongji_str.split(','):
            if '_' in part:
                key, value = part.split('_', 1)
                if key in mapping and value.isdigit():
                    result[mapping[key]] = int(value)
        
        return result
    
    def fetch_multiple_pages(self, max_pages: int = 50, max_hours: int = 24) -> List[Dict]:
        """抓取多页数据"""
        all_products = []
        
        for page in range(1, max_pages + 1):
            # 随机延迟
            delay = random.uniform(0.5, 1.5)
            time.sleep(delay)
            
            # 抓取一页
            products = self.fetch_deals(page)
            if not products:
                break
            
            # 检查时间范围
            if max_hours > 0:
                products = [p for p in products if p.get('age_hours', 0) <= max_hours]
                if not products:
                    break
            
            all_products.extend(products)
            
            logger.info(f"已抓取 {len(all_products)} 个商品")
        
        return all_products

# 全局爬虫实例
_crawler_instance = None

def get_crawler(config: Dict, proxy_manager=None) -> SmzdmCrawler:
    """获取全局爬虫实例"""
    global _crawler_instance
    if _crawler_instance is None:
        _crawler_instance = SmzdmCrawler(config, proxy_manager)
    return _crawler_instance

def reset_crawler():
    """重置爬虫实例"""
    global _crawler_instance
    _crawler_instance = None
