# 服务器容量与崩溃风险评估

内部文档，非用户向。基于 2026-08-01 对线上 EC2 的实测数据（不是纸面估算）。

**更新（2026-08-01，同日）：下面「建议的优先级」1-4 项已全部上线执行完毕**——2GB swap（`/swapfile`，已写入 `/etc/fstab` 持久化）、5 处 OpenAI/Anthropic client 加了显式 `timeout`（commit `a593146`，已部署）、`docker builder prune` 每周日 4am UTC 的 cron（顺手手动跑了一次，回收了 3.4GB，磁盘从 60% 降到 43%）、S3 项目数据备份 + EBS 整机快照（详见 `docs/storage-decoupling-assessment.md`「执行状态」一节）。至此这轮容量/崩溃风险审计里发现的所有缺口都已补上。

## 一句话结论

**目前的负载下，这台机器不会崩**——30 天 uptime，0 次容器重启，0 次 OOM 记录，CPU/内存都远没跑满。真正的风险不是"现在扛不住"，而是**缺了几个兜底**：一旦真的撞上内存尖峰或磁盘写满，没有缓冲，会直接从"正常"跳到"进程被杀"，而不是优雅降级。这些兜底成本很低（加 swap 是 5 分钟的事），值得现在就补上，而不是等出事再修。

## 实测数据（2026-08-01，EC2 100.59.43.246）

| 项目 | 数值 |
|---|---|
| CPU | 2 vCPU（Xeon Platinum 8259CL，t3.small 级别） |
| 内存 | 1.9GB 总量，886MB 已用，406MB 空闲，**0 swap** |
| 磁盘 | 19GB 总量，9.0GB 已用，9.4GB 可用（49%） |
| Docker build cache | 5.3GB（占了将近三分之一的磁盘，可回收） |
| 后端容器内存 | 113.8MB（idle） |
| 前端容器内存 | 48.4MB（idle） |
| CPU 使用率 | 后端 0.24%，前端 0%（几乎全空闲） |
| 项目数据大小 | 33MB / 7 个项目 ≈ 4.7MB/项目 |
| Uptime | 30 天，load average 0.00 |
| OOM / 容器重启历史 | 0 次（`dmesg`/`journalctl` 无记录，`RestartCount: 0`） |

**读法**：现在的负载（低频、单人/少数人使用）里，CPU 是完全够用的——生成图片这类操作是"等 OpenAI 回包"，不是"本机算得慢"，所以 2 核几乎用不到。真正会紧张的资源是**内存**和**磁盘**，而不是 CPU。

## 并发模型（为什么这很重要）

后端用 `uvicorn main:app`，**没指定 `--workers`，默认是单进程**。FastAPI 里 `def`（同步）路由和 `BackgroundTasks`（图片生成走的就是这条路）都跑在 Starlette 内置的共享线程池里（默认上限约 40 个线程）。这意味着：

- 多个用户同时发起生成请求，不会互相"卡住"对方——线程池并行处理，每个线程大部分时间在等 OpenAI 网络回包，不占 CPU。
- 但**这 40 个线程是全站共享的一个池子**：如果因为某种原因有请求"挂住不返回"，占线程的数量攒多了，新请求会排队甚至超时——表现为"网站打不开了"，但进程其实还活着，只是线程池满了。

## 找到的三个真实风险点（已修 vs 待修）

### 1. 没配 swap ← 影响最大，建议立刻做
`free -h` 显示 swap = 0。Linux 在内存快用完时，有 swap 能把不常用的页面换到磁盘，进程会变慢但不会死；没有 swap，内存一旦被短时冲高（比如某个依赖有内存尖峰、或几个生成请求恰好撞在一起），OOM killer 会**直接杀掉进程**——docker 的 `restart: unless-stopped` 会把它拉起来，但期间：
- 正在写盘的请求（比如刚生成完图片、正在存 `generated.png` 那一刻）有被打断、文件写一半的风险。
- 用户会看到几秒到几十秒的服务中断，且**你不会收到任何通知**，只能等用户反馈或自己刷新才发现。

**修法**：加一个 2GB swap 文件，5 分钟搞定，之后同样的内存尖峰会变成"慢一点"而不是"进程被杀"。这是所有建议里性价比最高的一项。

### 2. OpenAI 调用没设超时 ← 会导致"线程池被占满"式假死
`tools/image_gen.py` 和 `tools/llm.py` 里 `OpenAI(api_key=...)` 都没传 `timeout`，用的是 SDK 默认值（数分钟级别）。`tools/vision.py` 已经支持传 `timeout` 参数了，但没有全局强制。正常情况下 OpenAI 响应很快就回来，不是问题；但一旦 OpenAI 那边偶发卡顿（发生过，不算罕见），没超时的请求会一直占着线程池里的一个线程，多个这样的请求叠加就会把线程池占满，新请求全部排队——现象上就是"网站卡死了"，但其实进程活得好好的。

**修法**：给三处 `OpenAI(...)` 客户端统一加一个显式 `timeout`（比如 90s，和前端 `useApi.ts` 的 `REQUEST_TIMEOUT_MS` 对齐），超时了就该失败就失败，别一直占着线程。

### 3. Docker build cache 会无限增长，迟早把磁盘写满
现在 5.3GB 的 build cache 已经占了将近三分之一的磁盘。CLAUDE.md 里明确要求每次代码改动都要 `docker compose up --build`（不能用 `restart`），这意味着 build cache 会随着部署次数持续增长——现在磁盘还有 9.4GB 余量,但照这个趋势迟早会把磁盘写满。磁盘写满时最糟的情况不是"部署失败"这么简单,而是后端往 `/app/storage` 写新生成的图片/项目数据时也会失败,可能出现半个文件、损坏的 json。

**修法**：部署脚本里加一行 `docker builder prune -f --filter until=72h`（每次部署顺手清理 3 天前的 build cache），或者干脆加个每周跑一次的 cron。

## 不用担心的地方

- **项目数据存储增长很慢**：33MB / 7 项目，就算涨到 500 个项目也就 ~2.4GB，磁盘清完 build cache 之后绰绰有余，短期不用管。
- **CPU 完全没有压力**：生成图片是网络 I/O 等待，不吃本机 CPU；除非未来真的接入本地跑的模型（比如 CLAUDE.md 待办里提到的 DWPose 姿态检测），CPU 大概率一直不会是瓶颈。
- **内存的"静态"占用很小**：两个容器加起来 idle 只占 162MB，1.9GB 里还有很大余量——真正的风险是"尖峰"而不是"稳态"，这也是为什么"加 swap"比"加内存"更划算：先用便宜的方式接住尖峰，而不是一上来就扩容。

## 建议的优先级

1. **立刻做（本周内）**：加 2GB swap（零成本、5 分钟，防住最大的崩溃风险）
2. **顺手做**：三处 OpenAI client 统一加 `timeout=90`
3. **部署流程里加一行**：`docker builder prune -f --filter until=72h`
4. **可选、看你想不想睡得更安心**：一个免费的外部监控（UptimeRobot 之类，或自己写个 cron 每 5 分钟 curl 一下首页/健康检查端点，失败就发个邮件/消息给自己）——这样进程真被杀的话你会立刻知道，而不是等用户投诉。

## 什么时候才需要真正升级机器

现在**不需要**升级——当前负载下 CPU/磁盘都很宽松，内存的风险用 swap 就能兜住大半。触发"该升级了"的信号是下面任意一条：
- 开始有**多人同时在线、经常性并发生成**（不是偶尔撞车，而是常态），而不是现在这种低频使用；
- 做完上面 1-3 项之后，`dmesg`/`docker compose logs` 里**仍然**能看到 OOM 或容器被杀的记录。

到那个时候，该加的是**内存**（比如跳到 2 vCPU / 4GB 的档位），而不是 CPU——这个工作负载的瓶颈模式很清楚是内存/IO，不是算力。

## 自查命令（以后想确认健康状况时用）

```bash
ssh -i refimage-key.pem ubuntu@100.59.43.246

free -h                                    # 内存 + swap 使用情况
df -h /                                    # 磁盘剩余空间
docker system df -v                        # build cache 占了多少
docker stats --no-stream                   # 各容器实时内存/CPU
docker inspect refimage-backend-1 --format "RestartCount: {{.RestartCount}}"  # 有没有被杀过重启
dmesg | grep -i oom                        # 有没有 OOM 记录
docker compose -f ~/RefImage/docker-compose.yml logs backend --since 48h | grep -iE "error|traceback|exception"
```
