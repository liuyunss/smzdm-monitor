"""
什么值得买爬虫模块
"""
import requests
import time
import logging
import re
import random
from typing import List, Dict, Optional
from datetime import datetime

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
        # type=youhui 有互动数据，faxian 频道互动数据全为0
        api_url = f'https://api.smzdm.com/v1/list?limit=20&offset={(page-1)*20}&type=youhui&order=time'
        
        proxy = None
        if self.proxy_manager:
            proxy = self.proxy_manager.get_proxy()
        
        try:
            start_time = time.time()
            
            if proxy:
                response = self.session.get(api_url, proxies=proxy.dict, timeout=30)
            else:
                response = self.session.get(api_url, timeout=30)
            
            response_time = time.time() - start_time
            
            if proxy and self.proxy_manager:
                self.proxy_manager.on_success(proxy)
            
            if response.status_code != 200:
                logger.warning(f"HTTP {response.status_code}: {api_url}")
                return None
            
            data = response.json()
            
            # API 返回格式: {data: {rows: [...], total_num: ...}}
            rows = data.get('data', {}).get('rows', [])
            if not rows:
                logger.info(f"无数据: {api_url}")
                return None
            
            products = []
            for item in rows:
                product = self._parse_item(item)
                if product:
                    products.append(product)
            
            logger.info(f"第{page}页: 获取{len(products)}个商品 (耗时{response_time:.1f}s)")
            return products
            
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败: {e}")
            if proxy and self.proxy_manager:
                self.proxy_manager.on_failure(proxy)
            return None
    
    def _parse_item(self, item: Dict) -> Optional[Dict]:
        """解析商品数据"""
        try:
            article_id = item.get('article_id')
            title = item.get('article_title', '').strip()
            # 提取纯数字价格（去掉'元'、'（需用券）'等后缀）
            raw_price = item.get('article_price', '').strip()
            price_match = re.search(r'[\d,.]+', raw_price)
            price = price_match.group() if price_match else raw_price
            mall = item.get('article_mall', '').strip()
            url = item.get('article_url', '').strip()
            channel_type = item.get('article_channel_type', '').strip()
            
            if not article_id or not title:
                return None
            
            # 解析互动数据
            worthy = max(0, int(item.get('article_worthy', 0) or 0))
            unworthy = max(0, int(item.get('article_unworthy', 0) or 0))
            comments = max(0, int(item.get('article_comment', 0) or 0))
            collection = max(0, int(item.get('article_collection', 0) or 0))
            
            # 优先从 tongji_hudong 获取精确数据
            tongji = self._parse_tongji_hudong(item.get('tongji_hudong', ''))
            if tongji['worthy'] > 0:
                worthy = tongji['worthy']
            if tongji['unworthy'] > 0:
                unworthy = tongji['unworthy']
            if tongji['comments'] > 0:
                comments = tongji['comments']
            if tongji['collection'] > 0:
                collection = tongji['collection']
            
            # 计算商品年龄（小时）- 使用 publish_date_lt 时间戳
            age_hours = 0
            pub_ts = item.get('publish_date_lt', '')
            if pub_ts and str(pub_ts).isdigit():
                pub_dt = datetime.fromtimestamp(int(pub_ts))
                age_hours = (datetime.now() - pub_dt).total_seconds() / 3600
            
            return {
                'id': str(article_id),
                'title': title,
                'price': price,
                'mall': mall,
                'url': url,
                'channel_type': channel_type,
                'pub_time': item.get('article_format_date', ''),
                'comments': comments,
                'collection': collection,
                'worthy': worthy,
                'unworthy': unworthy,
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
    def fetch_multiple_pages(self, target_minutes: int = 30, max_pages: int = 50) -> List[Dict]:
        """动态页数抓取：覆盖 target_minutes 分钟的数据量，自动停止"""
        all_products = []
        target_hours = target_minutes / 60

        for page in range(1, max_pages + 1):
            delay = random.uniform(0.5, 1.5)
            time.sleep(delay)

            products = self.fetch_deals(page)
            if not products:
                break

            all_products.extend(products)

            # 检查最旧数据是否已超出目标时间窗口
            oldest_age = max((p.get('age_hours', 0) for p in products), default=0)
            if oldest_age >= target_hours:
                logger.info(f"覆盖{target_minutes}分钟，停止（第{page}页，最旧{oldest_age:.1f}h）")
                break

        logger.info(f"共抓取 {len(all_products)} 个商品（{page}页）")
        return all_products

def get_crawler(config: Dict, proxy_manager=None):
    """创建爬虫实例"""
    return SmzdmCrawler(config, proxy_manager)
