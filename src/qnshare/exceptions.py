# -*- coding: utf-8 -*-
"""
自定义异常模块
定义qnshare包中使用的各种异常类
"""


class QnShareError(Exception):
    """qnshare包的基础异常类"""
    pass


class ConfigError(QnShareError):
    """配置相关异常"""
    pass


class ConfigNotFoundError(ConfigError):
    """配置文件未找到异常"""
    pass


class ConfigValidationError(ConfigError):
    """配置验证失败异常"""
    pass


class AuthenticationError(QnShareError):
    """认证失败异常"""
    pass


class NetworkError(QnShareError):
    """网络相关异常"""
    pass


class BucketError(QnShareError):
    """存储空间相关异常"""
    pass


class FileNotFoundError(QnShareError):
    """文件未找到异常"""
    pass


class UploadError(QnShareError):
    """上传失败异常"""
    pass


class DownloadError(QnShareError):
    """下载失败异常"""
    pass


class HashVerificationError(QnShareError):
    """文件哈希验证失败异常"""
    pass
