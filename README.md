# Mneme-Asterion

**v4.0 · ScopedState** — 带有来源核验与撤回／恢复状态管理的完整文本记忆系统。

基于 ActiveMemoryIndex（AMI）：保留事实抽取、更新、向量索引；补充有来源的原文证据，并按人物、属性和有效指令处理当前记忆状态。Search 返回记忆证据，由评测平台独立回答和评分。

本仓库 v4.0 保留已上线的修复版 V4 核心字节。它在 LoCoMo-Refined 五轮独立建库评测中为 **85.30 ± 0.67**；本次新增的是发布检查、接口身份校验和文档，不改变检索算法。详细实验条件见[结果](docs/02_RESULTS.md)。

## 启动

Python 3.11，Linux 示例；创建自己的私有配置目录：

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
mkdir -p ../mneme-private
cp .env.example ../mneme-private/v4.env
# 编辑 ../mneme-private/v4.env：填写模型服务地址、模型 Key、记忆服务鉴权 Token
.venv/bin/python run_v4.py --env-file ../mneme-private/v4.env --check
.venv/bin/python run_v4.py --env-file ../mneme-private/v4.env --db ./data/v4.sqlite3 --host 127.0.0.1 --port 8014
```

私有配置放在源码目录外；不要上传真实 env。

Windows 使用 `.venv\Scripts\python.exe`。生产使用 `run_v4.py`，固定 `P2_SCOPED_STATE=1` 和单 worker；该入口在启动前核验模型、鉴权及核心源码。旧 `launch.py` 仅为兼容实验保留。

接口：`GET /health`，`POST /add`，`POST /search`；使用 Bearer Token。生产部署通过反向代理提供 HTTPS。

## 验收和阅读

```sh
python verify_candidate.py
python -m unittest tools.test_preflight
python tools/verify_release.py
python tools/verify_manifest.py
# 已启动服务后再执行；这一步会调用真实 API
python tools/smoke.py --url http://127.0.0.1:8014 --method ScopedStateV4
```

- [一分钟理解方法](docs/01_TEAM_BRIEF.md)
- [实验结果与版本对应](docs/02_RESULTS.md)
- [详细设计及代码位置](docs/03_DESIGN.md)
- [启动、验收与评测](docs/04_EVALUATION.md)
- [官方提交说明草稿](docs/05_PUBLICATION.md)
- [本次严格审查](docs/07_STRICT_REVIEW.md)
- [运维与回滚](docs/08_OPERATIONS.md)

来源与许可见 [ATTRIBUTION.md](ATTRIBUTION.md)。不分发模型密钥、业务数据库或官方评测原始数据。内部服务标识仍是 `scoped-state-v4-review-rc1-20261026`，Search 方法标识为 `ScopedStateV4`；`v4.0` 是本次整理后的公开发布名称。

## 固定版本

正式发布标签：`v4.0`。使用 `git rev-parse HEAD` 获取完整commit，官网登记该值。旧v0保留在Git历史中的 `a2f9ca273caa237025add32ea181d5b30a7a45d4`；当前根目录提供完整V4系统，不混用旧v0启动脚本。
