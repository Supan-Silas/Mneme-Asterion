# HTTP API

基础地址示例：`http://127.0.0.1:8014`。Add/Search使用 `Authorization: Bearer <service-token>`；Token对应配置中的 `AMI_AUTH_TOKEN`。

## GET /health

无需鉴权，正常返回HTTP200：

```json
{"status":"ok"}
```

## POST /add

```json
{
  "request_id":"example-001",
  "user_id":"alice",
  "session_id":"session-1",
  "messages":[
    {"role":"user","speaker":"Alice","content":"My project color is violet."}
  ]
}
```

成功响应：

```json
{"success":true,"request_id":"example-001","user_id":"alice","session_id":"session-1"}
```

`request_id`、`user_id`、`session_id`标识写入请求及其归属；消息使用文本content和user/assistant角色。成功返回表示写入已提交，可立即检索。同一user_id/request_id重复提交相同内容幂等；更改内容应使用新的request_id。

## POST /search

```json
{"user_id":"alice","query":"What is my project color?","top_k":100}
```

返回结构：

```json
{
  "data":[{"id":"evidence-id","content":"Source-backed memory text","score":1.0,"source_ids":["source-id"]}],
  "method":"ScopedStateV4"
}
```

`data`按检索顺序返回最多100条证据；数量同时受top_k限制。`content`是供回答模型使用的证据文本，包含必要的状态表达。没有相关记忆时可以返回空列表。撤回保护在有限重试后仍无法完成时，HTTP 200响应仅包含记忆暂不可用提示，不包含未完成保护的证据；该提示不是检索到的事实。查询只访问对应user_id的数据。选择题可在请求中提供 `options` 字符串数组，传入基础检索。

## 调用示例

```python
import httpx

with httpx.Client(
    base_url="http://127.0.0.1:8014",
    headers={"Authorization": "Bearer <service-token>"},
    timeout=600,
) as client:
    result = client.post("/search", json={
        "user_id": "alice", "query": "What is my project color?", "top_k": 100,
    })
    result.raise_for_status()
    memories = result.json()["data"]
```

## 错误处理

| 状态 | 含义与处理 |
|---|---|
| 401 | 鉴权失败，检查服务Token |
| 409 | 写入冲突，核对request_id及原始内容 |
| 422 | 请求字段或文本格式无效 |
| 429 | 服务或模型限流，按Retry-After退避 |
| 502／503等临时错误 | 上游或处理失败，调用方保留原请求进行有界重试 |

重试Add时使用相同请求ID和相同内容。具体响应可能包含更细的错误说明。
