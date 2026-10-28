# Mneme-Asterion P2

完整文本记忆服务：AMI rc3 写入/索引/基础检索 + R1Q 原文补证 + P2 撤回信息治理。统一使用 `launch.py` 启动。

先看 [队友一页说明](docs/01_TEAM_BRIEF.md)、[实验结果](docs/02_RESULTS.md)、[详细设计](docs/03_DESIGN.md)。来源见 [ATTRIBUTION.md](ATTRIBUTION.md)，验收见 [ACCEPTANCE.md](ACCEPTANCE.md)。

## 启动（Python 3.11，Windows / Linux）

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -c "import tiktoken; print(tiktoken.encoding_for_model('gpt-4o-mini').name)"
```

复制 `.env.example` 为 `.env.private`，填写自己的 LLM 地址/Key、Embedding 地址/Key 和服务鉴权 token。两种模型分别为 `gpt-4o-mini`、`text-embedding-v4`；地址应是 OpenAI 兼容 base URL（通常以 `/v1` 结束）。私有配置不要提交 Git。

```sh
python launch.py --env-file .env.private --check
python launch.py --env-file .env.private --db ./data/p2.sqlite3 --port 8013
```

首次启动会执行真实 Embedding 预热，Add/Search 会产生 API 费用。首次使用新数据库；不能直接挂载缺少原文 journal 的旧 AMI 数据库。单进程、单 worker；不要用多个进程共享同一数据库。默认仅监听本机，正式部署在外层配置 HTTPS 反向代理。

## 验收与评测

```sh
python tools/verify_release.py
python -m unittest test_http test_quote_repair test_repair_v1 test_state_echo test_state_policy test_state_withdrawal test_release -v
# 上述测试不调用模型 API；首次 tokenizer 缓存应先完成。
python tools/smoke.py --url http://127.0.0.1:8013
```

最后一条会交互读取服务 token，发起合成 Add/Search，检查接口。性能评测参见 [04_EVALUATION.md](docs/04_EVALUATION.md)。官方评测由 AML 负责 Answer/Judge，本仓库服务只提供 `/add`、`/search`、`/health`。

实验概览：两组五 seed 的七能力均分均领先 B0/E/R1Q；LoCoMo 对照为 743/861；官方 Smoke 为 66.39。实验设置与完整结果见上面的实验报告。

## 目录

- `app/`：完整 AMI 核心；`mneme_e/`：原文 journal、Add 与用户隔离。
- `e_core/`、`repair_*.py`、`variants.py`：原文候选、规划、范围与引用核验。
- `state_withdrawal*.py`、`state_policy.py`：撤回识别、删除片段、状态提示。
- `p2_service.py`：P2 HTTP 接口；`launch.py`：可移植启动。
- `memory_benchmark/`：仅 P2 内部需要的 Evidence/token 打包辅助，不是完整评测框架。
- `evaluation/`：外部冻结小 benchmark 的 HTTP 评测入口；`evidence/`：汇总成绩。
- `provenance/`：源码来源和历史部署验收；历史文件中的服务器路径不是本包运行依赖。

本包不含密钥、数据库、官方评测原始对话、金标或模型权重。旧 `reproduction/` 辅助脚本保留作来源参考，P2 的支持入口以本 README 为准。
