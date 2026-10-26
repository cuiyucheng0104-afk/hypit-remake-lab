// Thin wrappers over the Studio backend (/studio/api/*) and ComfyUI's own upload/view endpoints.

export async function getOptions() {
  return (await fetch('/studio/api/options')).json()
}

export async function upload(file) {
  const fd = new FormData()
  fd.append('image', file, file.name)
  fd.append('overwrite', 'false')
  const r = await fetch('/upload/image', { method: 'POST', body: fd })
  if (!r.ok) throw new Error('上传失败：' + file.name)
  const j = await r.json()
  return j.subfolder ? `${j.subfolder}/${j.name}` : j.name
}

export function inputUrl(name) {
  return `/view?type=input&filename=${encodeURIComponent(name)}`
}

export function outputUrl(f) {
  return `/view?type=output&subfolder=${encodeURIComponent(f.subfolder || '')}&filename=${encodeURIComponent(f.filename)}`
}

export async function submit(payload) {
  const r = await fetch('/studio/api/submit', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })
  const j = await r.json()
  if (!r.ok) {
    const detail = j.detail?.node_errors ? Object.values(j.detail.node_errors).flatMap(e => e.errors.map(x => x.details || x.message)).join('；') : ''
    throw new Error((j.error || '提交失败') + (detail ? '：' + detail : ''))
  }
  return j
}

export async function job(pid) {
  return (await fetch(`/studio/api/job/${pid}`)).json()
}

export async function listCanvases() {
  return (await fetch('/studio/api/canvases')).json()
}

export async function loadCanvas(name) {
  return (await fetch(`/studio/api/canvas/${encodeURIComponent(name)}`)).json()
}

export async function saveCanvas(name, data) {
  await fetch(`/studio/api/canvas/${encodeURIComponent(name)}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
  })
}

export function kindOf(name) {
  const ext = name.split('.').pop().toLowerCase()
  if (['mp4', 'mov', 'webm', 'mkv', 'avi', 'm4v'].includes(ext)) return 'video'
  if (['mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac'].includes(ext)) return 'audio'
  if (['glb', 'gltf'].includes(ext)) return 'model'
  return 'image'
}
