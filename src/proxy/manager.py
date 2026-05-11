"""
代理IP管理模块
"""
import requests
import time
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

class Proxy:
    """代理IP类"""
    
    def __init__(self, host: str, port: int, protocol: str = 'http', username: str = None, password: str = None):
        self.host = host
        self.port = port
        self.protocol = protocol
        self.username = username
        self.password = password
        self.success_count = 0
        self.fail_count = 0
        self.avg_response_time = 0
        self.last_used = None
    
    @property
    def url(self) -> str:
        """代理URL"""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"
    
    @property
    def dict(self) -> Dict:
        """代理字典格式"""
        return {
            'http': self.url,
            'https': self.url
        }
    
    def __str__(self):
        return self.url
    
    def __eq__(self, other):
        return self.host == other.host and self.port == other.port
    
    def __hash__(self):
        return hash((self.host, self.port))

class ProxyManager:
    """代理管理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.proxies: List[Proxy] = []
        self.current_index = 0
        self._load_config()
        
        if self.config.get('enabled', True):
            self._fetch_proxies()
    
    def _load_config(self):
        """加载配置"""
        self.enabled = self.config.get('enabled', True)
        self.source = self.config.get('source', 'free')
        self.validation_enabled = self.config.get('validation', {}).get('enabled', True)
        self.validation_url = self.config.get('validation', {}).get('test_url', 'https://httpbin.org/ip')
        self.validation_timeout = self.config.get('validation', {}).get('timeout', 10)
        self.on_request = self.config.get('rotation', {}).get('on_request', True)
        self.rotate_on_failure = self.config.get('rotation', {}).get('on_failure', True)
        self.max_failures = self.config.get('rotation', {}).get('max_failures', 3)
    
    def _fetch_proxies(self):
        """获取代理列表"""
        if self.source == 'free':
            self._fetch_free_proxies()
        elif self.source == 'api':
            self._fetch_api_proxies()
        
        # 验证代理
        if self.validation_enabled and self.proxies:
            self._validate_proxies()
        
        logger.info(f"获取到 {len(self.proxies)} 个可用代理")
    
    def _fetch_free_proxies(self):
        """获取免费代理"""
        sources = self.config.get('free_sources', [])
        
        for source in sources:
            try:
                response = requests.get(source, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    proxies = self._parse_proxy_list(data)
                    self.proxies.extend(proxies)
            except Exception as e:
                logger.warning(f"获取代理失败 {source}: {e}")
    
    def _parse_proxy_list(self, data: Dict) -> List[Proxy]:
        """解析代理列表"""
        proxies = []
        
        # 解析 Geonode 格式
        if 'data' in data and isinstance(data['data'], list):
            for item in data['data']:
                try:
                    proxy = Proxy(
                        host=item['ip'],
                        port=item['port'],
                        protocol=item.get('protocols', ['http'])[0]
                    )
                    proxies.append(proxy)
                except Exception:
                    continue
        
        # 解析其他格式
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    host = item.get('ip') or item.get('host')
                    port = item.get('port')
                    protocol = item.get('type') or item.get('protocol', 'http')
                    if host and port:
                        proxies.append(Proxy(host=host, port=int(port), protocol=protocol))
        
        return proxies
    
    def _fetch_api_proxies(self):
        """从API获取代理"""
        api_url = self.config.get('api_url')
        api_key = self.config.get('api_key')
        
        if not api_url:
            return
        
        try:
            headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
            response = requests.get(api_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                proxies = self._parse_proxy_list(data)
                self.proxies.extend(proxies)
        except Exception as e:
            logger.warning(f"从API获取代理失败: {e}")
    
    def _validate_proxies(self):
        """验证代理有效性"""
        valid_proxies = []
        
        def test_proxy(proxy: Proxy) -> Tuple[Proxy, bool]:
            try:
                start_time = time.time()
                response = requests.get(
                    self.validation_url,
                    proxies=proxy.dict,
                    timeout=self.validation_timeout
                )
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    proxy.avg_response_time = response_time
                    return proxy, True
            except Exception:
                pass
            return proxy, False
        
        # 并发验证
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(test_proxy, proxy): proxy for proxy in self.proxies}
            for future in as_completed(futures):
                proxy, is_valid = future.result()
                if is_valid:
                    valid_proxies.append(proxy)
        
        self.proxies = valid_proxies
        self.current_index = 0
    
    def get_proxy(self) -> Optional[Proxy]:
        """获取下一个代理"""
        if not self.proxies:
            return None
        
        if self.on_request:
            self.current_index = (self.current_index + 1) % len(self.proxies)
        
        return self.proxies[self.current_index]
    
    def on_success(self, proxy: Proxy):
        """代理请求成功"""
        proxy.success_count += 1
        proxy.last_used = datetime.now()
    
    def on_failure(self, proxy: Proxy):
        """代理请求失败"""
        proxy.fail_count += 1
        
        if self.rotate_on_failure and proxy.fail_count >= self.max_failures:
            # 移除失败过多的代理
            self.proxies = [p for p in self.proxies if p != proxy]
            logger.warning(f"移除失效代理: {proxy}")
    
    def add_proxy(self, proxy: Proxy):
        """添加代理"""
        if proxy not in self.proxies:
            self.proxies.append(proxy)
    
    def remove_proxy(self, proxy: Proxy):
        """移除代理"""
        self.proxies = [p for p in self.proxies if p != proxy]
    
    def get_stats(self) -> Dict:
        """获取代理统计"""
        if not self.proxies:
            return {'total': 0, 'avg_success_rate': 0, 'avg_response_time': 0}
        
        total_success = sum(p.success_count for p in self.proxies)
        total_fail = sum(p.fail_count for p in self.proxies)
        total_requests = total_success + total_fail
        
        return {
            'total': len(self.proxies),
            'total_requests': total_requests,
            'success_rate': (total_success / total_requests * 100) if total_requests > 0 else 0,
            'avg_response_time': sum(p.avg_response_time for p in self.proxies) / len(self.proxies)
        }

# 全局代理管理器实例
_proxy_manager = None

def get_proxy_manager(config: Dict) -> ProxyManager:
    """获取全局代理管理器"""
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager(config)
    return _proxy_manager

def reset_proxy_manager():
    """重置代理管理器"""
    global _proxy_manager
    _proxy_manager = None
