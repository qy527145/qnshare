# -*- coding: utf-8 -*-
"""
配置管理模块
处理配置文件的读取、写入和验证
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

from .exceptions import ConfigError, ConfigNotFoundError, ConfigValidationError
from .utils import get_config_file_path, ensure_config_dir


class Config:
    """配置管理类"""
    
    # 默认配置
    DEFAULT_CONFIG = {
        'access_key': '',
        'secret_key': '',
        'encrypt_key': '',  # 空字符串表示未设置，会在需要时自动生成
        'prefix': 'share/',
        'dead_time': 3600,
        'bucket_name': None,
        'domain': None
    }
    
    # 必需的配置项
    REQUIRED_FIELDS = ['access_key', 'secret_key']
    
    def __init__(self):
        self.config_file = get_config_file_path()
        self._config = {}
        self.load()
    
    def load(self) -> None:
        """加载配置文件"""
        if not self.config_file.exists():
            # 如果配置文件不存在，使用默认配置
            self._config = self.DEFAULT_CONFIG.copy()
            return
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
            
            # 合并默认配置和加载的配置
            self._config = self.DEFAULT_CONFIG.copy()
            self._config.update(loaded_config)
            
        except json.JSONDecodeError as e:
            raise ConfigError(f'配置文件格式错误: {e}')
        except Exception as e:
            raise ConfigError(f'读取配置文件失败: {e}')
    
    def save(self) -> None:
        """保存配置到文件"""
        try:
            # 确保配置目录存在
            ensure_config_dir()
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            
            # 设置文件权限（仅用户可读写）
            if os.name != 'nt':  # 非Windows系统
                os.chmod(self.config_file, 0o600)
                
        except Exception as e:
            raise ConfigError(f'保存配置文件失败: {e}')
    
    def validate(self) -> None:
        """验证配置的有效性"""
        for field in self.REQUIRED_FIELDS:
            if not self._config.get(field):
                raise ConfigValidationError(f'缺少必需的配置项: {field}')
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """设置配置项"""
        self._config[key] = value
    
    def update(self, config_dict: Dict[str, Any]) -> None:
        """批量更新配置"""
        self._config.update(config_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """返回配置字典的副本"""
        return self._config.copy()
    
    def is_configured(self) -> bool:
        """检查是否已配置必需项"""
        try:
            self.validate()
            return True
        except ConfigValidationError:
            return False
    
    def reset_to_default(self) -> None:
        """重置为默认配置"""
        self._config = self.DEFAULT_CONFIG.copy()
    
    def exists(self) -> bool:
        """检查配置文件是否存在"""
        return self.config_file.exists()

    def get_or_generate_encrypt_key(self) -> str:
        """
        获取加密密钥，如果不存在则自动生成一个

        Returns:
            加密密钥字符串
        """
        encrypt_key = self.get('encrypt_key', '')
        if not encrypt_key:
            # 自动生成32位随机密钥
            import secrets
            import string
            encrypt_key = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

            # 保存到配置中
            self.set('encrypt_key', encrypt_key)
            self.save()

            print(f"自动生成防盗链加密密钥: {encrypt_key}")

        return encrypt_key


def get_config() -> Config:
    """获取配置实例（单例模式）"""
    if not hasattr(get_config, '_instance'):
        get_config._instance = Config()
    return get_config._instance


def init_config(access_key: str, secret_key: str, encrypt_key: str = '',
                prefix: str = 'share/', dead_time: int = 3600,
                bucket_name: str = '', domain: str = '') -> None:
    """
    初始化配置

    Args:
        access_key: 七牛云Access Key
        secret_key: 七牛云Secret Key
        encrypt_key: 防盗链加密密钥（可选）
        prefix: 文件前缀
        dead_time: 链接有效期（秒）
        bucket_name: 存储空间名称（可选，留空则自动获取）
        domain: 绑定域名（可选，留空则自动获取）
    """
    config = get_config()

    # 验证必需参数
    if not access_key or not access_key.strip():
        raise ConfigValidationError('Access Key 不能为空')
    if not secret_key or not secret_key.strip():
        raise ConfigValidationError('Secret Key 不能为空')

    # 清理和验证参数
    access_key = access_key.strip()
    secret_key = secret_key.strip()
    encrypt_key = encrypt_key.strip() if encrypt_key else ''
    bucket_name = bucket_name.strip() if bucket_name else ''
    domain = domain.strip() if domain else ''

    if not prefix.endswith('/'):
        prefix = prefix + '/'

    if dead_time <= 0:
        raise ConfigValidationError('链接有效期必须大于0')

    # 验证域名格式（如果提供）
    if domain and not _is_valid_domain(domain):
        raise ConfigValidationError(f'域名格式不正确: {domain}')

    config.update({
        'access_key': access_key,
        'secret_key': secret_key,
        'encrypt_key': encrypt_key,
        'prefix': prefix,
        'dead_time': dead_time,
        'bucket_name': bucket_name or None,
        'domain': domain or None
    })
    config.save()


def _is_valid_domain(domain: str) -> bool:
    """
    验证域名格式的简单检查

    Args:
        domain: 域名字符串

    Returns:
        是否为有效域名格式
    """
    import re
    # 简单的域名格式检查
    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
    return bool(re.match(pattern, domain)) and len(domain) <= 253


def show_config() -> Dict[str, Any]:
    """显示当前配置（隐藏敏感信息）"""
    config = get_config()
    display_config = config.to_dict()
    
    # 隐藏敏感信息
    sensitive_fields = ['access_key', 'secret_key', 'encrypt_key']
    for field in sensitive_fields:
        if display_config.get(field):
            display_config[field] = '*' * 8
    
    return display_config
