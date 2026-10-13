# 05 发布 · Postiz 本机试用部署 Spec（条目化）

> **文档状态**：v0.1，2026-10-13。记录 Postiz 在策划 Mac 上的**试用部署**（评估界面、Public API 与平台接入流程），**不是**生产部署。生产部署是否做、放在哪里，仍由总纲 [pipeline-skeleton-spec.md](pipeline-skeleton-spec.md) 的 DEC-10 / DEC-03 决定（PLAN-10，W3 末）。
> **与总纲的关系**：总纲 BL-08 写明「本机部署由另一个会话处理，不在本 spec 范围内」，本文就是那份记录。HW-15 要求 Mac 不再跑 Postiz——本次试用经用户同意作为例外，放在独立 Colima profile 里，不占 default，评估结束后按 PZL-12 卸载。
> **公开仓库提示**：本文不写 IP、主机名、令牌、账号。条目格式、证据等级沿用总纲 CONV-01/02：`**ID** 要求/现状 —— 理由〔出处〕｜等级【…】｜验收：…｜状态：…`。

---

## 1 现状（2026-10-13 实测）

| 项 | 值 |
|---|---|
| 运行位置 | 策划 Mac，Colima profile `postiz`（2 CPU / 8 GiB / 40 GiB 磁盘，aarch64，docker runtime） |
| docker context | `colima-postiz`（**不是**全局默认；默认仍是 `colima` = default profile） |
| 部署目录 | `pipeline/stages/05-publish/deploy/`（compose + `setup.sh` + `dynamicconfig/`；`.env` 不入库） |
| 服务 | 8 个：postiz、postiz-postgres、postiz-redis、temporal、temporal-postgresql、temporal-elasticsearch、temporal-admin-tools、temporal-ui |
| 主镜像 | `ghcr.io/gitroomhq/postiz-app@sha256:d2b37802…7fde1`（2026-10-11 构建的 `latest`，镜像无版本 label，故钉 digest） |
| 入口 | Postiz UI `http://localhost:4007`；Temporal UI `http://localhost:8080`；Temporal gRPC `localhost:7233`——三者都只绑 127.0.0.1 |
| 占用 | 镜像 11.6 GB，卷约 140 MB（空库） |
| 账号 | 未注册。首个注册者即管理员，由用户本人完成 |

- **PZL-01** 8 个容器全部 Up，postgres / redis 健康检查 healthy；`GET http://localhost:4007` 返回 307 跳转到 `/auth`，注册页可渲染；后端 pm2 error 日志为空。 —— 〔实测 2026-10-13〕｜等级【实测】｜验收：`docker --context colima-postiz compose ps`｜状态：已具备
- **PZL-02** 端口只绑回环：compose 的三处 `ports` 改为 `127.0.0.1:4007:5000`、`127.0.0.1:7233:7233`、`127.0.0.1:8080:8080`。改前 Mac 上 `lsof` 显示监听 `*:4007/*:7233/*:8080`（Colima ssh 转发跟随容器绑定地址），即局域网可直接访问开放注册页和无认证的 Temporal UI。改后监听为 `127.0.0.1:*`，从本机局域网 IP 访问 4007 连接被拒。 —— 〔总纲 SW-02、R1-20〕｜等级【实测】｜验收：`lsof -nP -iTCP -sTCP:LISTEN | grep -E ':(4007|7233|8080) '` 只出现 127.0.0.1；`curl http://<本机局域网IP>:4007` 失败｜状态：已具备
- **PZL-03** 主镜像钉 digest，其余 7 个镜像沿用 compose 原有的固定 tag。 —— 〔总纲 SW-02、BL-08〕｜等级【实测】｜验收：`docker compose config --images` 不含 `:latest`｜状态：已具备
- **PZL-04** `JWT_SECRET` 由 `setup.sh` 用 `openssl rand -hex 32` 生成到 `.env`（权限 600，`.gitignore` 已忽略）；compose 用 `${JWT_SECRET:?run ./setup.sh first}` 读取，缺失即拒绝启动。 —— 〔总纲 SW-02、表 9 密钥清单〕｜等级【实测】｜验收：`git check-ignore -v .env`；`stat -f %Lp .env` = 600｜状态：已具备
- **PZL-05** `DISABLE_REGISTRATION` 仍为 `'false'`：用户还没注册管理员，必须先开着。 —— 〔总纲 SW-02〕｜等级【实测】｜验收：见 PZL-09｜状态：待用户注册后执行
- **PZL-06** 存储 `STORAGE_PROVIDER='local'`（卷 `postiz-uploads`），与总纲 STO-02「先用 local」一致；`API_LIMIT: 30`（总纲 B-17 的 90/30 冲突，自部署以此为准）。 —— 〔R1-21、STO-02、B-17〕｜等级【实测】｜状态：已具备

## 2 部署步骤（可复现）

- **PZL-07** 从零部署：
  ```bash
  colima start postiz --disk 40 --cpu 2 --memory 8
  docker context use colima          # ⚠ 必须立刻切回，见 PZL-08
  cd pipeline/stages/05-publish/deploy
  ./setup.sh                         # 只生成一次 .env
  docker --context colima-postiz compose pull
  docker --context colima-postiz compose up -d
  ```
  内存给 8 GiB 而非 6 GiB：Elasticsearch + Temporal + Postiz（前端、后端、orchestrator 三个 pm2 进程）同机，6 GiB 偏紧【推断】。磁盘 40 GiB = 镜像 11.6 GB + 上传卷与数据库余量。 —— 〔实测 2026-10-13〕｜等级【推断】（依据【实测】）｜验收：PZL-01｜状态：已具备
- **PZL-08** `colima start <profile>` 会**静默把全局 docker context 切到新 profile**。default profile 由另一个会话共用、且其脚本直接调用裸 `docker`，切走会让那边连错虚拟机。因此：启动后立即 `docker context use colima`；本文所有 Postiz 命令一律显式带 `--context colima-postiz`，不依赖全局 context。 —— 〔实测 2026-10-13：启动输出 `Current context is now "colima-postiz"`〕｜等级【实测】｜验收：`docker context ls` 的 `*` 在 `colima`｜状态：已具备
- **PZL-09** 用户注册管理员后，关闭注册：把 compose 中 `DISABLE_REGISTRATION: 'false'` 改为 `'true'`，再 `docker --context colima-postiz compose up -d`。 —— 〔总纲 SW-02〕｜等级【推断】｜验收：退出登录后 `/auth` 不再显示注册表单｜负责：用户注册，Claude agent 改配置｜状态：待做

## 3 运维

- **PZL-10** 常用命令（均在 `pipeline/stages/05-publish/deploy/` 下）：
  ```bash
  docker --context colima-postiz compose ps
  docker --context colima-postiz compose logs -f postiz
  docker --context colima-postiz compose stop      # 暂停，保留数据
  docker --context colima-postiz compose start
  colima stop postiz                               # 释放 8 GiB 内存；不影响 default
  ```
  ｜等级【实测】｜状态：已具备
- **PZL-11** 试用期数据只在 Colima 卷里（`postiz_postgres-volume`、`postiz_postiz-uploads` 等），不做备份；如果试用中录入了需要保留的配置（平台应用、账号授权），迁到生产前用 `pg_dump` 导出 postiz 库。 —— 〔总纲 STO-11〕｜等级【推断】｜状态：待做（视试用结果）
- **PZL-12** 卸载（评估结束或要回收磁盘时）：`docker --context colima-postiz compose down -v` → `colima delete postiz`。只删 `postiz` profile，**不得**对 default 执行 stop/delete/prune。 —— 〔总纲 HW-15〕｜等级【推断】｜验收：`colima list` 只剩 default，且 default 状态不变｜负责：用户确认后执行｜状态：待做

## 4 试用要回答的问题（喂给 DEC-10）

- **PZL-13** 需要在试用中确认、再回填总纲的事项： ｜等级【未知】｜状态：待做
  1. Public API 写草稿（UPLOAD 到收件箱）在自部署版的实际行为与限额（B-17：`API_LIMIT=30` 是否按每小时请求数计）。
  2. TikTok / YouTube 等平台应用在自部署版需要的 client key、回调 URI（总纲 NET-11 要 https 公网域名——Mac 本机试用拿不到，平台授权这一步预计无法在本机走通【推断】）。
  3. 资源实际占用（`docker stats`），用于修正总纲 HW 表里 Postiz 的 CPU / 内存 / 磁盘估算。
  4. 运营是否真的需要 Postiz UI，还是手机原生发布 + 表格回填就够（DEC-27）。

## 5 与总纲 SW-02 的对照

| SW-02 要求 | 本机试用现状 | 条目 |
|---|---|---|
| 镜像钉到具体版本 | 已钉 digest | PZL-03 |
| 4007、7233、8080 绑 127.0.0.1 | 已绑 | PZL-02 |
| `DISABLE_REGISTRATION=true` | 待用户注册后改 | PZL-05、PZL-09 |
| Temporal UI 不对外 | 只绑回环 | PZL-02 |
| `.env` 权限 600 | 已是 600 | PZL-04 |
