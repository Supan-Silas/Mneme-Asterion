# 配置

复制 `.env.example` 为 `.env`，由 `--env-file` 指定配置文件。该文件采用 `KEY=value` 格式，模型服务配置与记忆接口鉴权分别设置。

## 模型与接口

| 参数 | 默认值／用途 |
|---|---|
| `OPENAI_BASE_URL`、`OPENAI_API_KEY` | LLM服务地址与密钥 |
| `AMI_EMBED_BASE_URL`、`AMI_EMBED_API_KEY` | 嵌入服务地址与密钥 |
| `AMI_LLM_MODEL` | `gpt-4o-mini` |
| `AMI_EMBED_MODEL` | `text-embedding-v4` |
| `AMI_EMBED_BACKEND` | `openai`，使用兼容接口 |
| `AMI_EMBED_DIMENSIONS` | `1024` |
| `AMI_AUTH_SCHEME` | `bearer` |
| `AMI_AUTH_TOKEN` | Add/Search接口的访问Token |
| `P2_SCOPED_STATE` | `1`，启用ScopedState V4 |

`python -m mneme_asterion`验证以上模型与方法配置。P2对照可通过 `python -m mneme_asterion.cli --env-file <配置文件>` 配合 `P2_SCOPED_STATE=0`运行。

## 并发与超时

| 参数 | 默认值 |
|---|---:|
| `AMI_ADD_MAX_INFLIGHT` | 4 |
| `AMI_SEARCH_MAX_INFLIGHT` | 8 |
| `AMI_LLM_CONCURRENCY` | 8 |
| `AMI_EMBED_CONCURRENCY` | 4 |
| `AMI_ADMISSION_WAIT` | 45秒 |
| `AMI_RETRY_AFTER` | 10秒 |
| `AMI_LLM_TIMEOUT` | 180秒 |
| `AMI_EMBED_TIMEOUT` | 20秒 |
| `AMI_LLM_RETRIES`、`AMI_EMBED_RETRIES` | 0（SDK内部重试） |
| `AMI_PROVIDER_ATTEMPTS` | 3（阶段调用尝试上限） |
| `AMI_REQUEST_TIMEOUT` | 1500秒（请求总时限） |
| `AMI_GATE_WAIT` | 15秒 |
| `AMI_RETRY_BASE` | 0.5秒 |

HTTP请求并发与上游模型并发分别限流。阶段重试受请求总时限约束；可选抽取、补证和状态保护具有独立降级路径。无法完成的必要步骤返回HTTP错误，调用方可使用原请求进行有界重试。

## 存储与检索

`--db`覆盖 `AMI_DB_PATH`，默认数据目录为 `data/`。`--host`默认为127.0.0.1，未指定`--port`时使用8013；本文启动示例显式使用8014。服务使用单worker；用户锁与进程内向量缓存不跨worker共享。

基础检索上限100条，补证最多3段／600 token。V4.1对可选抽取采用原文降级策略；`AMI_EXTRACT_REQUIRED`保留用于底层配置兼容，不作为关闭该降级路径的开关。详细方法参数见[系统设计](architecture.md)。

## 检查

```sh
python -m mneme_asterion --env-file .env --check
python tools/verify_release.py
python tools/verify_manifest.py
```

第一条检查运行配置和发行版核心源文件；后两条校验源码及发布文件清单。`.env`和运行生成的数据库不参与常规启动扫描。打包维护者可用 `python tools/verify_release.py --package` 检查待分发目录。
