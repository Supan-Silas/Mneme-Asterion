# Mneme-Asterion 发布范围

发布 AMI 复现、benchmark 公共框架、独立抽样/prepare、四方法适配器、人工测试、来源及配置元数据。

不导入旧仓库 Git 历史，不上传原始数据、历史题目导出、参考 Word、真实环境文件、数据库、模型缓存、运行日志或官方私有评测内容。`examples/` 是人工测试数据，`configs/reproduction/` 的冻结 ID 仅保留为历史追溯。

新的默认工作流是 `download_all_public_sources.py` → `sample_small_benchmark.py`，不依赖历史五轮题集。旧导出脚本及其未随包分发的输入不是本次发布入口。

`SOURCE_ORIGIN.json` 固定复制前的来源文件指纹；根发布 manifest 固定本候选源码的最终字节。测试、依赖安装与真实评测结论分开记录，不把第三方历史测试写成本次结果。
