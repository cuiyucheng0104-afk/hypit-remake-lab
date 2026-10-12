import { execFile } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { promisify } from "node:util";
import { canonicalize, defineEndpointPackage, wakeAfter } from "@hypit/hypit/endpoint-kit";
import type { AsyncEndpoint, EndpointPricingDocument, EndpointRequest } from "@hypit/hypit/endpoint-kit";
import { generationTypes, sealGeneratedVideoSet } from "@hypit/hypit/generation";
import type { GenerationMediaValue, GenerationPortValue, GenerationRequest } from "@hypit/hypit/generation";

export const providerModule = { name: "@local/provider-autodl-market", version: "1" } as const;
export const capability = { module: { name: "@hypit/minimax-h3", version: "1" }, name: "minimax-h3" } as const;

const run = promisify(execFile);
/** 平台提供的空白音轨：六图工作流的 ref_audio_0 必填，SVML 没给音频时用它。 */
const BLANK_AUDIO = "https://codewithgpu.ks3-cn-beijing.ksyuncs.com/comfyui_api/blank/blank.wav";

export type Mode = "reference" | "frame" | "text";
export type MarketOptions = {
  instance: string;
  pool: string;
  baseUrl: string;
  /** 本机 Token 文件路径（只读取，不记录、不打印）。 */
  tokenFile: string;
  /** 三种模式各用市场上的哪个工作流。 */
  workflows: Record<Mode, string>;
  /** 参考图模式的分辨率档位：480p / 768p / 1088p / 1440p。 */
  referenceTier: string;
  /** 累计花费上限（元）与账本文件：超过上限的请求在提交前被拒绝。 */
  spendCapYuan: number;
  ledgerFile: string;
  pollIntervalMs: number;
  concurrency: number;
  fetch?: typeof globalThis.fetch;
};

/* ---------------- 请求解析 ---------------- */

export function ports(request: GenerationRequest) {
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

export function modeFor(request: GenerationRequest): Mode {
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

/** 市场工作流做不到的请求在 plan 阶段就明确拒绝，而不是悄悄降级。 */
export function serviceSupport(request: EndpointRequest) {
  const authored = request.constraints as unknown as GenerationRequest;
  const unsupported = (reason: string) => ({ status: "unsupported" as const, reason });
  if (countPort(request, "referenceVideo") > 0) {
    return unsupported("AutoDL 市场的 H3 工作流没有参考视频输入；需要参考视频的镜头请把 @hypit/minimax-h3 绑定切回 h3.autodl（自有服务器 U17）");
  }
  if (countPort(request, "referenceImage") > 6) return unsupported("六图工作流最多 6 张参考图");
  if (countPort(request, "referenceAudio") > 3) return unsupported("六图工作流最多 3 段参考音频");
  const first = countPort(request, "firstFrame"), last = countPort(request, "lastFrame");
  if ((first || last) && !(first && last)) {
    return unsupported("市场的首尾帧工作流要求首帧和尾帧都提供");
  }
  const resolution = authored.ports.resolution?.[0] as GenerationPortValue | undefined;
  if (resolution !== undefined && String(resolution) === "2K" && (first || last)) {
    return unsupported("市场的首尾帧工作流只有 736p，不出 2K");
  }
  return { status: "supported" as const };
}

/* ---------------- 分辨率与计价 ---------------- */

function orientation(aspectRatio: string | undefined, width?: number, height?: number): "横" | "竖" | "方" {
  if (width && height) return width > height ? "横" : width < height ? "竖" : "方";
  const [w, h] = (aspectRatio ?? "16:9").split(":").map(Number);
  return w! > h! ? "横" : w! < h! ? "竖" : "方";
}

/** 市场工作流分辨率枚举的标签（与 input_rules 的 options.label 一致）。 */
export function resolutionLabel(mode: Mode, tier: string, resolution: string | undefined, orient: "横" | "竖" | "方") {
  if (mode === "frame") return orient === "方" ? "736p(1:1)" : `736p${orient}`;
  if (mode === "text") return orient === "方" ? "768p(1:1)" : `768p${orient}`;
  const chosen = resolution === "2K" ? "1440p" : tier;
  const sizes: Record<string, [string, string]> = {
    "480p": ["480p横(864*480)", "480p竖(480*864)"], "768p": ["768p横(1376*768)", "768p竖(768*1376)"],
    "1088p": ["1088p横(1920*1088)", "1088p竖(1088*1920)"], "1440p": ["1440p横(2560*1440)", "1440p竖(1440*2560)"],
  };
  const pair = sizes[chosen] ?? sizes["1088p"]!;
  // 六图工作流没有 1:1 档，方形请求按横版出，由下游裁切。
  return orient === "竖" ? pair[1] : pair[0];
}

type Billing = { resolution: string; price: number; off_peak_price: number };

/** 北京时间 00:00–08:00 为闲时。价格字段单位是 0.001 元/秒。 */
export function yuanFor(billing: readonly Billing[], label: string, seconds: number, now = new Date()) {
  const hour = (now.getUTCHours() + 8) % 24;
  const tier = billing.find((b) => label.startsWith(b.resolution)) ?? billing[billing.length - 1];
  if (!tier) throw new Error(`没有 ${label} 的价格`);
  const perSecond = (hour < 8 ? tier.off_peak_price : tier.price) / 1000;
  return Math.round(perSecond * seconds * 1000) / 1000;
}

/* ---------------- 账本（花费上限） ---------------- */

type Ledger = { capYuan: number; spentYuan: number; entries: { at: string; operation: string; workflow: string; seconds: number; yuan: number }[] };

function readLedger(file: string, cap: number): Ledger {
  if (!existsSync(file)) return { capYuan: cap, spentYuan: 0, entries: [] };
  return JSON.parse(readFileSync(file, "utf8")) as Ledger;
}

/** 提交没有成功（没拿到 task_id）时退回这次预扣。 */
export function releaseBudget(file: string, operation: string) {
  if (!existsSync(file)) return;
  const ledger = JSON.parse(readFileSync(file, "utf8")) as Ledger;
  const entry = ledger.entries.find((e) => e.operation === operation);
  if (!entry) return;
  ledger.entries = ledger.entries.filter((e) => e !== entry);
  ledger.spentYuan = Math.max(0, Math.round((ledger.spentYuan - entry.yuan) * 1000) / 1000);
  writeFileSync(file, JSON.stringify(ledger, null, 1));
}

export function reserveBudget(file: string, cap: number, operation: string, workflow: string, seconds: number, yuan: number) {
  const ledger = readLedger(file, cap);
  if (typeof ledger.capYuan === "number" && ledger.capYuan > 0) cap = ledger.capYuan;  // 账本里设的上限优先
  if (ledger.entries.some((e) => e.operation === operation)) return ledger; // 同一 Operation 重试不重复记账
  if (ledger.spentYuan + yuan > cap + 1e-9) {
    throw new Error(`超出花费上限：已记 ¥${ledger.spentYuan.toFixed(3)}，本次 ¥${yuan.toFixed(3)}，上限 ¥${cap}。` +
      `确认后用 tools/market_ledger.py 调整上限或重置账本`);
  }
  ledger.spentYuan = Math.round((ledger.spentYuan + yuan) * 1000) / 1000;
  ledger.entries.push({ at: new Date().toISOString(), operation, workflow, seconds, yuan });
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, JSON.stringify(ledger, null, 1));
  return ledger;
}

/* ---------------- 截时长 ---------------- */

/** 生成结果若比请求长（H3 帧格 17k+5），截回请求时长；音视频一起截。 */
async function trimToDuration(bytes: Uint8Array, seconds: number) {
  const dir = await mkdtemp(join(tmpdir(), "autodl-market-"));
  try {
    const input = join(dir, "in.mp4"), output = join(dir, "out.mp4");
    await writeFile(input, bytes);
    await run("ffmpeg", ["-v", "error", "-y", "-i", input, "-t", String(seconds),
      "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p",
      "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output]);
    return new Uint8Array(await readFile(output));
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

/** 参考图长边缩到 1600 以内并转 JPEG，请求体小一个量级；参考图不需要更高分辨率。 */
async function shrinkImage(bytes: Uint8Array) {
  const dir = await mkdtemp(join(tmpdir(), "autodl-market-img-"));
  try {
    const input = join(dir, "in"), output = join(dir, "out.jpg");
    await writeFile(input, bytes);
    await run("ffmpeg", ["-v", "error", "-y", "-i", input,
      "-vf", "scale='min(1600,iw)':'min(1600,ih)':force_original_aspect_ratio=decrease", "-q:v", "3", output]);
    return { bytes: new Uint8Array(await readFile(output)), mediaType: "image/jpeg" };
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

/* ---------------- 市场 API ---------------- */

export function createAutodlMarketProvider(options: MarketOptions) {
  const base = options.baseUrl.replace(/\/$/u, "") + "/api/v1/comfyui";
  const fetcher = options.fetch ?? globalThis.fetch;
  const tokenPath = options.tokenFile.replace(/^~(?=\/)/u, homedir());
  const billingCache = new Map<string, Billing[]>();

  function token() {
    if (!existsSync(tokenPath)) throw new Error(`没有找到 Token 文件 ${options.tokenFile}，请在自己的终端保存`);
    const value = readFileSync(tokenPath, "utf8").trim();
    if (!value) throw new Error(`Token 文件 ${options.tokenFile} 是空的`);
    return value;
  }

  async function api(method: "GET" | "POST", path: string, body?: unknown) {
    const response = await fetcher(base + path, {
      method, headers: { Authorization: token(), "Content-Type": "application/json" },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal: AbortSignal.timeout(300_000),
    });
    const text = await response.text();
    if (response.status === 401) {
      throw new Error(`AutoDL 拒绝了令牌（HTTP 401）。市场要用「令牌管理」里 ComfyUI 分组的令牌，保存在 ${options.tokenFile}；` +
        "~/.config/autodl/token 是实例管理令牌，不能混用");
    }
    if (!response.ok) throw new Error(`AutoDL ${method} ${path} 返回 HTTP ${response.status}: ${text.slice(0, 600)}`);
    const json = JSON.parse(text) as { code?: string; msg?: string; data?: Record<string, unknown> };
    if (json.code && json.code !== "Success") throw new Error(`AutoDL ${method} ${path}：${json.code} ${json.msg ?? ""}`);
    return json.data ?? {};
  }

  async function billingFor(workflow: string) {
    const cached = billingCache.get(workflow);
    if (cached) return cached;
    const data = await api("GET", `/workflows/${workflow}`);
    const config = (data.billing_config ?? {}) as Record<string, Billing[]>;
    const list = Object.values(config)[0] ?? [];
    billingCache.set(workflow, list);
    return list;
  }

  async function dataUrl(bytes: Uint8Array, mediaType: string) {
    if (mediaType.startsWith("image/") && bytes.length > 400_000) {
      ({ bytes, mediaType } = await shrinkImage(bytes));
    }
    return `data:${mediaType};base64,${Buffer.from(bytes).toString("base64")}`;
  }

  /** 组装提交体；图片与音频以 base64 data URL 直接内嵌，不需要公网地址。 */
  async function buildBody(request: GenerationRequest, bytesOf: (media: GenerationMediaValue) => Promise<Uint8Array>) {
    const r = ports(request);
    const mode = modeFor(request);
    const workflow = options.workflows[mode];
    const seed = 1 + Math.floor(Math.random() * 999_999_999_999);
    let orient = orientation(r.aspectRatio);
    const body: Record<string, unknown> = { prompt: r.prompt, duration: r.duration, seed };
    if (mode === "reference") {
      for (const [i, media] of r.images.entries()) body[`ref_image_${i}`] = await dataUrl(await bytesOf(media), media.artifact.mediaType);
      for (const [i, media] of r.audios.entries()) body[`ref_audio_${i}`] = await dataUrl(await bytesOf(media), media.artifact.mediaType);
      if (!r.audios.length) body.ref_audio_0 = BLANK_AUDIO;
    } else if (mode === "frame") {
      const first = await bytesOf(r.first!);
      body.first_frame = await dataUrl(first, r.first!.artifact.mediaType);
      body.last_frame = await dataUrl(await bytesOf(r.last!), r.last!.artifact.mediaType);
      const size = imageSize(first);
      orient = orientation(undefined, size?.width, size?.height);
    }
    body.resolution = resolutionLabel(mode, options.referenceTier, r.resolution, orient);
    return { mode, workflow, body };
  }

  const endpoint: AsyncEndpoint = {
    async start(context) {
      const supported = serviceSupport(context.need);
      if (supported.status === "unsupported") throw new Error(supported.reason);
      const authored = context.need.constraints as unknown as GenerationRequest;
      await context.reportProgress?.({ phase: "组装请求" });
      const { workflow, body } = await buildBody(authored, async (media) => {
        const bytes = await context.resources.get(media.artifact.resource);
        if (bytes === undefined) throw new Error("参考素材不可用");
        return new Uint8Array(bytes);
      });
      const seconds = Number(body.duration);
      const yuan = yuanFor(await billingFor(workflow), String(body.resolution), seconds);
      reserveBudget(options.ledgerFile.replace(/^~(?=\/)/u, homedir()), options.spendCapYuan, context.operation, workflow, seconds, yuan);
      await context.reportProgress?.({ phase: `提交 ${workflow}（${body.resolution}，${seconds} 秒，约 ¥${yuan}）` });
      const ledgerFile = options.ledgerFile.replace(/^~(?=\/)/u, homedir());
      let taskId = "";
      try {
        const data = await api("POST", `/comfyui_workflow/${workflow}`, body);
        taskId = String(data.task_id ?? "");
        if (!taskId) throw new Error(`AutoDL 没有返回 task_id: ${JSON.stringify(data).slice(0, 400)}`);
      } catch (error) {
        releaseBudget(ledgerFile, context.operation);   // 没有建成任务就不算钱
        throw error;
      }
      await context.reportProgress?.({ phase: `已提交，市场任务号 ${taskId}` });   // 写进构建日志，方便直接查市场进度
      // 种子、分辨率、费用随 handle 持久化，便于复现与对账；回执只放任务号
      const handle = { taskId, workflow, duration: seconds, resolution: String(body.resolution), seed: Number(body.seed), yuan };
      const receipt = { id: taskId };
      await context.checkpoint?.({ handle, receipt });
      return { ...wakeAfter(handle, options.pollIntervalMs), receipt };
    },
    async poll(context) {
      const handle = context.handle as { taskId: string; workflow: string; duration: number };
      const data = await api("GET", `/comfyui_workflow/result/${handle.taskId}`);
      const status = String(data.status ?? "").toLowerCase();
      if (["failed", "error", "cancelled", "canceled"].includes(status)) {
        return { status: "failed", receipt: { id: handle.taskId }, failure: { code: "AUTODL_TASK_FAILED",
          message: `AutoDL 任务 ${handle.taskId} ${status}：${JSON.stringify(data).slice(0, 400)}` } };
      }
      const results = (data.results ?? []) as { url?: string; type?: string }[];
      const video = results.find((item) => item.url && (item.type ?? "video") === "video");
      if (status !== "completed" && status !== "success" || !video?.url) {
        return wakeAfter(handle, options.pollIntervalMs, Date.now(), { phase: status || "排队中" });
      }
      return { status: "ready", handle: { ...handle, url: video.url } };
    },
    async collect(context) {
      const { url, duration } = context.handle as { url: string; duration: number };
      await context.reportProgress?.({ phase: "下载成片（链接短时效）" });
      const response = await fetcher(url, { signal: AbortSignal.timeout(600_000) });
      if (!response.ok) throw new Error(`下载成片返回 HTTP ${response.status}`);
      const trimmed = await trimToDuration(new Uint8Array(await response.arrayBuffer()), duration);
      const artifact = await context.resources.put(trimmed, "video/mp4");
      return { status: "completed", result: { value: { kind: "inline", value: canonicalize(sealGeneratedVideoSet({ videos: [artifact] })) } } };
    },
  };

  async function readPricing(context: { request: EndpointRequest }): Promise<readonly EndpointPricingDocument[]> {
    const mode = modeFor(context.request.constraints as unknown as GenerationRequest);
    const workflow = options.workflows[mode];
    const billing = await billingFor(workflow);
    return [{
      source: `${options.baseUrl}/api/v1/comfyui/workflows/${workflow}`,
      data: canonicalize(billing as unknown as never),
      summary: billing.map((b) => `${b.resolution} 高峰 ¥${(b.price / 1000).toFixed(3)}/秒、闲时（北京时间 0–8 点）¥${(b.off_peak_price / 1000).toFixed(3)}/秒`).join("；")
        + `。按生成秒数计费；本 Endpoint 累计上限 ¥${options.spendCapYuan}`,
    }];
  }

  return {
    buildBody,
    package: defineEndpointPackage({
      module: providerModule, facet: "videos", instance: options.instance, pool: options.pool,
      defaultConcurrency: options.concurrency,
      actionLimits: { submit: { concurrency: options.concurrency }, poll: { concurrency: 4 }, collect: { concurrency: 2 } },
      pricing: { kind: "page", url: "https://www.autodl.art/" },
      readPricing,
      capabilities: [{ capability, returns: generationTypes.videoSet, lifecycle: "asynchronous", supports: serviceSupport, endpoint }],
    }),
  };
}

/** 读取 PNG / JPEG / WebP 的像素尺寸（首尾帧模式按首帧判断横竖）。 */
function imageSize(bytes: Uint8Array): { width: number; height: number } | undefined {
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
  return undefined;
}
