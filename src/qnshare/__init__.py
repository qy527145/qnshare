# -*- coding: utf-8 -*-
"""
qnshare - 七牛云文件共享工具

一个简单易用的七牛云存储命令行工具，支持文件上传、下载、管理等功能。
"""

from .client import QiniuClient
from .config import get_config, init_config, show_config
from .exceptions import (
    QnShareError, ConfigError, ConfigNotFoundError, ConfigValidationError,
    AuthenticationError, NetworkError, BucketError, FileNotFoundError,
    UploadError, DownloadError, HashVerificationError
)
from .utils import pybyte, get_user_config_dir, sanitize_filename, extract_filename_from_url
from .interactive import start_interactive_mode

__version__ = "0.1.0"
__author__ = "wmymz"
__email__ = "wmymz@icloud.com"

__all__ = [
    # 主要类
    'QiniuClient',

    # 配置相关
    'get_config',
    'init_config',
    'show_config',

    # 异常类
    'QnShareError',
    'ConfigError',
    'ConfigNotFoundError',
    'ConfigValidationError',
    'AuthenticationError',
    'NetworkError',
    'BucketError',
    'FileNotFoundError',
    'UploadError',
    'DownloadError',
    'HashVerificationError',

    # 工具函数
    'pybyte',
    'get_user_config_dir',
    'sanitize_filename',
    'extract_filename_from_url',

    # 交互式功能
    'start_interactive_mode',
]
