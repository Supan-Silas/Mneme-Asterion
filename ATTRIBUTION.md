# 来源与许可

Mneme-Asterion基于Xuhao Lin的 [ActiveMemoryIndex](https://github.com/linxuhao/ActiveMemoryIndex)，使用academic-v4-20261005-rc3历史复现基底，保留原MIT许可与版权声明。原始技术说明为 [An Index, Not a Store: The Model Does Remember — It Just Needs Its Notebook](https://github.com/linxuhao/index-not-store)。

## 代码复用

| 组件 | 来源 |
|---|---|
| `app/` | AMI事实抽取、更新、存储及基础检索实现 |
| `reproduction/` | AMI复现工程的配置、模型接入与测试辅助 |
| `memory_benchmark/` | Nonlotus-eater评测框架中的Evidence与context辅助 |
| 原始复现起点 | [Nonlotus-eater/ami-reproduction](https://github.com/Nonlotus-eater/ami-reproduction)，commit `27b57e4d397f9f4aaa0848215a673ae37f78627b`，包含历史工作树修改 |

AMI原始快照的上游commit未记录；来源标识及文件指纹保存于 `provenance/UPSTREAM.json` 和 `provenance/BASELINE_SHA256.json`。

## 方法参考与本项目实现

- 原文补证参考ReFind的聊天块检索、BM25与邻接补全思路。
- 本项目实现问题范围约束、逐字引用核验、撤回片段过滤及状态提示。
- ScopedState实现人物／属性作用域的控制解释、来源关联、撤回与恢复状态投影。
- 服务层提供原文日志、幂等写入、用户隔离、接口序列化与部署入口。

代码按仓库 [LICENSE](LICENSE) 的MIT条款发布，第三方依赖沿用各自许可。

## 小benchmark与评测工程

[Agent Memory Benchmark](https://github.com/Nonlotus-eater/ami-reproduction/tree/main/benchmark) 提供公开数据抽样、原生方法适配、统一Reader、评分和能力汇总。本项目使用其评测协议进行方法比较，并在迭代过程中实现和分享了多seed并发调度、共享模型准入、持久化恢复及失败补跑代码。完整评测框架在其独立仓库维护；本仓库提供记忆服务、HTTP评测接入示例与实验统计。

README的小benchmark结果对应 `27d2733` 和本项目扩展的seed17–26。LoCoMo的逐轮结果与统计设置见 `results/locomo_refined.json`。
