# -*- coding: utf-8 -*-
"""
qn.py - 向后兼容模块

此模块保留了原有的接口以确保向后兼容性。
建议使用新的模块化接口：
- qnshare.client.QiniuClient 替代 Qiniu 类
- qnshare.cli 命令行工具替代 main() 函数

注意：此模块中的硬编码密钥已被移除，请使用配置文件。
"""

import warnings
from typing import List, Dict, Any

# 导入新的模块
from .client import QiniuClient
from .config import get_config
from .utils import pybyte
from .exceptions import ConfigValidationError

# 发出弃用警告
warnings.warn(
    "qn.py模块已弃用，请使用新的模块化接口。参考文档进行迁移。",
    DeprecationWarning,
    stacklevel=2
)


# 向后兼容的Qiniu类，现在是QiniuClient的包装器
class Qiniu:
    """
    向后兼容的Qiniu类

    警告：此类已弃用，请使用 qnshare.client.QiniuClient
    """

    def __init__(self, access_key=None, secret_key=None):
        warnings.warn(
            "Qiniu类已弃用，请使用qnshare.client.QiniuClient",
            DeprecationWarning,
            stacklevel=2
        )

        # 如果提供了密钥参数，更新配置
        if access_key and secret_key:
            config = get_config()
            config.update({
                'access_key': access_key,
                'secret_key': secret_key
            })

        # 使用新的客户端
        try:
            self._client = QiniuClient()
            # 为了向后兼容，暴露一些属性
            self.bucket_name = self._client.bucket_name
            self.domain = self._client.domain
        except ConfigValidationError:
            raise Exception('配置无效，请先运行 qnshare init 进行配置')

    def is_exist(self, file_name: str) -> bool:
        """判断七牛云中是否存在特定文件"""
        return self._client.is_exist(file_name)

    def get_file_list(self, prefix=None) -> List[Dict[str, Any]]:
        """查询七牛云中保存的文件列表"""
        return self._client.get_file_list(prefix)

    def upload_local_file(self, file_path: str, remote_name=None, delete_after_days=None) -> str:
        """上传本地文件"""
        return self._client.upload_local_file(file_path, remote_name, delete_after_days)

    def upload_stream_file(self, file_stream, remote_name, delete_after_days=None) -> str:
        """上传二进制文件流到七牛云"""
        return self._client.upload_stream_file(file_stream, remote_name, delete_after_days)

    def fetch_url(self, url: str, remote_name: str = None, delete_after_days=None) -> str:
        """抓取网络资源，可用于离线下载"""
        return self._client.fetch_url(url, remote_name, delete_after_days)

    def delete_file(self, file_name: str, delete_after_days=None):
        """删除七牛云文件"""
        self._client.delete_file(file_name, delete_after_days)

    def get_download_link(self, file_name: str) -> str:
        """获取下载链接"""
        return self._client.get_download_link(file_name)

    def get_timestamp_link(self, file_name: str, dead_time=None, encrypt_key=None) -> str:
        """获取带时间戳的防盗链链接"""
        return self._client.get_timestamp_link(file_name, dead_time, encrypt_key)

    def refresh(self, file_name: str) -> None:
        """刷新七牛云CDN"""
        self._client.refresh(file_name)


def main():
    """
    向后兼容的main函数

    现在会启动交互式模式，提供类似原版的体验
    """
    warnings.warn(
        "qn.py模块已弃用，建议使用新的CLI工具：qnshare",
        DeprecationWarning,
        stacklevel=2
    )

    print("=" * 60)
    print("🎯 QnShare 交互式模式 (兼容模式)")
    print("=" * 60)
    print("检测到您在使用原版接口，现在启动交互式模式...")
    print("")
    print("💡 提示：新版本提供了更多功能：")
    print("  qnshare --help        # 查看所有命令")
    print("  qnshare interactive   # 直接启动交互式模式")
    print("  qnshare -i            # 交互式模式简写")
    print("=" * 60)

    # 启动交互式模式
    try:
        from .interactive import start_interactive_mode
        start_interactive_mode()
    except ImportError:
        print("\n无法启动交互式模式，请检查安装")
    except Exception as e:
        print(f"\n启动交互式模式时出错: {e}")
        print("请尝试运行 'qnshare interactive' 或 'qnshare -i'")


if __name__ == '__main__':
    main()
