# Hypit Studio（员工用的画布网页）

挂在 5090 的 ComfyUI 端口上：**http://<5090内网IP>:8188/studio**。不用装任何东西，浏览器打开就能用；所有任务进 ComfyUI 同一个队列、共用一张显卡。测试阶段**没有登录**（之后再加）。

## 能做什么

| 卡片 | 模型 | 用法 |
| --- | --- | --- |
| 🖼 图片生成 | Qwen-Image 2.1 int8（审查版 / 未审查版可切换） | 不连图 = 文生图；连 1–6 张图 = 图生图 / 多图参考；可开「提示词扩写」（Qwen3.5-9B PE） |
| 🎬 视频生成 | MiniMax H3 int8（FL2VA / Ref2VA） | 文生视频、图生视频（首帧 / 首尾帧）、参考生视频（图·视频·音频）、多参考（关键帧钉到第几秒）、续写（取视频最后一帧接着拍）；可选加速 LoRA、二采高清、任意叠加本机 LoRA（动作·打斗·文戏、研究用） |
| ⬜ 视频转白膜 | SAM 3D Body + 自写去重影节点 | 真人视频 → 0.78 灰白模视频 + 叠原片核对视频 + GLB |

画布是 React Flow：素材 / 生成结果右边的圆点拖到生成器左边对应接口就是输入；生成结果会出现在生成器右边，还能再连到下一个生成器（生成的图 → 图生视频，生成的视频 → 续写 / 白膜）。画布存在服务器 `ComfyUI/user/studio/canvases/`，每次提交记在 `ComfyUI/user/studio/jobs.jsonl`。

## 目录

- `hypit_studio/` —— ComfyUI 插件，部署到 `ComfyUI/custom_nodes/hypit_studio`
  - `__init__.py`：`/studio` 页面和 `/studio/api/*`（选项、提交、查进度、画布存取）
  - `graphs.py`：把表单拼成 ComfyUI API 任务（结构对照官方模板 `video_minimax_h3_*`、`image_qwen_image_2_1_*` 和 LBH 二采示例）
  - `qwen_pe.json`：Qwen 提示词扩写的系统提示词（取自官方模板）
  - `sam3d_whitebox.json`：白膜任务模板（由「SAM3D白膜-灰底」工作流导出）
  - `web/index.html`：打包好的单文件网页（JS/CSS 全内联，内网电脑不需要外网）
- `web-src/` —— 网页源码（React 18 + @xyflow/react 12 + Vite），`npm run build` 输出到 `hypit_studio/web/`
- `deploy.sh` —— 打包并复制到 5090：`./deploy.sh ROG@<5090内网IP>`

## 验证记录

- 2026-10-23 在 5090 上逐个实测 `graphs.py` 生成的任务：H3 文生 / 图生 / 参考生（图+视频）/ 参考生+二采+打斗 LoRA（1280×736）/ 多参考 / 续写，Qwen 文生图（审查+扩写、未审查）/ 双图编辑，白膜 —— 全部 `success`。
- 2026-10-26 网页在本机模拟后端（接口同真后端、提交参数经真 `graphs.build` 校验）上用 Playwright 真鼠标拖拽跑通：上传 / 拖入素材、连线（错类型接口被拒）、参考生视频 + LoRA 强度 + 二采、文生图 → 结果连到图生视频首帧、生成视频 → 续写、白膜、多参考关键帧改秒数、刷新后画布与连线完整恢复、新卡片和结果卡片不重叠。
- **还没在 5090 上用真后端跑过网页**（当时不在内网）。部署后第一件事：每种卡片各点一次生成。
