# -*- coding: utf-8 -*-
"""
七牛云客户端模块
提供七牛云存储的操作接口
"""

import os
import time
from dataclasses import dataclass, field
from typing import Callable, List, Dict, Any, Optional, Tuple

from qiniu import Auth, BucketManager, etag, put_file, put_data
from qiniu.services.cdn.manager import create_timestamp_anti_leech_url, CdnManager

from .config import get_config
from .exceptions import (
    AuthenticationError, NetworkError, BucketError,
    FileNotFoundError, UploadError, HashVerificationError
)
from .utils import extract_filename_from_url, walk_directory


@dataclass
class UploadSummary:
    """一次批量上传的结果汇总"""
    succeeded: List[Tuple[str, str]] = field(default_factory=list)   # (本地路径, 远端key)
    failed: List[Tuple[str, str]] = field(default_factory=list)      # (本地路径, 错误信息)
    skipped: List[Tuple[str, str]] = field(default_factory=list)     # --skip-existing 跳过的 (本地路径, 远端key)
    warnings: List[str] = field(default_factory=list)
    empty_dirs: List[str] = field(default_factory=list)
    hidden_skipped: int = 0
    refresh_ok: int = 0
    refresh_failed: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """没有文件失败即为成功（空目录、跳过隐藏文件、CDN刷新失败都不算失败）"""
        return not self.failed


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

    def stat_exact(self, file_name: str) -> bool:
        """
        严格判断七牛云中是否存在特定文件

        与 is_exist 的区别：网络/鉴权等真实错误会抛出异常，而不是被当成「不存在」。
        --skip-existing 与 --force 依赖这个语义，否则一次网络抖动就会导致误判。

        Args:
            file_name: 文件名

        Returns:
            存在则返回True，确认不存在则返回False

        Raises:
            NetworkError: 查询本身失败（网络、鉴权、非612错误码）
        """
        try:
            ret, info = self.bucket_manager.stat(self.bucket_name, file_name)
        except Exception as e:
            raise NetworkError(f'查询文件失败: {e}')

        if ret is not None:
            return True

        status = getattr(info, 'status_code', None)
        # 七牛用 HTTP 612 表示「文件不存在」，这是唯一能确认不存在的信号
        if status == 612:
            return False
        raise NetworkError(f'查询文件失败: HTTP {status}')

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
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f'本地文件不存在或不是文件: {file_path}')

        if not remote_name:
            remote_name = f"{self.prefix}{os.path.basename(file_path)}"

        try:
            token = self.auth.upload_token(self.bucket_name, remote_name)
            ret, _ = put_file(token, remote_name, file_path)

            if not ret:
                raise UploadError('上传失败')

            # 验证文件hash
            if not (ret['key'] == remote_name and ret['hash'] == etag(file_path)):
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

    def upload_paths(self, paths: List[str], recursive: bool = True,
                     include_hidden: bool = False, overwrite: bool = True,
                     force: bool = False, refresh_cdn: bool = False,
                     delete_after_days: Optional[int] = None,
                     reporter: Optional[Callable[[str, str], None]] = None
                     ) -> UploadSummary:
        """
        批量上传本地路径，文件与目录可以混传

        目录会保留相对结构：`qnshare upload photos` 下的 photos/2024/b.jpg
        上传后key为 `<prefix>photos/2024/b.jpg`；单个文件参数则保持
        `<prefix><basename>` 不变（向后兼容）。

        Args:
            paths: 本地文件或目录路径列表
            recursive: 目录是否递归，默认True
            include_hidden: 是否包含'.'开头的文件/目录，默认False
            overwrite: 云端已存在时覆盖，默认True
            force: 云端已存在时先删除再上传，用于重置元数据/生命周期
            refresh_cdn: 上传后刷新CDN缓存
            delete_after_days: 每个文件上传后自动删除的天数
            reporter: 进度回调，签名为 (事件名, 消息)，事件名取值
                      start/success/failure/skip/warning

        Returns:
            UploadSummary 汇总对象

        Note:
            单个文件的失败会被记录进 summary 而不会抛出，
            以免一个坏文件中断整批上传；配置/初始化错误仍会正常抛出。
        """
        summary = UploadSummary()
        seen: Dict[str, str] = {}   # 远端key -> 本地路径，用于批内去重

        def emit(event: str, message: str) -> None:
            if reporter:
                reporter(event, message)

        def on_skip(hidden_path: str) -> None:
            summary.hidden_skipped += 1

        for path in paths:
            if os.path.isfile(path):
                targets = [(path, f"{self.prefix}{os.path.basename(path)}")]
            elif os.path.isdir(path):
                root_name = os.path.basename(os.path.abspath(path))
                if not root_name:
                    summary.failed.append((path, '无法确定目录名（不能直接上传磁盘根目录）'))
                    emit('failure', f"上传失败 {path}: 无法确定目录名")
                    continue
                targets = [
                    (file_path, f"{self.prefix}{root_name}/{rel_key}")
                    for file_path, rel_key in walk_directory(
                        path, recursive=recursive, include_hidden=include_hidden,
                        on_skip=on_skip)
                ]
                if not targets:
                    summary.empty_dirs.append(path)
                    emit('warning', f"目录为空（或只含隐藏文件）: {path}")
                    continue
            else:
                summary.failed.append((path, '路径不存在'))
                emit('failure', f"上传失败 {path}: 路径不存在")
                continue

            for file_path, remote_key in targets:
                if remote_key in seen:
                    message = (f"跳过重复的key {remote_key}"
                               f"（已由 {seen[remote_key]} 占用）")
                    summary.warnings.append(message)
                    emit('warning', message)
                    continue
                seen[remote_key] = file_path

                # 先决定「已存在」时的处理方式，再决定要不要传
                try:
                    if not overwrite:
                        if self.stat_exact(remote_key):
                            summary.skipped.append((file_path, remote_key))
                            emit('skip', f"已存在，跳过: {remote_key}")
                            continue
                    elif force and self.stat_exact(remote_key):
                        self.delete_file(remote_key)
                except NetworkError as e:
                    summary.failed.append((file_path, str(e)))
                    emit('failure', f"上传失败 {file_path}: {e}")
                    continue
                except Exception as e:
                    # 预删除失败不阻止上传——七牛本身就会覆盖
                    message = f"删除已存在的 {remote_key} 失败，将直接覆盖: {e}"
                    summary.warnings.append(message)
                    emit('warning', message)

                emit('start', f"正在上传: {file_path}")
                try:
                    self.upload_local_file(file_path, remote_name=remote_key,
                                           delete_after_days=delete_after_days)
                except Exception as e:
                    summary.failed.append((file_path, str(e)))
                    emit('failure', f"上传失败 {file_path}: {e}")
                    continue

                summary.succeeded.append((file_path, remote_key))
                emit('success', f"上传成功: {remote_key}")

        if refresh_cdn and summary.succeeded:
            try:
                summary.refresh_ok, summary.refresh_failed = self.refresh_many(
                    [remote_key for _, remote_key in summary.succeeded])
            except NetworkError as e:
                summary.refresh_failed = [k for _, k in summary.succeeded]
                summary.warnings.append(str(e))

        return summary

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

        Raises:
            NetworkError: 刷新请求失败，或接口返回了错误码
        """
        self.refresh_many([file_name])

    def refresh_many(self, file_names: List[str], chunk_size: int = 100) -> Tuple[int, List[str]]:
        """
        批量刷新七牛云CDN

        七牛刷新接口单次最多接受 100 个URL，这里自动分块，单块失败不影响其余块。

        Args:
            file_names: 文件名列表
            chunk_size: 每批提交的数量

        Returns:
            (刷新成功的数量, 刷新失败的key列表)

        Raises:
            NetworkError: 全部批次都失败且没有任何成功的key
        """
        succeeded = 0
        failed: List[str] = []

        for start in range(0, len(file_names), chunk_size):
            chunk = file_names[start:start + chunk_size]
            urls = [f'http://{self.domain}/{name}' for name in chunk]
            try:
                ret, info = self.cdn_manager.refresh_urls(urls)
            except Exception as e:
                failed.extend(chunk)
                continue

            # 刷新接口出错时 HTTP 仍可能是 200，真正的错误在 body 的 code/error 里
            body_error = None
            if isinstance(ret, dict):
                code = ret.get('code')
                if code is not None and code != 200:
                    body_error = ret.get('error') or f"code={code}"
            if (info is None or not info.ok()) or body_error:
                failed.extend(chunk)
            else:
                succeeded += len(chunk)

        if failed and not succeeded:
            raise NetworkError(f'CDN刷新失败: {len(failed)} 个文件未能刷新')

        return succeeded, failed
