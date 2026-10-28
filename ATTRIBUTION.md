# 来源、复用与本项目改动

ScopedState v4 基于 P2；P2 基于 Xuhao Lin 的 [ActiveMemoryIndex](https://github.com/linxuhao/ActiveMemoryIndex)，使用本项目历史复现的 academic-v4-20261005-rc3 基底。保留原 MIT License 和版权通知；该标签不是本项目核验出的上游Git commit。原始源码快照的确切上游commit未知，不补造。

原作者技术说明：*An Index, Not a Store: The Model Does Remember — It Just Needs Its Notebook*，参考 https://github.com/linxuhao/index-not-store （沿用已归档来源说明）。历史复现来源 https://github.com/Nonlotus-eater/ami-reproduction ，原公开项目起点见 provenance/B0_SOURCE_ORIGIN.json；该起点不是P2当前代码的commit。

- `app/` 复用实际评测B0的完整运行核心，来源SHA256见provenance/ALGORITHM_SHA256.json。
- `reproduction/`、原文journal与E基础框架继承本项目复现/工程工作。
- `e_core/` 的原文补证设计参考ReFind的原始聊天块、BM25、邻接和继续检索思路；未宣称完整复现ReFind，也不把AMI复用算法改称独立原创。
- `repair_v1.py`、`repair_quotes.py`、`state_withdrawal*.py`、`state_policy.py` 是本项目实验形成的范围检查、引用修正、显式撤回过滤与状态提示。
- `memory_benchmark/` 中Evidence/context辅助继承Nonlotus-eater评测工程；实际评分须使用独立完整benchmark，不包含在该小命名空间中。
- 新增便携launch、合成HTTP探针、HTTP评测入口和交付验收，不改变已测核心算法。依赖库遵循各自许可证；模型权重和评测数据未随包分发。

本包采用保留的MIT许可文本发布代码；若后续合入第三方新代码，应另核对其许可证。完整旧来源说明位于provenance，旧文档提到但本包未携带的实验目录不是运行依赖。不会声称本包复现了上游论文全部实验。


## ScopedState v4 新增与发布修复

本项目增加 `scoped_adapter.py`、`provenance_v4.py`、`intent_scope_v5.py`、`state_finalize_v6.py`、`state_scoped*.py` / `state_projection_v4.py`，实现查询局部的用户/属性状态表达。v4 不改变 AMI 原生事实抽取模型，也不是通用物理删除系统。

本发布候选额外修复原文跨 session 顺序和条件式授权，修正外部评测方法身份。精确差异见 `provenance/REVIEW_PATCH.diff`。修复前冻结版结果单独标记；当前修复版已完成五轮独立建库LoCoMo，均值85.30±0.67。此次发布整理只新增配置/身份防错检查与文档，冻结算法字节未变。
