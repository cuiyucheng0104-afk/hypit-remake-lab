---
title: 云端ComfyUI · AutoDL 应用实例 API
date: 2026-09-29
tags:
  - AIGC创意工具设计
  - 云端ComfyUI
  - AutoDL
  - API参考
  - 云算力
aliases:
  - AutoDL 开发者 API
  - AutoDL 应用实例 API
  - autodl.py
type: 速查
source: 用户 2026-09-29 提供的 AutoDL「应用实例API」官方文档原文；2026-09-29 本机 tools/autodl.py 实测（list、status）
---

# 云端ComfyUI · AutoDL 应用实例 API

> [!abstract] 一句话
> AutoDL 的开发者 API 能用程序**开、关、查、释放**基于「应用」（预装镜像，如 Zealman ComfyUI）开出来的显卡实例。它是「按需开机 → 跑批 → 立刻关机」这条省钱链路的开关。本机已写好 `tools/autodl.py`，`list` 与 `status` 实测通过；Token 只存在本机文件里，Claude 不经手。

## 1. 基本信息

| 项 | 值 | 证据 |
| --- | --- | --- |
| 服务地址 | `https://www.autodl.art` | 【文档】 |
| 接口前缀 | `/api/v1/adl_dev/dev/instance/pro/` | 【文档】 |
| 鉴权 | 请求头 `Authorization: <Token>`，**不带** `Bearer` 前缀 | 【文档】【实测】 |
| Token 来源 | AutoDL 控制台 → 账号 → 设置 → 开发者 Token | 【文档】 |
| 计费方式 | API 创建的实例一律按量计费，不能选包日包月 | 【文档】 |
| 实例 ID | 形如 `<INSTANCE_ID>`；容器主机名是 `autodl-<INSTANCE_ID>` | 【实测】 |
| 返回结构 | `{ code: "Success", data, msg, request_id }`，`code` 不是 `Success` 即失败 | 【文档】【实测】 |

> [!info] 「应用实例」是什么
> AutoDL 上的「应用」是别人（或你自己）打包发布的镜像，如 `ComfyUI-纯净版`、`zealman-ComfyUI`。应用实例 = 用某个应用开出来的一台机器，ID 以 `pro-` 开头。本页的 API 只管这类实例。你现在那台就是：主机名带 `autodl-pro-` 前缀【实测】。

## 2. 接口一览

| 方法 | 路径 | 作用 | 本机实测 |
| --- | --- | --- | --- |
| POST | `/create` | 新建一台实例（会开始计费） | 未测，脚本故意不提供 |
| GET | `/snapshot` | 实例完整详情，**含 root 密码** | 被拦截，脚本已删除 |
| GET | `/status` | 运行状态 | ✅ 返回 `running` |
| POST | `/list` | 分页列出全部应用实例 | ✅ |
| POST | `/power_on` | 有卡开机 | 未测（会开始计费） |
| POST | `/power_off` | 关机 | 未测（会改变计费状态） |
| POST | `/release` | 释放实例（删除数据） | 未测，脚本故意不提供 |

## 3. 各接口详解

### 3.1 创建 `POST /create`

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `req_gpu_amount` | 是 | GPU 数量，1–4 |
| `expand_system_disk_by_gb` | 是 | 系统盘扩容 GB，0–500 |
| `gpu_spec_uuid` | 是 | 算力规格 ID，见 [[#4. GPU 规格 ID]] |
| `application_uuid` | 是 | 应用的 UUID，在网页应用详情里看 |
| `application_version` | 是 | 应用版本；填 `latest` 用最新版 |
| `data_center_list` | 否 | 限定机房，如 `westDC3`（西北）、`beijingDC2`（北京）；不填系统自动选 |
| `instance_name` | 否 | 备注名 |
| `start_command` | 否 | 开机后执行的命令；成败不影响开机 |

返回 `data` 为新实例 ID。创建后是否自动开机，文档没写【空白】。

### 3.2 详情 `GET /snapshot`

参数 `instance_uuid`。返回里有用的字段：

| 字段 | 含义 |
| --- | --- |
| `payg_price` / `origin_pay_price` | 折扣后 / 折扣前的按量价格。示例值 1970 / 3030，**单位文档没写**【空白】 |
| `snapshot_gpu_alias_name` | 显卡型号 |
| `usage_info` | CPU、内存、磁盘占用，镜像拉取进度 |
| `ssh_command` / `proxy_host` / `ssh_port` | SSH 连接方式 |
| `root_password` | ⚠️ root 密码明文 |
| `jupyter_token` / `jupyter_domain` | JupyterLab 登录 token 与地址 |
| `service_6006_domain` | 6006 端口（ComfyUI 原生页面）的公网地址 |
| `service_6008_domain` | 6008 端口（Zealman 控制面板）的公网地址 |
| `cg_application_info` | 所用应用的名称、UUID、版本 |

> [!warning] 这个接口会返回实例 root 密码
> 2026-09-29 本机调用时，Claude Code 自动模式以「Credential Materialization（凭证落地）」拦截——即使脚本打印前会隐去密码，密码也已经进入进程【实测】。因此 `autodl.py` 删掉了 `info` 命令。需要的 SSH 地址和面板地址直接用已知值：SSH 见 [[云端ComfyUI · 实例与工作流清单]]，面板地址在服务器 `/root/面板地址.txt`。

### 3.3 状态 `GET /status`

参数 `instance_uuid`，`data` 直接是状态字符串，实测为 `running`。其他取值（`shutdown`、`starting` 等）来自 Zealman 并发文档的说明，见 [[云端ComfyUI · Zealman 并发 API]]。

### 3.4 列表 `POST /list`

请求体 `{ "page_index": 1, "page_size": 50 }`。每条记录的主要字段：`uuid`、`status`、`region_name`、`gpu_spec_uuid`、`req_gpu_amount`、`charge_type`、`start_mode`（`gpu` = 有卡）、`started_at` / `stopped_at`、`timed_shutdown_at`、`cg_application_info`。

实测结果（2026-09-29）：

```text
<INSTANCE_ID>  running  北京B区  4090D x1  zealman-ComfyUI
```

`gpu_spec_uuid` 实际返回 `4090D`，这个值不在文档附录的规格表里【实测】。

### 3.5 开机 `POST /power_on` · 关机 `POST /power_off`

- 开机：`{ "instance_uuid": "...", "payload": "gpu" }`。只能有卡开机（API 不支持无卡模式）；可带 `start_command`，会覆盖创建时设的命令。
- 关机：`{ "instance_uuid": "..." }`。关机后停止 GPU 计费，数据保留。

### 3.6 释放 `POST /release`

`{ "instance_uuid": "..." }`。必须先关机，否则可能释放失败。**释放后数据全部删除，不可恢复。**

## 4. GPU 规格 ID

| 网页显示型号 | 规格名称 | API 规格 ID |
| --- | --- | --- |
| H800-80G | 通用型 | `h800` |
| 4090-48G | 通用型 | `v-48g` |
| PRO6000-96G | 性能型 | `pro6000-p` |
| 4080(S)-32G | 性能型 | `v-32g-p` |
| 3090-48G | 通用型 | `v-48g-350w` |
| 5090-32G | 性能型 | `5090-p` |

## 5. 本机工具 `autodl.py`

位置：`~/hypit-projects/tools/autodl.py`。

```bash
python3 ~/hypit-projects/tools/autodl.py list
python3 ~/hypit-projects/tools/autodl.py status <INSTANCE_ID>
python3 ~/hypit-projects/tools/autodl.py on <INSTANCE_ID>
python3 ~/hypit-projects/tools/autodl.py off <INSTANCE_ID>
python3 ~/hypit-projects/tools/autodl.py wait <INSTANCE_ID> running 600
```

| 设计 | 原因 |
| --- | --- |
| Token 从 `~/.config/autodl/token`（权限 600）读取，脚本不打印 | Claude 不经手 Token |
| 不提供 `create` / `release` | 一个花钱、一个删数据，留给控制台人工操作 |
| 不提供 `info`（snapshot） | 返回 root 密码，见 3.2 |
| 默认用 `/etc/ssl/cert.pem` 做证书校验 | 见下节「坑 2」 |

Token 的存法（在自己的终端运行，粘贴时不回显）：

```bash
mkdir -p ~/.config/autodl && read -rs "?粘贴新的 AutoDL Token（输入不显示）: " T && printf '%s' "$T" > ~/.config/autodl/token && chmod 600 ~/.config/autodl/token && unset T && echo && echo 已保存
```

## 6. 实测踩到的坑

1. **GET 接口的参数要放查询字符串。** 文档把 `snapshot`、`status` 的参数写成「请求 Body」，实测放请求体返回 `RequestParameterIsWrong 请求参数错误`，改成 `?instance_uuid=...` 后正常【实测】。
2. **证书校验失败。** 本机 HTTPS 代理（127.0.0.1:1082）给出的证书链带自签根证书，python.org 版 Python 自带的证书库不认，报 `CERTIFICATE_VERIFY_FAILED`；改用系统证书库 `/etc/ssl/cert.pem` 即通过。没有关闭证书校验【实测】。
3. **Token 不能进聊天。** 2026-09-29 Token 曾被明文贴进对话，已作废重生成，新 Token 由用户自己用 `read -rs` 写入文件【实测】。拿到 Token 的人能开机器扣钱，还能通过 snapshot 读出所有实例的 root 密码。

## 原始资料

- 官方帮助文档：[AutoDL 帮助文档](https://www.autodl.com/docs/quick_start/)；同类接口页 [容器实例 Pro API](https://www.autodl.com/docs/instance_pro_api/)（按镜像开机器；搜索摘要显示它也走 `/instance/pro/create`，与本页按应用开机器的接口是否完全一致未逐页核对）。本页依据的「应用实例 API」原文由用户在对话中贴出，官方网址未找到。
- [[AutoDL 应用实例 API 原文]]：用户贴出的原文，待用户自行保存（链接变实即已保存）

## 相关

- [[云端ComfyUI · 总览]]
- [[云端ComfyUI · Zealman 并发 API]]：Zealman 面板把本页接口又包了一层（`/api/concurrent/instance/*`），但要把 Token 交给面板
- [[云端ComfyUI · 实例与工作流清单]]
