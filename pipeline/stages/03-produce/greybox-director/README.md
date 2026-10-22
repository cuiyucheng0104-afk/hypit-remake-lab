# 03c · 灰模导演台：参考片反推白膜（调研完成，待实验）

> **2026-10-22 第三轮（用户拍板后）**：03b 和 03c 合并为一层。源视频转白膜的主路改为「遮头 + Seedance 2.5 edit」，SAM 3D Body 已在 5090 上实测，作为后备和补充（见 [sam3d/](sam3d/)）；原创镜头的白膜改用 seedance-skill 作底座。详见 [白膜管线第三轮调研](../../../docs/research/白膜管线第三轮调研.md)。

> **2026-10-22 第二轮调研**：见 [动作迁移与白膜调研-2026-10-22](../../../docs/research/动作迁移与白膜调研-2026-10-22.md)。和本页相关的变化：
> - 首选原型从 PromptHMR（非商用）改为 **SAM 3D Body + SAM 3.1**：ComfyUI 原生，可商用，相机空间重投影，不需要世界坐标；遮挡严重时加 SAM-Body4D；
> - Meshcapade 已被 Epic 收购，SMPL 商用授权这条后备方案不稳；
> - 白膜消费端多了开源的 LTX-2.5 Layout-to-Render；
> - agent 接 Blender 可以用本机官方 Blender Lab MCP 的无头模式；
> - 第一个要做的实验是**方舟白膜过审探针**（调研文档 P0-2）。

**目标**：从参考片反推出 Blender 白膜场景，包括逐镜头的相机轨迹，以及每个人在世界坐标里的 3D 全身动作（带脚步位移）；渲染成白模视频，作为参考视频交给 Seedance 等模型生成。
- **原片画面不进生成器**，避免原演员的脸、服装漏到成片里；
- **动作可以在 Blender 里改**，比如补上 S01 没演出来的"倒握"。

Blender 侧（灰模脚本、白模参数、Seedance 的 `reference_video` 接口）已在 Obsidian「04 灰模预演管线」里实测跑通；这里补的是"从参考片反推"这一段。

调研原始数据（每个项目都用 gh api 核实了 stars、license、更新时间）：[../../../docs/research/视频反推白膜调研.json](../../../docs/research/视频反推白膜调研.json)，调研日期 2026-10-12。

## 结论
- **没有端到端方案**：没有开源项目能一步完成"快切 + 手持甩镜 + 多人 → 相机 + 世界坐标人体 → Blender"。人体和相机是两半，尺度、坐标的对齐和多人的相对站位都要自己写。
- **都不处理切点**：所有项目都要求先按切点把参考片拆开，逐段处理。切点我们已经有（02 读片的产物）。
- **超短镜头相机难解**：0.3–0.5 秒的镜头只有 9–15 帧，SLAM 类方法大概率初始化失败。这类镜头要么按固定机位处理，要么用前馈模型估相机，再在 Blender 里手调。
- **快动作会被"压平"**：GVHMR 等模型会把快速的肢体动作抹平，需要用 2D 关键点做后优化（SMPLify 回贴）。
- **硬件**：几乎都要 CUDA，所以推理跑在 AutoDL 4090D 上，Mac 本机只做 Blender 端。

## 候选

| 用途 | 项目 | 关键事实 | 许可 |
| --- | --- | --- | --- |
| **人 + 相机一体，首选原型** | [PromptHMR](https://github.com/yufu-wang/PromptHMR)（497★） | 多人（SAM2 跟踪）、世界坐标、DROID-SLAM 相机；**官方 GLB 可直接导入 Blender，人体和相机都在** | 非商业（代码与 SMPL-X 都是） |
| 人 + 相机 + 场景点云，速度最快 | [Human3R](https://github.com/fanegg/Human3R)（543★） | 前馈一次出多人 SMPL-X、点云和相机，约 8GB 显存、15 FPS；没有 Blender 导入 | CC BY-NC-SA |
| 多人 + 相机，代码 MIT | [TRAM](https://github.com/yufu-wang/tram)（643★） | 遮掉人体后跑 DROID-SLAM，再用深度定尺度；每人一条轨迹 | 代码 MIT；SMPL 非商业 |
| 单人质量最好，社区工具最多 | [GVHMR](https://github.com/zju3dv/GVHMR)（2105★） | demo 只取一条轨迹，多人要逐人循环；社区有 Blender 链路（mixamo-llm-mocap、mocap-wrapper、ComfyUI-MotionCapture） | 非商业 |
| Blender 导入的参考实现 | [WHAC](https://github.com/MotrixLab/WHAC) | 官方 `import_to_blender.py`，同时导入人体和相机 | 非商业 |
| 只解相机（短镜头友好） | [VGGT](https://github.com/facebookresearch/vggt)（14490★）、[MapAnything](https://github.com/facebookresearch/map-anything) | 前馈模型，不需要 SLAM 初始化；要先用人体遮罩挡掉人；输出 COLMAP 格式，经 [Photogrammetry Importer](https://github.com/SBCV/Blender-Addon-Photogrammetry-Importer) 导入 Blender | VGGT 商用权重需申请；MapAnything 有 Apache 权重 |
| **可商用的人体链路** | [GEM-X](https://github.com/NVlabs/GEM-X)（SOMA 骨架）、SAM 3D Body（MHR，ComfyUI 原生节点可导出多人 BVH） | 不依赖 SMPL；GEM-X 只支持单人，SAM 3D Body 逐帧估计、没有世界轨迹 | Apache / NVIDIA Open Model；SAM License（需读原文确认） |
| 多人遮挡补全 | [sam-body4d](https://github.com/gaomingqi/sam-body4d) | 专门处理重遮挡；但 5 人 90 帧要 35–53GB 显存，超出 24GB | 代码 MIT |
| 商业对照 | Autodesk Flow Studio（原 Wonder Studio） | 相机追踪 + 动捕 + 导出 Blender 场景；Pro 档 $95/月，最多 4 人（第三方报价） | 商业 |

## 许可红线（已核原文）

SMPL / SMPL-X 只许非商业科研，明文禁止"用于商业产品或商业服务"，商用要向 Meshcapade 购买授权。所以：
- **研发验证阶段**：可以用 PromptHMR、TRAM 等；
- **投产前**：要么买 SMPL-X 商业授权，要么换成 SOMA（GEM-X）或 MHR（SAM 3D Body）的链路。

## 第一个实验（待做）

1. 取 S01 的 L 镜、M 镜（打斗 + 运镜），按切点帧切出片段；
2. 在 AutoDL 4090D 上跑 PromptHMR-video，短于 15 帧的镜头加 `--static_camera`；
3. 把 GLB 导入 Blender，人体换成白膜人偶，按即梦参数渲染白模视频：WORKBENCH、0.78 灰、24fps；
4. 用 Human3R 跑同样的镜头做对照；有条件再加 Flow Studio 做商业基线；
5. 白模视频交给 Seedance 生成，用 `04-review/scripts/review_metrics.py` 和原片、Bernini 结果做三方对比。

这一步同时回答灰模管线里一直没验证的核心假设：灰模到底能把机位和动作钉多紧。

## 第三方：PromptHMR（git submodule）

`pipeline/third_party/PromptHMR` 只是对官方仓库的引用（固定在提交 `3b566b7`），**源码不在本仓库内**。
- **许可证**：Meshcapade 的 PromptHMR License。只许非商业科研，未经书面许可不得复制、修改后提供给第三方。拉取子模块（`git submodule update --init`）即表示接受这些条款。
- **商用授权**：sales@meshcapade.com。
- **衔接脚本**：我们自己写，放在本目录，不改动它的源码。
