# Mneme-Asterion · Small Benchmark Toolkit

版本标识：**s_benchmark_v1**；随工作台 **v0** 发布。固定版本规则保存在 `configs/sampling/s_benchmark_v1.json`，`small.json` 保留为同内容兼容别名。

默认入口是从完整公开来源独立抽样，而非恢复固定 seed 17–21 或旧 99 题。

```bash
python -m pip install -e '.[data,api]'
python scripts/download_all_public_sources.py --root datasets/raw --workers 2
python scripts/sample_small_benchmark.py --suite configs/suites/public-full.example.json --seeds 101 102 --output runs/iteration-001
```

下载需联网；抽样/prepare 阶段离线。`--output` 必须是尚不存在的新目录，禁止覆盖旧实验。

- [独立抽样规则与完整命令](docs/independent_sampling.md)
- [六来源数据版本与布局](datasets/README.md)
- [能力映射](docs/capability_label_mapping.md)
- [评测契约、评分、原生方法边界](docs/evaluation_contract.md)
- [本次发布范围](docs/publication_scope.md)

框架保留 AMI、Mem0、InvMem、ReFind 适配器。源码包不附带原生第三方环境，路径与凭据必须按目标 Linux 环境配置。InvMem/ReFind 固定接口需要整数 top_k；通用无截断配置与 `configs/reproduction/runtime.json` 的有界历史配置是不同实验条件。真实方法调用、Answer/Judge 和 `scripts/release_smoke.py` 会收费，须另行授权。

`configs/reproduction/`、`sample_five_seeds.py`、`prepare_five_seeds.py` 与旧导出脚本用于历史追溯。新抽样不依赖它们，默认也不发布历史题目数据和参考 Word。人工 `examples/` 只用于离线测试。
