# 系统设计

## 设计目标

Mneme-Asterion 将长期记忆检索中的三个问题分开处理：找得到相关信息、返回的信息有来源、信息在当前语境下仍然有效。

写入层沿用 AMI 的原文与事实双通道；检索层增加问题驱动的原文补证；状态层按人物和属性处理撤回及恢复。P2 表示前两者加撤回处理的对照版本，ScopedState V4 在其上增加查询局部状态投影。

## 模块与数据流

| 模块 | 代码 | 职责 |
|---|---|---|
| 启动与配置 | `run_v4.py`、`mneme_asterion/cli.py`、`app/config.py` | 配置加载、模型与方法身份、服务启动 |
| 持久化 | `app/store.py`、`mneme_e/raw_store.py` | 事实／原文向量、更新记录、原文日志 |
| 写入 | `app/main.py`、`app/llm.py`、`app/updates.py` | 事实抽取、更新识别和提交 |
| 基础检索 | `app/main.py`、`app/rerank.py` | AMI检索与证据组织 |
| 原文补证 | `e_core/`、`mneme_asterion/retrieval/` | 问题范围、BM25、邻接消息、引用核验 |
| 撤回处理 | `mneme_asterion/state/withdrawal.py`、`echo.py`、`policy.py` | 显式控制识别、片段过滤、有效性提示 |
| 作用域状态 | `mneme_asterion/state/adapter.py`、`intent.py`、`transitions.py`、`ownership.py`、`scope.py`、`projection.py` | 人物／属性状态与查询局部投影 |
| 来源关联 | `mneme_asterion/provenance.py` | 证据到写入请求及原始消息的映射 |
| HTTP输出 | `mneme_asterion/service.py`、`mneme_e/service.py` | 用户隔离、Add/Search接口与结果序列化 |

`retrieval/` 将候选构造、检索规划、引用核验分别放在 `support.py`、`planning.py`、`quotes.py`。`state/` 将控制识别、撤回片段处理、残留旧值处理、状态转换、归属过滤和查询投影分层组合；`adapter.py`负责连接状态处理与来源信息。

## 写入与建库

1. 验证请求与鉴权，获取当前用户锁。
2. 以 `(user_id, request_id)` 记录原文请求。
3. AMI进行事实抽取、更新识别与向量编码。
4. 提交SQLite事务并更新用户向量缓存，返回成功。

原文日志只对原生写入已提交的请求可见。同一请求重复提交相同内容可幂等重试；同一标识对应不同内容返回冲突。原文按已提交日志的顺序组织，仅合并相邻的同会话片段，保留交错会话的顺序。

SQLite使用WAL与FULL同步策略；向量以1024维float32存储。默认抽取失败时可保留原文继续写入，`AMI_EXTRACT_REQUIRED=1`可将抽取成功设为必要条件。

## 检索与原文补证

AMI先返回最多100条基础证据。规划器读取其中最多4096 token，识别问题涉及的人物、关系、时间范围和回答操作，生成最多3个补充检索词。

原问题与补充词用于检索原文块，并扩展邻接消息。原文块约420 token，选择器最多接收24,000 token候选。选择器返回来源ID和逐字引用；引用需在指定来源中匹配。ID不匹配时，只接受可唯一定位的字面引用；无法定位的内容被舍弃。

最终最多补入3段、合计600 token的材料，前置于AMI基础证据。这里的4096和600属于方法内部预算；下游Reader的总输入窗口是另一项配置。

## 撤回与恢复

P2从原文中识别显式撤回指令，过滤受影响的证据片段，并在需要时加入不包含旧值的状态提示。

ScopedState进一步构建 `S(人物, 属性, 位置)`：

| 输入 | 状态解释 |
|---|---|
| “My project color is violet.” | 记录属性值 |
| “Please forget my project color.” | 属性被撤回 |
| “Remember it again if I confirm tomorrow.” | 条件尚未成立，保持撤回 |
| “Please remember my project color again: amber.” | 明确恢复，使用新值 |

状态控制要求可识别的说话人、属性范围和有效指令；引用、问句和条件式表达不会直接变成恢复授权。同一精确范围按后续有效控制更新。

检索时围绕当前问题投影状态：被撤回属性不再由旧副本或他人的值补回；未撤回属性继续保留。恢复后只有能够证明早于恢复边界的来源才被认定为旧来源。HTTP序列化使用处理后的文本，避免按原ID重新取值时恢复已过滤内容。

## 来源与适用范围

来源链为 `item.id → request_id → message source_id`，粒度是写入请求。状态提示表达来源支持的有效性信息，供下游Reader解释。

当前状态规则主要覆盖明确英文指令和字面属性。无法识别的范围保持P2处理结果。撤回作用于检索输出，原始记录仍存储在数据库中。完整实验条件与覆盖范围见[评测](evaluation.md)。
