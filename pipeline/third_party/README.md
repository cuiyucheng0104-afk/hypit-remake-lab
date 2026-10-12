# third_party：第三方组件

| 目录 | 来源 | 方式 | 许可 | 用途 |
| --- | --- | --- | --- | --- |
| `postiz/` | [gitroomhq/postiz-app](https://github.com/gitroomhq/postiz-app) `main`，导入于 2026-10-13 | 完整源码（git subtree，squash） | **AGPL-3.0** | 05 发布：多账号排期、发布、Public API / MCP、基础数据回收 |
| `postiz-docs/` | [gitroomhq/postiz-docs](https://github.com/gitroomhq/postiz-docs) `main`，导入于 2026-10-13 | 完整文档（git subtree，squash） | MIT | Postiz 官方文档：自部署、各平台接入、Public API、CLI、MCP |
| `PromptHMR/` | [yufu-wang/PromptHMR](https://github.com/yufu-wang/PromptHMR) `3b566b7` | **只有子模块引用，源码不在仓库内** | Meshcapade 非商业许可，不得再分发 | 03c 灰模导演台：从参考片反推相机和多人 3D 动作 |

## 许可注意
- **Postiz（AGPL-3.0）**：
  - 修改后若以网络服务的形式提供给他人使用，必须公开修改后的源码；
  - 它是独立的程序，我们的代码通过 Public API 调用它，不和它的源码混编。
- **自带的 agent 说明文件**：`postiz/CLAUDE.md`、`postiz-docs/SKILL.md` 是上游项目写给 AI 助手的说明，只适用于开发 Postiz 本身，**不是本仓库的规则**。

## 更新上游
```bash
git subtree pull --prefix pipeline/third_party/postiz https://github.com/gitroomhq/postiz-app.git main --squash
git subtree pull --prefix pipeline/third_party/postiz-docs https://github.com/gitroomhq/postiz-docs.git main --squash
git submodule update --init pipeline/third_party/PromptHMR   # 会下载 PromptHMR，表示接受其许可
```

## Postiz 常用入口
| 要看什么 | 位置 |
| --- | --- |
| 自部署 | `postiz/docker-compose.yaml`；`postiz-docs/self-host/` |
| TikTok 接入（UPLOAD 和 DIRECT_POST 两种模式） | `postiz/libraries/nestjs-libraries/src/integrations/social/tiktok.provider.ts`、`tiktok.business.provider.ts` |
| YouTube、Instagram、Facebook、X | 同目录下的 `youtube.provider.ts`、`instagram*.provider.ts`、`facebook.provider.ts`、`x.provider.ts` |
| Public API（我们的管线从这里调用） | `postiz-docs/public-api/` |
| 给 agent 用的 CLI 和 MCP | `postiz-docs/cli/`、`postiz-docs/mcp/` |
| 审批流、数据统计 | `postiz-docs/cli/approvals.mdx`、`postiz-docs/cli/analytics.mdx`、`postiz-docs/general/analytics.mdx` |
| 应用结构 | `postiz/apps/`：backend、frontend、orchestrator、sdk、extension、commands |
