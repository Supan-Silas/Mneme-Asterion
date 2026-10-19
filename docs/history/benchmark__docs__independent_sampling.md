# 从完整源数据独立构建小 benchmark

入口为 `scripts/sample_small_benchmark.py`，规则为 `configs/sampling/small.json`。不需要旧 99 题 manifest、参考 Word、固定 seed 17–21 清单、模型密钥或运行中的 AMI。原 `sample_five_seeds.py` 保留用于历史审计，两者共用相同的来源索引和 SHA-256 排序算法。

## 运行条件

Python 3.11+、可用的 `pyarrow`、六套完整源数据及来源 manifest。新入口直接加入本仓库 `src`，不必把包安装到 AMI 环境。无需 tiktoken、tokenizer 下载或系统时区数据库；时间记录使用 UTC。所有 JSON、JSONL、CSV 和源码按 UTF-8 读取。

`--suite` 中的相对数据路径以该配置文件所在目录为基准；推荐本机使用绝对路径。源配置不得包含预选题目或历史限制。manifest 相对路径同时接受 `/` 和 `\`。来源校验以文件字节为准；只有经过审计的原生 Python 源码允许 Git 的 CRLF/LF 换行转换，内容变化仍报错。

本机已准备 `D:/SUPAN/AML/data/benchmark-v1/suite.local.json` 和独立 Parquet 依赖目录 `_tools`。便捷启动文件为 `D:/SUPAN/AML/data/benchmark-v1/run_small_benchmark.ps1`；它只在子进程所需范围内加入依赖路径，结束后恢复当前 PowerShell 环境。

以下是未来执行示例；本次开发验证仅使用人工数据，没有抽取真实题集：

```powershell
& D:/SUPAN/AML/data/benchmark-v1/run_small_benchmark.ps1 `
  -Seeds 101,102,103,104,105 `
  -Output D:/SUPAN/AML/data/benchmark-v1/samples/iteration-001
```

通用 Python 入口（依赖已就绪时）：

```text
python scripts/sample_small_benchmark.py --suite <完整来源配置.json> --seeds 101 102 --output <新目录>
```

可以使用一个或多个互不相同的整数 seed，不局限于五轮。`--rules` 可以指向独立规则配置；默认采用已发布的小 benchmark 参数。不存在失败后自动放宽配额或切换来源的行为。

## 规则与校验

完整母库预期 10,649 题，BEAM 限定 100K 后预期 9,249 题。先选历史：LoCoMo 2、LongMemEval 7、CLBench 4、PersonaMem v1/v2 各 2、BEAM 2。随后按缺失能力和总题数需求补历史，总数上限 30；有候选的小类至少 min(2, 母库可用数) 题，每大类最多 40 题，每轮至少 91 题。F1 属于 D 大类，A2/B2/B3 无候选映射。轮内不重复、轮间允许重合。

全局母库数量由 suite 的 `question_bank_expected_counts` 校验，过滤后数量由规则的 `expected_eligible_questions` 校验。新数据版本若改变数量，需要审计后明确更新配置。脚本核对来源 hash、复演 seed 并反转输入顺序检查结果稳定性，还通过原生加载器验证选中题目、能力标签和完整历史的关联。PersonaMem v1 保留原生因果前缀，其余历史不额外截断。所有操作禁止网络，不读取 `.env`，不调用模型 API。

## 每次运行的产物

根目录保存完整候选索引、来源配置、规则、版本/hash 清单、代码指纹和汇总；每个 `seed-N` 目录保存选中历史、补充历史原因、题目元数据、题目 ID，以及可直接交给 prepare 的 `suite.json`。保存结果使用 UTF-8。已有输出目录不能覆盖，失败后的不完整目录也不能复用；只有 `summary.json` 的 `status=complete` 才表示完成。

默认仅抽样并保存清单。若还要构建完整历史、查询及独立评分目标，可显式添加 `--prepare-runtime <runtime.json>`，或在本机启动脚本中添加 `-PrepareRuntime <runtime.json>`。该步骤只调用离线 prepare，不启动评测；每轮的 `prepared/` 可交给现有评测入口。生成的 `seed-N/suite.json` 也可稍后通过现有 `memory-benchmark prepare` 命令使用，其 `question_ids` 会约束全部六个加载器。

后续方法比较应复用同一份清单和 prepared 输入。换 seed 创建新的实验目录，单独衡量跨样本稳定性。抽样来源必须是已授权的完整公开母库；本工具不加载 OurMemory nightly/research split，也不自动发现或访问服务器 held-out 数据。

## 验证边界

本次开发使用人工六来源数据验证抽样、来源 hash、中文路径、相对路径、原生历史关联、选中 ID 的 prepare 和重复运行一致性，不使用真实母库抽样。Windows worker 的资源统计和 CPU 亲和性读取、可恢复队列的排他锁均已兼容：Windows 读取当前进程峰值工作集及 CPU 时间，队列使用系统字节范围锁；Unix 保留原资源统计与 flock 行为。

人工数据的离线 worker、回答、评分和汇总链路已通过 Windows 回归验证；队列的恢复、结果防篡改和跨进程排他锁也已验证。此结果证明公共框架的离线链路可运行，不代表各方法的原生环境、tokenizer 缓存、模型连接或真实方法成绩已验证。真实评测仍需单独配置方法环境和模型连接，本次未读取或修改 `.env`，未调用模型 API。
