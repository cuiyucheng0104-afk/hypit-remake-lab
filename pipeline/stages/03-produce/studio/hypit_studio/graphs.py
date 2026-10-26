"""把 Studio 网页的表单拼成 ComfyUI API 任务（prompt）。

结构都照官方模板（在 ComfyUI 前端导出成 API 格式后对照着写）：
- H3：video_minimax_h3_{t2v,i2v,r2v,multiframe_reference,i2v_continuation}
- 二采（低分辨率先出 → 潜空间放大 → 低噪声精修）：LBH-123-AI/Minimax_h3_latent_Upscaler 的 r2v 示例
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
    "fl2va": ("minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors", 8),
    "ref2va": ("minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors", 4),
}
TURBO_FILES = {f for f, _ in H3_TURBO.values()}
H3_TEXT_ENCODER = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
H3_VIDEO_VAE = "minimax_h3_video_vae_int8_convrot.safetensors"
H3_AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"
H3_UPSCALER = "minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors"
REFINE_SIGMAS = "0.9035, 0.6316, 0.3158, 0.0000"  # 二采第二遍，取自 LBH 的 r2v 示例

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
    quality_mp = _num(p.get("megapixels"), 0.2, 2.0, 0.4)
    turbo = bool(p.get("turbo", True))
    upscale = bool(p.get("upscale"))
    seed = _seed(p)

    g = Graph()
    model = [g.add("UNETLoader", unet_name=H3_UNET[kind], weight_dtype="default"), 0]
    if turbo:
        model = [g.add("LoraLoaderModelOnly", model=model, lora_name=H3_TURBO[kind][0], strength_model=1.0), 0]
    model = _apply_loras(g, model, p, lora_choices)
    if upscale:
        model = [g.add("MiniMaxH3SigmaShift", model=model, shift_video=12.0, shift_audio=3.0), 0]

    clip = [g.add("CLIPLoader", clip_name=H3_TEXT_ENCODER, type="minimax", device="default"), 0]
    vvae = [g.add("VAELoader", vae_name=H3_VIDEO_VAE), 0]
    avae = [g.add("VAELoader", vae_name=H3_AUDIO_VAE), 0]
    res = g.add("ResolutionSelector", aspect_ratio=aspect, megapixels=0.25 if upscale else quality_mp, multiple=32)
    size = dict(width=[res, 0], height=[res, 1], length=frames)

    def scaled_image(name):
        img = g.add("LoadImage", image=name)
        return [g.add("ImageScaleToTotalPixels", image=[img, 0], upscale_method="lanczos",
                      megapixels=0.9, resolution_steps=32), 0]

    if kind == "fl2va":
        cond_in = dict(clip=clip, vae=vvae, prompt=prompt, **size)
        if mode == "i2v":
            if not p.get("first_frame"):
                raise ValueError("图生视频需要首帧图")
            cond_in["first_frame"] = scaled_image(p["first_frame"])
            if p.get("last_frame"):
                cond_in["last_frame"] = scaled_image(p["last_frame"])
        elif mode == "continue":
            if not p.get("source_video"):
                raise ValueError("续写需要一段要接着往下拍的视频")
            v = g.add("VHS_LoadVideo", video=p["source_video"], force_rate=0, custom_width=0, custom_height=0,
                      frame_load_cap=0, skip_first_frames=0, select_every_nth=1, format="None")
            last = g.add("ImageFromBatch", image=[v, 0], batch_index=-1, length=1)
            cond_in["first_frame"] = [g.add("ImageScaleToTotalPixels", image=[last, 0], upscale_method="lanczos",
                                            megapixels=0.9, resolution_steps=32), 0]
        cond = g.add("MiniMaxH3ImageToVideo", **cond_in)
        positive = [cond, 0]
    else:
        cond_in = dict(clip=clip, vae=vvae, audio_vae=avae, prompt=prompt, ref_image_size="match", **size)
        images, videos, audios = p.get("ref_images") or [], p.get("ref_videos") or [], p.get("ref_audios") or []
        keyframes = p.get("keyframes") or []
        if mode == "r2v" and not (images or videos):
            raise ValueError("参考生视频至少要一张参考图或一段参考视频")
        if mode == "multiref" and not keyframes:
            raise ValueError("多参考需要至少一张关键帧图")
        for i, name in enumerate(images[:9]):
            cond_in[f"ref_images.ref_image_{i}"] = [g.add("LoadImage", image=name), 0]
        for i, name in enumerate(videos[:3]):
            v = g.add("VHS_LoadVideo", video=name, force_rate=24, custom_width=0, custom_height=0,
                      frame_load_cap=360, skip_first_frames=0, select_every_nth=1, format="None")
            cond_in[f"ref_videos.ref_video_{i}"] = [v, 0]
            if p.get("use_video_audio"):
                cond_in[f"ref_video_audios.ref_video_audio_{i}"] = [v, 2]
        for i, name in enumerate(audios[:3]):
            cond_in[f"ref_audios.ref_audio_{i}"] = [g.add("LoadAudio", audio=name), 0]
        cond = g.add("MiniMaxH3ReferenceToVideo", **cond_in)
        positive = [cond, 0]
        # 多参考：把关键帧钉在指定秒数上（官方 multiframe_reference 模板的 MiniMaxH3AddGuide 链）
        for kf in keyframes[:8]:
            t = _num(kf.get("time"), 0, seconds, 0)
            positive = [g.add("MiniMaxH3AddGuide", positive=positive, latent=[cond, 1], frame_idx=round(t * 24),
                              vae=vvae, audio_vae=avae, image=[g.add("LoadImage", image=kf["image"]), 0]), 0]

    noise = [g.add("RandomNoise", noise_seed=seed), 0]
    guider = [g.add("BasicGuider", model=model, conditioning=positive), 0]
    if upscale:
        sampler = [g.add("KSamplerSelect", sampler_name="euler"), 0]
        steps = H3_TURBO[kind][1] * 2 if turbo else 20
        sched = g.add("BasicScheduler", model=model, scheduler="simple", steps=steps, denoise=1.0)
        split = g.add("SplitSigmas", sigmas=[sched, 0], step=steps // 2)
        pass1 = g.add("SamplerCustomAdvanced", noise=noise, guider=guider, sampler=sampler,
                      sigmas=[split, 0], latent_image=[cond, 1])
        sep = g.add("LTXVSeparateAVLatent", av_latent=[pass1, 1])
        up = g.add("MinimaxH3LatentUpscaler3D", latent=[sep, 0], model_name=H3_UPSCALER, mode="megapixels",
                   **{"mode.megapixels": quality_mp}, align=32, enable_temporal_chunking=True,
                   force_unload=True, device="cuda", precision="fp16")
        cat = g.add("LTXVConcatAVLatent", video_latent=[up, 0], audio_latent=[sep, 1])
        sig2 = g.add("ManualSigmas", sigmas=REFINE_SIGMAS)
        final = g.add("SamplerCustomAdvanced", noise=noise, guider=guider, sampler=sampler,
                      sigmas=[sig2, 0], latent_image=[cat, 0])
    else:
        sampler = [g.add("KSamplerSelect", sampler_name="res_multistep"), 0]
        steps = H3_TURBO[kind][1] if turbo else int(_num(p.get("steps"), 4, 50, 20))
        sched = g.add("BasicScheduler", model=model, scheduler="simple", steps=steps, denoise=1.0)
        final = g.add("SamplerCustomAdvanced", noise=noise, guider=guider, sampler=sampler,
                      sigmas=[sched, 0], latent_image=[cond, 1])

    frames_img = g.add("VAEDecode", samples=[final, 0], vae=vvae)
    audio = g.add("VAEDecodeAudio", samples=[final, 0], vae=avae)
    video = g.add("CreateVideo", images=[frames_img, 0], audio=[audio, 0], fps=24.0, bit_depth=8,
                  color_space="sRGB", codec="none")
    g.add("SaveVideo", video=[video, 0], filename_prefix=f"studio/{mode}", format="auto",
          **{"format.codec": "auto"}, codec="auto")
    return g.nodes, {"seed": seed, "frames": frames, "steps": steps}


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
    g["18"]["inputs"]["max_objects"] = 1 if p.get("single") else 0
    g["135"]["inputs"]["filename_prefix"] = "studio/whitebox"
    g["147"]["inputs"]["filename_prefix"] = "studio/whitebox_check"
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
