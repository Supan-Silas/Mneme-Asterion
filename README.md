# Mneme-Asterion

**V4.1**

**面向长对话的智能体记忆系统：原文补证、来源核验与作用域状态管理。**

Mneme-Asterion 基于 [ActiveMemoryIndex（AMI）](https://github.com/linxuhao/ActiveMemoryIndex)，提供持久化的写入与检索接口。系统将对话组织为原文、事实和更新记录，并在检索时补齐证据、处理撤回与恢复，向下游回答模型提供当前有效的记忆。

## 贡献与改进

- **问题驱动的原文补证**：在 AMI 检索结果上识别人物关系、时间锚点和列表成员等信息缺口，通过 BM25 与邻接消息补充证据。
- **可追溯的证据选择**：补充内容必须匹配来源中的原文引用；生成式选择器负责挑选材料，返回内容保留来源关联。
- **作用域状态管理（ScopedState）**：按人物和属性解释显式撤回与恢复，抑制失效副本，区分条件表达与有效授权，同时保留无关属性。
- **小规模多能力评测与运行工程**：基于 [Agent Memory Benchmark](https://github.com/Nonlotus-eater/ami-reproduction/tree/main/benchmark) 建立多seed评测流程；本项目迭代中提供了并发调度、共享模型准入、断点恢复与失败补跑实现，用于缩短实验反馈周期。

写入、事实抽取和向量索引继承 AMI；记忆方法改进集中在证据检索、组织与有效性处理。小benchmark由独立仓库维护，完整抽样与并发运行代码见上述链接。模块与来源见[系统设计](docs/architecture.md)和[来源说明](ATTRIBUTION.md)。

## V4.1 更新

- **稳定运行**：模型请求采用有限重试；事实抽取和补证失败时使用原文降级路径。
- **一致写入**：成功提交顺序、幂等记录和原文可见性保持一致，支持交错写入与检索。
- **完整状态与来源**：撤回控制全量处理，长输入分批；降级补证保留说话人、时间和来源，并围绕实际命中位置选取原文。

原文和向量索引持久化成功后，Add才返回成功。撤回处理无法完成时，本次Search返回暂不可用状态。V4.1使用独立数据库；旧版本数据库保留给原版本恢复使用。

## 工作流程

```text
对话 → 原文日志 → AMI事实抽取／更新 → SQLite与向量索引
                                           ↓
问题 → AMI基础检索 → 原文补证与引用核验 → 撤回过滤 → ScopedState → 记忆证据
```

`Add` 写入完成后即可检索；`Search` 返回证据，由调用方的回答模型生成答案。

## 实验结果

### V4.1 评测基线

统一使用 `gpt-4o-mini` 和 `text-embedding-v4`，从头独立建库，完成检索、回答与评分。

| 评测集 | 规模 | RC15（V4.1评测基线） |
|---|---|---:|
| LoCoMo-Refined | 10条完整历史，861题，1轮 | **85.83%** |
| 小benchmark | seed17–26，每seed 200题，共2,000题次 | **57.88 ± 2.38%** |

小benchmark使用 [Agent Memory Benchmark（27d2733）](https://github.com/Nonlotus-eater/ami-reproduction/tree/27d2733/benchmark)，按公开数据集及原生题型比例抽样，保留完整历史，覆盖六个数据版本与七项能力。分数为七能力等权宏平均，再报告十seed均值与样本标准差；LoCoMo报告单轮准确率。

V4.1在RC15上加入全量撤回控制、命中位置补证和来源标记修复。全量产物检查定位到7道降级补证题，修复前后重新回答与评分为**0升、0降、7平**。上表是RC15完整评测结果；V4.1发布版完成定向验证与接口验收，未另跑完整评测。详见[评测记录](docs/evaluation.md)。

### 历史版本对照

| 方法 | LoCoMo-Refined：五轮准确率（%） | 小benchmark：十seed能力宏平均（%） |
|---|---:|---:|
| AMI | 82.58 ± 0.50 | 53.51 ± 2.43 |
| InvMem | 82.32 ± 0.53 | 52.00 ± 2.98 |
| ReFind | 76.61 ± 0.97 | 51.86 ± 4.66 |
| P2 | 85.25 ± 0.25 | 56.21 ± 2.53 |
| ScopedState V4 | **85.30 ± 0.67** | **57.17 ± 2.82** |

LoCoMo各方法进行五轮独立建库；V4相对AMI平均提高2.72个百分点。小benchmark采用历史冻结版本，AMI、P2、V4共享新建冻结库，InvMem与ReFind使用原生建库；该轮P2与V4的Reader输入相同，分差来自回答与评分波动。两列对应不同实验批次，版本与逐轮结果见[评测文档](docs/evaluation.md)。

## 代码结构

```text
run_v4.py             启动入口
mneme_asterion/
  cli.py              配置与启动
  service.py          HTTP接口与检索流程
  provenance.py       证据来源关联
  retrieval/          检索规划、原文补证与引用核验
  state/              撤回、恢复、归属与状态投影
app/                  AMI写入、更新与基础检索
mneme_e/               原文日志与服务基础
e_core/               BM25与邻接补证辅助
tests/                单元与HTTP集成测试
evaluation/           外部评测框架接入
docs/                 系统文档
```

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
