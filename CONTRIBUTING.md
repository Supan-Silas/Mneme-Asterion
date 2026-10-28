# 开发指南

## 代码结构

```text
app/                 AMI写入、更新、存储与基础检索
mneme_e/             原文日志与服务基础
e_core/              原文候选检索与补证辅助
memory_benchmark/    证据类型及token打包辅助
reproduction/        配置与模型接入辅助
tests/               单元与HTTP集成测试
scripts/             测试入口
tools/               配置、源码和接口检查
evaluation/          外部评测框架的HTTP示例入口
results/             实验统计数据
docs/                方法、配置、API、评测和部署文档
```

检索与状态模块的具体文件映射见[系统设计](docs/architecture.md)。

## 测试

```sh
python scripts/test.py
```

测试使用模拟模型、临时数据库和本地HTTP客户端，各测试模块在独立进程中运行，避免模型替身及配置污染。单独运行示例：

```sh
python -m unittest tests.test_state_transitions
python -m unittest tests.test_configuration
```

运行中的真实服务可用 `python tools/smoke.py --url http://127.0.0.1:8014` 检查Add/Search接口；该检查会调用模型。

## 修改与实验

状态相关改动应覆盖撤回、条件恢复、明确恢复、他人属性、复合属性和无控制指令的情况。检索相关改动记录来源覆盖、返回证据及逐题回答差异。比较检索模块时可复用同一冻结数据库；比较完整系统时独立建库并报告跨轮次统计。

发行版核心指纹在 `provenance/CORE_SHA256.json`，完整文件清单在 `SHA256SUMS.json`。算法改动应在新实验版本中更新指纹与结果，保持版本和评测对应。
