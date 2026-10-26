import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, addEdge,
  useNodesState, useEdgesState, useReactFlow,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './styles.css'
import { nodeTypes, DEFAULTS, ACCEPTS, SINGLE } from './nodes'
import { OptionsContext } from './context'
import { getOptions, upload, inputUrl, kindOf, listCanvases, loadCanvas, saveCanvas } from './api'
import { freeSpot } from './layout'

const uid = p => `${p}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`

function Studio() {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [options, setOptions] = useState({ loras: [], aspects: [] })
  const [canvases, setCanvases] = useState([])
  const [name, setName] = useState(() => {
    try { return localStorage.getItem('studio.canvas') || '默认画布' } catch (e) { return '默认画布' }
  })
  const [saved, setSaved] = useState('')
  const [loaded, setLoaded] = useState(false)
  const rf = useReactFlow()
  const fileRef = useRef(null)
  const saveTimer = useRef(null)

  useEffect(() => { getOptions().then(setOptions).catch(() => {}) }, [])
  useEffect(() => { listCanvases().then(setCanvases).catch(() => {}) }, [name])

  // load a canvas
  useEffect(() => {
    setLoaded(false)
    try { localStorage.setItem('studio.canvas', name) } catch (e) { /* private mode */ }
    loadCanvas(name).then(c => {
      setNodes(c?.nodes || [])
      setEdges(c?.edges || [])
      if (c?.viewport) rf.setViewport(c.viewport)
      else setTimeout(() => rf.fitView({ padding: 0.2 }), 50)
      setLoaded(true)
    }).catch(() => setLoaded(true))
  }, [name])

  // autosave (debounced)
  useEffect(() => {
    if (!loaded) return
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      const strip = nodes.map(({ selected, dragging, measured, ...n }) => n)
      try {
        await saveCanvas(name, { nodes: strip, edges, viewport: rf.getViewport() })
        setSaved(new Date().toLocaleTimeString())
      } catch (e) { setSaved('保存失败') }
    }, 1200)
  }, [nodes, edges, loaded])

  const centre = (dx = 0, dy = 0) => {
    const { x, y, zoom } = rf.getViewport()
    const el = document.querySelector('.react-flow')
    return { x: (el.clientWidth / 2 - x) / zoom - 180 + dx, y: (el.clientHeight / 2 - y) / zoom - 200 + dy }
  }

  // New cards never land on top of existing ones: step right (generators) or down (assets) until the spot is free.
  const addGen = type => setNodes(ns => [...ns, {
    id: uid(type), type, position: freeSpot(ns, type, centre(), { x: 440, y: 0 }), data: { ...DEFAULTS[type] },
  }])

  const addFiles = async files => {
    const base = centre(-460, 0)
    for (const f of files) {
      try {
        const ref = await upload(f)
        const kind = kindOf(f.name)
        setNodes(ns => [...ns, {
          id: uid('a'), type: 'asset', position: freeSpot(ns, 'asset', base, { x: 0, y: 320 }),
          data: { kind, ref, url: inputUrl(ref), label: f.name },
        }])
      } catch (e) { alert(e.message) }
    }
  }

  const isValidConnection = useCallback(c => {
    const src = rf.getNode(c.source)
    const accept = ACCEPTS[c.targetHandle]
    if (!src?.data?.kind || !accept) return false
    return accept.includes(src.data.kind)
  }, [rf])

  const onConnect = useCallback(c => setEdges(es => {
    let next = es
    if (SINGLE.has(c.targetHandle)) next = next.filter(e => !(e.target === c.target && e.targetHandle === c.targetHandle))
    const order = Math.max(0, ...next.filter(e => e.target === c.target).map(e => e.data?.order ?? 0)) + 1
    return addEdge({ ...c, id: uid('e'), data: { order, time: 0 } }, next)
  }), [])

  const onDrop = useCallback(e => {
    e.preventDefault()
    if (e.dataTransfer.files?.length) addFiles([...e.dataTransfer.files])
  }, [])

  const newCanvas = () => {
    const n = window.prompt('新画布名字：')
    if (n && n.trim()) setName(n.trim())
  }

  return (
    <OptionsContext.Provider value={options}>
      <div className="app" onDragOver={e => e.preventDefault()} onDrop={onDrop}>
        <header className="bar">
          <b className="logo">Hypit Studio</b>
          <select value={name} onChange={e => setName(e.target.value)} title="切换画布">
            {[...new Set([name, ...canvases])].map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <button onClick={newCanvas}>＋ 新画布</button>
          <span className="sep" />
          <button onClick={() => fileRef.current.click()}>⬆ 上传素材</button>
          <input ref={fileRef} type="file" multiple hidden accept="image/*,video/*,audio/*"
            onChange={e => { addFiles([...e.target.files]); e.target.value = '' }} />
          <button onClick={() => addGen('imageGen')}>🖼 图片生成</button>
          <button onClick={() => addGen('videoGen')}>🎬 视频生成</button>
          <button onClick={() => addGen('whitebox')}>⬜ 视频转白膜</button>
          <span className="grow" />
          <span className="hint">素材右边的圆点拖到生成器左边的接口 · 选中按 Delete 删除 · 文件可直接拖进画布</span>
          <span className="saved">{saved && `已保存 ${saved}`}</span>
        </header>
        <ReactFlow
          nodes={nodes} edges={edges} nodeTypes={nodeTypes}
          onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
          isValidConnection={isValidConnection}
          minZoom={0.1} maxZoom={2} deleteKeyCode={['Delete', 'Backspace']}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={24} color="#2a2a2a" />
          <Controls />
          <MiniMap pannable zoomable nodeColor={n => ({ asset: '#4a6', result: '#c84', imageGen: '#48c', videoGen: '#a5c', whitebox: '#999' }[n.type])} />
        </ReactFlow>
        {loaded && !nodes.length && (
          <div className="empty">
            <h2>开始使用</h2>
            <ol>
              <li>点上面的「🖼 图片生成」或「🎬 视频生成」，在画布上放一个生成器。</li>
              <li>需要参考图、首帧、参考视频时，点「⬆ 上传素材」（或直接把文件拖进来），再从素材右边的圆点拉一根线到生成器左边对应的接口。</li>
              <li>写提示词，选参数和 LoRA，点「生成」。结果出现在生成器右边，也能再连到下一个生成器继续用（比如生成的图拿去做图生视频）。</li>
            </ol>
            <p>所有人共用一张显卡，任务按先后排队。画布自动保存在服务器上，换一台电脑打开也能看到。</p>
          </div>
        )}
      </div>
    </OptionsContext.Provider>
  )
}

export default function App() {
  return <ReactFlowProvider><Studio /></ReactFlowProvider>
}
