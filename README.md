# Mneme-Asterion

**面向长对话的智能体记忆系统：原文补证、来源核验与作用域状态管理。**

Mneme-Asterion 基于 [ActiveMemoryIndex（AMI）](https://github.com/linxuhao/ActiveMemoryIndex)，提供持久化的写入与检索接口。系统将对话组织为原文、事实和更新记录，并在检索时补齐证据、处理撤回与恢复，向下游回答模型提供当前有效的记忆。

## 贡献与改进

- **问题驱动的原文补证**：在 AMI 检索结果上识别人物关系、时间锚点和列表成员等信息缺口，通过 BM25 与邻接消息补充证据。
- **可追溯的证据选择**：补充内容必须匹配来源中的原文引用；生成式选择器负责挑选材料，返回内容保留来源关联。
- **作用域状态管理（ScopedState）**：按人物和属性解释显式撤回与恢复，抑制失效副本，区分条件表达与有效授权，同时保留无关属性。

写入、事实抽取和向量索引继承 AMI；上述改进集中在证据检索、组织与有效性处理。模块与来源见[系统设计](docs/architecture.md)和[来源说明](ATTRIBUTION.md)。

## 工作流程

```text
对话 → 原文日志 → AMI事实抽取／更新 → SQLite与向量索引
                                           ↓
问题 → AMI基础检索 → 原文补证与引用核验 → 撤回过滤 → ScopedState → 记忆证据
```

`Add` 写入完成后即可检索；`Search` 返回证据，由调用方的回答模型生成答案。

## 实验结果

LoCoMo-Refined：10条完整历史、861题，每种方法进行5轮独立建库评测。统一使用 gpt-4o-mini、text-embedding-v4，报告准确率均值与样本标准差。

| 方法 | 准确率（%） |
|---|---:|
| AMI | 82.58 ± 0.50 |
| P2：原文补证与撤回处理 | 85.25 ± 0.25 |
| **Mneme-Asterion：ScopedState V4** | **85.30 ± 0.67** |

相对 AMI 提高 **2.72 个百分点**。P2 与 V4 在该静态问答集上表现相近；状态变化测试及完整实验条件见[评测文档](docs/evaluation.md)。逐轮正确数提供于 [results/locomo_refined.json](results/locomo_refined.json)。

## 快速开始

需要 Python 3.11 和兼容 OpenAI API 的模型服务。

```sh
git clone https://github.com/Supan-Silas/Mneme-Asterion.git
cd Mneme-Asterion
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

在 `.env` 中填写以下五项：

```dotenv
OPENAI_BASE_URL=https://your-llm-provider.example/v1
OPENAI_API_KEY=your-llm-api-key
AMI_EMBED_BASE_URL=https://your-embedding-provider.example/v1
AMI_EMBED_API_KEY=your-embedding-api-key
AMI_AUTH_TOKEN=your-service-token
```

启动服务：

```sh
python run_v4.py --env-file .env --check
python run_v4.py --env-file .env --db ./data/memory.sqlite3 --port 8014
```

上述命令监听 `127.0.0.1:8014`。Windows 可使用 `.venv\Scripts\Activate.ps1` 激活环境。

| 接口 | 功能 |
|---|---|
| `GET /health` | 健康检查 |
| `POST /add` | 持久化对话与记忆 |
| `POST /search` | 检索当前用户的记忆证据 |

请求示例见 [API 文档](docs/api.md)。

## 文档与开发

- [系统设计](docs/architecture.md)：各模块实现、状态处理与参数。
- [配置](docs/configuration.md)：模型、并发、存储及检索设置。
- [API](docs/api.md)：请求、响应和错误处理。
- [评测](docs/evaluation.md)：实验设置、结果与复现入口。
- [部署](docs/deployment.md)：持久化、进程管理和HTTPS。
- [开发指南](CONTRIBUTING.md)：代码结构与测试。

```sh
python scripts/test.py
```

## 来源与许可

基于 Xuhao Lin 的 ActiveMemoryIndex，保留原作者署名及 MIT 许可。代码复用、方法参考与本项目改动见 [ATTRIBUTION.md](ATTRIBUTION.md)。
