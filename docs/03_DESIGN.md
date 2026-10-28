# ScopedState v4：详细设计与实现

## 1. 系统边界和执行顺序

```text
Add：鉴权 → 同 user 锁 → 原文 journal 暂存 → AMI 抽取/更新/嵌入 → SQLite 提交与缓存更新 → 成功响应
Search：鉴权 → 同 user 锁 → 已提交原文 + AMI top100 → R1Q 补证 → P2 撤回过滤/状态提示 → v4 查询局部状态处理 → 返回证据
官方平台：证据 → Answer → Judge（不属于记忆服务）
```

v4 使用 P2 的完整系统，不是单独的补丁脚本。`launch.py` 在导入服务前读取配置；`p2_service.py` 是生产入口。`mneme_e/service.py` 的原 E Search 路由会被替换，Add 与原文存储继续复用。

## 2. 写入、建库和隔离

- `mneme_e/raw_store.py::stage` 记录 `(user_id, request_id, payload)`；同请求相同内容可重试，不同内容返回冲突。
- 原文暂存不等于 Add 成功。`history` JOIN 原生 `requests`，仅原生提交成功的请求可见。
- `app/main.py`、`app/llm.py`、`app/updates.py` 继承 AMI 的事实抽取、更新识别与查询处理；`app/embed.py` 调用嵌入；`app/store.py` 持久化并更新用户向量缓存。
- 单进程单 worker，每用户锁与 SQLite 事务控制一致性。256 个哈希锁可能让不同用户短暂共享锁，但不会共享检索范围。
- v4 状态处理不执行数据库删除，旧事实仍在磁盘。任务数据与派生副本的到期删除需要部署方另行执行。
- 当前修复版：只合并**相邻**同 session/时间的原文段，避免 A→B→A 会话交错写入被重排为 A→A→B。按提交可见的 journal 原始顺序解释指令，不按无依据的推测事件时间排序。

## 3. P2 的基础检索和补证

`repair_quotes.py::generate_r1q` 读取 AMI 基础证据，规划是否缺少关系、时间锚点或列表成员。当前规划器上下文仍为 **4096 token**；这是方法内部参数，与外部 Reader 的 117,760-token 总输入窗口不同。

规划器最多提出 3 个查询词；原问题也参与 BM25 检索。`e_core/base_tools.py` 将原文递归切为最多约 420 token 的片段，保留 source ID、说话人和时间。候选检索后补相邻消息，最多装入 24,000-token 候选。

选择器需说明问题涉及的人物、关系及 fact/list/count/comparison/duration/time 等操作，并给出原文逐字引用。`reconcile_quotes` 核验片段 ID 与原文引用；ID 不匹配时仅允许唯一字面匹配，不能用任意正文替换引用。

最终最多 3 段补证、600-token 预算，前置于基础证据并保持返回数量上限。这些参数继承已测 P2，不因发布整理而放大。

## 4. P2 的撤回处理

`withdrawal_state` 从当前已写入原文发现显式控制，按人物和后续声明检查状态。`state_withdrawal_v2.py` 对证据执行窄范围删除；删除必须引用真实 control ID、原文控制片段及实际证据片段，保留无关子句。

`state_policy.py` 必要时增加不包含旧值的状态提示。该提示是实现的一部分，需在 AML 来源和方法说明中公开；不能将其描述为没有影响 Reader 的普通原文。提示不含金标或评分指令，也不保证自动通过官方审核。

## 5. v4 的入口与来源补齐

`scoped_adapter.py::apply`：

```python
_, audit = withdrawal_state(raw, count)
_, preflight = finalize(query, evidence, raw, audit)
if preflight['scoped_parity']:
    return list(evidence), preflight
enriched, proof = attach(evidence, request_source_map(db_path, raw, user_id=user_id))
out, trace = finalize(query, enriched, raw, audit)
```

不激活时原样返回 P2 证据。激活时只读同用户数据库，沿 `item.id → request_id → payload source_id` 补来源。

**这是请求级来源，不是精确事实句级来源。**只有能证明所有关联来源都早于恢复时，才把证据视为旧来源；来源不全或跨越边界时不猜测。

## 6. 状态推导

`intent_scope_v5.py` 补充 `remove … from memory`、`stop remembering …` 等明确语法。`state_finalize_v6.py` 按规范化属性词集合区分状态，并检查：

- 指令来自可接受的用户来源；非引用、假设或条件式表达。
- 属性是可识别的多词名词范围，而非把旧值直接塞进“无值状态卡”。
- 恢复来自同一说话人、更晚位置，包含该属性的全部范围词。
- 同一精确属性范围以最后有效控制为准。

可简写为 `S(owner, attribute, t)`：撤回后为 withdrawn；符合上述条件的后续恢复令其 active。代码使用字面词集合和有界正则，不是通用语义状态机。

发布审查修复：`safe_source` 排除 if/unless/would/could/might、问句和引号等，防止条件恢复变成已恢复。明确无条件恢复仍可使用。

## 7. 查询局部投影

- `state_scoped_v3.py`：单一当前用户属性被撤回时，以有来源的撤回状态替代该问题的证据，防止其他副本或他人的值填充空槽；明确同事属性问题可返回同事声明。
- `state_scoped.py`：两属性固定问法，分别处理撤回属性与仍有效属性，避免一并清空。
- `state_scoped_v1.py`：处理其余有明确当前用户范围的状态提示；不确定时回退 P2。
- `state_projection_v4.py` 与 `state_scoped.py` 保留原评测版的同字节实现；运行入口实际导入后者。

例如撤回 access tag，但 delivery tag 仍有效，两个槽分别返回撤回状态与 delivery 的字面声明。投影不修改原始证据对象或原文数据库。

## 8. HTTP 输出和模型故障

`encode_result` 必须序列化**处理后的 text**，不能因为 ID 未变就重新拿原始 content，否则会恢复已屏蔽内容。返回条数不超过请求 top_k，最多 100。

模型临时故障返回可重试错误，不把失败伪装成成功的基础检索结果。内部格式恢复有界；不在生产服务中增加无限重试。官方调度与本地 benchmark 的全局费用账本不是这个服务的组成部分。

## 9. 参数与限制

| 项目 | 当前值／约束 |
|---|---|
| LLM | gpt-4o-mini |
| Embedding | text-embedding-v4，1024 维 |
| 基础候选／返回上限 | 100 |
| 规划器上下文 | 4096 token |
| 原文片段 | 约 420 token |
| 补证 | 最多 3 段，共 600 token |
| 候选选择上下文 | 24,000 token |
| v4 额外模型调用 | 0 |
| 并发 | 单 worker；默认 Add 4、Search 8；模型 8、Embedding 4 |
| v4 语言与表达 | 明确英文、字面属性、有界问法；未覆盖表达回退 P2 |

默认 `AMI_EXTRACT_REQUIRED=0` 继承已测配置，抽取失败路径可能仅保留原文；不应把每次 Add 成功等同于全部模型抽取成功。改变该开关属于新运行配置，需重新验证。
