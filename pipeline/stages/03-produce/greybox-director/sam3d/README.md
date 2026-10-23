# SAM 3D Body 白膜（ComfyUI 原生节点，ROG 5090 实测 2026-10-22）

从源视频重建每个人的 3D 人体（MHR 网格），按原相机重投影渲成白膜视频，并导出带骨骼动画的 GLB。结论与实测数据见 [白膜管线第三轮调研 §2](../../../../docs/research/白膜管线第三轮调研.md)。

- `sam3d_run.py <clip.mp4> <帧数> <max_objects> [--det]`：经 SSH 隧道（本地 18188 → ROG 8188）向 ComfyUI 提交；默认用 SAM 3.1 追踪，`--det` 改为 RT-DETR 逐帧检测。每次输出三条视频（rA：网格叠在 0.78 灰底上；rB：网格半透明叠在原片上，用来核对；rC：法线着色）和一个 GLB。
- `glb_probe.py`：`blender -b --python glb_probe.py -- x.glb out_prefix`，导入 GLB，统计骨架和动画，按 WORKBENCH 0.78 灰渲 3 帧。
- `SAM3D白膜-灰底.json`：在官方模板上改的 UI 工作流（2026-10-23 在 ROG 实跑通过）。改动包括：背景换成 0.78 灰纯色图（`EmptyImage` 64×64、1 张，渲染时会自动复用到每帧并缩放）；所有人用同一种灰（`person_palette_falloff=1.0`）；`max_objects=0`，追踪人数不设上限；另加一路「半透明叠原片」的核对输出。放到 `ComfyUI/user/default/workflows/` 后，在侧栏的「工作流」里打开。
- `evidence/`：只有白膜图，不含原片画面。`*_track.png` 是追踪模式（上：灰底网格；下：法线），`*_det.png` 是逐帧检测，`T3_glb_in_blender.png` 是 GLB 导进 Blender 后的渲染。

所需权重（Comfy-Org 重打包，未设门控）：`detection/sam_3d_body_dinov3_bf16`、`checkpoints/sam3.1_multiplex_fp16`、`geometry_estimation/moge_2_vitl_normal_fp16`、`diffusion_models/rt_detr_v4-x-hgnet_fp32`。
