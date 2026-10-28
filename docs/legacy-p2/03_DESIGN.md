# P2 详细设计与改造地图

## 执行链

`Add → 原文 journal + AMI 原文/事实/更新索引 → AMI Search → R1Q 原文补证 → P2-W2 撤回过滤 → P2-P 状态提示 → Search data → 外部 Reader → 外部 Judge`

本包是完整记忆服务，Answer/Judge 不属于参赛系统。`mneme_e` 的目录名是历史继承，P2 入口实际替换了其 `/search` 路由。

## 1. 写入、建库与隔离

`mneme_e/service.py:add` 先按 user_id 加锁、将原始请求写入 `e_raw_requests`，再调用 `app/main.py:add`。传给 AMI 的消息加入说话人；无时间时明确“记录日期未知”，不以入库时间推断事件时间。

`app/llm.py` 提取事实、解析查询与更新意图；`app/embed.py` 对原文/事实使用 text-embedding-v4；`app/store.py` 用 SQLite 持久化及内存索引检索；`app/updates.py` 实现基底的更新识别/旧值处理。沿用 AMI rc3 配置。

原文 journal 可见性与 AMI 成功请求表连接：原文先暂存不代表 Add 成功，只有原生写入成功的请求才进入 P2 原文搜索。相同 user_id/request_id 同内容幂等，内容冲突返回409。所有 Search 按 user_id 隔离，session_id 只标识来源。

新数据库必须包含原文 journal；旧 AMI 数据库无该表中对应消息时启动拒绝，不能静默退化为缺原文的 P2。SQLite FULL，单 worker；备份使用一致性 SQLite backup，不直接复制运行中的主库文件而漏掉 WAL。

## 2. AMI 基础检索

`p2_service.py:search` 调用 native.search(top_k=100)。基底结合原文查询与用户口吻 recall 查询、向量候选、事实和原文，应用更新规则，并按既有 RAW_FIRST/邻居窗口组织结果。邻接补全已存在：AMI 默认 WINDOW_RADIUS=1；后续原文补证也独立看相邻消息。

默认 RETURN_LIMIT=100、字符预算400000、RAW_FIRST=1、WINDOW_RADIUS=1、UPDATE_VERSION=7。C1 的词法 RRF 分支未启用（AMI_LEXICAL_ENABLED=0）。

## 3. R1Q：先明确缺什么，再补原文

`repair_quotes.py:generate_r1q` / `repair_v1.py` / `variants.py` / `e_core/methods.py`：

1. 把 AMI 基础材料按4096-token打包给规划器，输出 needed、gap 和最多3个检索词。这里4096是内部规划预算，不是最后外部 Reader 的窗口。needed=false 时基础材料直接保留。
2. 对完整原始消息做 BM25：原问题最多24候选，每个规划词最多12候选，同 session 邻居±1；候选打包最多24000tokens。排除通用 Assistant 等非个人记录，但保留具名人物即使其角色是 assistant。
3. 选择器先写 scope：subject_quote、requested_relation、operation（事实、列表、数量、比较等）。提示词也要求区分事件/时间，但不是所有语义要求都由类型检查保证。
4. 对每段支持材料验证 source_id、逐字 quote、重复 ID、scope 字面依据。错误 ID 只有在引用能唯一映射原文时才修正；歧义、找不到、意译引用不擅自替换为其他内容。
5. 最多3段、合计600tokens，带来源、说话人和必要句子边界；放在基础材料前面，保留基础前100-n项。它可能挤掉尾部证据；600是冻结实验预算，不随外部窗口自动放大。

例（说明用合成数据）：问题“Alice 养的乌龟在哪里买？”基础材料只说 Alice 喜欢动物；原文“我在宠物店买了这只乌龟”只有能绑定 Alice、且引用与原文一致时才可补入。单纯出现“宠物店”不证明那是 Alice 的乌龟。当前代码能校验引用真实，却不能完全证明人物/事件语义绑定正确，这正是后续优化方向。

## 4. P2 三层处理

### 第一层：哪些撤回仍有效

`state_withdrawal.py` 与 `state_withdrawal_v2.py:withdrawal_state` 扫描原文，识别显式英文撤回表达，例如 Please forget / do not remember / stop using / remove。限制控制材料预算约14000tokens，并审计省略。区分部分明确的 fictional/hypothetical 情形；恢复要求同说话人之后显式 remember/restore/use again 且属性词匹配。

当前主要覆盖显式英文指令；间接表达、别名和复杂引用是后续改进点。

### 第二层：只删除受影响片段

在已选证据上让 mini 提议精确删除区间，按约16000token批次处理；代码再检查 source quote、span、属性重合和具名主体。宽泛删除包含无关分句时拒绝，不把整条记忆无差别删除。对撤回请求自身重复旧值、以及明确确认回声也做确定性过滤。

例：证据“Alice likes coffee. Alice has a dog.”，Alice明确撤回咖啡偏好，应保留养狗信息。删除需要通过原文片段与范围校验。

这里过滤的是返回给 Reader 的材料，原数据库记录仍保留。

### 第三层：防止从背景猜回旧偏好

`state_policy.py:add_policy_notice` 判断当前问题是否直接需要已撤回属性。相关时把固定 NOTICE 加到首条证据前；无证据时返回 memory-status。NOTICE 不含旧值，说明该属性不可用于个性化、保留其他有效记忆、可给一般建议。无相关撤回时不加。

例：咖啡偏好已撤回，问题“按我的口味推荐饮品”，不能因为职业/生活背景猜回咖啡；但问“我养什么宠物”不应因为饮品撤回而丢失狗的证据。

NOTICE 的完整文本位于 `state_policy.py`，属于当前 P2 的固定实现。

## 5. HTTP 与失败边界

`p2_service.py:encode_result` 必须返回变换后的 text，不能按同一ID取回旧content，否则撤回会被撤销。输出不超 min(top_k,100)。上游临时异常返回错误，不静默退回B0并仍标成P2。

模型调用固定 mini、temperature=0、seed=17，最多3次结构校验尝试，普通输出上限8192、相关性判断1000。SDK重试/超时由配置决定；它们与3次格式修复不同。温度0和seed不保证确定性。

服务内LLM8、Embedding4，Add准入4、Search8；每用户锁保证一致性。调整并发时，主要观察上游429/503和实际成功RPM。

## 6. 继续优化的控制变量

保留基底、原文及冻结配置；只改一个模块。先核对错误题：原文有没有→事实/更新有没有→候选有没有→补证有没有→Reader是否见到→Answer是否用对→Judge是否一致。证据真实不等于证据相关，证据在场不等于模型会正确使用。

QBind追加前一句整条消息在微实验中有收益，但861题全量无净提升，故未合入默认P2。下一步可测试只补与当前关系相关的问句/事件，不扩写无关句；必须同时检查原先答对题的退步。

对照应冻结数据库并用一致Reader/评分口径，再做独立建库的完整评测。内部规划4096、支持600、外部Answer输入117760是三个不同约束，不能混用。不得让检索模块读取金标或错题标签。
