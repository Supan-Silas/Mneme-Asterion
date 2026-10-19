# Linux / 阿里云部署

现有验证部署仍位于 `/opt/aml/ami-reproduction`；发布新仓库不自动替换线上代码。以下模板用于另行明确部署，不在运行中的服务上直接重建数据库或重启。

## 环境与服务

Ubuntu22.04、Python3.11、独立Conda/venv，远程模型模式不要求GPU。安装根 `requirements-academic.txt`；不要在现有共享环境里混装GPU依赖。

```bash
python -m pip install -r requirements-academic.txt
python -m pip check
cp .env.example /path/to/private/ami.env
```

在私有配置中填写 OPENAI_API_KEY / OPENAI_BASE_URL、AMI_EMBED_API_KEY / AMI_EMBED_BASE_URL 和 AMI_AUTH_TOKEN。LLM必须为gpt-4o-mini，Embedding为text-embedding-v4；启动器会校验。AMI_AUTH_TOKEN是参赛方提供的记忆系统Key，不是官方ldbd Eval Key。

首次显式启动会进行付费embedding预热；Add/Search也会调用模型：

```bash
python -B -m reproduction.serve --mode academic \
  --env-file /path/to/private/ami.env \
  --db /path/to/private/memory-v4.sqlite3 --port 8012 --allow-paid-api
```

仅监听127.0.0.1，单worker。运行账号需要数据库目录及SQLite WAL/SHM写权限，环境文件限制为管理员/服务账号可读。不要混用fake向量数据库、不同embedding身份的数据库或多个不一致的进程缓存。

`deploy/ami.service` 是无凭据模板，需将代码目录替换成实际clone目录，保证独立环境路径和ami服务账号已存在，再由管理员安装。仅重启本服务也会重新触发embedding预热，须按实际授权操作。

## 当前已验证入口

- `https://101.201.140.97/health`：无需鉴权，成功时200。
- `https://101.201.140.97/add`：POST，必填 request_id/messages/user_id/session_id。
- `https://101.201.140.97/search`：POST，必填 query/user_id/top_k；options可选。

外层Nginx只代理这些路径；后端8012不对公网开放。安全组公网443用于HTTPS，80用于ACME HTTP-01，SSH22用于维护。现有服务器使用Let’s Encrypt短期IP证书，续期timer启用且模拟成功；保留80验证路径。EIP及证书状态需持续维护，节省停机期间官方无法访问接口或完成续期。

模板 `deploy/nginx.conf.example` 沿用已验证的新IP与证书名称；其他IP不可直接沿用证书。IP证书配置使用支持IP和shortlived profile的Certbot；本次已验证版本5.8.0。发布内容不附带私钥或证书账户凭据。

此前运行检查的准入配置为Add4/Search8，LLM8/Embedding4。最新环境文件显示Add16/Search0，且文件修改时间晚于服务启动时间，因此它不能视为已生效参数；本次未修改文件或重启服务。首次官方Smoke仍建议1/1。平台单次请求允许30分钟，Nginx当前代理超时1800秒。小规模HTTP成功不能代替满负载容量测试。

## 数据、版本与平台

发布固定commit前，比较服务目录中的app/与reproduction/源码指纹。真实模型配置由脱敏参数记录，密钥不参与公开指纹。重新提交申请时填固定仓库和commit、完整来源改动说明，并披露旧版本迁移原因。

平台新增版本会继承旧鉴权，因此Memory System Key必须与本服务一致。官方Key用于平台身份，不填进AMI_AUTH_TOKEN。现有Key的新端点绑定曾被平台拒绝；新仓库本身不会解除绑定限制或产生新评测额度。

先通过官方Smoke，再决定正式Full。服务端只负责Add/Search，官方Answer/Eval由平台执行；不要把本地benchmark targets、gold或官方私有数据放进服务路径。官方评测数据及其派生副本在任务结束30天内删除，同时落实备份清理；人工测试数据与真实评测scope分开。
