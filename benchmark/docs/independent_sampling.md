# 从完整公开来源独立构建小 benchmark

版本标识：**s_benchmark_v1**；随工作台 **v0** 发布。固定版本规则保存在 `configs/sampling/s_benchmark_v1.json`，`small.json` 保留为同内容兼容别名。

入口：`scripts/sample_small_benchmark.py`；规则：`configs/sampling/s_benchmark_v1.json`。

## 前置条件

Python 3.11+、pyarrow、六套完整公开来源及下载 manifest。新入口可直接从源码执行，不必安装到 AMI 运行环境。抽样不需要模型凭据、tiktoken 下载、旧 99 题 manifest、参考 Word 或固定 seed 清单。

```bash
cd benchmark
python -m pip install -e '.[data]'
python scripts/download_all_public_sources.py --root datasets/raw --workers 2
python scripts/sample_small_benchmark.py \
  --suite configs/suites/public-full.example.json \
  --seeds 101 102 103 104 105 --output runs/iteration-001
```

下载是显式联网操作；完成后抽样和 prepare 强制禁止网络。suite 中相对路径以 suite 文件目录为基准，例子已经指向 `benchmark/datasets/raw`。也可复制模板到本地配置，使用服务器已有数据的绝对路径；不要提交真实本地配置或更改 source revision 来绕过校验。

## 固定规则

完整母库预期 10,649 题；BEAM 仅使用 100K split，候选池预期 9,249 题。初始历史数：LoCoMo 2、LongMemEval 7、CLBench 4、PersonaMem v1/v2 各 2、BEAM 2。根据缺失能力及总题数补历史，每轮历史总数上限 30。每个有候选的细类至少 min(2, 母库可用数) 题，每个大类最多 40 题，每轮至少 91 题。F1 归 D 类；A2/B2/B3 当前无候选映射，不伪造覆盖。

先选历史，再按能力配额选题；使用固定 SHA-256 排序并校验输入顺序反转和 seed 重放的一致性。轮内不重复，轮间允许重合。允许任意一个或多个互不相同的整数 seed。数据 hash、题量或配额不满足时失败，不自动放宽规则。

PersonaMem v1 保留原生因果前缀，其余历史不额外截断。来源索引、题目 ID、原生历史关联与能力映射均纳入验证。能力映射是本地粗映射，不声明与官方私有套件完全一致。

## 产物和方法迭代

根目录保存候选索引、来源及规则、来源 hash、代码指纹与汇总。每个 `seed-N` 保存选中历史、补充原因、题目元数据、题目 ID 和可供 prepare 使用的 `suite.json`。`summary.json` 的 `status=complete` 才代表成功。输出目录不可复用，失败产物也不能覆盖重跑。

如需完整历史、查询和仅评分端可见的 targets，可显式追加：

```bash
python scripts/sample_small_benchmark.py \
  --suite configs/suites/public-full.example.json --seeds 101 102 \
  --output runs/iteration-002 \
  --prepare-runtime configs/reproduction/runtime.json
```

这里复用的是已声明的有界 runtime 配置，绝不限定旧 seed 或旧题目。该步骤仅离线 prepare，不启动方法评测。比较方法时复用同一份冻结清单及 prepared 输入；换 seed 另建实验目录。

评分目标与 gold 仅属于本地评测端，不传给 AMI 或其他记忆服务。公开原始数据、题集产物、官方私有数据均不进入新仓库；不使用 OurMemory nightly_v1/research_dev_v2，也不自动发现 held-out 目录。

## 平台边界

Windows 已适配公共框架的进程资源统计和排他锁；InvMem/ReFind 的原生桥接仍以 Linux 为目标，需要独立依赖环境。人工离线测试通过与真实方法分数是不同证据。付费方法评测必须单独配置、明确启动；抽样成功不意味着官方 Smoke 或 Full 已通过。
