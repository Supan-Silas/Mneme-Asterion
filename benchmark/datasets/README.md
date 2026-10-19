# 完整公开源数据

源文件保存在本地 `benchmark/datasets/raw`，由 Git 忽略。六来源版本固定在 `configs/datasets/public_sources.json`（四个完整 Hugging Face 仓库）及 `configs/datasets/file_sources.json`（LoCoMo-Refined 与 LongMemEval-S 的三个公开文件）。

```bash
python scripts/download_all_public_sources.py --root datasets/raw --workers 2
```

这个命令下载公开来源并验证 SHA-256，不下载 AML 私有套件，不调用模型。

```text
raw/
  LoCoMo-Refined/{conversations.jsonl,questions.jsonl,download_manifest.json}
  LongMemEval/{longmemeval_s_cleaned.json,download_manifest.json}
  CL-bench/{snapshot/,download_manifest.json}
  PersonaMem-v1/{snapshot/,download_manifest.json}
  PersonaMem-v2/{snapshot/,download_manifest.json}
  BEAM/{snapshot/,download_manifest.json}
```

LoCoMo-Refined 使用完整公开 conversation/question 配对；LongMemEval 仅使用完整 cleaned-S 文件，不包括 M/oracle。PersonaMem v2 固定 generative 模式；BEAM 下载完整作者仓库，但小 benchmark 仅选 100K。

如果复用现有源数据，复制 suite 模板并填写已有目录，保留原 manifest，运行相同校验。不能用同名更新版替换固定版本。使用和再分发数据时遵循各来源的许可；本仓库只分发工具和来源元数据。
