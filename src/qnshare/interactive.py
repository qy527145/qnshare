# -*- coding: utf-8 -*-
"""
交互式模式模块
提供类似原版qn.py的交互式命令行体验
"""

import os
import sys
from urllib.request import urlretrieve
from typing import Dict, Callable, Any

from .client import QiniuClient
from .config import get_config
from .exceptions import QnShareError
from .utils import pybyte


class InteractiveShell:
    """交互式Shell类"""
    
    def __init__(self):
        self.client = None
        self.commands = {}
        self.running = True
        self._setup_commands()
    
    def _setup_commands(self):
        """设置命令映射"""
        self.commands = {
            'l': ('列出云端文件', self.list_files),
            'list': ('列出云端文件', self.list_files),
            'p': ('上传本地文件', self.upload_files),
            'put': ('上传本地文件', self.upload_files),
            'upload': ('上传本地文件', self.upload_files),
            'g': ('下载文件（例如：g file.zip）', self.download_file),
            'get': ('下载文件（例如：get file.zip）', self.download_file),
            'download': ('下载文件（例如：download file.zip）', self.download_file),
            's': ('离线下载（例如：s https://example.com/file.zip）', self.fetch_url_to_qiniu),
            'set': ('离线下载（例如：set https://example.com/file.zip）', self.fetch_url_to_qiniu),
            'fetch': ('离线下载（例如：fetch https://example.com/file.zip）', self.fetch_url_to_qiniu),
            'd': ('删除云端文件（例如：d file.zip）', self.delete_file),
            'del': ('删除云端文件（例如：del file.zip）', self.delete_file),
            'delete': ('删除云端文件（例如：delete file.zip）', self.delete_file),
            'r': ('刷新文件CDN（例如：r file.zip）', self.refresh_file),
            'refresh': ('刷新文件CDN（例如：refresh file.zip）', self.refresh_file),
            'link': ('获取文件链接（例如：link file.zip）', self.get_file_link),
            'config': ('显示配置信息', self.show_config),
            'help': ('显示帮助信息', self.show_help),
            'h': ('显示帮助信息', self.show_help),
            '?': ('显示帮助信息', self.show_help),
            'exit': ('退出程序', self.exit_shell),
            'quit': ('退出程序', self.exit_shell),
            'q': ('退出程序', self.exit_shell),
        }
    
    def _init_client(self):
        """初始化客户端"""
        if self.client is None:
            try:
                self.client = QiniuClient()
                print(f"✓ 连接成功 - 存储空间: {self.client.bucket_name}, 域名: {self.client.domain}")
            except Exception as e:
                print(f"✗ 连接失败: {e}")
                print("请先运行 'qnshare init' 进行配置")
                return False
        return True
    
    def except_handle(self, func: Callable) -> Callable:
        """异常处理装饰器"""
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except QnShareError as e:
                print(f"错误: {e}")
            except Exception as e:
                print(f"未知错误: {e}")
        return wrapper
    
    @property
    def prefix(self):
        """获取文件前缀"""
        if self.client:
            return self.client.prefix
        config = get_config()
        return config.get('prefix', 'share/')
    
    def list_files(self, *args):
        """列出云端文件"""
        if not self._init_client():
            return
        
        try:
            files = self.client.get_file_list(self.prefix)
            split_len = len(self.prefix)
            files = [file for file in files if file['key'][split_len:]]
            
            if not files:
                print("没有找到文件")
                return
            
            print('=' * 50)
            print(f'{"大小":>10}\t文件名')
            print('=' * 50)
            for file in files:
                size_str = pybyte(file['fsize'])
                filename = file['key'][split_len:]
                print(f"{size_str:>10}\t{filename}")
            print('=' * 50)
            print(f'一共 {len(files)} 个文件')
        except Exception as e:
            print(f"获取文件列表失败: {e}")
    
    def download_file(self, *args):
        """下载文件"""
        if not args:
            print('命令需要携带参数（例如：g file.zip）')
            return
        
        if not self._init_client():
            return
        
        name = args[0]
        remote_name = f'{self.prefix}{name}'
        
        try:
            if not self.client.is_exist(remote_name):
                print('不存在该文件，无法下载')
                return
            
            print(f'正在下载: {name}')
            download_url = self.client.get_download_link(remote_name)
            urlretrieve(download_url, name)
            print(f'下载成功: {name}')
        except Exception as e:
            print(f"下载失败: {e}")
    
    def upload_files(self, *args):
        """上传文件"""
        if not self._init_client():
            return
        
        if args:
            # 如果提供了文件路径参数
            for file_path in args:
                self._upload_single_file(file_path)
        else:
            # 交互式选择文件
            try:
                from tkinter import Tk
                from tkinter import filedialog
                
                tk = Tk()
                tk.withdraw()
                file_paths = filedialog.askopenfilenames(title="选择要上传的文件")
                tk.destroy()
                
                if file_paths:
                    for file_path in file_paths:
                        self._upload_single_file(file_path)
                else:
                    print("未选择文件")
            except ImportError:
                print("无法启动文件选择对话框，请直接指定文件路径")
                print("用法: p <文件路径1> [文件路径2] ...")
    
    def _upload_single_file(self, file_path: str):
        """上传单个文件"""
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            return
        
        try:
            print(f'正在上传: {file_path}')
            remote_name = f"{self.prefix}{os.path.basename(file_path)}"
            self.client.upload_local_file(file_path, remote_name=remote_name)
            print(f'上传成功: {os.path.basename(file_path)}')
        except Exception as e:
            print(f"上传失败 {file_path}: {e}")
    
    def fetch_url_to_qiniu(self, *args):
        """离线下载"""
        if not args:
            print('命令需要携带参数（例如：s https://example.com/file.zip）')
            return
        
        if not self._init_client():
            return
        
        url = args[0]
        
        try:
            print(f'离线下载: {url}')
            name = url.split('/')[-1].split('?')[0] or 'unknown'
            remote_name = f'{self.prefix}{name}'
            
            print(f'云端正在下载...')
            self.client.fetch_url(url, remote_name=remote_name)
            print(f'云端下载成功: {name}')
            
            # 询问是否下载到本地
            response = input(f'是否下载到本地？(y/N): ').strip().lower()
            if response in ['y', 'yes', '是']:
                print(f'正在下载到本地: {name}')
                download_url = self.client.get_download_link(remote_name)
                urlretrieve(download_url, name)
                print(f'本地下载成功: {name}')
        except Exception as e:
            print(f"离线下载失败: {e}")
    
    def delete_file(self, *args):
        """删除文件"""
        if not args:
            print('命令需要携带参数（例如：d file.zip）')
            return
        
        if not self._init_client():
            return
        
        name = args[0]
        remote_name = f'{self.prefix}{name}'
        
        try:
            if not self.client.is_exist(remote_name):
                print('不存在该文件，删除失败')
                return
            
            # 确认删除
            response = input(f'确定要删除文件 "{name}" 吗？(y/N): ').strip().lower()
            if response in ['y', 'yes', '是']:
                self.client.delete_file(remote_name)
                print(f'删除成功: {name}')
            else:
                print('取消删除')
        except Exception as e:
            print(f"删除失败: {e}")
    
    def refresh_file(self, *args):
        """刷新CDN"""
        if not args:
            print('命令需要携带参数（例如：r file.zip）')
            return
        
        if not self._init_client():
            return
        
        name = args[0]
        remote_name = f'{self.prefix}{name}'
        
        try:
            if not self.client.is_exist(remote_name):
                print('不存在该文件，CDN刷新失败')
                return
            
            self.client.refresh(remote_name)
            print(f'CDN刷新成功: {name}')
        except Exception as e:
            print(f"CDN刷新失败: {e}")
    
    def get_file_link(self, *args):
        """获取文件链接"""
        if not args:
            print('命令需要携带参数（例如：link file.zip）')
            return
        
        if not self._init_client():
            return
        
        name = args[0]
        remote_name = f'{self.prefix}{name}'
        
        try:
            if not self.client.is_exist(remote_name):
                print('不存在该文件')
                return
            
            # 普通下载链接
            download_url = self.client.get_download_link(remote_name)
            print(f'下载链接: {download_url}')
            
            # 询问是否需要防盗链
            response = input('是否生成防盗链？(y/N): ').strip().lower()
            if response in ['y', 'yes', '是']:
                try:
                    timestamp_url = self.client.get_timestamp_link(remote_name)
                    print(f'防盗链: {timestamp_url}')
                except Exception as e:
                    print(f"生成防盗链失败: {e}")
        except Exception as e:
            print(f"获取链接失败: {e}")
    
    def show_config(self, *args):
        """显示配置"""
        config = get_config()
        print("\n当前配置:")
        print("-" * 30)
        
        # 显示配置信息（隐藏敏感信息）
        config_dict = config.to_dict()
        for key, value in config_dict.items():
            if key in ['access_key', 'secret_key', 'encrypt_key'] and value:
                display_value = f"{value[:8]}..." if len(value) > 8 else "已设置"
            else:
                display_value = value
            print(f"  {key}: {display_value}")
        
        print(f"\n配置文件: {config.config_file}")
        if config.is_configured():
            print("✓ 配置完整")
        else:
            print("✗ 配置不完整，请运行 'qnshare init' 进行配置")
    
    def show_help(self, *args):
        """显示帮助"""
        print("\n可用命令:")
        print("-" * 50)
        
        # 按功能分组显示命令
        groups = {
            "文件管理": ['l/list', 'p/put/upload', 'g/get/download', 'd/del/delete'],
            "网络功能": ['s/set/fetch', 'r/refresh', 'link'],
            "系统功能": ['config', 'help/h/?', 'exit/quit/q']
        }
        
        for group_name, commands in groups.items():
            print(f"\n{group_name}:")
            for cmd in commands:
                # 获取第一个命令的描述
                first_cmd = cmd.split('/')[0]
                if first_cmd in self.commands:
                    desc = self.commands[first_cmd][0]
                    print(f"  {cmd:<20} - {desc}")
        
        print(f"\n提示:")
        print(f"  - 输入命令后按回车执行")
        print(f"  - 大部分命令支持简写（如 l 代表 list）")
        print(f"  - 输入 'exit' 或 'q' 退出程序")
    
    def exit_shell(self, *args):
        """退出Shell"""
        print("再见！")
        self.running = False
    
    def run(self):
        """运行交互式Shell"""
        print("=" * 60)
        print("🎯 QnShare 交互式模式")
        print("=" * 60)
        print("欢迎使用 QnShare 交互式文件管理工具！")
        print("输入 'help' 查看可用命令，输入 'exit' 退出程序")
        
        # 检查配置
        config = get_config()
        if not config.is_configured():
            print("\n⚠️  警告: 尚未配置，请先运行 'qnshare init' 进行初始化")
            print("或者在交互模式中输入 'config' 查看配置状态")
        
        print("-" * 60)
        
        while self.running:
            try:
                # 显示提示符
                user_input = input("\nqnshare> ").strip()
                
                if not user_input:
                    continue
                
                # 解析命令和参数
                parts = user_input.split()
                command = parts[0].lower()
                args = parts[1:] if len(parts) > 1 else []
                
                # 执行命令
                if command in self.commands:
                    desc, func = self.commands[command]
                    func(*args)
                else:
                    print(f"未知命令: {command}")
                    print("输入 'help' 查看可用命令")
                    
            except KeyboardInterrupt:
                print("\n\n使用 'exit' 命令退出程序")
            except EOFError:
                print("\n再见！")
                break
            except Exception as e:
                print(f"执行命令时出错: {e}")


def start_interactive_mode():
    """启动交互式模式"""
    shell = InteractiveShell()
    shell.run()
