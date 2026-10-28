# 启动与评测简表

## 三种检查不要混为一谈

1. `python -m unittest ...`：无模型调用的契约/算法规则验收，不是方法成绩。
2. `python tools/smoke.py --url ...`：自己的合成请求，收费的真实链路检查，不是AML官方Smoke或准确率。
3. 小benchmark或AML评测：包含独立Answer/Judge，才产生对应口径成绩。

## 官方 Smoke / Full

运行本包服务后，对外以 HTTPS 提供 `/add`、`/search`、`/health`。在AML绑定正确版本与服务token；模型Key不交给平台。Smoke已过的线上P2不需要因发给队友而重复跑。新部署先Smoke，再确认固定commit、署名、容量与规则后Full。不要在Full运行期间替换算法。

P2只负责Add/Search；平台Reader、模型提示词、评分由平台控制。页面16并发是请求上限，不是服务内LLM槽位；本包LLM8/Embedding4及Add4/Search8可在私有配置调整，调整需记入运行身份。

## 本地小benchmark完整评分入口

本包新增 `evaluation/run_prepared.py` 是**简洁的顺序HTTP接入路径**，用原版a3f9610的分块、Reader、Judge和汇总；不是生成历史成绩的四方法高并发执行器。它能从空库完成Add→Search→Answer→Judge，不会伪装仅跑AMI。历史结果是共享冻结建库的另一实验，详见结果说明。

请在 Linux/WSL2 中运行此完整评分入口；参考框架使用 fcntl，Windows 原生终端只支持本包服务和合成 smoke。检出时关闭自动 CRLF 转换，否则官方评分源文件 SHA 校验会失败。不要删除哈希校验来绕过。

准备外部依赖（本包未复制题库或第三方完整评测仓库）：

```sh
git -c core.autocrlf=false clone https://github.com/Nonlotus-eater/ami-reproduction.git benchmark-reference
git -C benchmark-reference checkout a3f9610073839165dc504c769eddd8cc4e4218d3
python -m pip install -e './benchmark-reference/benchmark[api,data]'
```

按照该版本的数据说明下载公开来源并准备冻结输入。固定seed17–21使用它的公开固定清单；重新抽样用sample_small_benchmark.py，不把临时选择说成原始seed清单。prepared的runtime必须保存真实Reader/Judge配置及独立env_file，top_k=100、answer_input_token_limit=117760，并采用AML前缀打包策略。不要把内部规划4096填成Reader限制。

先在另一个终端启动P2，再运行（用自己的prepared绝对路径替换示例）：

```sh
python evaluation/run_prepared.py --benchmark-root ./benchmark-reference/benchmark --prepared /path/to/prepared-seed17 --output ./runs/p2-seed17 --check
python evaluation/run_prepared.py --benchmark-root ./benchmark-reference/benchmark --prepared /path/to/prepared-seed17 --output ./runs/p2-seed17 --url http://127.0.0.1:8013
```

第二条交互读取服务token，或从P2_MEMORY_TOKEN环境变量读取。每次生成唯一user_id范围；不复用其他方法答案。所有Answer落盘后才读取targets；HTTP记忆服务只收到历史和问题。选择题选项仍由reference Reader处理，此入口的P2检索仅用query原文，与当前P2规划接口一致。

**限制要明确**：该简版顺序执行，目标是容易复现，不承诺现有并行执行器速度；HTTP临时错误最多3次、保持Add ID与请求体；失败保留文件并标记incomplete，不补零。该入口不支持resume，勿用同一输出目录重启后冒充续跑。Reader/Judge预算只覆盖其自身，不包含远端Add/Search的模型消费。长期并发/断点任务应继续使用已单独交付的timeout-fixed并行包，并做P2适配，不能直接把原来的AMI方法名当P2。

这一新入口做离线接口/输入验收，不宣称已完整重跑出历史成绩。准确复现还需要相同公开数据版本、冻结输入、模型供应商及运行配置；模型随机性仍会造成差异。服务端预算、请求上限和账单需独立管理。

## 验收后修改

冻结的43份运行/算法来源文件有SHA256基线。改动它们后verify_release失败是预期提醒：应建立新版本、更新来源清单并重新评测，不可悄悄覆盖P2身份。`.env.private` 和数据库会被发布扫描拒绝，但不影响正常启动；扫描用于发包前，不要求运行目录永远没有私有配置。

## 重做新入口的离线集成验收

在Linux/WSL2、准备好上述reference仓库及tokenizer缓存后：

```sh
python evaluation/test_pipeline_offline.py --benchmark-root ./benchmark-reference/benchmark
```

使用reference仓库自带的两种格式、三道合成题，HTTP与模型替换为假实现；检查全部链路与评分产物，不输出性能结论，不需要服务token或真实API Key。
