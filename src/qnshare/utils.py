# -*- coding: utf-8 -*-
"""
工具函数模块
包含各种通用的工具函数
"""

import os
from pathlib import Path
from typing import Union


def pybyte(size: Union[int, float], is_speed: bool = False, precision: int = 2) -> str:
    """
    文件大小自动转换
    byte      ---- (B)
    kilobyte  ---- (KB)
    megabyte  ---- (MB)
    gigabyte  ---- (GB)
    terabyte  ---- (TB)
    petabyte  ---- (PB)
    exabyte   ---- (EB)
    zettabyte ---- (ZB)
    yottabyte ---- (YB)
    
    Args:
        size: 大小（字节）
        is_speed: 是否为传输速率计算(bps/bit)
        precision: 精确到小数点位数
        
    Returns:
        格式化后的大小字符串
        
    Raises:
        TypeError: 当size不是数字类型时
        ValueError: 当size小于0时
    """
    if not isinstance(size, (float, int)):
        raise TypeError('需要浮点数或整数')
    if size < 0:
        raise ValueError('数字必须大于等于零')
    
    formats = ['KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    unit = 1000.0 if is_speed else 1024.0
    
    for i in formats:
        size /= unit
        if size < unit:
            return f'{round(size, precision)}{i}'
    return f'{round(size, precision)}'


def get_user_config_dir() -> Path:
    """
    获取用户配置目录路径
    
    Returns:
        用户配置目录的Path对象
    """
    home = Path.home()
    config_dir = home / '.qn'
    return config_dir


def ensure_config_dir() -> Path:
    """
    确保配置目录存在，如果不存在则创建
    
    Returns:
        配置目录的Path对象
    """
    config_dir = get_user_config_dir()
    config_dir.mkdir(exist_ok=True)
    
    # 设置目录权限（仅用户可访问）
    if os.name != 'nt':  # 非Windows系统
        os.chmod(config_dir, 0o700)
    
    return config_dir


def get_config_file_path() -> Path:
    """
    获取配置文件路径
    
    Returns:
        配置文件的Path对象
    """
    config_dir = ensure_config_dir()
    return config_dir / 'config.json'


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除不安全的字符
    
    Args:
        filename: 原始文件名
        
    Returns:
        清理后的文件名
    """
    # 移除路径分隔符和其他不安全字符
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    
    # 移除前后空格和点
    filename = filename.strip(' .')
    
    # 如果文件名为空或只包含不安全字符，使用默认名称
    if not filename:
        filename = 'unknown_file'
    
    return filename


def extract_filename_from_url(url: str) -> str:
    """
    从URL中提取文件名
    
    Args:
        url: URL地址
        
    Returns:
        提取的文件名
    """
    # 移除查询参数
    url_without_params = url.split('?')[0]
    # 提取最后一部分作为文件名
    filename = url_without_params.split('/')[-1]
    
    if not filename:
        filename = 'unknown_file'
    
    return sanitize_filename(filename)
