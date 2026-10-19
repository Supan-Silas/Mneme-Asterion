# 评测申请草稿 · 待复核后提交

本文件不包含任何真实密钥。新仓库并不保证平台允许同邮箱重发Key；应如实说明迁移背景，不重复申领评测额度。

| 字段 | 准备值 |
|---|---|
| 系统名称 | Mneme-Asterion / AMI baseline |
| 版本名称 | v0 |
| 赛道 | Textual Memory |
| 组别 | 学术榜 / 开源方法榜（以平台现行名称为准） |
| Add | https://101.201.140.97/add |
| Search | https://101.201.140.97/search |
| Health | https://101.201.140.97/health |
| 认证方式 | Authorization: Token；服务也兼容 Bearer |
| 记忆系统 Key | 仅在官方受控表单内填写 `/etc/ami/ami.env` 的 AMI_AUTH_TOKEN |
| GitHub | https://github.com/Supan-Silas/Mneme-Asterion |
| 固定 commit | 提交时填写新仓库标签v0所指commit SHA（git rev-parse v0）；不要使用旧来源commit |
| 首次 Smoke 并发 | Add 1 / Search 1 |
| 当前服务准入上限 | 此前运行检查为Add4/Search8；最新环境文件为Add16/Search0，启动后曾变更，尚未重启确认；均非已验证吞吐量 |

## 提交说明草稿

本次为原已申请系统的服务器迁移及工程整理。原平台版本为 ami-deployment-v1.0-rc1。新仓库统一发布 AMI 复现、完整公开源数据的独立小 benchmark 抽样/prepare工具与部署文档；Mneme-Asterion 是工程工作台名称，并非新的原创记忆算法。

原“新增版本”快捷入口返回 endpoint is immutable for this leaderboard key，申请表未显示文档描述的已有Key新增版本选项，因此请求官方协助迁移或确认重新申请方式。此次不请求绕过原Key评测额度，也不把部署迁移视为独立方法。

记忆实现来源于 Xuhao Lin 的 ActiveMemoryIndex，保留 MIT 许可与署名，原始工作及所有适配修改见 ATTRIBUTION.md、CHANGELOG.md、SOURCE_ORIGIN.json。上游快照的确切Git commit未知，已有源码指纹固定，不伪造上游版本信息。

服务自行托管于阿里云北京ECS，Ubuntu22.04、8vCPU/32GiB、100GiB云盘、200Mbps按流量EIP。单worker、SQLite持久化、Nginx公网HTTPS、IP证书自动续期；后端仅监听loopback。Add同步持久化并可立即Search；重复request_id/user_id幂等，按user_id隔离。Search返回记忆证据，不输出最终答案。

LLM相关组件使用gpt-4o-mini；Embedding使用阿里云text-embedding-v4、1024维。凭据通过环境配置。已有公网小规模真实链路验证；尚未通过此次地址的官方Smoke/Full，不声明质量成绩或Full容量保证。官方评测内容及派生副本仅用于当前评测，任务结束30天内清理，并覆盖相关备份。

新仓库本地benchmark只访问授权公开来源。它不属于官方私有评测套件，不会把gold、rubric、能力标签或题集文件传给记忆服务。模型、输入、预算及评分规则会随实验配置冻结。
