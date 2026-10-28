# 启动、验收与评测

服务启动见根README。生产入口是 `run_v4.py`，其先检查V4开关、Bearer鉴权、指定模型和核心文件SHA256，再调用原 `launch.py`。默认模型并发8、嵌入4、Add4、Search8，单worker；平台并发16是请求上限，服务自行准入。

离线验收：`python verify_candidate.py`、`python -m unittest tools.test_preflight`、`python tools/verify_release.py`、`python tools/verify_manifest.py`。真实合成检查：`python tools/smoke.py --url http://127.0.0.1:8014 --method ScopedStateV4`，交互输入本服务Token。真实探针会调用模型；不产生方法成绩。

## 可选的开放问答复现入口

```sh
python evaluation/run_prepared.py --benchmark-root /path/to/a3f9610/benchmark --prepared /path/to/prepared --output /path/to/new-output --method ScopedStateV4 --check
python evaluation/run_prepared.py --benchmark-root /path/to/a3f9610/benchmark --prepared /path/to/prepared --output /path/to/new-output --method ScopedStateV4 --url http://127.0.0.1:8014
```

这是Linux/WSL上的a3f9610顺序HTTP示例，不是历史五轮或27d2733十seed并发执行器。它只支持无选项的开放问答（如LoCoMo）；发现选择题会在付费调用前拒绝，防止静默遗漏options。需新输出目录，无断点恢复。benchmark的运行配置与密钥在外部提供；Answer/Judge计费不包含远程服务Add/Search费用。

复现新版评测需另外取得27d2733完整框架与公开数据，通过其HTTP适配器连接服务并转发完整query/options。包内 `memory_benchmark` 仅提供Evidence/context运行辅助，不包含评测器和数据。服务不挂载targets；独立评测器先保存所有答案，再读target评分。

上述示例是便利入口；已公布分数的实验条件与版本对应以结果页为准。当前修复版已经完成五轮LoCoMo和真实边界验收，历史自建流式/StreamMemBench保留历史版本标记。
