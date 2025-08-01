# -*- coding: utf-8 -*-
"""
七牛云客户端模块
提供七牛云存储的操作接口
"""

import os
import time
from typing import List, Dict, Any, Optional

from qiniu import Auth, BucketManager, etag, put_file, put_data
from qiniu.services.cdn.manager import create_timestamp_anti_leech_url, CdnManager

from .config import get_config
from .exceptions import (
    AuthenticationError, NetworkError, BucketError, 
    FileNotFoundError, UploadError, HashVerificationError
)
from .utils import extract_filename_from_url


class QiniuClient:
    """七牛云客户端"""
    
    def __init__(self):
        self.config = get_config()
        self.config.validate()  # 验证配置
        
        self.access_key = self.config.get('access_key')
        self.secret_key = self.config.get('secret_key')
        self.encrypt_key = self.config.get('encrypt_key', '')
        self.prefix = self.config.get('prefix', 'share/')
        self.dead_time = self.config.get('dead_time', 3600)
        
        # 初始化七牛云认证和管理器
        self.auth = Auth(self.access_key, self.secret_key)
        self.bucket_manager = BucketManager(self.auth)
        self.cdn_manager = CdnManager(self.auth)
        
        # 获取存储空间和域名
        self._init_bucket_and_domain()
    
    def _init_bucket_and_domain(self) -> None:
        """初始化存储空间和域名"""
        try:
            # 获取存储空间
            bucket_name = self.config.get('bucket_name')
            if bucket_name:
                # 用户已配置存储空间，验证其有效性
                self.bucket_name = bucket_name
                print(f"使用配置的存储空间: {bucket_name}")

                # 验证存储空间是否存在
                buckets, _ = self.bucket_manager.list_bucket('')
                if buckets is None:
                    raise NetworkError('网络错误，无法验证存储空间')

                bucket_ids = [bucket.get('id') for bucket in buckets if isinstance(buckets, list)]
                if bucket_name not in bucket_ids:
                    raise BucketError(f'配置的存储空间 "{bucket_name}" 不存在，可用空间: {bucket_ids}')
            else:
                # 自动获取第一个存储空间
                buckets, _ = self.bucket_manager.list_bucket('')
                if buckets is None:
                    raise NetworkError('网络错误，无法获取存储空间列表')
                if not isinstance(buckets, list) or len(buckets) == 0:
                    raise BucketError('七牛云账户没有创建存储空间')
                self.bucket_name = buckets[0].get('id')
                print(f"自动选择存储空间: {self.bucket_name}")
                # 保存到配置中
                self.config.set('bucket_name', self.bucket_name)
                self.config.save()

            # 获取域名
            domain = self.config.get('domain')
            if domain:
                # 用户已配置域名，验证其有效性
                self.domain = domain
                print(f"使用配置的域名: {domain}")

                # 验证域名是否绑定到存储空间
                domains, _ = self.bucket_manager.bucket_domain(self.bucket_name)
                if isinstance(domains, list) and domain not in domains:
                    print(f"警告: 配置的域名 '{domain}' 可能未绑定到存储空间 '{self.bucket_name}'")
                    print(f"存储空间绑定的域名: {domains}")
            else:
                # 自动获取第一个域名
                domains, _ = self.bucket_manager.bucket_domain(self.bucket_name)
                if not isinstance(domains, list) or len(domains) == 0:
                    raise BucketError(f'存储空间 {self.bucket_name} 没有绑定域名')
                self.domain = domains[0]
                print(f"自动选择域名: {self.domain}")
                # 保存到配置中
                self.config.set('domain', self.domain)
                self.config.save()

        except Exception as e:
            if isinstance(e, (NetworkError, BucketError)):
                raise
            raise AuthenticationError(f'认证失败或网络错误: {e}')
    
    def is_exist(self, file_name: str) -> bool:
        """
        判断七牛云中是否存在特定文件
        
        Args:
            file_name: 文件名
            
        Returns:
            存在则返回True，否则返回False
        """
        try:
            ret, _ = self.bucket_manager.stat(self.bucket_name, file_name)
            return ret is not None
        except Exception:
            return False
    
    def get_file_list(self, prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        查询七牛云中保存的文件列表
        
        Args:
            prefix: 文件前缀过滤
            
        Returns:
            文件信息的列表
        """
        try:
            if prefix is None:
                prefix = self.prefix
            ret, _, _ = self.bucket_manager.list(self.bucket_name, prefix)
            return ret.get('items', [])
        except Exception as e:
            raise NetworkError(f'获取文件列表失败: {e}')
    
    def upload_local_file(self, file_path: str, remote_name: Optional[str] = None, 
                         delete_after_days: Optional[int] = None) -> str:
        """
        上传本地文件
        
        Args:
            file_path: 本地文件的路径
            remote_name: 保存在七牛云的文件名
            delete_after_days: 上传后自动删除的时间（天）
            
        Returns:
            远程文件名
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f'本地文件不存在: {file_path}')
        
        if not remote_name:
            remote_name = f"{self.prefix}{os.path.basename(file_path)}"
        
        try:
            token = self.auth.upload_token(self.bucket_name, remote_name)
            ret, _ = put_file(token, remote_name, file_path)
            
            if not ret:
                raise UploadError('上传失败')
            
            # 验证文件hash
            if ret['key'] == remote_name and ret['hash'] == etag(file_path):
                print('文件hash验证无误')
            else:
                raise HashVerificationError('文件上传过程中损坏')
            
            # 设置自动删除
            if delete_after_days:
                self.delete_file(remote_name, delete_after_days)
            
            return remote_name
            
        except Exception as e:
            if isinstance(e, (UploadError, HashVerificationError)):
                raise
            raise UploadError(f'上传失败: {e}')
    
    def upload_stream_file(self, file_stream: bytes, remote_name: str, 
                          delete_after_days: Optional[int] = None) -> str:
        """
        上传二进制文件流到七牛云
        
        Args:
            file_stream: 二进制文件流
            remote_name: 保存在七牛云的文件名
            delete_after_days: 上传后自动删除的时间（天）
            
        Returns:
            远程文件名
        """
        try:
            token = self.auth.upload_token(self.bucket_name, remote_name)
            ret, _ = put_data(token, remote_name, file_stream)
            
            if not ret:
                raise UploadError('上传失败')
            
            # 设置自动删除
            if delete_after_days:
                self.delete_file(remote_name, delete_after_days)
            
            return remote_name
            
        except Exception as e:
            if isinstance(e, UploadError):
                raise
            raise UploadError(f'上传失败: {e}')
    
    def fetch_url(self, url: str, remote_name: Optional[str] = None, 
                  delete_after_days: Optional[int] = None) -> str:
        """
        抓取网络资源，可用于离线下载
        
        Args:
            url: 网络资源url
            remote_name: 保存在七牛云的文件名
            delete_after_days: 离线下载后自动删除的时间（天）
            
        Returns:
            远程文件名
        """
        if not remote_name:
            filename = extract_filename_from_url(url)
            remote_name = f"{self.prefix}{filename}"
        
        try:
            ret, _ = self.bucket_manager.fetch(url, self.bucket_name, remote_name)
            if ret is None:
                raise UploadError('资源抓取失败')
            
            # 设置自动删除
            if delete_after_days:
                self.delete_file(remote_name, delete_after_days)
            
            return remote_name
            
        except Exception as e:
            if isinstance(e, UploadError):
                raise
            raise UploadError(f'资源抓取失败: {e}')
    
    def delete_file(self, file_name: str, delete_after_days: Optional[int] = None) -> None:
        """
        删除七牛云文件
        
        Args:
            file_name: 文件名称
            delete_after_days: 设置后会延迟删除（天）
        """
        if not self.is_exist(file_name):
            raise FileNotFoundError(f'文件不存在: {file_name}')
        
        try:
            if delete_after_days:
                self.bucket_manager.delete_after_days(self.bucket_name, file_name, delete_after_days)
            else:
                self.bucket_manager.delete(self.bucket_name, file_name)
        except Exception as e:
            raise NetworkError(f'删除文件失败: {e}')
    
    def get_download_link(self, file_name: str) -> str:
        """获取下载链接"""
        return f'http://{self.domain}/{file_name}'
    
    def get_timestamp_link(self, file_name: str, dead_time: Optional[int] = None,
                          encrypt_key: Optional[str] = None) -> str:
        """
        获取带时间戳的防盗链链接

        Args:
            file_name: 文件名
            dead_time: 链接有效期（秒）
            encrypt_key: 加密密钥（如果不提供，会自动生成）

        Returns:
            带时间戳的防盗链URL
        """
        if dead_time is None:
            dead_time = self.dead_time

        if encrypt_key is None:
            # 如果没有提供加密密钥，尝试从配置获取或自动生成
            if not self.encrypt_key:
                # 自动生成加密密钥
                encrypt_key = self.config.get_or_generate_encrypt_key()
                # 更新实例变量
                self.encrypt_key = encrypt_key
            else:
                encrypt_key = self.encrypt_key

        deadline = int(time.time()) + dead_time
        try:
            link = create_timestamp_anti_leech_url(
                self.domain, file_name, None, encrypt_key, deadline)
            return f'http://{link}'
        except Exception as e:
            from .exceptions import NetworkError
            raise NetworkError(f"生成防盗链失败: {e}")
    
    def refresh(self, file_name: str) -> None:
        """
        刷新七牛云CDN
        
        Args:
            file_name: 文件名
        """
        try:
            self.cdn_manager.refresh_urls([f'http://{self.domain}/{file_name}'])
        except Exception as e:
            raise NetworkError(f'CDN刷新失败: {e}')
