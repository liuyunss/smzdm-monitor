"""
配置加载模块
支持 config.yaml + 环境变量覆盖 + .env 文件
"""
import os
import yaml
from typing import Dict, Any

try:
    from dotenv import load_dotenv
    # 加载 .env 文件（不覆盖已有环境变量）
    load_dotenv(override=False)
except ImportError:
    pass


class ConfigLoader:
    """配置加载器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = {}
        self._load()
    
    def _load(self):
        """加载配置文件"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 环境变量覆盖
        self._env_override()
    
    def _env_override(self):
        """环境变量覆盖配置（优先级高于 config.yaml）"""
        env_map = {
            'SMZDM_EMAIL_USERNAME': ('notifier', 'email', 'username'),
            'SMZDM_EMAIL_PASSWORD': ('notifier', 'email', 'password'),
            'SMZDM_EMAIL_TO': ('notifier', 'email', 'to_email'),
            'SMZDM_DB_PATH': ('storage', 'db_path'),
            'SMZDM_PROXY_API_KEY': ('proxy', 'api_key'),
        }
        
        for env_key, cfg_path in env_map.items():
            value = os.environ.get(env_key)
            if value:
                self._set_nested(cfg_path, value)
    
    def _set_nested(self, keys: tuple, value: Any):
        """设置嵌套配置值"""
        d = self.config
        for key in keys[:-1]:
            d = d[key]
        d[keys[-1]] = value
    
    def get(self, *keys, default=None):
        """获取配置值"""
        d = self.config
        for key in keys:
            if isinstance(d, dict) and key in d:
                d = d[key]
            else:
                return default
        return d
    
    def update(self, *keys, value):
        """更新配置值"""
        self._set_nested(keys, value)
    
    def save(self):
        """保存配置到文件"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)
    
    def __getitem__(self, keys):
        """支持 dict['key1']['key2'] 方式访问"""
        return self.get(*keys) if isinstance(keys, tuple) else self.config.get(keys)


# 全局配置实例
_config_instance = None

def get_config(config_path: str = "config.yaml") -> ConfigLoader:
    """获取全局配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader(config_path)
    return _config_instance

def reload_config(config_path: str = "config.yaml"):
    """重新加载配置"""
    global _config_instance
    _config_instance = ConfigLoader(config_path)
    return _config_instance
