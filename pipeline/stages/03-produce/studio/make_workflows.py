"""把 graphs.py 拼出来的 H3 任务做成 ComfyUI 侧边栏工作流（H3/ 和 H3-研究用/ 各 6 个），和 Studio 网页用同一套参数。

用法：python3 make_workflows.py http://<5090>:8188
  1. 本脚本生成规格（API 格式任务 + 节点标题 + 要绕过的 LoRA + 说明），上传到 ComfyUI 的 user/default/studio_wfspec.json；
  2. 在浏览器打开 ComfyUI 页面，控制台执行本文件末尾 LOADER_JS 里的函数：逐个 loadApiJson → 改标题 / 绕过 / 加说明 → 存成工作流。
"""
import json
import sys
import urllib.request

sys.path.insert(0, __file__.rsplit("/", 1)[0] + "/hypit_studio")
import graphs  # noqa: E402

ACTION = ["minimax\\H3_Combat_V2.safetensors", "minimax\\Motion_Repair_V2.safetensors", "minimax\\Motion_Repair.safetensors",
          "minimax\\wushu_h3_v8_5000step.safetensors", "minimax\\wushu_h3_r2v_v7_2000.safetensors"]
COMMON_NOTE = """- **清晰度**：「画幅与清晰度」里 megapixels 默认 0.9（≈1280×720）；越大越清楚也越慢，最大建议 1.5。
- **时长**：H3 节点的 length，24 帧 = 1 秒，取 17k+5（73≈3 秒，124≈5 秒，最长约 15 秒）。
- **加速**：已接 768p 版加速 LoRA（lightx2v Turbo v1.1，8 步，shift 6/3）。不想加速：把它和 SigmaShift 设为绕过，「步数」改成 20。
- **画质要点**（2026-10-26 对照 YZ 整合包优化）：768p 加速 LoRA、fp16 视频 VAE、H.264 CRF 16 输出；旧的 544p 加速 LoRA 叠在上面会糊，别再接。
"""
UPSCALE_NOTE = "- **二采**：先按清晰度完整出片，再潜空间每边放大 1.5 倍（按放大后的尺寸重建条件），用 Turbo 网格最后两步（0.667→0.462→0）精修补细节。0.9 → 约 1952×1088。\n"
LORA_NOTE = "\n**所有 LoRA 节点默认是「绕过」（紫色）**：要用哪个，选中后按 Ctrl+B 点亮，再调 strength_model（0.6–1.0 常用）。可以同时点亮多个叠加。\n- 输出在 ComfyUI/output/studio/ 下。\n"

FLOWS = [
    ("H3 文生视频", dict(mode="t2v", prompt="A swordsman in a dark blue robe walks through a rainy night street lined with red lanterns, slow push-in, cinematic."),
     "只写提示词出视频。可以写对白（用引号）、音效、镜头运动。"),
    ("H3 图生视频（首帧·可加尾帧）", dict(mode="i2v", prompt="The swordsman slowly turns toward the camera as rain falls, cinematic lighting.", first_frame="hero.jpg"),
     "「首帧」LoadImage 换成你的图；要首尾帧过渡，再加一个 LoadImage 接到 H3 节点的 last_frame。"),
    ("H3 参考生视频（图·视频·音频）", dict(mode="r2v", prompt="<Picture 1> is the swordsman. He spins and strikes with his sword, following the motion and camera of <Video 1>.",
                                    ref_images=["hero.jpg"], ref_videos=["spin.mp4"]),
     "参考图（最多 9 张）→ 提示词里用 <Picture 1>、<Picture 2>；参考视频（最多 3 段，2–15 秒）→ <Video 1>；参考音频 → <Audio 1>。编号按接线顺序。"),
    ("H3 参考生视频·二采高清", dict(mode="r2v", upscale=True, prompt="<Picture 1> is the swordsman. He spins and strikes with his sword, following the motion and camera of <Video 1>.",
                                 ref_images=["hero.jpg"], ref_videos=["spin.mp4"]),
     "同「参考生视频」，多一道二采高清。"),
    ("H3 多参考（关键帧钉时间点）", dict(mode="multiref", prompt="<Picture 1> is the swordsman. He walks through the rainy courtyard toward the camera.",
                                   ref_images=["hero.jpg"], keyframes=[{"image": "scene.jpg", "time": 0}]),
     "参考图定人物和风格；每个 MiniMaxH3AddGuide 把一张关键帧钉在 frame_idx（= 秒数 × 24）上，可以串多个。"),
    ("H3 续写（接着上一段视频往下拍）", dict(mode="continue", prompt="The swordsman lands, sheathes his sword and looks around.", source_video="spin.mp4"),
     "LoadVideo 换成要接着拍的视频，会取它的最后一帧当首帧往下拍。"),
]


def spec(research_loras):
    out = []
    for folder, extra in (("H3", []), ("H3-研究用", research_loras)):
        names = ACTION + extra
        for title, p, usage in FLOWS:
            p = dict(p, seconds=3, aspect="16:9", megapixels=0.9, turbo=True, seed=7,
                     loras=[{"name": n, "strength": 1.0} for n in names])
            api, _ = graphs.build_h3(p, set(names))
            titles, bypass = {}, []
            for nid, n in api.items():
                c, i = n["class_type"], n["inputs"]
                if c == "LoraLoaderModelOnly":
                    if i["lora_name"] in names:
                        titles[nid] = "LoRA · " + i["lora_name"].split("\\")[-1].rsplit(".", 1)[0]
                        bypass.append(nid)
                    else:
                        titles[nid] = "加速 LoRA（768p Turbo，8 步）"
                elif c == "UNETLoader":
                    titles[nid] = "主模型"
                elif c == "ResolutionSelector":
                    titles[nid] = "画幅与清晰度（megapixels 越大越清晰越慢）"
                elif c in ("MiniMaxH3ImageToVideo", "MiniMaxH3ReferenceToVideo"):
                    titles[nid] = "H3（提示词写在这里）"
                elif c == "BasicScheduler":
                    titles[nid] = "步数"
                elif c == "RandomNoise":
                    titles[nid] = "随机种子"
                elif c == "MinimaxH3LatentUpscaler3D":
                    titles[nid] = "二采：潜空间放大 ×1.5"
                elif c == "ManualSigmas":
                    titles[nid] = "二采：精修噪声"
            lora_kind = "动作类（打斗 Combat、动作修复 Motion_Repair V1/V2、武术 wushu）" + (
                f"和研究用（成人内容）全部 {len(extra)} 个" if extra else "")
            note = (f"# {title}{'（研究用）' if extra else ''}\n\n- **用法**：{usage}\n" + COMMON_NOTE
                    + (UPSCALE_NOTE if p.get("upscale") else "") + f"- **LoRA**：已接好{lora_kind}。\n" + LORA_NOTE)
            out.append({"path": f"{folder}/{title}.json", "api": api, "titles": titles, "bypass": bypass, "note": note})
    return out


LOADER_JS = r"""
async () => {
  const app = window.comfyAPI.app.app
  const specs = await (await fetch('/api/userdata/studio_wfspec.json')).json()
  const done = []
  for (const s of specs) {
    await app.loadApiJson(s.api, s.path.split('/').pop())
    for (const n of app.graph._nodes) {
      const k = String(n.id)
      if (s.titles[k]) n.title = s.titles[k]
      if (s.bypass.includes(k)) n.mode = 4
    }
    app.graph.arrange()
    const note = LiteGraph.createNode('MarkdownNote')
    note.title = '说明'
    note.widgets[0].value = s.note
    note.size = [760, 420]
    note.pos = [60, -480]
    app.graph.add(note)
    const r = await fetch('/api/userdata/workflows%2F' + encodeURIComponent(s.path) + '?overwrite=true',
      { method: 'POST', body: JSON.stringify(app.graph.serialize()) })
    done.push(s.path + ' ' + r.status)
  }
  return done
}
"""

if __name__ == "__main__":
    host = sys.argv[1].rstrip("/")
    info = json.load(urllib.request.urlopen(host + "/object_info/LoraLoaderModelOnly"))
    names = info["LoraLoaderModelOnly"]["input"]["required"]["lora_name"][0]
    research = sorted(n for n in names if n.startswith("research_nsfw"))
    data = json.dumps(spec(research), ensure_ascii=False).encode()
    req = urllib.request.Request(host + "/api/userdata/studio_wfspec.json?overwrite=true", data, method="POST")
    print(urllib.request.urlopen(req).status, len(data), "bytes; now run LOADER_JS in the ComfyUI page")
