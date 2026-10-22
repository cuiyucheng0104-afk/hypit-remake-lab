# 05 发布 · Postiz 本机试用部署与云版调研 Spec（条目化）

> **文档状态**：v0.2，2026-10-22。**本机自部署试用已于 2026-10-22 卸载**（§1–§5 保留为历史记录，可按 PZL-07 复现）；方向转为 Postiz 云版，调研记录见 §6，**仍在探索，未拍板**。v0.1（2026-10-13）记录 Postiz 在策划 Mac 上的**试用部署**（评估界面、Public API 与平台接入流程），**不是**生产部署。生产部署是否做、放在哪里，仍由总纲 [pipeline-skeleton-spec.md](pipeline-skeleton-spec.md) 的 DEC-10 / DEC-03 决定（PLAN-10，W3 末）。
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
- **PZL-05** `DISABLE_REGISTRATION` 仍为 `'false'`：用户还没注册管理员，必须先开着。 —— 〔总纲 SW-02〕｜等级【实测】｜验收：见 PZL-09｜状态：作废（未注册即卸载；若按 PZL-07 复现，仍需执行 PZL-09）
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
- **PZL-09** 用户注册管理员后，关闭注册：把 compose 中 `DISABLE_REGISTRATION: 'false'` 改为 `'true'`，再 `docker --context colima-postiz compose up -d`。 —— 〔总纲 SW-02〕｜等级【推断】｜验收：退出登录后 `/auth` 不再显示注册表单｜负责：用户注册，Claude agent 改配置｜状态：作废（同 PZL-05）

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
- **PZL-12** 卸载（评估结束或要回收磁盘时）：`docker --context colima-postiz compose down -v` → `colima delete postiz`。只删 `postiz` profile，**不得**对 default 执行 stop/delete/prune。 —— 〔总纲 HW-15〕｜等级【推断】｜验收：`colima list` 只剩 default，且 default 状态不变｜负责：用户确认后执行｜状态：已具备（2026-10-22 执行：卷与 `colima-postiz` 实例已删除，`colima list` 只剩 default 且仍 Running，docker 默认 context 仍为 `colima`）

## 4 试用要回答的问题（喂给 DEC-10）

- **PZL-13** 需要在试用中确认、再回填总纲的事项： ｜等级【未知】｜状态：作废（自部署已放弃，原因见 PZC-01；云版要确认的事项见 PZC-12）
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

## 6 云版调研（2026-10-22，探索中，未拍板）

> 本节只记录调研结论和待验证项，不改变总纲的 NG-02、DEC-10。是否采用云版、用哪种发布模式，等 PZC-12 实测后再由用户在 DEC-10 拍板。

### 6.1 为什么放弃自部署

- **PZC-01** 自部署版发 TikTok 必须自带 TikTok 开发者应用：在 `.env` 里填 `TIKTOK_CLIENT_ID` / `TIKTOK_CLIENT_SECRET`，开通 Login Kit 和 Content Posting API，再加一个 https 公网域名（服务条款页、隐私页、域名验证、https 回调）。用户拿不到 TikTok API，所以自部署这条路发不了 TikTok，换哪台服务器都一样。另有自部署者被 TikTok 以「个人或公司内部使用不符合条件」拒审（gitroomhq/postiz-app#2297，2026-10-20）。 —— 〔`postiz-docs/self-host/providers/tiktok.mdx`、`self-host/configuration/reference.mdx` 平台凭据表、GitHub #2297〕｜等级【文档】｜状态：已具备

### 6.2 云版的接入方式

- **PZC-02** 云版所有套餐都带 Public API、CLI、MCP。TikTok 用的是 Postiz 官方应用，用户只需在网页上用 OAuth 授权自己的 TikTok 账号，不需要开发者账号。接入方式：CLI `npm i -g postiz` + `POSTIZ_API_KEY`（或 `postiz auth:login` 设备码登录）；API `https://api.postiz.com/public/v1/*`，请求头 `Authorization: <key>`；MCP `https://mcp.postiz.com/mcp/<key>`。管线编排器优先用 CLI/API（行为确定），MCP 只用于对话式操作。 —— 〔`postiz-docs/cli/*`、`mcp/setup.mdx`、`public-api/introduction.mdx`、`cloud/plans.mdx`；postiz.com 首页〕｜等级【文档】｜状态：已具备
- **PZC-03** 套餐与限额：$29 / $39 / $49 / $99 每月，对应 5 / 10 / 30 / 100 个频道，每月发帖条数不限。发帖接口限额，`cloud/limits.mdx` 写每小时 90 次请求，`public-api/introduction.mdx` 写「云版 100」，⚠待核实（同总纲 B-17）。一次请求可以带多条帖子。 —— 〔`cloud/plans.mdx`、`cloud/limits.mdx`〕｜等级【文档】｜状态：已具备
- **PZC-04** 能发视频：先 `postiz upload <mp4>` 拿到 `uploads.postiz.com` 地址，再 `posts:create`。TikTok 的设置项有 `content_posting_method`、`privacy_level`、`video_made_with_ai`（即 is_aigc）、`duet`、`stitch`、`comment`、`brand_*`。`postiz analytics:*` 可以拉回指标，供 06 回测用。 —— 〔`cli/media-upload.mdx`、`cli/platform-examples.mdx`、`public-api/providers/tiktok.mdx`〕｜等级【文档】｜状态：已具备
- **PZC-05** 出口 IP：网页授权这一步来自操作者浏览器所在的网络；管线到 Postiz 的上传和发帖命令来自我方服务器；**真正发到 TikTok 的请求来自 Postiz 云服务器**（服务器之间直接调接口），不经我方网络和手机。Postiz 服务器在哪个国家，文档没写。总纲 DEC-10 担心的「5 个账号从我方同一出口上传」，在云版下变成「从 Postiz 的共享出口上传」：这个出口同时服务大量 Postiz 用户，它本身是否构成账号关联信号【未知】。 —— 〔`tiktok.provider.ts` 服务端调用；总纲 DEC-10、NET-12〕｜等级【推断】（依据【文档】）｜状态：待验证

### 6.3 官方 TikTok 应用是否已过审

- **PZC-06** 结论：**大概率已过审，能公开发**；但没有官方明文确认，也没找到云版用户「帖子公开可见」的实测。证据并列如下（CONV-03）。 ｜等级【推断】（依据【第三方】）｜状态：待 PZC-12 实测
  - 支持：维护者在 gitroomhq/postiz-app#1908（2026-08-17 合并）中说官方应用上限是每天 1000 个活跃用户，TikTok 拒绝调高。按 TikTok 规则，未审核应用最多 5 个用户/24 小时，所以 1000 的额度暗示已过审（推断）。
  - 支持：云版用户在 #1854（2026-08-07，09-05 另一用户补充）用 `DIRECT_POST` + `PUBLIC_TO_EVERYONE` 失败，报的是 `reached_active_user_cap`，不是未审核错误码；后一位用户自述看不到底层报错，只说「可能同因」。
  - 支持：`public-api/openapi.json` 的 cover 字段说明称官方测试中封面只对公开帖生效，说明官方发出过公开帖。
  - 不利：云版文档没写 TikTok 应用的审核状态。源码把未审核错误映射为「App not approved for public posting, contact support」。官方编辑器默认选 `PUBLIC_TO_EVERYONE`，不符合 TikTok 现行界面规范，已有自部署者因此被拒审（#1563），云版用同一套代码，复审时理论上有风险。
- **PZC-07** 真正的风险是**名额被占满**：官方应用全体用户共享每天 1000 个活跃用户的名额，满了就发帖失败，用户自己解决不了。维护者为此新增了 `tiktok-business` 渠道（走 TikTok Business Accounts API，没有按应用计的名额；发布用 `PULL_FROM_URL`）。用这个渠道的前提是账号能切换为企业号，这条渠道是否支持「发到收件箱」【未知】。 —— 〔#1908、#1854；`tiktok.provider.ts` 217–226 行 `MIGRATE_PROVIDERS`〕｜等级【文档】｜状态：待验证

### 6.4 发到草稿箱、人在手机上发布（UPLOAD 模式）

- **PZC-08** UPLOAD 模式**不发布**：视频只进账号的 TikTok App 收件箱，账号主人要在 24 小时内手动完成发布，否则作废。这正是总纲 DEC-10 预留的选项，与 NG-02「不做自动发布」不冲突。 —— 〔`public-api/providers/tiktok.mdx:72`、`tiktok.provider.ts:29`〕｜等级【文档】｜状态：已具备
- **PZC-09** UPLOAD 模式的限制： ｜等级【文档】｜状态：已具备
  1. TikTok 只保留标题（不超过 90 字），`privacy_level`、`video_made_with_ai`、`duet`、`stitch` 等设置全部被丢弃，**AI 生成标注必须在手机上手动打**（表 11-2 #3）。
  2. 每个账号 24 小时内最多 5 条待发草稿，超出报 `spam_risk_too_many_pending_share`（`tiktok.provider.ts:195-199`，#1300）。
  3. Postiz 在推到收件箱时就报「发布成功」（`tiktok.mdx:75`），编排器不能把这个当作已发布，状态机要停在「待人工发布」。
  4. Postiz 只记录 `publishId`，`releaseURL` 指向收件箱，拿不到最终公开帖子的 ID（`tiktok.provider.ts:490-503`），所以 06 回测需要人工发布后**回填帖子链接**（经 DEC-27 的运营入口）。
- **PZC-10** UPLOAD 模式大概率不受「未审核只能私密」的限制（那条限制针对 Direct Post）；但很可能仍占用官方应用每天 1000 个活跃用户的名额。 ｜等级【推断】｜状态：待 PZC-12 实测
- **PZC-11** 如果走 DIRECT_POST，必须显式传 `content_posting_method: "DIRECT_POST"`。设为 `SELF_ONLY` 的帖子拿不到公开帖子 ID，指标为空（`tiktok.provider.ts` 1176–1181 行）。DIRECT_POST 仍与 NG-02 冲突，需要用户改 DEC-10 才能采用。 ｜等级【文档】｜状态：已具备

### 6.5 7 天试用的验证清单

- **PZC-12** 用测试号、不对外宣传的前提下验证以下事项，结果回填本节和总纲 DEC-10： ｜负责：用户（授权账号、手机发布、联系客服）；Claude agent（CLI 调用与记录）｜状态：待做
  1. 「TikTok」和「TikTok Business」两种渠道各连一次，截图授权页上的应用名。
  2. UPLOAD：推 1 条草稿，确认手机收件箱收到、标题保留；手动发布后用未登录的浏览器确认公开可见；隔天再推一条，看名额问题。
  3. DIRECT_POST（仅验证用，不作为采用依据）：用公开测试号发 `PUBLIC_TO_EVERYONE`，用未登录的浏览器确认可见；不同日期、不同时段至少 3 次；记录报错原文，区分「App not approved…」（未过审）和「daily user quota/limit reached」（名额满）。
  4. 向官方客服书面确认：官方应用是否已过审、名额多少、是否推荐 TikTok Business 渠道。回复存档（用户本人发送）。

### 6.6 待讨论：账号与设备

- **PZC-13** 多个 TikTok 账号怎么登录、在哪台设备上发布，还没定，下一步讨论。候选方案：(a) 5090 上开容器跑安卓模拟器，各登一个账号；(b) 账号只在 Postiz 授权，最后一步在真机上发布（总纲 NET-12「一号一机一出口」、NG-02）。注意：(a) 与总纲 NG-02「不做群控、改机」直接冲突，且 TikTok 社区准则禁止用自动化运营多个账号（R5-45、R6·E16），需要先改总纲并评估封号风险。 ｜等级【推断】｜状态：待用户拍板
- **PZC-14** 运营前提（用户确认，2026-10-22）：在美国运营美国区账号，由专人在美国负责；策划约一半时间在美国。因此账号的登录、授权、发布这一端本来就在美国网络上，5090（大陆）只负责生产成片，不登录任何账号。 ｜等级【实测】（用户陈述）｜状态：已具备
- **PZC-15** 推荐方案（待用户拍板）：账号在 Postiz 云版授权，管线经 CLI 推草稿（UPLOAD）；美国运营人员用**一号一机的真手机**在 App 里完成发布并打 AI 标注，再回填帖子链接。不在 5090 上跑模拟器登号（NG-02）。账号的授权和日常登录始终从美国一侧进行；策划人在国内时不直接登录这些账号，必要时使用固定的美国出口。 ｜等级【推断】｜状态：待用户拍板
