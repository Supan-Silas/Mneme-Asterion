# Mneme-Asterion · v0

**Memory systems & benchmark workbench** · AMI 复现、公开源数据抽样、方法迭代与自托管评测接口。

Mneme-Asterion 是工程工作台名称。当前记忆方法为 Xuhao Lin 的 [ActiveMemoryIndex](https://github.com/linxuhao/ActiveMemoryIndex) 复现，不声明新的记忆算法，不是 AML 官方评测平台。

本仓库的 **v0** 是团队用于工程复现与评测准备的初始版本：复现 **ActiveMemoryIndex（AMI）**，原作者 **Xuhao Lin**，来源 **https://github.com/linxuhao/ActiveMemoryIndex**。小 benchmark 工具独立记为 **s_benchmark_v1**，不是官方私有题集。仓库地址：[Supan-Silas/Mneme-Asterion](https://github.com/Supan-Silas/Mneme-Asterion)。

## 你可以用它做什么

- 运行 AMI 的文本 Add/Search 服务，接入远程 `gpt-4o-mini` 与 `text-embedding-v4`。
- 从六套固定版本的完整公开来源中，按能力覆盖规则和任意整数 seed 构建小 benchmark。
- 冻结题目 ID、完整历史关联、源数据 hash 和评分配置，供方法迭代重复比较。
- 使用公共 Answer/Judge、运行队列和 AMI/Mem0/InvMem/ReFind 适配器；其他方法仍需单独安装原生仓库和环境。

服务与离线 benchmark 是两个用途：提交赛事时仅部署 Add/Search；本地评分器、题目与 gold 不参与服务推理。

## 安装

Linux 建议 Python 3.11，使用独立环境；无需 GPU。

```bash
python -m pip install -r requirements-academic.txt
python -m pip install -e './benchmark[data,api]'
python -m pip check
```

只抽样时安装 `./benchmark[data]` 即可。公开数据、真实环境文件、数据库和缓存在仓库外准备，不会随源码下载。

## 从完整公开来源构建小 benchmark

```bash
cd benchmark
python scripts/download_all_public_sources.py --root datasets/raw --workers 2
python scripts/sample_small_benchmark.py \
  --suite configs/suites/public-full.example.json \
  --seeds 101 102 103 104 105 --output runs/iteration-001
```

下载约数 GB，需联网。下载后抽样与 prepare 禁止网络、不读 `.env`、不调用模型；本次发布整理不执行下载或真实抽样。输入数据版本及文件 hash 不匹配时直接失败。详见 [抽样规则与运行说明](benchmark/docs/independent_sampling.md)。

不依赖旧 99 题 manifest、参考 Word 或 seed 17–21 的固定清单。旧清单工具保留作历史审计入口，旧题目导出及参考 Word 不在本发布包中。

## 服务部署与验证

- [Linux/阿里云部署说明](docs/DEPLOYMENT.md)
- [当前验证状态与限制](REPRODUCTION_STATUS.md)
- [评测申请材料草稿](EVALUATION_ACCESS_DRAFT.md)
- [来源及改动披露](ATTRIBUTION.md)、[源快照记录](SOURCE_ORIGIN.json)、[许可证](LICENSE)

离线验证（无模型调用）：

```bash
python -m reproduction.run_tests
python -m reproduction.check_http
cd benchmark
PYTHONPATH=src python -m unittest discover -s tests
```

`fake` 验证不代表真实模型能力；仓库内的小 benchmark 也不等于官方私有套件或官方 Smoke/Full。正式评测前应固定 commit，配置凭据，并在官方平台通过 Smoke。

## 目录

```text
app/             AMI 实现，保留原作者署名
reproduction/    独立启动、离线验证与协议适配
benchmark/       独立抽样、prepare、评分、方法适配与测试
deploy/          无凭据的 Linux 服务模板
docs/            部署说明与历史文档
upstream/        原始来源文档、指纹及兼容差异
```

原始 AMI 来源的确切 upstream commit 尚未核实；保留原快照 SHA-256 记录，不把来源文档中的版本标签误称为已验证的 Git commit。历史文档中的运行与成绩属于各自注明的原始作者或历史阶段，不是本工作台的新成绩。
