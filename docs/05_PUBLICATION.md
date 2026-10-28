# AML 最终提交准备

核对日期：2026-10-28。依据[AML官方文档](https://agentmemories.ai/zh-cn/docs)及[官方仓库](https://github.com/AML-memory/agent-memory-leaderboard)。

## 公开版本

- 系统名：**Mneme-Asterion**；公开版本：**v4.0（ScopedState）**。
- 仓库：https://github.com/Supan-Silas/Mneme-Asterion 。本次发布将主分支从旧v0更新为完整V4，旧版本保留在Git历史。
- 检出正式发布标签 `v4.0` 后，用 `git rev-parse HEAD` 获取真实commit，登记到平台。不要把旧v0 commit当作V4。仓库旧历史和MIT署名应保留。
- Add：`https://101.201.140.97/add`；Search：`https://101.201.140.97/search`；Health：`https://101.201.140.97/health`。鉴权Bearer，密钥通过平台私密字段提供。
- 当前已绑定版本标签p2实际路由到修复V4。提交前将平台版本说明与真实方法、commit对应；如界面不能改标签，向审核方明确说明，不更换已锁定端点。

## 可粘贴的提交说明

Mneme-Asterion v4.0（ScopedState）基于Xuhao Lin的ActiveMemoryIndex历史rc3复现基底，保留作者署名和MIT许可。我们增加有来源核验的原文补证、显式撤回过滤、按人物与属性作用域解释撤回及恢复的状态表达，并修复交错session顺序和条件式恢复误判。来源、改动和文件哈希随公开代码提供；固定commit请填写实际发布提交。

所有LLM调用使用gpt-4o-mini，嵌入使用text-embedding-v4。服务在阿里云自部署，单worker、SQLite WAL持久化、Nginx HTTPS。同步Add支持重试幂等；Search按user_id隔离，只返回记忆证据，由平台统一Answer/Eval。状态处理会产生有来源依据的有效性提示，说明属性已撤回或恢复；不包含标准答案、评分指令或针对隐藏评测ID的分支。撤回是检索层有效性控制，并非物理删除。官方评测原始数据不包含在公开包中。

## 发布与正式评测顺序

1. 本地验收通过，推送完整代码到公开仓库，记录真实commit及发布包SHA256。
2. 核对平台名称／版本说明、commit、端点和鉴权；核对线上核心哈希与发布包一致。
3. 本次已完成实际证书续期验证，保持自动续期开启，再启动Full；Full接受后保持代码、配置、路由稳定，直至结束。

材料截止为10月31日23:59（北京时间），评测关闭为11月4日23:59；Full通常需要0.5–2天。应在截止前完成公开版本和提交，不能等到最后一刻。官方审核决定参赛合规与最终成绩；本次工程审查不代替官方审核。
