# QnShare - 七牛云文件共享工具

一个简单易用的七牛云存储命令行工具，支持文件上传、下载、管理等功能。

## 特性

- 🚀 现代化的命令行界面
- 🔒 安全的配置管理（配置文件存储在用户目录）
- 📁 支持文件上传、下载、删除等操作
- 🌐 支持离线下载网络文件
- 🔄 支持CDN刷新
- 🔗 支持生成下载链接和防盗链
- 📦 可作为uv tool安装

## 安装

### 使用 uv（推荐）

```bash
# 作为工具安装
uv tool install qnshare

# 或者从本地安装
uv tool install .
```

### 使用 pip

```bash
pip install qnshare
```

## 快速开始

### 1. 初始化配置

首次使用需要配置七牛云的Access Key和Secret Key：

```bash
qnshare init
```

按提示输入您的七牛云密钥信息。配置文件将安全地存储在 `~/.qn/config.json`。

### 2. 基本使用

```bash
# 列出云端文件
qnshare list

# 上传文件
qnshare upload file1.txt file2.jpg

# 上传整个目录（递归，保留相对结构）
qnshare upload photos

# 下载文件
qnshare download file1.txt

# 离线下载网络文件
qnshare fetch https://example.com/file.zip

# 删除文件
qnshare delete file1.txt

# 刷新CDN
qnshare refresh file1.txt

# 获取下载链接
qnshare link file1.txt

# 获取防盗链（带时间戳，会自动生成加密密钥）
qnshare link file1.txt --timestamp

# 手动设置防盗链加密密钥（可选）
qnshare config --set-encrypt-key

# 重新生成随机加密密钥（可选）
qnshare config --generate-encrypt-key

# 配置存储空间和域名（可选）
qnshare config --list-buckets           # 列出可用存储空间
qnshare config --set-bucket my-bucket   # 设置存储空间
qnshare config --list-domains my-bucket # 列出域名
qnshare config --set-domain my.domain.com # 设置域名

# 启动交互式模式（类似原版体验）
qnshare interactive
# 或使用简写
qnshare -i
```

## 命令详解

### `qnshare init`
初始化配置，设置七牛云的Access Key、Secret Key等信息。

### `qnshare config [OPTIONS]`
显示或修改当前配置（敏感信息会被隐藏）。

选项：
- `--set-encrypt-key`: 设置防盗链加密密钥
- `--generate-encrypt-key`: 生成新的随机加密密钥
- `--set-bucket <name>`: 设置存储空间名称
- `--set-domain <domain>`: 设置绑定域名
- `--list-buckets`: 列出可用的存储空间
- `--list-domains <bucket>`: 列出指定存储空间的绑定域名

### `qnshare list [--prefix PREFIX]`
列出云端文件，可选择指定前缀过滤。

### `qnshare upload PATHS... [--delete-after DAYS] [--recursive/--no-recursive] [--hidden/--no-hidden] [--overwrite/--skip-existing] [--force] [--refresh]`
上传一个或多个本地文件或目录，可设置自动删除时间。

- 目录**默认递归**上传，并保留相对目录结构：`qnshare upload photos` 会把 `photos/2024/b.jpg` 传成 `<prefix>photos/2024/b.jpg`。
- 单个文件参数保持原行为，远端为 `<prefix><文件名>`。
- 隐藏文件（`.` 开头）默认跳过，`--hidden` 可包含。
- 云端已存在同名文件时默认**覆盖**；`--skip-existing` 改为跳过；`--force` 先删除再上传（用于重置元数据/生命周期）。
- `--refresh` 在上传完成后刷新这些文件的CDN缓存（自动按100个一批提交）。

```bash
# 上传整个目录（含子目录，保留结构）
qnshare upload photos

# 只传目录第一层，跳过隐藏文件
qnshare upload photos --no-recursive

# 当前目录全量同步：含隐藏文件、先删后传、并刷新CDN
qnshare upload . --hidden --force --refresh

# 云端已有同名文件时跳过，不覆盖
qnshare upload photos --skip-existing
```

只要有文件上传失败，命令退出码即为 `1`（空目录、跳过隐藏文件、CDN刷新失败都不算失败）。

### `qnshare download FILENAME [--output OUTPUT]`
下载云端文件到本地，可指定输出文件名。

### `qnshare fetch URL [--name NAME] [--delete-after DAYS] [--no-download]`
离线下载网络文件到云端，默认同时下载到本地。

### `qnshare delete FILENAME`
删除云端文件（需要确认）。

### `qnshare refresh FILENAME`
刷新文件的CDN缓存。

### `qnshare link FILENAME [--timestamp]`
获取文件下载链接，可选择生成带时间戳的防盗链。

### `qnshare interactive` 或 `qnshare -i`
启动交互式模式，提供类似原版qn.py的命令行体验。

在交互式模式中可用的命令：
- `l` 或 `list` - 列出文件
- `p` 或 `upload` - 上传文件或目录（不带参数时弹出文件选择对话框）
- `g <filename>` 或 `download <filename>` - 下载文件
- `s <url>` 或 `fetch <url>` - 离线下载
- `d <filename>` 或 `delete <filename>` - 删除文件
- `r <filename>` 或 `refresh <filename>` - 刷新CDN
- `link <filename>` - 获取文件链接
- `config` - 显示配置信息
- `help` - 显示帮助
- `exit` 或 `q` - 退出

## 配置文件

配置文件位于 `~/.qn/config.json`，包含以下字段：

```json
{
  "access_key": "your_access_key",
  "secret_key": "your_secret_key",
  "encrypt_key": "your_encrypt_key",
  "prefix": "share/",
  "dead_time": 3600,
  "bucket_name": null,
  "domain": null
}
```

- `access_key`: 七牛云Access Key（必需）
- `secret_key`: 七牛云Secret Key（必需）
- `encrypt_key`: 防盗链加密密钥（可选，留空时会在需要时自动生成）
- `prefix`: 文件前缀，默认为 "share/"
- `dead_time`: 防盗链有效期（秒），默认3600秒
- `bucket_name`: 存储空间名称（可手动设置，留空则自动获取第一个）
- `domain`: 绑定域名（可手动设置，留空则自动获取第一个）

## 编程接口

除了命令行工具，您也可以在Python代码中使用：

```python
from qnshare import QiniuClient, init_config

# 初始化配置（仅需一次）
init_config(
    access_key="your_access_key",
    secret_key="your_secret_key"
)

# 创建客户端
client = QiniuClient()

# 上传文件
remote_name = client.upload_local_file("local_file.txt")

# 获取下载链接
download_url = client.get_download_link(remote_name)

# 列出文件
files = client.get_file_list()
```

## 迁移指南

如果您之前使用的是旧版本的qn.py，请注意：

1. **配置方式变更**：不再使用硬编码的密钥，需要运行 `qnshare init` 进行配置
2. **命令行界面**：新的CLI命令替代了原有的交互式shell
3. **API变更**：建议使用新的 `QiniuClient` 类替代旧的 `Qiniu` 类

旧的接口仍然可用但已标记为弃用，建议尽快迁移到新接口。

## 安全注意事项

- 配置文件会自动设置适当的权限（仅用户可读写）
- 不要在代码中硬编码密钥信息
- 定期检查和更新您的七牛云密钥

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！