# ref105 重制 · 进度

## 2026-09-29
- 方舟 SSO 已由用户重新登录。账号 profile `platform_cn-beijing_accountwide`，API Key 已配。
- 模型：`doubao-seedance-2-5`（版本 260628）在模型广场可见，计费状态 Available。账号下现有 EP 里**没有** 2.5 的接入点
  （有 2.0 的 `ep-20260424203934-ghqfk`）；首次按模型名调用时才能确认是否已开通。
- 2.5 关键参数（`arkcli models get doubao-seedance-2-5 --transform supported_params`）：
  - `omni_reference_task_type`: auto / reference / **edit** / extend。
    edit = 视频编辑：必须带 reference_video（4–30 s），ratio 必须 adaptive，duration 必须 -1（跟随原片）。
  - resolution: 480p / 720p / 1080p（无 4k）；duration 4–30 或 -1；不支持 seed、camera_fixed、draft。
  - 默认 `generate_audio=true`，`watermark=false`。
- 单价（元/千 tokens）：带视频输入 720p 0.042、1080p 0.046；不带视频输入 720p 0.07、1080p 0.077。
- 路线：edit 模式逐段重绘（原片段做 reference_video，人物/场景图做 reference_image）。用 arkcli 直调，Hypit 做拆解与合成。

## 试拍参考片段（已就绪，未花钱）
`refclips/`，已裁掉底部字幕条（保留 1280×620）、抹掉抖音 logo/抖音号/"Q 坚果"/作者署名，去掉音频：
- `A_0293-0830.mp4`：源 2.933–8.300 s，5.37 s。反握剑手部→俯拍→人群→冲锋→主角特写→开打。
- `B_1987-2587.mp4`：源 19.867–25.867 s，6.0 s。大全景群战、踩水、倒地。
- 检查图 `check_A.jpg`、`check_B.jpg`。右下角去水印处留有一块柔和的模糊，运动中不明显。

## 等用户
- 新人物（主角；黑衣敌人是否一起换）与新场景：图片或文字描述。
- 试拍分辨率（720p / 1080p）与试拍花费确认。

## 2026-09-29 试拍提交结果：被内容安全拦截（未生成）
- `doubao-seedance-2-5` 按名称调用报无权限；带版本号 `doubao-seedance-2-5-260628` 可访问。
- arkcli 本地校验不接受 `duration=-1`，需放进 `--extra-body '{"omni_reference_task_type":"edit","duration":-1}'`。
- reference_video 只接受网络 URL（本地文件被拒）。用户同意后曾用 ngrok 临时隧道提供两段片段，已关闭、已删除服务目录。
  （TOS：当前 ve 登录凭证 list_buckets 返回 AccessDenied。）
- A、B 两次提交均被拦：`InputImageSensitiveContentDetected.PrivacyInformation`，content[0]（主角定妆图 hero.jpg）被判"可能含真人"。
  方舟规则：输入参考图/视频含真实人脸即拦截；官方合规通道是"录入真人形象素材"（可信素材库，需核验/授权）。
- 结论：写实定妆图需走可信素材库；原剧片段含未获授权的真人演员，不能作为方舟参考输入，也不做打码规避。
  "动作一致"需改用无真人脸的动作参考（自有白模 previz、自拍/授权演员素材），或放弃参考视频、按拆解重新调度镜头。

## 2026-09-29 改用方舟预置虚拟人像试拍（用户指示）
- 素材库 OpenAPI 可用：`ve ark <Action> --force --version 2024-01-01 --method POST --body '{...}'`。
  - 预置库：`ListAssetGroups/ListAssets` 的 `Filter.GroupType="Public"`。"青年-男-xx"是**音色**；人像命名形如"中国 31岁 男 山野渡劫散修"。
  - 私域库：`GroupType="AIGC"`，用户已有 8 组（心屿小屋 C01–C06、藏锋·角色、陈青），均为脚本式批量创建，素材 Active。
    → 用户自己的定妆图也可走 `CreateAssetGroup` + `CreateAsset(URL)` 录入私域库。
- 主角选用预置人像 14 号"中国 31岁 男 山野渡劫散修"：`asset-20260720212606-gfgzw`（全身）、`asset-20260720212605-jvvb6`（半身）。
  配角群用文字描述（henchmen.jpg 露脸会被拦）；场景用 `assets/scene-courtyard-1280.jpg`（base64 内嵌）。
- `arkcli +gen` 不认 `asset://`；改用 `arkcli api arkruntime.create_content_generation_task --params "$(cat prompts/req-X.json)"`。
  **坑：`arkcli api` 不理会 `--dry-run`，会真实提交。**
- 模式：reference（无参考视频，按 TIMELINE 镜头顺序文字调度），16:9、6 s、720p、generate_audio=true。
  单价按不带视频输入 0.07 元/千 tokens，两段估算约 18 元（在已批 10–21 元内）。
- 任务：A `cgt-20260929011938-n9ryy`（prompts/ref-A-v1.txt）；B `cgt-20260929012126-tor8o`（prompts/ref-B-v1.txt）。

## 2026-09-29 试拍结果（预置人像 v1）
- A、B 各 130,500 tokens，按 0.07 元/千 tokens 合计约 18.3 元（在已批 10–21 元内）。
- 输出：`refclips/out/pilotA-preset-v1.mp4`、`pilotB-preset-v1.mp4`、拼接 `pilot-AB-preset-v1.mp4`；检查图 `*-grid.jpg`。
- 观察（逐 0.25 s 看帧）：
  - A 基本按 6 个镜头走完：手握刀鞘特写→高角度独立院中→从刀客背后看主角→刀客冲锋溅水→主角正面近景→交手。
    "正顶视"成了高角度俯拍；"反握刀、刀身贴小臂"没出来，是横握刀鞘。
  - B 场景与用户图1 构图高度一致（左侧回廊廊柱）；闪避肘击、摔人、贴地扫腿水幕都有；最后一镜只剩倒地刀客、主角不在画面里。
  - 人物一致性：脸型两段一致；**发型不一致**——A 近景披发、看不到发髻木簪，B 有发髻。
  - 鲤鱼刺绣被做成胸前一整条银色大鲤鱼贴片，不是用户设定里的暗纹满绣。
  - 斗笠：A 偏黑、B 偏银灰金属感，前后不统一。
  - 无文字/水印；有生成音轨，全程无 >0.4 s 静音段（未试听）。

## 2026-09-29 转为"外部平台人工生成 + 本地回装"
- 用户决定：生成在用户自己的平台人工完成（可直接用参考视频做一比一编辑）；我负责拆分交付包与回装、最后用 Hypit 合成字幕与配乐。
- 交付包 `export/`（说明见 `export/README.md`）：
  - 全片帧级切点 82 个（`references/ref-105/evidence/cuts-frame-0.3.txt`，scene>0.3）。
  - 正片按真实切点分 9 段（S01–S09，5.3–13.2 s，合计 85.767 s），已裁字幕条、去水印；S09 额外抹掉落版圆环（t≥6.2 s 左缘）。
  - 每段提示词 `prompts/Sxx.txt`，统一上传顺序：图片1 主角 / 图片2 反派头目 / 图片3 配角群 / 图片4 场景 / 视频1 分段。
  - `conform.py` 已空跑验证：缺段灰度占位，时长偏差 >0.04 s 自动变速；产出 conformed / conformed_720 / compare。
  - `captions-template.srt`：原片 9 行字幕实测时间（换行多卡在剪辑切点上）。
- 等用户：生成结果 `export/generated/Sxx.mp4`、新字幕文案、有版权的配乐。平台参考视频时长上限若 <13.3 s 需重切。
- 2026-09-29：交付包已复制到桌面 `~/Desktop/ref105重制-交付包/`（用户要求）。用户的生成结果会放在桌面这份的 `generated/` 里，回装以桌面这份为准。

## 2026-09-29 私域素材库录入工具（用户手动运行已跑通，3 张均 Active）
- 写了 `~/hypit-projects/tools/ark_asset_upload.py`：ListAssetGroups 找同名组/CreateAssetGroup(AIGC) → 临时 ngrok 挂图（或 --base-url）→ CreateAsset(URL) → GetAsset 轮询 Active → 关隧道 → 清单写入 `~/hypit-projects/assets-registry/<组名>.json`。
- Claude 自动模式的权限审核拦截了运行（External Ingress Tunnel），连 --help 也拦；**脚本尚未实跑，CreateAsset 参数按文档与开源实现编写，未经验证**。
- 待用户在自己终端运行一次；之后可用只读 ListAssets 核对状态。

## 2026-09-29 AutoDL 云显卡服务器（用户提供）
- 连接：`ssh -i ~/.ssh/autodl_ed25519 -p <SSH_PORT> root@<AUTODL_SSH_HOST>`（密钥登录，用户用 ssh-copy-id 装的公钥；密码不记录）。
- RTX 4090D 24GB，503GB 内存，Ubuntu 22.04；系统盘仅剩 16GB，模型在只读共享盘 `/.autodl-model`。
- 镜像 Zealman ComfyUI v9.31：ComfyUI 跑在 127.0.0.1:6006；面板 API 在 6008（`/api/workflow/generate`，参数写"节点ID:字段名"，工作流需先在面板"API 生成"页保存）。
- 相关工作流 `/root/ComfyUI/user/default/workflows/K视频-人物替换/`：
  - K05 影视二创·多人版：输入仅 LoadImage(57 角色参考) + VHS_LoadVideo(63 原视频)，姿态驱动，可全自动。
  - K03 影视二创：需 PointsEditor(559) 在某帧手动打点给 SeC 分割目标人物，适合在界面里操作。
  - K01：含"换背景"分支（SAM3 分离人物/背景）。
- 模型齐全：Wan2.2-Animate-14B（fp8/bf16/int8）、Wan Animate 2、Wan2.1 VACE 14B/1.3B、SeC-4B、SDPose、CLIP Vision H。

## 2026-09-29 S01 在 AutoDL 上跑 Wan2.2 Animate 替换（进行中）
- 方案：K03「影视二创」的替换模式——SeC 在第 0 帧按点位跟踪主角（可跨剪辑点），Wan Animate 只重绘被遮罩的人，保留原片镜头/动作/背景/其他人。
  第一步只换主角（hero.jpg），敌人（henchmen）与场景（scene）后续分步做。
- K03 存档时 SeC 分割段是旁路（mode 4），且 AnimateEmbeds 没接 bg_images/mask；已在转换时启用分割段并补接 bg_images←DrawMaskOnImage(391)、mask←BlockifyMask(401)。
- 转换方法：SSH -L 16006→服务器 6006，内置浏览器打开 ComfyUI，`comfyAPI.app.app.loadGraphData()` + `graphToPrompt()` 导出 API 格式，存到服务器 userdata `ref105/K03_api_raw.json`。
  本地存档：`comfy/workflows/K03_api_raw.json`、`S01_hero_v1.json`；补丁脚本 `~/hypit-projects/tools/autodl/patch_k03.py`，提交 `submit.py`，轮询 `poll.sh`。
- 参数：1280×624、30 fps、4 步（lightning LoRA）、fp8 Animate 14B、blockswap 30。SeC 点位（1280×624 坐标，第 0 帧）：正 9 点（斗笠/脸/下巴/头发/蓝袍），负 8 点（窗格/顶部/门洞）。
- 坑：VHS_LoadVideo 遇到无音轨视频会报错 → `export/refclips_sil/` 为九段补了静音音轨，服务器上用这批。
- 任务：第一次 ae5c516f（音轨报错），重提 8399dd44。

## 2026-09-29 S01 第一版结果与遮罩修正
- v1（SeC 第 0 帧打点）：前 4 秒主角替换成功；约 4.9 s 后跟丢；手部特写没认出；输出被补帧到 321 帧，需截回 249 帧。
  成片/对照：`comfy/out/S01_hero_v1_trim.mp4`、`S01_compare_v1.mp4`（桌面交付包 `本地生成测试/` 也有）。
- SAM3 文字分割（`easy sam3ImageSegmentation`）：“blue robe”会误选深蓝黑衣敌人；“light blue robe”+“straw hat”无误选但漏模糊帧、特写只圈斗笠不圈脸。
- 最终遮罩做法（`~/hypit-projects/tools/autodl/mask_merge.py` v6）：
  1. SAM3 导出三路原始遮罩：light blue robe(0.45) / straw hat(0.45) / person(0.35)（`mask_export.py`）。
  2. 种子=长袍∪斗笠；与种子重叠的 person 连通块整体并入（补上斗笠下的脸），过宽的粘连块不并。
  3. 低阈值(0.12)重测切点，S01 共 15 个镜头；人工标注有主角镜头 1,2,3,6,7,8,9,12,13,14,15，其余强制清空。
  4. 有主角但没检测到的帧：在 person 连通块中挑“亮蓝像素比例”最高者（原片主角是唯一亮蓝袍）；与最近锚点（种子帧）水平距离 >25% 画宽则判为跳错。
  5. 镜头内 ±30 帧补帧、±1 帧平滑、膨胀 12 px。遮罩视频加静音音轨后上传。
- v2：`patch_mask.py` 去掉 SeC，改为 VHS_LoadVideo(遮罩)→ImageToMask(red)→GrowMask，任务 02dab0ac。

## 2026-09-29 用户要求暂停
- S01 v3（单人全身参考 hero_front、正向提示词、relight 0.5、SDPose 阈值 0.2）：俯拍改善；打斗镜头袍子仍是亮蓝、5.1 s 双脸、3.1 s 手部仍冒脸。
  输出 `comfy/out/S01_hero_v3_trim.mp4`。
- 正在排查“袍子没被重画”：已导出第 198 帧的生成用挖空背景 `comfy/out/bgdebug_198.png`，与 v3 同帧对照 `bg_vs_v3_198.jpg`，**尚未查看**。
- 已停止：服务器队列清空并中断（GPU 空闲），本地 SSH 隧道与所有轮询进程已结束。AutoDL 实例本身仍开机计费，由用户决定是否关机。

## 2026-09-29 三路线对照试验（服务器本地跑，零平台费用）
镜头：T1 S07 0–1.5 s 主角近景（45 帧）；T2 S03 0–1.9 s 群战全景（57 帧）；T3 S04 3.43–5.87 s 旋身穿人群（73 帧）。
素材：`export/characters/` 四张图；切片 `trial/clips/`；脚本 `trial/run_*.py`（经 16006 隧道提交），对照 `trial/out/stack_*.mp4`、`compare_*.jpg`。

| 路线 | T1 近景 | T2 群战 | T3 旋身 | 单镜头耗时 |
| --- | --- | --- | --- | --- |
| Bernini rv2v（K08，960×480，4+4 步） | 身份换对、动作 1:1、背景换了 ✅ | 动作逐帧一致、主角换对；敌人/场景没换 | 敌人戴斗笠、场景换了、动作跟住；偏暗偏糊 | 6–12 min |
| Bernini + cfg_chain（V1.25 I4.5 TI4.0） | — | 主角更清晰；敌人/场景仍没换，略过曝 | — | 23 min |
| SCAIL-2 替换（P24，只追踪主角） | 动画模式：斗笠和原演员脸基本保留 ❌ | 主角换对（偏青）；拖影帧遮罩丢 | 主角不稳定（长发、浅色下摆） | 约 8–10 min |
| H3 打斗（U20 + 参考视频） | 未跑（参考需 ≥2 s） | 人物最清晰，但重新编排打斗 ❌ | 动作构图跟原片，但没换场景/敌人 | 15–18 min |

结论：动作 1:1 最稳的是 Bernini；它可靠地换「一个主体」，一次生成里多主体+场景替换时有时无。
下一步候选：首帧精修（Qwen-Edit 2511 多图编辑把主角/敌人/场景一次换对）→ Bernini 以精修首帧为参考做传播（vi2v 系统提示）；或两遍 Bernini（先主角、再敌人+场景）。
- 坑：UI 的 FastGroupsBypassSwitch 转 API 后缺另一路输入会报错，需去掉开关直连；ffmpeg 无 drawtext，对照图用 PIL 贴标签。

## 2026-09-29 S01 首帧精修 + Bernini 传播（v1，全段 8.3 s）
- 流水线 `s01/pipeline.py`（prepare / frames / videos / assemble），经 16006 隧道调服务器 ComfyUI；未用 Hypit。
- 切分：0.12 阈值切点合并 #1–#3 后共 13 个镜头 A–M；每镜头末帧重复补到 4n+1 帧，生成后截回。
- 首帧：Qwen-Image-Edit 2511（Y01 结构 + image2/3 参考，4 步）。教训：指令里「背景替换为图3」或给场景图会让模型重画成对称回廊全景、丢构图；
  改为「只换人、背景保持原建筑只调成雨夜」（`--local`）后构图稳。最终选用：A D F I J M = local，B E G H K L = v2，C = v1（`s01/chosen/`）。
- 视频：Bernini rv2v，参考图1 = 精修首帧 + 主角脸/刺客图，系统提示用 vi2v（content propagation），960×480，13 镜头共约 38 分钟。
- 成片 `s01/S01_remake.mp4`（249 帧）、对照 `s01/S01_compare.mp4`；桌面交付包 `本地生成测试/` 有副本。
- 已知：主角脸经 Qwen 精修后偏年轻精致，与参考图的硬朗脸不完全一致；镜头间地面色调略有差异（部分偏绿）。

## 2026-09-30 S02–S09 批量（进行中）与质量发现
- 切分：0.3 阈值切点（S02–S09 共 66 镜头，<3 帧碎片并入前一镜头），人工分类 hero/hench/both/hand/boss（`segs/plan.json`）。
  0.12 阈值误切太多（雨水闪光），0.3 会漏掉部分真切点 → 部分镜头内含切点，首帧传播只管到切点前。
- 首帧：全部用「只换人、背景保持原建筑调成雨夜」；66 张里 46 张可用，20 张（拖影/抽象画面）Qwen 编出站位合影 → 改走「原片+参考图」rv2v。
- 流水线 `segs/pipeline.py`（prepare/frames/videos/faceswap/assemble），`segs/chain.sh` 视频完成后自动换脸+拼全片。
- **发现：Bernini 在部分镜头上忽略参考、照抄原片**（S04 大半镜头几乎不变；S02-1/5/6、S03-2/6 主角斗笠保留）。
  排查：非文件名冲突（服务器上是精修帧）、非环境问题（重跑 S01-A 结果完全一致）、非场景提示词（换成 S01 描述无效）、
  把原视频第 0 帧替换为精修帧也无效。cfg_chain（V1.25 I4.5 TI4.0）能在开头换对，但数帧后斗笠又回来。
  结论：原片中醒目的斗笠/浅蓝袍，Bernini 单次编辑改不干净，是模型上限而非参数问题。
- ComfyUI 重启方法：`ssh … 'setsid nohup bash /root/zealman-app/start-comfyui.sh > /root/comfy-restart.log 2>&1 < /dev/null &'`
  （脚本自己会杀掉占 6006 的旧进程；脚本无执行权限需用 bash 调）。S01-M 换脸卡死在 Wan torch.compile，换脸已关掉编译。
