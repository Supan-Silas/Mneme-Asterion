# 验证状态 · 2026-10-19

Mneme-Asterion 当前使用 AMI 复现方法，不声明原创算法或新成绩。原始复现记录保存在 `docs/history/`，其中的未来计划、路径、计数和旧阶段结论不代表当前状态。

## 阿里云现有部署

Ubuntu 22.04，Python 3.11 独立 Conda 环境；单进程 AMI，SQLite，全新运行数据库，外层 Nginx HTTPS。LLM 为 gpt-4o-mini，Embedding 为 text-embedding-v4、1024维。新 EIP 101.201.140.97。

2026-10-19 已从 Windows 公网客户端完成 2 次新增 Add、1 次重复 Add、5 次 Search。全部 HTTP200；字段回显、即时检索、top_k、两侧用户隔离和未知用户空结果通过。重复写入的 SQLite 测试记录摘要不变，没有额外 LLM 调用。该次 LLM 计数增加8、失败0；嵌入调用未单独计数，实际费用需查账单。

Bearer/Token 鉴权、未授权401、非法请求422通过。新IP证书受信任，续期模拟通过。测试后AMI active，未重启。仅7条合成测试 items，不是正式评测数据；无真实 benchmark 质量分数。

## 尚未完成

- 新仓库的发布 commit 与部署代码指纹核对（以最终生成的校验记录为准）。
- 平台现有 Key 的新地址绑定：快捷入口报 endpoint is immutable；需要官方确认迁移或重新申请流程。
- 新地址的官方 Smoke、正式 Full 和满负载容量验证。
- Mem0/InvMem/ReFind 在本次目标服务器上的原生依赖和真实方法评测。

此前开发已验证独立抽样与公共框架的离线路径；本候选会另行记录实际运行的人工离线检查。来源 hash 保证版本对应，不代表已经重现官方私有套件、Streaming 或论文/榜单分数。


## 本次v0发布候选的离线验证

2026-10-19在阿里云隔离临时目录运行，无线上环境文件、假模型、独立临时SQLite和loopback服务：AMI的26个独立测试文件全部退出0；37项HTTP检查全部通过；benchmark的90项测试全部通过（无跳过）。测试后线上AMI保持MainPID=900、NRestarts=0、active。测试摘要位于docs/verification。

Windows上的benchmark测试同样通过（90项、其中1项因本机未安装tiktoken而跳过）。继承的AMI独立测试在Windows存在SQLite临时目录清理及asyncio自管道与严格禁网guard兼容问题；HTTP断言通过但临时数据库清理曾失败。因此AMI完整测试与部署以已验证的Linux结果为准，不宣称完整Windows支持。

18个AMI app/reproduction Python源码与现有部署指纹一致，详见deploy/source-match.json。配置另行披露：环境文件的修改时间晚于服务启动，最新文件中Add16/Search0与此前检查的4/8不一致；它是文件快照，不保证已被运行进程加载。本次不修改配置或重启服务，官方Smoke先使用1/1。
