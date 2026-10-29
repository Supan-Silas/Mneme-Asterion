# 评测

## V4.1：完整评测基线与发布验证

V4.1由RC15与三项定向修复组成。完整评测使用RC15，从头独立建库；原始结果保持不变。

| 评测 | 完成题量 | 指标 | 结果（%） |
|---|---:|---|---:|
| LoCoMo-Refined | 861 / 861 | 单轮准确率 | 85.83 |
| 小benchmark，seed17–26 | 2,000 / 2,000 | 七能力宏平均，十seed均值±样本标准差 | 57.88 ± 2.38 |
| 同轮小benchmark | 2,000 / 2,000 | 数据集宏平均，十seed均值±样本标准差 | 57.47 ± 3.05 |

模型为gpt-4o-mini、text-embedding-v4。小benchmark沿用27d2733抽样与评分框架，每seed 200题；LoCoMo为10条完整历史。单轮LoCoMo结果不带跨轮标准差。

发布前定向修复包括：撤回控制不再按14,000 token截断、降级补证围绕实际命中位置取连续原文、补证保留说话人与时间等来源标记。

检查完整2,861题产物：控制材料最大4,983 token，无控制预算遗漏；7题触发降级补证（LoCoMo 2题、小benchmark 5题）。复用现有库和基础材料，对这7题替换补证并重做状态保护、Answer和Judge，配对结果0升、0降、7平。其余2,854题的正常R1Q路径不受两项降级补证修改影响。这是定向对照，不是V4.1的完整Search重跑。

最终发布代码通过147项离线测试及真实模型、HTTP、撤回恢复、用户隔离和重启持久化验收。

数据：[V4.1评测与验证摘要](../results/v4_1_validation.json)。

## 历史V4：LoCoMo-Refined五轮独立建库

每轮包含10条完整对话历史、861个问题。各方法每轮从头建库，独立执行检索、回答和评分。17–21是重复实验编号，题目集合保持不变。

- LLM：`gpt-4o-mini`；嵌入：`text-embedding-v4`，1024维。
- Reader：最多100条检索结果，采用 `aml_ranked_prefix_v1` 打包，总输入窗口117,760 token。
- 指标：每轮正确题数／861；汇总为五轮准确率均值与样本标准差。
- 该轮 ScopedState V4 包含交错会话顺序与条件恢复修复；v4.0.1整理公开文档，v4.0.2整理模块布局，二者沿用v4.0的记忆算法。

| 方法 | 第17轮 | 第18轮 | 第19轮 | 第20轮 | 第21轮 | 准确率（%） |
|---|---:|---:|---:|---:|---:|---:|
| AMI | 711 | 709 | 714 | 716 | 705 | 82.58 ± 0.50 |
| P2 | 734 | 737 | 734 | 734 | 731 | 85.25 ± 0.25 |
| **Mneme-Asterion / ScopedState V4** | **726** | **731** | **739** | **737** | **739** | **85.30 ± 0.67** |
| InvMem | 705 | 710 | 703 | 713 | 713 | 82.32 ± 0.53 |
| ReFind | 671 | 665 | 652 | 652 | 658 | 76.61 ± 0.97 |
| Mem0 | 693 | 691 | 691 | 692 | 689 | 80.28 ± 0.17 |

表中每格为该轮正确题数，分母均为861。AMI使用其各轮独立数据库重跑原生Search、Answer和Judge；此前入口误接E链路的结果不计入本表。

V4相对AMI提高2.72个百分点，与P2相差0.05个百分点。LoCoMo主要检验静态历史问答；撤回、恢复与跨人物状态另外使用流式序列检查。

数据：[逐轮统计](../results/locomo_refined.json)。可复算：

```sh
python tools/summarize_results.py
```

## 历史冻结版本：多能力与流式测试

本节使用边界修复前的冻结V4，保留为方法发展过程的实验记录。

| 测试／指标（%） | AMI | P2 | 冻结V4 |
|---|---:|---:|---:|
| 小benchmark：能力宏平均 | 53.51 ± 2.43 | 56.21 ± 2.53 | 57.17 ± 2.82 |
| 自建流式：检查点通过率 | 80.17 | 82.67 | 99.83 |
| StreamMemBench：记忆保真度 | 91.90 | 91.90 | 91.43 |
| StreamMemBench：初始证据使用 | 2.86 | 2.86 | 2.86 |
| StreamMemBench：反馈吸收 | 17.65 | 16.18 | 17.16 |
| StreamMemBench：后续复用 | 3.81 | 4.76 | 4.76 |

实验设置：

- **小benchmark**：使用[评测框架27d2733](https://github.com/Nonlotus-eater/ami-reproduction/tree/27d2733/benchmark)，seed17–26，每seed 200题。三种方法共享新建冻结AMI库，比较检索和状态模块。P2与V4的2,000份Reader输入相同，状态模块未触发；两者分差来自回答与评分波动。
- **自建流式**：120条序列、600个检查点，按写入、提问、更新、再次提问执行；AMI/P2/V4分别通过481/496/599个检查点。该集合用于开发回归，覆盖保留、更新、撤回、恢复与作用域隔离。
- **[StreamMemBench](https://github.com/landian60/StreamMemBench)**：6人、7天、3,347段输入、210个抽样评测点；反馈吸收分母为204，其余指标分母为210。

数据：[历史版本统计与设置](../results/historical_evaluations.json)。

## 使用HTTP接口评测

系统提供Add/Search，外部评测框架负责Reader和Judge。每轮使用独立的用户命名空间；写入传入历史，检索传入问题及选项，参考答案仅交给评分端。

仓库的 `evaluation/run_prepared.py` 是面向开放问答的串行接入示例，与[框架a3f9610](https://github.com/Nonlotus-eater/ami-reproduction/tree/a3f9610/benchmark)配合使用。它读取框架生成的prepared目录，依次执行Add、Search、Answer和Judge，输出逐题产物及汇总。选择题应使用转发options的完整框架适配器。

```sh
python evaluation/run_prepared.py \
  --benchmark-root /path/to/ami-reproduction/benchmark \
  --prepared /path/to/prepared \
  --output /path/to/new-output \
  --url http://127.0.0.1:8014 --method ScopedStateV4 --check
```

`--check`只检查输入；移除此参数开始评测，并按提示输入记忆服务Token。Reader/Judge的模型配置由prepared中的runtime指定。示例要求新建输出目录，不支持断点恢复；其费用账本记录Reader/Judge，远端Add/Search消费由服务侧统计。上表的多轮并发实验使用独立实验调度器。

## 离线验证

```sh
python scripts/test.py
python evaluation/test_pipeline_offline.py --benchmark-root /path/to/ami-reproduction/benchmark
```

第一条运行单元与HTTP集成测试，第二条用三个合成问题验证外部框架接入。两者均使用模型替身，不发起真实模型调用。
