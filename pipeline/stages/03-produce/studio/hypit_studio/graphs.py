"""把 Studio 网页的表单拼成 ComfyUI API 任务（prompt）。

结构都照官方模板（在 ComfyUI 前端导出成 API 格式后对照着写）：
- H3：video_minimax_h3_{t2v,i2v,r2v,multiframe_reference,i2v_continuation}
- 加速：lightx2v 的 768p 版 Turbo LoRA（v1.1，8 步，训练用 video/audio shift 6/3、1344×768）
- 二采（第一遍完整出片 → 潜空间放大 ×1.5 → 低噪声精修）：参考 YZ 整合包 U08/U09/U17 的做法，
  放大模型是 LBH-123-AI/Minimax_h3_latent_Upscaler
- Qwen-Image 2.1：image_qwen_image_2_1_{t2i,image_edit}；提示词扩写的系统提示词存在 qwen_pe.json
- 白膜：sam3d_whitebox.json（由「SAM3D白膜-灰底」工作流导出）
"""
import copy
import json
import os
import random

HERE = os.path.dirname(__file__)

H3_UNET = {
    "fl2va": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    "ref2va": "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
}
H3_TURBO = {
    "fl2va": ("minimax_h3_fl2v_turbo_8step_v1.1_768p_comfyui_bf16.safetensors", 8),
    "ref2va": ("minimax_h3_ref2v_turbo_8step_v1.1_768p_comfyui_bf16.safetensors", 8),
}
TURBO_SHIFT = (6.0, 3.0)  # 768p 版 Turbo 训练时的 video / audio shift
# FastH3 Omni（hao-ai-lab FastVideo）：整模型蒸馏的参考生视频模型，8 步，shift 12/3，不叠加速 LoRA；只用于参考生 / 多参考
FAST_OMNI_UNET = "fasth3_omniref_8step_pruned_int8_convrot.safetensors"
FAST_OMNI = (8, 12.0, 3.0)
# 旧的 544p 版加速 LoRA 也不放进 LoRA 列表（叠在新的上面会糊）
TURBO_FILES = {f for f, _ in H3_TURBO.values()} | {
    "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
    "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",
}
H3_TEXT_ENCODER = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
H3_VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"  # int8 版解码会损失细节
H3_AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"
H3_UPSCALER = "minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors"
UPSCALE_BY = 1.5  # 二采放大倍数（每边）
REFINE_SIGMAS = "0.667, 0.462, 0.0"
RTX_SR_MAX_SIDE = 3840  # RTX 超分后长边上限（4K），防止二采 + 超分把内存撑爆  # 二采精修：Turbo 8 步网格（shift 6）的最后两步

QWEN_UNET = {
    "censored": "qwen_image_2.1_int8_convrot.safetensors",
    "uncensored": "qwen-image-2.1-UC-int8_convrot.safetensors",
}
QWEN_TEXT_ENCODER = "qwen3vl_8b_int8_convrot.safetensors"
QWEN_PE = {
    "t2i": "qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors",
    "edit": "qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors",
}
QWEN_VAE = "qwen_image_2.1_vae_bf16.safetensors"

ASPECTS = {
    "16:9": "16:9 (Widescreen)", "9:16": "9:16 (Portrait Widescreen)", "1:1": "1:1 (Square)",
    "4:3": "4:3 (Standard)", "3:4": "3:4 (Portrait Standard)", "3:2": "3:2 (Photo)",
    "2:3": "2:3 (Portrait Photo)", "21:9": "21:9 (Ultrawide)",
}
H3_MODES = ("t2v", "i2v", "r2v", "multiref", "continue")
IMAGE_MODES = ("t2i", "edit")


class Graph:
    def __init__(self):
        self.nodes = {}

    def add(self, class_type, **inputs):
        nid = str(len(self.nodes) + 1)
        self.nodes[nid] = {"class_type": class_type, "inputs": inputs}
        return nid


def resolution(aspect, megapixels, multiple=32):
    """和 ComfyUI 的 ResolutionSelector 一样的算法，返回 (宽, 高)。"""
    import math
    w, h = (float(x) for x in aspect.split(" ")[0].split(":"))
    scale = math.sqrt(megapixels * 1024 * 1024 / (w * h))
    return round(w * scale / multiple) * multiple, round(h * scale / multiple) * multiple


def h3_frames(seconds):
    """H3 帧数：24fps，向上取到 17k+5（与官方模板里的 ComfyMathExpression 相同）。"""
    f = max(5, round(float(seconds) * 24))
    return f + (5 - f % 17) % 17


def _num(v, lo, hi, default):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _seed(p):
    try:
        s = int(p.get("seed"))
        if s > 0:
            return s
    except (TypeError, ValueError):
        pass
    return random.randint(1, 2**48)


def _prompt(p):
    text = (p.get("prompt") or "").strip()
    if not text:
        raise ValueError("请填写提示词")
    return text


def _apply_loras(g, model, p, lora_choices):
    for item in p.get("loras") or []:
        name = item.get("name")
        if name not in lora_choices or name in TURBO_FILES:
            raise ValueError(f"LoRA 不存在：{name}")
        strength = _num(item.get("strength"), -2, 2, 1.0)
        if strength == 0:
            continue
        model = [g.add("LoraLoaderModelOnly", model=model, lora_name=name, strength_model=strength), 0]
    return model


def build_h3(p, lora_choices):
    mode = p.get("mode")
    if mode not in H3_MODES:
        raise ValueError("未知的视频生成方式")
    kind = "ref2va" if mode in ("r2v", "multiref") else "fl2va"
    prompt = _prompt(p)
    seconds = _num(p.get("seconds"), 1, 15, 5)
    frames = h3_frames(seconds)
    aspect = ASPECTS.get(p.get("aspect"), ASPECTS["16:9"])
    base_mp = _num(p.get("megapixels"), 0.2, 1.5, 0.9)
    turbo = bool(p.get("turbo", True))
    upscale = bool(p.get("upscale"))
    seed = _seed(p)

    omni = kind == "ref2va" and p.get("engine") == "fasth3_omni"
    if omni:
        turbo = True  # 本身就是 8 步蒸馏模型

    g = Graph()
    model = [g.add("UNETLoader", unet_name=FAST_OMNI_UNET if omni else H3_UNET[kind], weight_dtype="default"), 0]
    if turbo and not omni:
        model = [g.add("LoraLoaderModelOnly", model=model, lora_name=H3_TURBO[kind][0], strength_model=1.0), 0]
    model = _apply_loras(g, model, p, lora_choices)
    if omni:
        model = [g.add("MiniMaxH3SigmaShift", model=model, shift_video=FAST_OMNI[1], shift_audio=FAST_OMNI[2]), 0]
    elif turbo:
        model = [g.add("MiniMaxH3SigmaShift", model=model, shift_video=TURBO_SHIFT[0], shift_audio=TURBO_SHIFT[1]), 0]

    clip = [g.add("CLIPLoader", clip_name=H3_TEXT_ENCODER, type="minimax", device="default"), 0]
    vvae = [g.add("VAELoader", vae_name=H3_VIDEO_VAE), 0]
    avae = [g.add("VAELoader", vae_name=H3_AUDIO_VAE), 0]
    # 素材只加载一次；条件（首帧 / 参考 / 关键帧）按分辨率建，二采时在放大后的尺寸上再建一份
    if kind == "fl2va":
        if mode == "i2v":
            if not p.get("first_frame"):
                raise ValueError("图生视频需要首帧图")
            first = [g.add("LoadImage", image=p["first_frame"]), 0]
            last = [g.add("LoadImage", image=p["last_frame"]), 0] if p.get("last_frame") else None
        elif mode == "continue":
            if not p.get("source_video"):
                raise ValueError("续写需要一段要接着往下拍的视频")
            v = g.add("VHS_LoadVideo", video=p["source_video"], force_rate=0, custom_width=0, custom_height=0,
                      frame_load_cap=0, skip_first_frames=0, select_every_nth=1, format="None")
            first, last = [g.add("ImageFromBatch", image=[v, 0], batch_index=-1, length=1), 0], None
        else:
            first = last = None
    else:
        images, videos, audios = p.get("ref_images") or [], p.get("ref_videos") or [], p.get("ref_audios") or []
        keyframes = p.get("keyframes") or []
        if mode == "r2v" and not (images or videos):
            raise ValueError("参考生视频至少要一张参考图或一段参考视频")
        if mode == "multiref" and not keyframes:
            raise ValueError("多参考需要至少一张关键帧图")
        refs = {}
        for i, name in enumerate(images[:9]):
            refs[f"ref_images.ref_image_{i}"] = [g.add("LoadImage", image=name), 0]
        for i, name in enumerate(videos[:3]):
            v = g.add("VHS_LoadVideo", video=name, force_rate=24, custom_width=0, custom_height=0,
                      frame_load_cap=360, skip_first_frames=0, select_every_nth=1, format="None")
            refs[f"ref_videos.ref_video_{i}"] = [v, 0]
            if p.get("use_video_audio"):
                refs[f"ref_video_audios.ref_video_audio_{i}"] = [v, 2]
        for i, name in enumerate(audios[:3]):
            refs[f"ref_audios.ref_audio_{i}"] = [g.add("LoadAudio", audio=name), 0]
        guides = [(round(_num(kf.get("time"), 0, seconds, 0) * 24), [g.add("LoadImage", image=kf["image"]), 0])
                  for kf in keyframes[:8]]

    def conditioning(mp):
        """在 mp 百万像素的画布上建条件，返回 (positive, 空 latent, 宽高节点)。"""
        res = g.add("ResolutionSelector", aspect_ratio=aspect, megapixels=mp, multiple=32)
        size = dict(width=[res, 0], height=[res, 1], length=frames)
        if kind == "fl2va":
            def scaled(img):
                return [g.add("ImageScaleToTotalPixels", image=img, upscale_method="lanczos",
                              megapixels=mp, resolution_steps=32), 0]
            cond_in = dict(clip=clip, vae=vvae, prompt=prompt, **size)
            if first:
                cond_in["first_frame"] = scaled(first)
            if last:
                cond_in["last_frame"] = scaled(last)
            cond = g.add("MiniMaxH3ImageToVideo", **cond_in)
            return [cond, 0], [cond, 1], res
        cond = g.add("MiniMaxH3ReferenceToVideo", clip=clip, vae=vvae, audio_vae=avae, prompt=prompt,
                     ref_image_size="match", **size, **refs)
        positive = [cond, 0]
        # 多参考：把关键帧钉在指定帧上（官方 multiframe_reference 模板的 MiniMaxH3AddGuide 链）
        for frame_idx, img in guides:
            positive = [g.add("MiniMaxH3AddGuide", positive=positive, latent=[cond, 1], frame_idx=frame_idx,
                              vae=vvae, audio_vae=avae, image=img), 0]
        return positive, [cond, 1], res

    positive, latent, _ = conditioning(base_mp)
    noise = [g.add("RandomNoise", noise_seed=seed), 0]
    # 第一遍：完整出片（Turbo 用 euler 走蒸馏时的步数网格）
    sampler = [g.add("KSamplerSelect", sampler_name="euler" if turbo else "res_multistep"), 0]
    steps = FAST_OMNI[0] if omni else H3_TURBO[kind][1] if turbo else int(_num(p.get("steps"), 4, 50, 20))
    sched = g.add("BasicScheduler", model=model, scheduler="simple", steps=steps, denoise=1.0)
    final = g.add("SamplerCustomAdvanced", noise=noise, guider=[g.add("BasicGuider", model=model, conditioning=positive), 0],
                  sampler=sampler, sigmas=[sched, 0], latent_image=latent)
    if upscale:
        # 二采：潜空间放大到 ×1.5 的尺寸，在放大后的尺寸上重建条件，用 Turbo 网格的最后两步补细节（不改构图和动作）
        hi_pos, _, hi_res = conditioning(base_mp * UPSCALE_BY ** 2)
        sep = g.add("LTXVSeparateAVLatent", av_latent=[final, 0])
        up = g.add("MinimaxH3LatentUpscaler3D", latent=[sep, 0], model_name=H3_UPSCALER, mode="target dimensions",
                   **{"mode.width": [hi_res, 0], "mode.height": [hi_res, 1]}, align=32,
                   enable_temporal_chunking=True, force_unload=True, device="cuda", precision="fp16")
        cat = g.add("LTXVConcatAVLatent", video_latent=[up, 0], audio_latent=[sep, 1])
        sig2 = g.add("ManualSigmas", sigmas=REFINE_SIGMAS)
        final = g.add("SamplerCustomAdvanced", noise=noise,
                      guider=[g.add("BasicGuider", model=model, conditioning=hi_pos), 0],
                      sampler=sampler, sigmas=[sig2, 0], latent_image=[cat, 0])

    frames_img = [g.add("VAEDecode", samples=[final, 0], vae=vvae), 0]
    if p.get("rtx_sr"):
        # RTX 视频超分（NVIDIA VFX，ComfyUI_Nvidia_VFX_Nodes）：像素空间每边 ×2，长边不超过 4K
        w, _ = resolution(aspect, base_mp * (UPSCALE_BY ** 2 if upscale else 1))
        scale = round(min(2.0, RTX_SR_MAX_SIDE / max(w, 1)), 2)
        if scale > 1.0:
            frames_img = [g.add("RTXVideoSuperResolution", images=frames_img, resize_type="scale by multiplier",
                                **{"resize_type.scale": scale}, quality="ULTRA",
                                strength=1.0, image_encoding="8-bit RGB"), 0]
    audio = g.add("VAEDecodeAudio", samples=[final, 0], vae=avae)
    video = g.add("CreateVideo", images=frames_img, audio=[audio, 0], fps=24.0, bit_depth=8,
                  color_space="sRGB", codec="none")
    _save_video(g, video, f"studio/{mode}")
    return g.nodes, {"seed": seed, "frames": frames, "steps": steps}


def _save_video(g, video, prefix):
    """H.264 重新编码，CRF 16（默认的 auto 码率偏低，细节和暗部会糊）。"""
    g.add("SaveVideo", video=[video, 0], filename_prefix=prefix, format="mp4",
          **{"format.codec": "h264", "format.codec.encoding": "re-encode", "format.codec.encoding.crf": 16.0})


_PE = None


def build_image(p, lora_choices):
    global _PE
    mode = p.get("mode")
    if mode not in IMAGE_MODES:
        raise ValueError("未知的图片生成方式")
    if _PE is None:
        with open(os.path.join(HERE, "qwen_pe.json"), encoding="utf-8") as f:
            _PE = json.load(f)
    prompt = _prompt(p)
    seed = _seed(p)
    steps = int(_num(p.get("steps"), 4, 60, 25))
    variant = "uncensored" if p.get("uncensored") else "censored"
    images = (p.get("ref_images") or [])[:6]
    if mode == "edit" and not images:
        raise ValueError("图生图需要至少一张参考图")

    g = Graph()
    unet = [g.add("UNETLoader", unet_name=QWEN_UNET[variant], weight_dtype="default"), 0]
    model = _apply_loras(g, unet, p, lora_choices)
    model = [g.add("QwenImage21Cache", model=model, device="auto", dtype="default"), 0]
    clip = [g.add("CLIPLoader", clip_name=QWEN_TEXT_ENCODER, type="qwen_image", device="default"), 0]
    vae = [g.add("VAELoader", vae_name=QWEN_VAE), 0]
    loaded = [[g.add("LoadImage", image=name), 0] for name in images]

    text = prompt
    if p.get("enhance"):  # 提示词扩写：官方模板里的 Qwen3.5-9B PE 模型 + 系统提示词
        pe_clip = [g.add("CLIPLoader", clip_name=QWEN_PE[mode],
                         type="stable_diffusion" if mode == "t2i" else "qwen_image", device="default"), 0]
        sysp = [g.add("PrimitiveStringMultiline", value=_PE["t2i_system" if mode == "t2i" else "i2i_system"]), 0]
        gen_in = dict(clip=pe_clip, prompt=prompt, max_length=4096, system_prompt=sysp, thinking=False,
                      use_default_template=True, mtp="auto", **{"sampling_mode.seed": seed},
                      **_PE["t2i_sampling" if mode == "t2i" else "i2i_sampling"])
        if mode == "edit":
            batch = g.add("BatchImagesNode", **{f"images.image{i}": im for i, im in enumerate(loaded)})
            gen_in["image"] = [batch, 0]
        text = [g.add("TextGenerate", **gen_in), 0]

    if mode == "t2i":
        aspect = ASPECTS.get(p.get("aspect"), ASPECTS["1:1"])
        res = g.add("ResolutionSelector", aspect_ratio=aspect, megapixels=_num(p.get("megapixels"), 0.3, 4.0, 1.0),
                    multiple=8)
        enc = g.add("TextEncodeQwenImage21", clip=clip, prompt=text, negative_prompt=p.get("negative") or "",
                    resolution=1024)
        latent = [g.add("EmptyLatentImage", width=[res, 0], height=[res, 1], batch_size=1), 0]
    else:
        enc_in = dict(clip=clip, vae=vae, prompt=text, negative_prompt=p.get("negative") or "", resolution=0)
        for i, im in enumerate(loaded):
            enc_in[f"images.image_{i + 1}"] = im
        enc = g.add("TextEncodeQwenImage21", **enc_in)
        latent = [enc, 2]  # 跟随第一张参考图的尺寸
    ks = g.add("KSampler", model=model, positive=[enc, 0], negative=[enc, 1], latent_image=latent, seed=seed,
               steps=steps, cfg=1.0, sampler_name="euler", scheduler="simple", denoise=1.0)
    img = g.add("VAEDecode", samples=[ks, 0], vae=vae)
    g.add("SaveImageAdvanced", images=[img, 0], filename_prefix=f"studio/{mode}_{variant}", format="png",
          **{"format.bit_depth": "8-bit", "format.input_color_space": "sRGB"})
    return g.nodes, {"seed": seed, "steps": steps}


_WB = None


def build_whitebox(p, lora_choices=None):
    global _WB
    if _WB is None:
        with open(os.path.join(HERE, "sam3d_whitebox.json"), encoding="utf-8") as f:
            _WB = json.load(f)
    if not p.get("source_video"):
        raise ValueError("请提供要转白膜的视频")
    g = copy.deepcopy(_WB)
    g["85"]["inputs"]["file"] = p["source_video"]
    g["125"]["inputs"]["start_time"] = _num(p.get("start"), 0, 3600, 0)
    g["125"]["inputs"]["duration"] = _num(p.get("seconds"), 0, 60, 10)
    # 一直追踪所有人（max_objects=1 只取最先检测到的人，常锁到路人身上）；「只有一个人」交给去重节点只留主角
    g["18"]["inputs"]["max_objects"] = 0
    g["148"]["inputs"]["main_only"] = bool(p.get("single"))
    if p.get("single"):
        g["127"]["inputs"]["pose_data"] = ["148", 0]  # GLB 也只导出主角
    g["127"]["inputs"]["fps"] = ["86", 2]  # GLB 动画帧率跟源视频走（原来固定 24，30fps 素材会变慢）
    for nid, prefix in (("135", "studio/whitebox"), ("147", "studio/whitebox_check")):
        g[nid] = {"class_type": "SaveVideo", "inputs": {"video": g[nid]["inputs"]["video"], "filename_prefix": prefix}}
        g[nid]["inputs"].update({"format": "mp4", "format.codec": "h264", "format.codec.encoding": "re-encode",
                                 "format.codec.encoding.crf": 16.0})
    g["143"]["inputs"]["filename_prefix"] = "studio/whitebox"
    return g, {}


def build(p, lora_choices):
    mode = p.get("mode")
    if mode in H3_MODES:
        return build_h3(p, lora_choices)
    if mode in IMAGE_MODES:
        return build_image(p, lora_choices)
    if mode == "whitebox":
        return build_whitebox(p, lora_choices)
    raise ValueError("未知的生成方式")
