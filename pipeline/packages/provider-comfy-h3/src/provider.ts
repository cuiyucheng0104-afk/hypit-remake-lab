import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import { canonicalize, defineEndpointPackage, wakeAfter } from "@hypit/hypit/endpoint-kit";
import type { AsyncEndpoint, EndpointRequest } from "@hypit/hypit/endpoint-kit";
import { generationTypes, sealGeneratedVideoSet } from "@hypit/hypit/generation";
import type { GenerationMediaValue, GenerationPortValue, GenerationRequest } from "@hypit/hypit/generation";

export const providerModule = { name: "@local/provider-comfy-h3", version: "1" } as const;
export const capability = { module: { name: "@hypit/minimax-h3", version: "1" }, name: "minimax-h3" } as const;

// 只出 768P：短边 768，按 32 对齐。2K 与超分交给服务器上单独的超分工作流。
const SHORT_SIDE = 768;
// U17 先在较低分辨率采样，再把潜空间放大 1.5 倍二次采样；基础尺寸 = 768 / 1.5。
const U17_LATENT_SCALE = 1.5;
// U17 只有一个参考视频槽（Hypit 的 H3 最多允许 3 段）。
const MAX_REFERENCE_VIDEOS = 1;
const FPS = 24;
const run = promisify(execFile);

/**
 * H3 的帧数必须是 17k+5，请求 4 秒会得到 107 帧（4.458 秒）。截掉尾部的填充帧，
 * 让交回 Hypit 的成片时长等于请求时长。音视频一起截，重新编码保证截点准确。
 */
async function trimToDuration(bytes: Uint8Array, seconds: number) {
  const dir = await mkdtemp(join(tmpdir(), "comfy-h3-"));
  try {
    const input = join(dir, "in.mp4"), output = join(dir, "out.mp4");
    await writeFile(input, bytes);
    await run("ffmpeg", ["-v", "error", "-y", "-i", input, "-frames:v", String(Math.round(seconds * FPS)), "-t", String(seconds),
      "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p",
      "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output]);
    return new Uint8Array(await readFile(output));
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

const RATIOS: Readonly<Record<string, readonly [number, number]>> = {
  "21:9": [21, 9], "16:9": [16, 9], "4:3": [4, 3], "1:1": [1, 1], "3:4": [3, 4], "9:16": [9, 16],
};

type Prompt = Record<string, { class_type: string; inputs: Record<string, unknown> }>;
type Mode = "text" | "frame" | "reference";
const TEMPLATE_FILES: Readonly<Record<Mode, string>> = {
  text: "API-U03-minimax_h3_light2v-文生视频加速版API-V2.json",
  frame: "API-U02-minimax_h3_图生视频基础版-V2.json",
  reference: "API-U17-9图1视频3音频V1-api.json",
};
// 每个模板里最终保存成片的节点。
const SAVE_NODE: Readonly<Record<Mode, string>> = { text: "92", frame: "92", reference: "180" };

function loadTemplate(mode: Mode): Prompt {
  const file = new URL(`../templates/${TEMPLATE_FILES[mode]}`, import.meta.url);
  const card = JSON.parse(readFileSync(file, "utf8")) as { workflow_template: Record<string, unknown> };
  const prompt: Prompt = {};
  // 面板卡片里除节点外还带 `_api_config` 等元数据，只保留真正的节点。
  for (const [id, node] of Object.entries(card.workflow_template)) {
    if (node && typeof node === "object" && "class_type" in node) prompt[id] = structuredClone(node) as Prompt[string];
  }
  return prompt;
}

function node(prompt: Prompt, id: string) {
  const found = prompt[id];
  if (!found) throw new Error(`ComfyUI template is missing node ${id}`);
  return found;
}

function remove(prompt: Prompt, ...ids: string[]) {
  for (const id of ids) delete prompt[id];
}

/** 删除节点后，确认没有输入还连着已删除的节点。 */
function assertLinks(prompt: Prompt) {
  for (const [id, entry] of Object.entries(prompt)) {
    for (const [name, value] of Object.entries(entry.inputs)) {
      if (Array.isArray(value) && value.length === 2 && typeof value[0] === "string" && !(value[0] in prompt)) {
        throw new Error(`ComfyUI template node ${id}.${name} still links removed node ${value[0]}`);
      }
    }
  }
}

function align32(value: number) {
  return Math.max(32, Math.round(value / 32) * 32);
}

/** 以短边为基准，按宽高比算出对齐到 32 的尺寸。 */
function sizeFor(width: number, height: number, shortSide: number) {
  const scale = shortSide / Math.min(width, height);
  return { width: align32(width * scale), height: align32(height * scale) };
}

function ratioSize(ratio: string | undefined, shortSide: number) {
  const [w, h] = RATIOS[ratio ?? "16:9"] ?? RATIOS["16:9"]!;
  return sizeFor(w, h, shortSide);
}

/** 读取 PNG / JPEG / WebP 的像素尺寸，用于首尾帧模式保持原图宽高比。 */
function imageSize(bytes: Uint8Array): { width: number; height: number } {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (bytes[0] === 0x89 && bytes[1] === 0x50) return { width: view.getUint32(16), height: view.getUint32(20) };
  if (bytes[0] === 0xff && bytes[1] === 0xd8) {
    let offset = 2;
    while (offset + 9 < bytes.length) {
      if (bytes[offset] !== 0xff) { offset += 1; continue; }
      const marker = bytes[offset + 1]!;
      const length = view.getUint16(offset + 2);
      if (marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)) {
        return { height: view.getUint16(offset + 5), width: view.getUint16(offset + 7) };
      }
      offset += 2 + length;
    }
  }
  if (String.fromCharCode(...bytes.subarray(8, 12)) === "WEBP") {
    const chunk = String.fromCharCode(...bytes.subarray(12, 16));
    if (chunk === "VP8X") return { width: 1 + (view.getUint32(24, true) & 0xffffff), height: 1 + (view.getUint32(27, true) & 0xffffff) };
    if (chunk === "VP8L") {
      const bits = view.getUint32(21, true);
      return { width: 1 + (bits & 0x3fff), height: 1 + ((bits >> 14) & 0x3fff) };
    }
    if (chunk === "VP8 ") return { width: view.getUint16(26, true) & 0x3fff, height: view.getUint16(28, true) & 0x3fff };
  }
  throw new Error("首尾帧只支持 PNG、JPEG 或 WebP 图片");
}

function ports(request: GenerationRequest) {
  const p = request.ports;
  const scalar = (name: string) => p[name]?.[0] as string | number | undefined;
  const media = (name: string) => (p[name] ?? []) as readonly GenerationMediaValue[];
  return {
    prompt: String(scalar("prompt") ?? ""),
    duration: Number(scalar("duration")),
    resolution: scalar("resolution") as string | undefined,
    aspectRatio: scalar("aspectRatio") as string | undefined,
    images: media("referenceImage"), videos: media("referenceVideo"), audios: media("referenceAudio"),
    first: media("firstFrame")[0], last: media("lastFrame")[0],
  };
}

function modeFor(request: GenerationRequest): Mode {
  const r = ports(request);
  if (r.first || r.last) return "frame";
  if (r.images.length + r.videos.length + r.audios.length > 0) return "reference";
  return "text";
}

function countPort(request: EndpointRequest, name: string) {
  const present = ((request.constraints as unknown as GenerationRequest).ports[name] ?? []).length;
  const pending = (request.pendingInputs ?? []).filter((item) => item.input === name).length;
  return present + pending;
}

function serviceSupport(request: EndpointRequest) {
  const authored = request.constraints as unknown as GenerationRequest;
  const resolution = authored.ports.resolution?.[0] as GenerationPortValue | undefined;
  if (resolution !== undefined && String(resolution) !== "768P") {
    return { status: "unsupported" as const, reason: `这台 ComfyUI 只出 768P，不出 ${String(resolution)}；需要更高清请另接超分工作流` };
  }
  const videos = countPort(request, "referenceVideo");
  if (videos > MAX_REFERENCE_VIDEOS) {
    return { status: "unsupported" as const, reason: `U17 工作流只有 ${MAX_REFERENCE_VIDEOS} 个参考视频槽，请求里有 ${videos} 段` };
  }
  return { status: "supported" as const };
}

const EXTENSIONS: Readonly<Record<string, string>> = {
  "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp",
  "video/mp4": "mp4", "video/quicktime": "mov", "video/webm": "webm",
  "audio/mpeg": "mp3", "audio/wav": "wav", "audio/x-wav": "wav", "audio/mp4": "m4a", "audio/aac": "aac",
};

export function createComfyH3Provider(options: {
  instance: string; pool: string; baseUrl: string; pollIntervalMs?: number; fetch?: typeof globalThis.fetch;
}) {
  const base = new URL(options.baseUrl).href.replace(/\/$/u, "");
  const url = new URL(base);
  if (url.protocol !== "http:" || !["127.0.0.1", "localhost"].includes(url.hostname)) {
    // 面板与 ComfyUI 都没有鉴权，只允许经本机 SSH 隧道访问。
    throw new Error("ComfyUI H3 baseUrl 必须是本机回环地址（经 SSH 隧道），例如 http://127.0.0.1:16006");
  }
  const fetcher = options.fetch ?? globalThis.fetch;
  const interval = options.pollIntervalMs ?? 5_000;

  async function json(path: string, init: RequestInit = {}) {
    const response = await fetcher(`${base}${path}`, { ...init, signal: AbortSignal.timeout(120_000) });
    const body = await response.text();
    if (!response.ok) throw new Error(`ComfyUI ${init.method ?? "GET"} ${path} 返回 HTTP ${response.status}: ${body.slice(0, 600)}`);
    return JSON.parse(body) as Record<string, unknown>;
  }

  async function upload(bytes: Uint8Array, mediaType: string, resource: string) {
    const extension = EXTENSIONS[mediaType] ?? mediaType.split("/")[1] ?? "bin";
    const form = new FormData();
    form.append("image", new Blob([new Uint8Array(bytes)], { type: mediaType }), `${resource}.${extension}`);
    form.append("type", "input");
    form.append("subfolder", "hypit");
    form.append("overwrite", "true");
    const result = await json("/upload/image", { method: "POST", body: form });
    const name = String(result.name), subfolder = String(result.subfolder ?? "");
    return subfolder ? `${subfolder}/${name}` : name;
  }

  async function buildPrompt(request: GenerationRequest, bytesOf: (media: GenerationMediaValue) => Promise<Uint8Array>) {
    const r = ports(request);
    const mode = modeFor(request);
    const prompt = loadTemplate(mode);
    const seed = Math.floor(Math.random() * 2 ** 32);
    const put = async (media: GenerationMediaValue) =>
      upload(await bytesOf(media), media.artifact.mediaType, media.artifact.resource);

    if (mode === "text") {
      const size = ratioSize(r.aspectRatio, SHORT_SIDE);
      node(prompt, "139").inputs.prompt = r.prompt;
      node(prompt, "141").inputs.value = r.duration;
      Object.assign(node(prompt, "120").inputs, { 自定义宽: size.width, 自定义高: size.height });
      node(prompt, "137").inputs.noise_seed = seed;
    } else if (mode === "frame") {
      const reference = (r.first ?? r.last)!;
      const dims = imageSize(await bytesOf(reference));
      const size = sizeFor(dims.width, dims.height, SHORT_SIDE);
      node(prompt, "139").inputs.prompt = r.prompt;
      node(prompt, "141").inputs.value = r.duration;
      Object.assign(node(prompt, "122").inputs, { 自定义宽: size.width, 自定义高: size.height });
      node(prompt, "137").inputs.noise_seed = seed;
      const i2v = node(prompt, "139").inputs;
      if (r.first) node(prompt, "114").inputs.image = await put(r.first);
      else { delete i2v.first_frame; remove(prompt, "114"); }
      if (r.last) node(prompt, "144").inputs.image = await put(r.last);
      else { delete i2v.last_frame; remove(prompt, "144"); }
    } else {
      const size = ratioSize(r.aspectRatio, SHORT_SIDE / U17_LATENT_SCALE);
      node(prompt, "250").inputs.value = r.prompt;
      node(prompt, "132").inputs.value = r.duration;
      node(prompt, "182").inputs.value = U17_LATENT_SCALE;
      node(prompt, "129").inputs.noise_seed = seed;
      const ref = node(prompt, "275").inputs;
      Object.assign(ref, { width: size.width, height: size.height });
      // ref_image_i 对应的 LoadImage 节点。
      const imageNodes = ["248", "249", "247", "246", "279", "280", "281", "282", "283"];
      for (const [i, id] of imageNodes.entries()) {
        const media = r.images[i];
        if (media) node(prompt, id).inputs.image = await put(media);
        else { delete ref[`ref_images.ref_image_${i}`]; remove(prompt, id); }
      }
      const video = r.videos[0];
      if (video) node(prompt, "256").inputs.video = await put(video);
      else { delete ref["ref_videos.ref_video_0"]; remove(prompt, "256", "263", "262", "264"); }
      // ref_audio_i ← TrimAudioDuration ← LoadAudio
      const audioNodes: readonly (readonly [string, string])[] = [["267", "259"], ["265", "260"], ["266", "261"]];
      for (const [i, [trim, load]] of audioNodes.entries()) {
        const media = r.audios[i];
        if (media) node(prompt, load).inputs.audio = await put(media);
        else { delete ref[`ref_audios.ref_audio_${i}`]; remove(prompt, trim, load); }
      }
      // 去掉最后一步 RTX 2 倍超分，成片停在 768P：RAMCleanup 直接接 VRAMCleanup。
      node(prompt, "277").inputs.anything = ["278", 0];
      remove(prompt, "276");
    }
    assertLinks(prompt);
    return { mode, prompt };
  }

  function outputFile(entry: Record<string, unknown>, mode: Mode) {
    const outputs = (entry.outputs ?? {}) as Record<string, Record<string, unknown>>;
    const saved = outputs[SAVE_NODE[mode]] ?? {};
    const files = [...((saved.images ?? []) as Record<string, string>[]), ...((saved.gifs ?? []) as Record<string, string>[])];
    const video = files.find((file) => /\.(mp4|mov|webm)$/iu.test(file.filename ?? ""));
    if (!video) throw new Error(`ComfyUI 任务完成了，但保存节点 ${SAVE_NODE[mode]} 没有视频输出`);
    return { filename: video.filename!, subfolder: video.subfolder ?? "", type: video.type ?? "output" };
  }

  const endpoint: AsyncEndpoint = {
    async start(context) {
      const supported = serviceSupport(context.need);
      if (supported.status === "unsupported") throw new Error(supported.reason);
      const authored = context.need.constraints as unknown as GenerationRequest;
      await context.reportProgress?.({ phase: "上传参考素材并填写工作流" });
      const { mode, prompt } = await buildPrompt(authored, async (media) => {
        const bytes = await context.resources.get(media.artifact.resource);
        if (bytes === undefined) throw new Error("参考素材不可用");
        return new Uint8Array(bytes);
      });
      await context.reportProgress?.({ phase: `提交 ${TEMPLATE_FILES[mode]}` });
      const submitted = await json("/prompt", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ prompt, client_id: `hypit-${options.instance}` }),
      });
      const id = String(submitted.prompt_id ?? "");
      if (!id) throw new Error(`ComfyUI 没有返回 prompt_id: ${JSON.stringify(submitted).slice(0, 400)}`);
      const handle = { id, mode, duration: ports(authored).duration }, receipt = { id, workflow: TEMPLATE_FILES[mode] };
      await context.checkpoint?.({ handle, receipt });
      return { ...wakeAfter(handle, interval), receipt };
    },
    async poll(context) {
      const { id, mode, duration } = context.handle as { id: string; mode: Mode; duration: number };
      const historyOf = async () => (await json(`/history/${encodeURIComponent(id)}`))[id] as Record<string, unknown> | undefined;
      let entry = await historyOf();
      if (!entry) {
        const queue = await json("/queue");
        const inQueue = (list: unknown) => Array.isArray(list) && list.some((item) => Array.isArray(item) && item[1] === id);
        if (inQueue(queue.queue_running)) return wakeAfter({ id, mode, duration }, interval, Date.now(), { phase: "生成中" });
        if (inQueue(queue.queue_pending)) return wakeAfter({ id, mode, duration }, interval, Date.now(), { phase: "排队中" });
        // 任务可能恰好在两次查询之间跑完：先离开队列、再出现在 history。队列里没有时再查一次 history。
        entry = await historyOf();
        // ComfyUI 重启会清空 history 与队列，任务结果已无从查询。
        if (!entry) return { status: "failed", receipt: { id }, failure: { code: "COMFY_TASK_LOST", message: `ComfyUI 找不到任务 ${id}（可能已重启）` } };
      }
      const status = (entry.status ?? {}) as { status_str?: string; completed?: boolean; messages?: unknown[] };
      if (status.status_str === "error") {
        const error = (status.messages ?? []).find((m) => Array.isArray(m) && m[0] === "execution_error") as [string, Record<string, unknown>] | undefined;
        const detail = error ? `${String(error[1].node_type)}: ${String(error[1].exception_message).slice(0, 400)}` : "未知错误";
        return { status: "failed", receipt: { id }, failure: { code: "COMFY_EXECUTION_ERROR", message: `ComfyUI 任务 ${id} 失败：${detail}` } };
      }
      if (!status.completed) return wakeAfter({ id, mode, duration }, interval, Date.now(), { phase: "生成中" });
      return { status: "ready", handle: { id, mode, duration, file: outputFile(entry, mode) } };
    },
    async collect(context) {
      const { file, duration } = context.handle as { duration: number; file: { filename: string; subfolder: string; type: string } };
      await context.reportProgress?.({ phase: "下载成片" });
      const query = new URLSearchParams({ filename: file.filename, subfolder: file.subfolder, type: file.type });
      const response = await fetcher(`${base}/view?${query}`, { signal: AbortSignal.timeout(600_000) });
      if (!response.ok) throw new Error(`ComfyUI /view 返回 HTTP ${response.status}`);
      await context.reportProgress?.({ phase: `截到 ${duration} 秒` });
      const trimmed = await trimToDuration(new Uint8Array(await response.arrayBuffer()), duration);
      const artifact = await context.resources.put(trimmed, "video/mp4");
      return { status: "completed", result: { value: {
        kind: "inline", value: canonicalize(sealGeneratedVideoSet({ videos: [artifact] })),
      } } };
    },
  };

  return defineEndpointPackage({
    module: providerModule, facet: "videos", instance: options.instance, pool: options.pool,
    // 单卡：同一时间只跑一个生成任务。
    defaultConcurrency: 1,
    actionLimits: { submit: { concurrency: 1 }, poll: { concurrency: 2 }, collect: { concurrency: 1 } },
    // 机器按租用时长计费，不按次收费。
    pricing: { kind: "local" },
    capabilities: [{ capability, returns: generationTypes.videoSet, lifecycle: "asynchronous", supports: serviceSupport, endpoint }],
  });
}
