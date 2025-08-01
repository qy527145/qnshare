# -*- coding: utf-8 -*-
"""
命令行接口模块
提供qnshare的CLI命令
"""

import os
import sys
from pathlib import Path
from urllib.request import urlretrieve
from typing import List

import click

from .client import QiniuClient
from .config import get_config, init_config, show_config
from .exceptions import QnShareError, ConfigValidationError
from .utils import pybyte, extract_filename_from_url


def handle_errors(func):
    """错误处理装饰器"""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except QnShareError as e:
            click.echo(f"错误: {e}", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"未知错误: {e}", err=True)
            sys.exit(1)
    return wrapper


@click.group(invoke_without_command=True)
@click.version_option()
@click.option('--interactive', '-i', is_flag=True, help='启动交互式模式')
@click.pass_context
def cli(ctx, interactive: bool):
    """七牛云文件共享工具"""
    if interactive:
        from .interactive import start_interactive_mode
        start_interactive_mode()
        sys.exit(0)
    elif ctx.invoked_subcommand is None:
        # 如果没有子命令且没有交互式选项，显示帮助
        click.echo(ctx.get_help())


@cli.command()
@click.option('--access-key', prompt='Access Key', help='七牛云Access Key')
@click.option('--secret-key', prompt='Secret Key', hide_input=True, help='七牛云Secret Key')
@click.option('--encrypt-key', help='加密密钥（用于防盗链，留空将在需要时自动生成）')
@click.option('--prefix', default='share/', help='文件前缀')
@click.option('--dead-time', default=3600, help='链接有效期（秒）')
@click.option('--bucket-name', help='存储空间名称（留空则自动获取第一个）')
@click.option('--domain', help='绑定域名（留空则自动获取第一个）')
@handle_errors
def init(access_key: str, secret_key: str, encrypt_key: str, prefix: str,
         dead_time: int, bucket_name: str, domain: str):
    """初始化配置"""
    # 如果没有提供encrypt_key，设置为空（将在需要时自动生成）
    if encrypt_key is None:
        encrypt_key = ''
    if bucket_name is None:
        bucket_name = ''
    if domain is None:
        domain = ''

    init_config(access_key, secret_key, encrypt_key, prefix, dead_time, bucket_name, domain)
    click.echo("配置初始化成功！")

    # 显示配置摘要
    click.echo("\n配置摘要:")
    click.echo(f"  文件前缀: {prefix}")
    click.echo(f"  链接有效期: {dead_time}秒")
    if bucket_name:
        click.echo(f"  存储空间: {bucket_name}")
    else:
        click.echo(f"  存储空间: 将自动获取第一个可用空间")
    if domain:
        click.echo(f"  绑定域名: {domain}")
    else:
        click.echo(f"  绑定域名: 将自动获取第一个可用域名")
    if encrypt_key:
        click.echo(f"  防盗链密钥: 已设置")
    else:
        click.echo(f"  防盗链密钥: 将在首次使用时自动生成")

    click.echo("\n提示:")
    click.echo("- 存储空间和域名如未指定，系统会自动获取账户下的第一个")
    click.echo("- 防盗链密钥用于生成带时间戳的安全下载链接")
    click.echo("- 可随时使用 'qnshare config' 命令查看或修改配置")


@cli.command()
@click.option('--set-encrypt-key', is_flag=True, help='设置防盗链加密密钥')
@click.option('--generate-encrypt-key', is_flag=True, help='生成新的防盗链加密密钥')
@click.option('--set-bucket', help='设置存储空间名称')
@click.option('--set-domain', help='设置绑定域名')
@click.option('--list-buckets', is_flag=True, help='列出可用的存储空间')
@click.option('--list-domains', help='列出指定存储空间的绑定域名')
@handle_errors
def config(set_encrypt_key: bool, generate_encrypt_key: bool, set_bucket: str,
           set_domain: str, list_buckets: bool, list_domains: str):
    """显示或修改当前配置"""
    config_obj = get_config()

    # 处理加密密钥设置
    if set_encrypt_key:
        current_key = config_obj.get('encrypt_key', '')
        if current_key:
            click.echo(f"当前加密密钥: {current_key[:8]}...")

        new_key = click.prompt('请输入新的加密密钥', default='', show_default=False)
        if new_key.strip():
            config_obj.set('encrypt_key', new_key.strip())
            config_obj.save()
            click.echo("加密密钥已更新")
        else:
            click.echo("加密密钥未更改")
        return

    if generate_encrypt_key:
        import secrets
        import string
        new_key = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        config_obj.set('encrypt_key', new_key)
        config_obj.save()
        click.echo(f"已生成新的加密密钥: {new_key}")
        return

    # 处理存储空间设置
    if set_bucket:
        config_obj.set('bucket_name', set_bucket)
        config_obj.save()
        click.echo(f"存储空间已设置为: {set_bucket}")
        return

    # 处理域名设置
    if set_domain:
        config_obj.set('domain', set_domain)
        config_obj.save()
        click.echo(f"域名已设置为: {set_domain}")
        return

    # 列出存储空间
    if list_buckets:
        try:
            from .client import QiniuClient
            client = QiniuClient()
            buckets, _ = client.bucket_manager.list_bucket('')
            if buckets:
                click.echo("可用的存储空间:")
                for bucket in buckets:
                    bucket_id = bucket.get('id', '')
                    bucket_name = bucket.get('name', '')
                    current = " (当前)" if bucket_id == config_obj.get('bucket_name') else ""
                    click.echo(f"  {bucket_id} - {bucket_name}{current}")
            else:
                click.echo("没有找到存储空间")
        except Exception as e:
            click.echo(f"获取存储空间列表失败: {e}", err=True)
        return

    # 列出域名
    if list_domains:
        try:
            from .client import QiniuClient
            client = QiniuClient()
            domains, _ = client.bucket_manager.bucket_domain(list_domains)
            if domains:
                click.echo(f"存储空间 '{list_domains}' 的绑定域名:")
                for domain in domains:
                    current = " (当前)" if domain == config_obj.get('domain') else ""
                    click.echo(f"  {domain}{current}")
            else:
                click.echo(f"存储空间 '{list_domains}' 没有绑定域名")
        except Exception as e:
            click.echo(f"获取域名列表失败: {e}", err=True)
        return

    # 显示当前配置
    config_dict = show_config()
    click.echo("当前配置:")
    for key, value in config_dict.items():
        click.echo(f"  {key}: {value}")

    # 显示配置文件位置
    click.echo(f"\n配置文件位置: {config_obj.config_file}")

    # 显示配置状态
    if config_obj.is_configured():
        click.echo("✓ 配置完整，可以正常使用")
    else:
        click.echo("✗ 配置不完整，请运行 'qnshare init' 进行初始化")

    # 显示配置管理提示
    click.echo(f"\n配置管理命令:")
    click.echo(f"  qnshare config --list-buckets           # 列出存储空间")
    click.echo(f"  qnshare config --set-bucket <name>      # 设置存储空间")
    click.echo(f"  qnshare config --list-domains <bucket>  # 列出域名")
    click.echo(f"  qnshare config --set-domain <domain>    # 设置域名")


@cli.command()
@click.option('--prefix', help='文件前缀过滤')
@handle_errors
def list(prefix: str):
    """列出云端文件"""
    client = QiniuClient()
    files = client.get_file_list(prefix)
    
    # 过滤掉前缀，只显示文件名部分
    display_prefix = prefix or client.prefix
    split_len = len(display_prefix)
    filtered_files = [file for file in files if file['key'][split_len:]]
    
    if not filtered_files:
        click.echo("没有找到文件")
        return
    
    click.echo("=" * 50)
    click.echo(f"{'大小':>10}\t文件名")
    click.echo("=" * 50)
    
    for file in filtered_files:
        size_str = pybyte(file['fsize'])
        filename = file['key'][split_len:]
        click.echo(f"{size_str:>10}\t{filename}")
    
    click.echo("=" * 50)
    click.echo(f"一共 {len(filtered_files)} 个文件")


@cli.command()
@click.argument('files', nargs=-1, required=True)
@click.option('--delete-after', type=int, help='上传后自动删除的天数')
@handle_errors
def upload(files: List[str], delete_after: int):
    """上传本地文件"""
    client = QiniuClient()
    
    for file_path in files:
        if not os.path.exists(file_path):
            click.echo(f"文件不存在: {file_path}", err=True)
            continue
        
        click.echo(f"正在上传: {file_path}")
        try:
            remote_name = client.upload_local_file(
                file_path, 
                delete_after_days=delete_after
            )
            click.echo(f"上传成功: {remote_name}")
        except Exception as e:
            click.echo(f"上传失败 {file_path}: {e}", err=True)


@cli.command()
@click.argument('filename')
@click.option('--output', '-o', help='输出文件名')
@handle_errors
def download(filename: str, output: str):
    """下载云端文件"""
    client = QiniuClient()
    
    # 添加前缀
    remote_name = f"{client.prefix}{filename}"
    
    if not client.is_exist(remote_name):
        raise FileNotFoundError(f"文件不存在: {filename}")
    
    output_name = output or filename
    click.echo(f"正在下载: {filename}")
    
    try:
        download_url = client.get_download_link(remote_name)
        urlretrieve(download_url, output_name)
        click.echo(f"下载成功: {output_name}")
    except Exception as e:
        click.echo(f"下载失败: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('url')
@click.option('--name', help='保存的文件名')
@click.option('--delete-after', type=int, help='下载后自动删除的天数')
@click.option('--download/--no-download', default=True, help='是否同时下载到本地')
@handle_errors
def fetch(url: str, name: str, delete_after: int, download: bool):
    """离线下载网络文件"""
    client = QiniuClient()
    
    if not name:
        name = extract_filename_from_url(url)
    
    remote_name = f"{client.prefix}{name}"
    
    click.echo(f"正在离线下载: {url}")
    try:
        client.fetch_url(url, remote_name, delete_after)
        click.echo(f"离线下载成功: {name}")
        
        if download:
            click.echo(f"正在下载到本地: {name}")
            download_url = client.get_download_link(remote_name)
            urlretrieve(download_url, name)
            click.echo(f"本地下载成功: {name}")
            
    except Exception as e:
        click.echo(f"离线下载失败: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('filename')
@handle_errors
def delete(filename: str):
    """删除云端文件"""
    client = QiniuClient()
    
    remote_name = f"{client.prefix}{filename}"
    
    if not client.is_exist(remote_name):
        raise FileNotFoundError(f"文件不存在: {filename}")
    
    if click.confirm(f"确定要删除文件 '{filename}' 吗？"):
        client.delete_file(remote_name)
        click.echo(f"删除成功: {filename}")
    else:
        click.echo("取消删除")


@cli.command()
@click.argument('filename')
@handle_errors
def refresh(filename: str):
    """刷新文件CDN"""
    client = QiniuClient()
    
    remote_name = f"{client.prefix}{filename}"
    
    if not client.is_exist(remote_name):
        raise FileNotFoundError(f"文件不存在: {filename}")
    
    client.refresh(remote_name)
    click.echo(f"CDN刷新成功: {filename}")


@cli.command()
@click.argument('filename')
@click.option('--timestamp/--no-timestamp', default=False, help='生成带时间戳的防盗链')
@handle_errors
def link(filename: str, timestamp: bool):
    """获取文件下载链接"""
    client = QiniuClient()

    remote_name = f"{client.prefix}{filename}"

    if not client.is_exist(remote_name):
        raise FileNotFoundError(f"文件不存在: {filename}")

    if timestamp:
        url = client.get_timestamp_link(remote_name)
        click.echo(f"带时间戳链接: {url}")
    else:
        url = client.get_download_link(remote_name)
        click.echo(f"下载链接: {url}")


@cli.command()
@handle_errors
def interactive():
    """启动交互式模式（类似原版qn.py的体验）"""
    from .interactive import start_interactive_mode
    start_interactive_mode()


def main():
    """主入口函数"""
    # 检查配置
    config = get_config()

    # 不需要配置的命令
    no_config_commands = ['init', '--help', '--version', 'interactive', '-i', '--interactive']

    # 检查是否有不需要配置的命令或选项
    needs_config = True
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg in no_config_commands or arg.startswith('--help'):
                needs_config = False
                break

    if needs_config and not config.is_configured():
        click.echo("错误: 尚未配置，请先运行 'qnshare init' 进行初始化", err=True)
        sys.exit(1)

    cli()


if __name__ == '__main__':
    main()
