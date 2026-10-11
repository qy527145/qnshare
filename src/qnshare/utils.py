# -*- coding: utf-8 -*-
"""
工具函数模块
包含各种通用的工具函数
"""

import os
from pathlib import Path
from typing import Callable, Iterator, Optional, Tuple, Union


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


def walk_directory(root: str, recursive: bool = True, include_hidden: bool = False,
                   on_error: Optional[Callable[[OSError], None]] = None,
                   on_skip: Optional[Callable[[str], None]] = None
                   ) -> Iterator[Tuple[str, str]]:
    """
    遍历本地目录，产出目录下的每一个文件

    Args:
        root: 要遍历的根目录
        recursive: 是否递归子目录，默认为True
        include_hidden: 是否包含隐藏文件/目录（'.'开头），默认为False
        on_error: 遇到无法进入的目录时的回调，接收该OSError
        on_skip: 因隐藏而被跳过时的回调，接收被跳过的路径

    Yields:
        (文件绝对/相对路径, 相对root的key) 元组，key一律使用'/'分隔符

    Note:
        只产出文件，不产出目录——对象存储没有真正的目录概念。
        目录软链不会被跟进（避免成环），文件软链按其目标内容上传。
    """
    def _skipped(name: str) -> bool:
        return not include_hidden and name.startswith('.')

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False,
                                                onerror=on_error):
        # topdown=True 时原地过滤才能真正剪掉整棵隐藏目录树
        for name in dirnames[:]:
            if _skipped(name):
                dirnames.remove(name)
                if on_skip:
                    on_skip(os.path.join(dirpath, name))

        # 排序保证顺序稳定，重复检测与输出可复现
        dirnames.sort()
        filenames.sort()

        # 非递归时只在根目录这一层产出文件
        if not recursive:
            dirnames[:] = []

        for name in filenames:
            if _skipped(name):
                if on_skip:
                    on_skip(os.path.join(dirpath, name))
                continue
            file_path = os.path.join(dirpath, name)
            # Windows下relpath返回反斜杠，必须换成'/'才能作为七牛key
            rel_key = os.path.relpath(file_path, root).replace('\\', '/').replace(os.sep, '/')
            yield file_path, rel_key
