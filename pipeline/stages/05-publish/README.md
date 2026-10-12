# 05 · 发布（待开发）

## 平台约束（官方规则，调研于 2026-10-05，详见 docs/research/平台与接口调研.json）

- **TikTok Content Posting API**：
  - 未通过审核的客户端只能发私密视频，24 小时内最多 5 个用户；
  - Direct Post 每个账号通常约 15 条/天，额度由所有客户端共享；每个 token 每分钟 6 次请求。
- **用途条款**：不接受"帮你或你的团队给自己管理的账号上传内容的工具"，也不接受"把其他平台的内容复制到 TikTok"的应用。所以设计上要有**人工确认发布**这一步：上传页显示昵称、发布前可预览、隐私设置由人手动选、明确同意后才上传。
- **社区准则**（2026-09-24 生效）：禁止用自动化运营多个账号、发重复内容；搬运或轻微编辑的非原创内容不进推荐流。
- **AI 标注**：写实类 AI 内容需标注，接口字段为 `post_info.is_aigc=true`。

## 方案候选

- 自托管 [Postiz](https://github.com/gitroomhq/postiz-app)：AGPL-3.0，走官方 API，有 Public API 和 MCP；需自行在 TikTok 开发者平台申请应用审核。
- Upload-Post 或 Ayrshare 这类付费发布 API。
- **不用**浏览器自动化或逆向网页接口的上传工具，比如 social-auto-upload、TiktokAutoUploader。

## 待定

审核状态、草稿流，以及"发布前人工确认"的界面放在哪里。
