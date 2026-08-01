# 存储解耦评估：现在要不要把数据搬出后端？

内部文档，非用户向。基于对代码库的实测 grep（2026-08-01）和对线上 EC2 的只读 SSH 检查。承接 `docs/server-capacity-notes.md` 里的容量评估——那份文档发现了三个待修的兜底缺口（swap / OpenAI timeout / build cache 清理），**截至本次检查，三个都还没修**（`free -h` 仍是 `Swap: 0B`；`grep timeout tools/*.py` 五处 `OpenAI(...)` 客户端全部没传 `timeout`）。这份文档回答一个新问题：要不要把项目数据（角色图、生成图、guide JSON、聊天记录）从后端本地磁盘搬到 S3 之类的外部存储。

## 一句话结论

**现在不需要解耦，但需要立刻补一个之前完全没有的东西：备份。** 33MB/7 个项目的数据量、单实例、零并发扩容压力，解耦到 S3 只是把风险从"机器坏了数据就没了"换成"多了网络调用失败、IAM 凭证管理、presigned URL 复杂度"这一堆新故障模式——用 CLAUDE.md 自己的话说，这正是"为假设性未来需求做设计"。真正该做、且现在完全没有的，是**灾备**：这台机器如果被误删/损毁，33MB 数据和 `.env` 里的 API key 会**一点不剩地消失**，因为——见下文实测——**目前没有任何形式的备份**。

## 实测发现一：代码里存储访问的耦合程度

`STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"` 这一行被**独立复制**在 17 个文件里（`grep -rl STORAGE_ROOT`），而不是从一个共享模块 import：

```
tools/image_gen.py, agents/planning_chat.py, api/shot.py,
services/{avatar,questionnaire,shot_guide,project,plan,export,
shot_plan,generate,cover,agent_state,moments,location,
wardrobe,home}_service.py
```

围绕这 17 个文件，直接的文件系统操作（`.read_text/.write_text/.read_bytes/.write_bytes/open(`）加起来遍布 `services/` `api/` `agents/` `tools/` 四层，`project_service.py` 一个文件里就有 40+ 处 `.exists()` 调用。这不是"5 个入口做适配层"的规模，是**几十个调用点分散在业务逻辑内部**——比如：

- **文件存在性直接充当业务逻辑**：`services/project_service.py:719` 的 `_clear_guide_cache`、以及 811-813 行"如果 `generated.png` 不存在就清空 `active_version_id`"，`shot_guide_service.py` 用 `camera.json` 是否存在判断要不要重新生成 guide——这些判断依赖的是**本地文件系统的强一致性**（写完立刻能读到、`exists()` 立刻反映刚才的写）。换成 S3 之后这类判断要么改造成显式状态字段，要么要处理 S3 的最终一致性/网络延迟，属于"顺手就能改"变成"要重新设计"的那类改动。
- **直接用 `FileResponse` 把本地文件当 HTTP 响应体**：`api/shot.py` 和 `api/project.py` 里合计 12 处 `FileResponse(path, media_type=...)`，前端 `<img>` 标签直接打后端 URL 拿图。换 S3 意味着要么后端读 S3 再转发（多一跳网络 I/O，等于没省事只是换了个数据源），要么前端全面改造成 presigned URL（涉及签名过期时间、CORS 配置、前端缓存策略——一次不小的前后端联动改动）。
- **同步文件 I/O 直接跑在请求处理函数里**，没有经过统一的存储抽象层，`shutil.copy2` / `.unlink()` 这类操作也是直接对本地路径操作（`project_service.py:808,813,817` 版本回退逻辑）。

**结论**：如果真要做 Option B（迁移到 S3），这不是"改 5 个调用点"的规模，保守估计要碰十几个文件、几十个调用点，外加前端 presigned URL 改造和 guide 缓存判断逻辑重新设计——对应 CLAUDE.md 里"改动范围要匹配问题大小"的原则，用一个几天到一两周的重构去解决一个"33MB 数据会不会丢"的问题，投入产出明显不成比例。

## 实测发现二：现在完全没有备份机制（确认，不是猜测）

SSH 到线上实例（只读检查，未创建/删除/修改任何东西）：

| 检查项 | 结果 |
|---|---|
| `crontab -l`（ubuntu 用户） | `no crontab for ubuntu` |
| `/etc/cron.d/` | 只有系统默认的 `.placeholder` 和 `e2scrub_all`，**没有任何自定义条目** |
| `systemctl list-timers --all` | 19 个 timer，全部是 Ubuntu 系统自带的（apt/logrotate/fwupd/man-db 等），**没有任何应用相关的备份 timer** |
| `aws` CLI | `bash: aws: command not found`——机器上根本没装，不可能有 `aws s3 sync` 或 `aws ec2 create-snapshot` 在跑 |
| 仓库/home 目录里的备份脚本 | `find ~/RefImage -iname '*backup*'` 和 `find /home/ubuntu -iname '*backup*'` 均为空 |
| Docker volume 类型 | `docker volume inspect refimage_storage` → `"Driver": "local"`，`Mountpoint: /var/lib/docker/volumes/refimage_storage/_data`——物理上就是根 EBS 卷上的一个目录，不是任何形式的托管存储或跨 AZ 复制 |

同时确认：本地开发机和 EC2 上都**没有安装/配置 AWS CLI**（`which aws` 两边都失败），说明这个项目此前从未接触过任何 AWS API 层面的自动化——EC2 实例本身大概率是当初手动在控制台建的。另外 `.env` 文件在 `.gitignore` 里（`grep -i env .gitignore` 命中 `.env` / `.env.*`），**只存在于这台 EC2 上，没有任何副本**——里面是 `OPENAI_API_KEY` 等密钥。这意味着风险不只是"33MB 项目数据"，如果实例本身丢了（误操作终止、EBS 卷损坏、AWS 账号问题），**连重新部署所需的密钥配置都要从头找回**。

这印证并强化了此前的猜测：不是"备份机制比较薄弱"，是**字面意义上的零备份**。

## 三个选项的评估

### Option A（推荐）：不做架构改动，只加自动备份

针对上面两个具体风险分别配一个便宜的兜底，都不改一行应用代码：

**A1. `storage/projects` 定期同步到 S3**（保护项目数据，支持按项目粒度恢复）
**A2. 根 EBS 卷的自动快照**（保护整机状态，包括 `.env`、docker 配置、系统本身）

两者互补：A1 恢复快、粒度细（能单独找回某一个项目），但不包含 `.env`/系统配置；A2 恢复粒度粗（要整卷/整机恢复）但连密钥配置一起保住。33MB 数据 + 19GB 系统盘，两者加起来的存储成本一个月大概几美分到一美元，setup 一次性投入约 30-40 分钟。

#### A1 具体步骤：S3 同步

1. **建 S3 bucket**（AWS 控制台或 CLI，选和 EC2 相同 region 省流量）：
   ```bash
   aws s3api create-bucket --bucket refimage-backups-<你的账号后缀> \
     --region <你的 region> \
     --create-bucket-configuration LocationConstraint=<你的 region>
   aws s3api put-bucket-versioning --bucket refimage-backups-<你的账号后缀> \
     --versioning-configuration Status=Enabled
   aws s3api put-public-access-block --bucket refimage-backups-<你的账号后缀> \
     --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
   ```
   开 versioning 的意义：即使脚本用 `--delete` 同步导致某个文件在 bucket 里被"删除"，历史版本还在，能找回误删/被 bug 破坏的项目。

2. **给 EC2 一个只能写这一个 bucket 的 IAM 权限**——两种方式选一种：
   - **推荐：IAM Role + Instance Profile**（不用在机器上存密钥）：建一个 IAM role，附加下面这条最小权限策略，然后 `aws ec2 associate-iam-instance-profile` 挂到正在跑的实例上（不需要重启实例）：
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [{
         "Effect": "Allow",
         "Action": ["s3:PutObject", "s3:ListBucket", "s3:GetObject"],
         "Resource": [
           "arn:aws:s3:::refimage-backups-<后缀>",
           "arn:aws:s3:::refimage-backups-<后缀>/*"
         ]
       }]
     }
     ```
   - **更快但要管密钥**：建一个 IAM user，同样的策略，生成 access key，`aws configure` 写到 EC2 的 `~/.aws/credentials`（注意这组密钥本身也要保护好，权限已经限定到只能碰这一个 bucket，泄露影响有限）。

3. **EC2 上装 AWS CLI**（目前没装）：
   ```bash
   ssh -i refimage-key.pem ubuntu@100.59.43.246
   sudo apt-get update && sudo apt-get install -y awscli
   # 或用官方安装包（版本更新）：
   # curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
   # unzip awscliv2.zip && sudo ./aws/install
   ```

4. **备份脚本**（放 `/home/ubuntu/backup-storage.sh`）：
   ```bash
   #!/bin/bash
   set -euo pipefail
   aws s3 sync /var/lib/docker/volumes/refimage_storage/_data/projects \
     s3://refimage-backups-<后缀>/projects/ \
     --delete \
     >> /home/ubuntu/backup.log 2>&1
   echo "$(date -Iseconds) backup done" >> /home/ubuntu/backup.log
   ```
   注意路径是 Docker named volume 在宿主机上的真实挂载点（`docker volume inspect refimage_storage` 查到的 `Mountpoint`），不是仓库里的 `backend/storage`——两者内容一致，但直接读宿主机挂载点不需要进容器、也不占用容器内的 CPU/内存。

5. **cron 定时**（每天凌晨 3 点 UTC，此时几乎没人用）：
   ```bash
   chmod +x /home/ubuntu/backup-storage.sh
   crontab -e
   # 加一行：
   0 3 * * * /home/ubuntu/backup-storage.sh
   ```

6. **验证**：手动跑一次脚本，`aws s3 ls s3://refimage-backups-<后缀>/projects/ --recursive | head`，确认文件都同步过去了；等第二天再看 `backup.log` 确认 cron 真的跑了。

成本：33MB 数据，S3 标准存储 $0.023/GB/月 ≈ 不到 $0.001/月；`PutObject` 请求数因为大部分文件同步后不变、`sync` 只传增量，月请求成本几美分。基本可以认为免费。

#### A2 具体步骤：EBS 自动快照（AWS Data Lifecycle Manager）

不用碰实例本身，纯 AWS 控制台/CLI 操作：

1. 找到根卷的 volume ID：`aws ec2 describe-instances --instance-ids <instance-id> --query "Reservations[].Instances[].BlockDeviceMappings"`，或者控制台 EC2 → 实例 → 存储标签页直接看。
2. 给这个卷打个 tag，比如 `Backup=daily`（DLM 靠 tag 选目标）：
   ```bash
   aws ec2 create-tags --resources <volume-id> --tags Key=Backup,Value=daily
   ```
3. 建一条 DLM 生命周期策略：每天快照一次，保留 7 天：
   ```bash
   aws dlm create-lifecycle-policy \
     --description "RefImage EC2 root volume daily snapshot" \
     --state ENABLED \
     --execution-role-arn arn:aws:iam::<account-id>:role/AWSDataLifecycleManagerDefaultRole \
     --policy-details '{
       "ResourceTypes": ["VOLUME"],
       "TargetTags": [{"Key": "Backup", "Value": "daily"}],
       "Schedules": [{
         "Name": "DailySnapshot",
         "CreateRule": {"Interval": 24, "IntervalUnit": "HOURS", "Times": ["04:00"]},
         "RetainRule": {"Count": 7},
         "CopyTags": true
       }]
     }'
   ```
   （`AWSDataLifecycleManagerDefaultRole` 是 AWS 提供的默认服务角色，控制台里第一次配置 DLM 时会提示自动创建；用控制台点几下比拼 CLI 参数更省事，效果一样。）

成本：增量快照，19GB 卷、日常改动量很小（主要是新项目的 4.7MB 和偶尔的 docker 镜像层变化），预计每月几十美分。

**做 A1 还是 A2？两个都做**——A1 十分钟出结果、成本几乎为零、粒度细；A2 多花 10-15 分钟但顺带把 `.env`、docker 配置、系统本身也保住了，这是 A1 覆盖不到的。两者都不碰应用代码，都不引入运行时的新故障模式（都是"锦上添花"的旁路机制，挂了也不影响线上服务），完全符合 CLAUDE.md"不做超出需求的设计"的原则——因为这里的需求是明确存在的（"数据丢了怎么办"是真实风险，不是假设性的），只是解法不需要碰架构。

### Option B：解耦到 S3（图片走 S3，JSON 元数据留本地或迁移到轻量 DB）

**收益**：图片不再占用 EC2 磁盘，理论上磁盘增长压力归零；如果未来真的需要多实例，静态资源已经外部化。

**实际代价**（基于上面的代码扫描，不是纸面估算）：
- 十几个文件、几十个调用点要改：所有 `STORAGE_ROOT` 相关的 `.read_bytes/.write_bytes/open()` 图片读写要换成 S3 SDK 调用。
- `api/shot.py`、`api/project.py` 里 12 处 `FileResponse` 要么改造成 presigned URL（前端配合改造、要处理 URL 过期），要么后端代理转发（多一跳网络，等于没解决"耦合"这个问题本身，只是换了数据落地位置）。
- `_clear_guide_cache`、`generated.png`/`camera.json` 这类"文件存在即状态"的缓存判断逻辑要重新设计成显式状态字段，否则 S3 的最终一致性会在偶发情况下让缓存判断出错（概率低，但排查起来会比"文件系统本地强一致"难得多）。
- 新增故障模式：S3 网络调用失败/限流、IAM 凭证轮换/过期、presigned URL 因为时钟偏移或前端缓存过旧而 403、`boto3` 客户端和现有 5 处 `OpenAI(...)` 客户端一样需要显式配置 timeout（不然会重蹈"没配 timeout 导致线程池假死"的覆辙，见 `server-capacity-notes.md` 风险点 2）。
- 迁移脚本：33MB 数据一次性 `aws s3 cp --recursive` 不难，但迁移过程中如果有用户正在用（哪怕概率很低），需要考虑双写窗口或短暂停机。
- 持续成本：S3 存储本身接近免费，但多了一个需要维护的外部依赖、一套新的权限模型、以及"S3 出问题时后端功能连带受影响"的新耦合点——对于一个只有 33MB 数据、日均可能个位数用户的项目，这是纯粹的复杂度净增加。

**结论**：值得做的时间点是"图片数据量真的开始让磁盘吃紧"（按 `server-capacity-notes.md` 的增长速率，500 个项目才 2.4GB，清完 build cache 后磁盘绰绰有余）或者"真的要上多实例/负载均衡"，两者现在都不成立。

### Option C：有没有发现新的、改变判断的因素？

专门找了一圈：`docker-compose.yml` 只定义了单份 `backend`/`frontend` 服务，没有 `replicas`/`deploy` 配置；CLAUDE.md、`docs/` 下所有文档、git log 里都没有提到任何多实例/负载均衡/水平扩容的规划。`server-capacity-notes.md`（本次评估的前置文档）明确写了"现在不需要升级"，触发升级的信号是"多人同时在线、经常性并发"——目前 CPU 利用率 0.24%，完全没有这个信号。**没有找到任何改变判断的新证据**，Option C 不成立。

## 最终建议

**不解耦。现在做 Option A（S3 同步 + EBS 快照双保险），不做 Option B。**

如果说要挑战一下"这个判断会不会也是路径依赖/懒得改"——反过来想：解耦到 S3 能解决的问题是"磁盘空间不够"和"要支持多实例"，而实测这两个问题现在都不存在（33MB 数据，19GB 盘，单实例零并发压力）。解耦真正回应不了、也不该用来回应的问题是"数据会不会丢"——这是备份该管的事，不是存储架构该管的事，两者不能混为一谈。用一次十几个文件的重构去换一个十五分钟 cron 脚本就能拿到的保障，成本收益完全不对称，这正是 CLAUDE.md 里"别为假设性未来需求做设计"想避免的情况。

## 执行状态（2026-08-01，已全部完成）

1. ✅ **Option A1（S3 同步备份）已上线**——bucket `refimage-backups-161583482522`（us-east-1，已开 versioning）；IAM role `RefImageBackupRole`（最小权限，只能碰这一个 bucket）已挂到实例上，走角色临时凭证，**机器上没有存任何静态密钥**；`/home/ubuntu/backup-storage.sh` 每天 3am UTC 跑 `aws s3 sync`。**踩过一个坑**：脚本一开始没加 `sudo`，`/var/lib/docker/volumes/...` 这条路径的父目录 `/var/lib/docker`（mode `0710`）对非 root 用户没有任何权限——`ubuntu` 用户虽在 `docker` 组，但那只管 docker daemon socket 权限，不代表能直接读宿主机上的卷文件，`aws s3 sync` 因此报"path does not exist"（Python 的 `os.path.exists` 把权限错误也归到"不存在"）。改成 `sudo` 跑之后手动验证：136 个文件、7 个项目全部同步成功。`ubuntu` 用户是 NOPASSWD sudo（`/etc/sudoers.d/90-cloud-init-users`），cron 非交互也能正常跑 `sudo`。
2. ✅ **Option A2（EBS 快照）已上线**——用了比原计划更简单的路径：没有手动打标签+建自定义 DLM 策略，而是直接用 AWS 提供的"默认策略"（account 级，自动覆盖所有卷，账号里当时只有 3 块盘，覆盖全部成本可忽略）。`policy-0d4db873252914b8e`，Enabled，Every day / 保留 7 天，IAM role 用 DLM 的 Default role（AWS 自动创建，和 `RefImageBackupRole` 无关，是两个独立的角色）。
3. ✅ **`server-capacity-notes.md` 里三个待修项也已全部完成**（同一天做的）：2GB swap（已写入 `/etc/fstab` 持久化）、5 处 `OpenAI(...)`/Anthropic client 加了显式 `timeout`（commit `a593146`，已部署到线上）、`docker builder prune` 每周日 4am UTC 的 cron（顺手手动跑了一次，回收 3.4GB，磁盘 60%→43%）。
4. **重新评估解耦的时间点不变**：出现下面任意一条时再重新考虑 Option B，而不是现在：
   - 项目数量涨到实测显示磁盘真的开始吃紧（按当前 4.7MB/项目的速率，得涨到几百上千个项目）；
   - 真的要上第二台实例/负载均衡（目前代码、配置、文档里都没有这个方向的任何迹象）。

## 自查命令（以后想确认备份是否在正常工作时用）

```bash
ssh -i refimage-key.pem ubuntu@100.59.43.246

crontab -l                                              # 确认备份 cron 还在（S3 sync + build cache prune 两条）
tail -20 /home/ubuntu/backup.log                        # 确认最近几次 S3 同步成功
aws s3 ls s3://refimage-backups-161583482522/projects/ --recursive | wc -l   # 确认 S3 上文件数和本地大致对得上
aws sts get-caller-identity                             # 确认走的是 RefImageBackupRole，不是某个静态密钥
```

EBS 快照走的是账号级 DLM 默认策略，`RefImageBackupRole` 没有 `dlm:*`/`ec2:*` 权限查不到——去控制台 EC2 → Elastic Block Store → Lifecycle Manager 看，或 Snapshots 页面看最近快照时间。
