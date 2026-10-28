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
