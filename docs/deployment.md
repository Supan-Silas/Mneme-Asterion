# 部署

## 进程与持久化

使用 `python -m mneme_asterion` 启动单worker服务。将SQLite数据库放在持久磁盘，模型地址与鉴权通过配置文件提供。监听地址和端口由 `--host`、`--port` 指定，默认监听本机。

```sh
python -m mneme_asterion --env-file /etc/mneme-asterion.env   --db /var/lib/mneme-asterion/memory.sqlite3 --host 127.0.0.1 --port 8014
```

配置、数据库目录和运行用户权限应与服务用户对应。SQLite备份使用其backup接口，或在停止写入后处理主库与WAL；运行期间保留完整持久化目录。

## systemd 示例

```ini
[Unit]
Description=Mneme-Asterion memory service
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/opt/mneme-asterion
ExecStart=/opt/mneme-asterion/.venv/bin/python -m mneme_asterion --env-file /etc/mneme-asterion.env --db /var/lib/mneme-asterion/memory.sqlite3 --port 8014
Restart=on-failure
RestartSec=5
TimeoutStopSec=1800

[Install]
WantedBy=multi-user.target
```

## HTTPS与请求超时

公网部署由反向代理终止TLS，将 `/health`、`/add`、`/search`转发到本机8014端口。Add可能包含多个模型请求，反向代理读取超时需要覆盖该处理时间；可采用1800秒代理超时及64MB请求体上限，并配置TLS证书自动续期。

## 资源规划

内存取决于活跃用户向量缓存，磁盘取决于原文、事实和向量数量。1024维float32向量每条4096字节，另有SQLite页、索引和日志开销。长消息与短消息具有不同的每token空间占用，容量规划应依据代表性历史建库测量。

关注可用磁盘、WAL增长、请求延迟及429/503比例。增加HTTP并发前检查上游配额；worker数量保持为1。

## 版本更新

停止接收新任务并等待在途写入结束后更新版本。保留数据库一致性备份，验证配置、health和Search方法身份后恢复流量。实验比较和正式评测期间固定版本与参数。

## V4.1 数据库

V4.1增加原子提交顺序记录。升级时为新版本指定独立的数据库路径，不直接复用旧V4数据库。保留旧版本、配置与原数据库供旧任务恢复。切换流量前验证写入、检索、幂等与用户隔离；同一评测任务运行期间保持代码、模型、提示词、配置及数据库一致。
