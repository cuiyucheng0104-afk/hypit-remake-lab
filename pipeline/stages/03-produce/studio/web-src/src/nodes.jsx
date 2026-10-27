import { memo, useContext, useEffect, useMemo, useRef } from 'react'
import { Handle, Position, useReactFlow, useEdges, useNodes } from '@xyflow/react'
import { job, submit, outputUrl, kindOf } from './api'
import { OptionsContext } from './context'
import { freeSpot } from './layout'

// ---------- shared bits ----------

const ASPECTS = ['16:9', '9:16', '1:1', '4:3', '3:4', '3:2', '2:3', '21:9']

export function newSeed() {
  return Math.floor(Math.random() * 2 ** 40) + 1
}

function Preview({ kind, url, small }) {
  if (kind === 'video') return <video className={small ? 'thumb' : 'media'} src={url} controls muted loop playsInline preload="metadata" />
  if (kind === 'audio') return <audio className="audio" src={url} controls preload="none" />
  if (kind === 'model') return <div className="model3d">3D 模型（GLB）<br /><a href={url} download>下载</a></div>
  return <img className={small ? 'thumb' : 'media'} src={url} alt="" draggable={false} />
}

function Field({ label, children, hint }) {
  return (
    <label className="field">
      <span className="flabel">{label}{hint && <em> {hint}</em>}</span>
      {children}
    </label>
  )
}

function Select({ value, onChange, options }) {
  return (
    <select className="nodrag" value={value} onChange={e => onChange(e.target.value)}>
      {options.map(o => typeof o === 'string'
        ? <option key={o} value={o}>{o}</option>
        : <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}

function Num({ value, onChange, min, max, step = 1 }) {
  return <input className="nodrag num" type="number" value={value} min={min} max={max} step={step}
    onChange={e => onChange(e.target.value === '' ? '' : Number(e.target.value))} />
}

function Toggle({ value, onChange, label }) {
  return (
    <label className="toggle nodrag">
      <input type="checkbox" checked={!!value} onChange={e => onChange(e.target.checked)} /> {label}
    </label>
  )
}

/** Inputs connected to a generator handle, in connection order. */
function useInputs(id) {
  const edges = useEdges()
  const nodes = useNodes()
  return useMemo(() => {
    const byId = Object.fromEntries(nodes.map(n => [n.id, n]))
    const out = {}
    edges.filter(e => e.target === id).sort((a, b) => (a.data?.order ?? 0) - (b.data?.order ?? 0)).forEach(e => {
      const src = byId[e.source]
      if (!src?.data?.ref) return
      ;(out[e.targetHandle] ||= []).push({ edge: e, node: src, ref: src.data.ref, kind: src.data.kind, url: src.data.url, label: src.data.label })
    })
    return out
  }, [edges, nodes, id])
}

/** Submit + poll a generation job; on success drop result nodes to the right of the generator. */
function useRunner(id, data) {
  const rf = useReactFlow()
  const timer = useRef(null)
  const st = data.status || {}

  useEffect(() => {
    if (!st.pid || !['queued', 'running', 'submitting'].includes(st.state)) return
    let stopped = false
    const tick = async () => {
      try {
        const j = await job(st.pid)
        if (stopped) return
        if (j.state === 'done' || j.state === 'error') {
          const me = rf.getNode(id)
          const files = j.files || []
          const placed = [...rf.getNodes()]
          files.forEach((f, i) => {
            const nid = `r_${st.pid.slice(0, 8)}_${i}`
            if (rf.getNode(nid)) return
            const kind = kindOf(f.filename)
            const ref = `output/${f.subfolder ? f.subfolder + '/' : ''}${f.filename}`
            const position = freeSpot(placed, 'result',
              { x: me.position.x + (me.measured?.width || 380) + 80, y: me.position.y }, { x: 0, y: 340 })
            const node = { id: nid, type: 'result', position, data: { kind, ref, url: outputUrl(f), label: f.filename, meta: st.summary } }
            placed.push(node)
            rf.addNodes(node)
            rf.addEdges({ id: `e_${id}_${nid}`, source: id, sourceHandle: 'out', target: nid, targetHandle: 'from', className: 'lineage' })
          })
          rf.updateNodeData(id, { status: { ...st, state: j.state, error: j.error, finishedAt: Date.now() } })
          return
        }
        rf.updateNodeData(id, { status: { ...st, state: j.state, ahead: j.ahead } })
      } catch (e) { /* transient network error: keep polling */ }
      if (!stopped) timer.current = setTimeout(tick, 2500)
    }
    timer.current = setTimeout(tick, 1000)
    return () => { stopped = true; clearTimeout(timer.current) }
  }, [st.pid, st.state])

  const run = async (payload, summary) => {
    rf.updateNodeData(id, { status: { state: 'submitting', startedAt: Date.now() } })
    try {
      const r = await submit(payload)
      rf.updateNodeData(id, { status: { state: 'queued', pid: r.prompt_id, startedAt: Date.now(), summary } })
    } catch (e) {
      rf.updateNodeData(id, { status: { state: 'error', error: e.message } })
    }
  }
  return run
}

function Status({ status }) {
  if (!status?.state) return null
  const secs = status.startedAt ? Math.round(((status.finishedAt || Date.now()) - status.startedAt) / 1000) : 0
  const text = {
    submitting: '提交中…',
    queued: status.ahead ? `排队中，前面还有 ${status.ahead} 个任务` : '排队中…',
    running: `生成中… ${secs} 秒`,
    done: `完成（${secs} 秒）`,
    error: '失败：' + (status.error || ''),
    unknown: '状态未知（可能 ComfyUI 重启过）',
  }[status.state]
  return <div className={`status s-${status.state}`}>{text}</div>
}

function useTicker(active) {
  const rf = useReactFlow()
  useEffect(() => {
    if (!active) return
    const t = setInterval(() => rf.setNodes(ns => [...ns]), 1000)
    return () => clearInterval(t)
  }, [active])
}

function InputList({ items, numbered, prefix, onTime }) {
  if (!items?.length) return null
  return (
    <div className="inputs">
      {items.map((it, i) => (
        <div className="inrow" key={it.edge.id}>
          <Preview kind={it.kind} url={it.url} small />
          <span className="inlabel">{numbered ? `${prefix} ${i + 1}` : ''} <small>{it.label}</small></span>
          {onTime && <span className="kt">第 <Num value={it.edge.data?.time ?? 0} min={0} max={15} step={0.5}
            onChange={v => onTime(it.edge.id, v)} /> 秒</span>}
        </div>
      ))}
    </div>
  )
}

function InHandle({ id, label, top }) {
  return (
    <>
      <Handle type="target" position={Position.Left} id={id} style={{ top }} />
      <span className="hlabel" style={{ top }}>{label}</span>
    </>
  )
}

function LoraPicker({ family, value, onChange }) {
  const { loras } = useContext(OptionsContext)
  const list = loras.filter(l => l.family === family)
  if (!list.length) return null
  const groups = {}
  list.forEach(l => (groups[l.group_label] ||= []).push(l))
  const sel = value || {}
  const count = Object.keys(sel).length
  return (
    <details className="loras nodrag nowheel" open={count > 0}>
      <summary>LoRA（已选 {count} 个，可多选叠加）</summary>
      {Object.entries(groups).map(([g, items]) => (
        <div key={g} className="lgroup">
          <div className="lgtitle">{g}</div>
          {items.map(l => {
            const on = l.name in sel
            return (
              <div className={'lrow' + (on ? ' on' : '')} key={l.name}>
                <label><input type="checkbox" checked={on} onChange={e => {
                  const next = { ...sel }
                  if (e.target.checked) next[l.name] = 1.0; else delete next[l.name]
                  onChange(next)
                }} /> {l.label}</label>
                {on && <><input type="range" min={0} max={1.5} step={0.05} value={sel[l.name]}
                  onChange={e => onChange({ ...sel, [l.name]: Number(e.target.value) })} />
                  <span className="lval">{Number(sel[l.name]).toFixed(2)}</span></>}
              </div>
            )
          })}
        </div>
      ))}
    </details>
  )
}

function SeedField({ value, onChange }) {
  return (
    <Field label="种子" hint="（0 = 每次随机）">
      <div className="seed">
        <Num value={value} min={0} onChange={onChange} />
        <button className="nodrag mini" onClick={() => onChange(0)}>随机</button>
      </div>
    </Field>
  )
}

// ---------- asset & result ----------

export const AssetNode = memo(({ data, selected }) => (
  <div className={'card asset' + (selected ? ' sel' : '')}>
    <div className="ctitle">{{ image: '图片素材', video: '视频素材', audio: '音频素材', model: '3D' }[data.kind]}</div>
    <Preview kind={data.kind} url={data.url} />
    <div className="fname">{data.label}</div>
    <Handle type="source" position={Position.Right} id="out" />
  </div>
))

export const ResultNode = memo(({ data, selected }) => (
  <div className={'card result' + (selected ? ' sel' : '')}>
    <Handle type="target" position={Position.Left} id="from" isConnectable={false} />
    <div className="ctitle">生成结果</div>
    <Preview kind={data.kind} url={data.url} />
    <div className="fname">{data.label} · <a className="nodrag" href={data.url} download={data.label}>下载</a></div>
    {data.meta && <div className="meta">{data.meta}</div>}
    {data.kind !== 'model' && <Handle type="source" position={Position.Right} id="out" />}
  </div>
))

// ---------- image generator (Qwen-Image 2.1) ----------

const IMAGE_MODES = [
  { value: 't2i', label: '文生图' },
  { value: 'edit', label: '图生图 / 多图参考（连 1–6 张图）' },
]

export const ImageGenNode = memo(({ id, data, selected }) => {
  const rf = useReactFlow()
  const set = patch => rf.updateNodeData(id, patch)
  const inputs = useInputs(id)
  const run = useRunner(id, data)
  const busy = ['submitting', 'queued', 'running'].includes(data.status?.state)
  useTicker(busy)
  const refs = inputs.refs || []
  const mode = refs.length ? 'edit' : 't2i'

  const go = () => {
    const payload = {
      mode, prompt: data.prompt, uncensored: data.uncensored, enhance: data.enhance, steps: data.steps,
      seed: data.seed || 0, aspect: data.aspect, megapixels: data.megapixels, negative: data.negative,
      ref_images: refs.map(r => r.ref),
    }
    run(payload, `${data.uncensored ? '未审查' : '审查'} · ${mode === 't2i' ? '文生图' : `参考 ${refs.length} 张`}`)
  }

  return (
    <div className={'card gen image' + (selected ? ' sel' : '')}>
      <InHandle id="refs" label="参考图" top={56} />
      <div className="ctitle">🖼 图片生成 · Qwen-Image 2.1</div>
      <div className="modebar">{mode === 't2i' ? '文生图（没有连参考图）' : `图生图：参考 ${refs.length} 张（图1、图2…按连线顺序）`}</div>
      <InputList items={refs} numbered prefix="图" />
      <Field label="模型">
        <Select value={data.uncensored ? 'u' : 'c'} onChange={v => set({ uncensored: v === 'u' })}
          options={[{ value: 'c', label: '审查版（原版）' }, { value: 'u', label: '未审查版（UC）' }]} />
      </Field>
      <Field label="提示词">
        <textarea className="nodrag nowheel" rows={5} value={data.prompt || ''} onChange={e => set({ prompt: e.target.value })}
          placeholder={mode === 't2i' ? '描述画面：主体、场景、光线、风格…' : '说清楚怎么改：例如「让图1的人物站在图2的庭院里，保持人物外貌不变」'} />
      </Field>
      <Toggle value={data.enhance} onChange={v => set({ enhance: v })} label="提示词扩写（用 Qwen3.5 把短提示词扩写成详细描述，多花 10–30 秒）" />
      <div className="row">
        {mode === 't2i' && <Field label="画幅"><Select value={data.aspect} onChange={v => set({ aspect: v })} options={ASPECTS} /></Field>}
        {mode === 't2i' && <Field label="清晰度" hint="百万像素"><Num value={data.megapixels} min={0.3} max={4} step={0.1} onChange={v => set({ megapixels: v })} /></Field>}
        <Field label="步数"><Num value={data.steps} min={4} max={60} onChange={v => set({ steps: v })} /></Field>
      </div>
      <SeedField value={data.seed} onChange={v => set({ seed: v })} />
      <details className="nodrag"><summary>负面提示词（可选）</summary>
        <textarea className="nowheel" rows={2} value={data.negative || ''} onChange={e => set({ negative: e.target.value })} />
      </details>
      <LoraPicker family="qwen" value={data.loras} onChange={v => set({ loras: v })} />
      <button className="nodrag go" disabled={busy || !data.prompt} onClick={go}>{busy ? '生成中…' : '生成图片'}</button>
      <Status status={data.status} />
      <Handle type="source" position={Position.Right} id="out" isConnectable={false} />
    </div>
  )
})

// ---------- video generator (MiniMax H3) ----------

const VIDEO_MODES = [
  { value: 't2v', label: '文生视频' },
  { value: 'i2v', label: '图生视频（首帧 / 首尾帧）' },
  { value: 'r2v', label: '参考生视频（参考图 / 视频 / 音频）' },
  { value: 'multiref', label: '多参考（关键帧钉在指定秒数）' },
  { value: 'continue', label: '续写（接着一段视频往下拍）' },
]
const VIDEO_HANDLES = {
  t2v: [],
  i2v: [['first', '首帧'], ['last', '尾帧（可选）']],
  r2v: [['images', '参考图'], ['videos', '参考视频'], ['audios', '参考音频']],
  multiref: [['images', '参考图'], ['keyframes', '关键帧']],
  continue: [['source', '源视频']],
}
const VIDEO_TIPS = {
  t2v: '只靠提示词出视频。可以写对白（用引号）、音效、镜头运动。',
  i2v: '把一张图连到「首帧」，视频从这张图开始；再连一张到「尾帧」就是首尾帧过渡。',
  r2v: '提示词里用 <Picture 1>、<Picture 2> 指参考图，<Video 1> 指参考视频，<Audio 1> 指参考音频，编号按连线顺序。参考视频要 2–15 秒。',
  multiref: '「参考图」定人物和风格；「关键帧」里的每张图会被钉在你填的那一秒。',
  continue: '连一段视频（素材或上一次的生成结果），会取它的最后一帧当首帧接着往下拍。',
}

export const VideoGenNode = memo(({ id, data, selected }) => {
  const rf = useReactFlow()
  const set = patch => rf.updateNodeData(id, patch)
  const options = useContext(OptionsContext)
  const inputs = useInputs(id)
  const run = useRunner(id, data)
  const busy = ['submitting', 'queued', 'running'].includes(data.status?.state)
  useTicker(busy)
  const mode = data.mode || 't2v'
  const handles = VIDEO_HANDLES[mode]
  const refs = k => (inputs[k] || [])

  const setEdgeTime = (edgeId, t) => rf.setEdges(es => es.map(e => e.id === edgeId ? { ...e, data: { ...e.data, time: t } } : e))

  const go = () => {
    const loras = Object.entries(data.loras || {}).map(([name, strength]) => ({ name, strength }))
    const payload = {
      mode, prompt: data.prompt, seconds: data.seconds, aspect: data.aspect, megapixels: data.megapixels,
      turbo: data.turbo, steps: data.steps, upscale: data.upscale, seed: data.seed || 0,
      engine: options.fast_omni && ['r2v', 'multiref'].includes(mode) ? (data.engine || 'fasth3_omni') : 'turbo',
      use_video_audio: data.useVideoAudio, rtx_sr: !!(options.rtx_sr && data.rtxSr), loras,
      first_frame: refs('first')[0]?.ref, last_frame: refs('last')[0]?.ref,
      ref_images: refs('images').map(r => r.ref), ref_videos: refs('videos').map(r => r.ref),
      ref_audios: refs('audios').map(r => r.ref), source_video: refs('source')[0]?.ref,
      keyframes: refs('keyframes').map(r => ({ image: r.ref, time: r.edge.data?.time ?? 0 })),
    }
    const lab = VIDEO_MODES.find(m => m.value === mode).label.split('（')[0]
    run(payload, `${lab}${payload.engine === 'fasth3_omni' ? ' · FastH3 Omni' : ''} · ${data.seconds} 秒${data.upscale ? ' · 二采' : ''}${payload.rtx_sr ? ' · RTX 超分' : ''}${loras.length ? ` · LoRA×${loras.length}` : ''}`)
  }

  return (
    <div className={'card gen video' + (selected ? ' sel' : '')}>
      {handles.map(([hid, label], i) => <InHandle key={hid} id={hid} label={label} top={56 + i * 26} />)}
      <div className="ctitle">🎬 视频生成 · MiniMax H3</div>
      <Field label="生成方式"><Select value={mode} onChange={v => set({ mode: v })} options={VIDEO_MODES} /></Field>
      <div className="tip">{VIDEO_TIPS[mode]}</div>
      {handles.map(([hid, label]) => (
        <InputList key={hid} items={refs(hid)} numbered={['images', 'videos', 'audios', 'keyframes'].includes(hid)}
          prefix={{ images: 'Picture', videos: 'Video', audios: 'Audio', keyframes: '关键帧' }[hid]}
          onTime={hid === 'keyframes' ? setEdgeTime : null} />
      ))}
      <Field label="提示词">
        <textarea className="nodrag nowheel" rows={6} value={data.prompt || ''} onChange={e => set({ prompt: e.target.value })}
          placeholder="英文效果最稳。写清楚谁在做什么、镜头怎么动、声音和对白。" />
      </Field>
      <div className="row">
        <Field label="时长" hint="秒（最长 15）"><Num value={data.seconds} min={1} max={15} step={0.5} onChange={v => set({ seconds: v })} /></Field>
        <Field label="画幅"><Select value={data.aspect} onChange={v => set({ aspect: v })} options={ASPECTS} /></Field>
        <Field label="清晰度" hint="百万像素，0.9 ≈ 1280×720"><Num value={data.megapixels} min={0.2} max={1.5} step={0.1} onChange={v => set({ megapixels: v })} /></Field>
      </div>
      <div className="row">
        <Toggle value={data.turbo} onChange={v => set({ turbo: v })} label="加速（8 步）" />
        {!data.turbo && <Field label="步数"><Num value={data.steps} min={4} max={50} onChange={v => set({ steps: v })} /></Field>}
        <Toggle value={data.upscale} onChange={v => set({ upscale: v })} label="二采高清" />
      </div>
      {options.fast_omni && ['r2v', 'multiref'].includes(mode) && (
        <Field label="模型" hint="FastH3 Omni：整模型蒸馏的参考生视频专用模型（FastVideo），8 步">
          <Select value={data.engine || 'fasth3_omni'} onChange={v => set({ engine: v })}
            options={[{ value: 'fasth3_omni', label: 'FastH3 Omni（蒸馏版，推荐）' }, { value: 'turbo', label: 'H3 + 768p 加速 LoRA' }]} />
        </Field>
      )}
      {options.rtx_sr && <Toggle value={data.rtxSr} onChange={v => set({ rtxSr: v })} label="RTX 超分 ×2（出片后用 NVIDIA RTX 放大，最高 4K）" />}
      {data.upscale && <div className="tip">二采：先按上面的「清晰度」完整出片，再在潜空间把每边放大 1.5 倍、低噪声精修补细节（0.9 → 约 1920×1080）。时间约为不开二采的 1.5–2 倍。</div>}
      {mode === 'r2v' && refs('videos').length > 0 && <Toggle value={data.useVideoAudio} onChange={v => set({ useVideoAudio: v })} label="同时参考视频里的原声" />}
      <SeedField value={data.seed} onChange={v => set({ seed: v })} />
      <LoraPicker family="h3" value={data.loras} onChange={v => set({ loras: v })} />
      <button className="nodrag go" disabled={busy || !data.prompt} onClick={go}>{busy ? '生成中…' : '生成视频'}</button>
      <Status status={data.status} />
      <Handle type="source" position={Position.Right} id="out" isConnectable={false} />
    </div>
  )
})

// ---------- whitebox (SAM 3D Body) ----------

export const WhiteboxNode = memo(({ id, data, selected }) => {
  const rf = useReactFlow()
  const set = patch => rf.updateNodeData(id, patch)
  const inputs = useInputs(id)
  const run = useRunner(id, data)
  const busy = ['submitting', 'queued', 'running'].includes(data.status?.state)
  useTicker(busy)
  const src = inputs.source || []
  const go = () => run({ mode: 'whitebox', source_video: src[0]?.ref, start: data.start, seconds: data.seconds, single: data.single },
    `白膜 · ${data.seconds || '全部'} 秒`)
  return (
    <div className={'card gen whitebox' + (selected ? ' sel' : '')}>
      <InHandle id="source" label="源视频" top={56} />
      <div className="ctitle">⬜ 视频转白膜 · SAM 3D Body</div>
      <div className="tip">把真人视频变成灰色白模人偶（保留站位、动作、运镜），同时出一条叠在原片上的核对视频和一个能在 Blender 里改的 GLB。画面清楚、动作不太快的镜头效果最好。</div>
      <InputList items={src} />
      <div className="row">
        <Field label="从第几秒开始"><Num value={data.start} min={0} max={3600} step={0.5} onChange={v => set({ start: v })} /></Field>
        <Field label="处理多长" hint="秒（0 = 到结尾）"><Num value={data.seconds} min={0} max={60} step={0.5} onChange={v => set({ seconds: v })} /></Field>
      </div>
      <Toggle value={data.single} onChange={v => set({ single: v })} label="只要主角（画面里最显眼的那个人，其他人不画）" />
      <button className="nodrag go" disabled={busy || !src.length} onClick={go}>{busy ? '处理中…' : '转白膜'}</button>
      <Status status={data.status} />
      <Handle type="source" position={Position.Right} id="out" isConnectable={false} />
    </div>
  )
})

export const nodeTypes = { asset: AssetNode, result: ResultNode, imageGen: ImageGenNode, videoGen: VideoGenNode, whitebox: WhiteboxNode }

export const DEFAULTS = {
  imageGen: { prompt: '', uncensored: false, enhance: false, aspect: '16:9', megapixels: 1.0, steps: 25, seed: 0, loras: {} },
  videoGen: { mode: 't2v', prompt: '', seconds: 5, aspect: '16:9', megapixels: 0.9, turbo: true, steps: 20, upscale: false, seed: 0, loras: {} },
  whitebox: { start: 0, seconds: 10, single: false },
}

/** Which source kinds a generator handle accepts. */
export const ACCEPTS = {
  refs: ['image'], first: ['image'], last: ['image'], images: ['image'], keyframes: ['image'],
  videos: ['video'], audios: ['audio', 'video'], source: ['video'],
}
export const SINGLE = new Set(['first', 'last', 'source'])
