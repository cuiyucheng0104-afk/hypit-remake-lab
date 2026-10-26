// Placement for new cards: never drop a card on top of an existing one.

export const SIZE = { asset: [280, 300], result: [320, 320], imageGen: [400, 720], videoGen: [400, 900], whitebox: [400, 460] }

const rect = n => {
  const [dw, dh] = SIZE[n.type] || [400, 500]
  return { x: n.position.x, y: n.position.y, w: n.measured?.width || dw, h: n.measured?.height || dh }
}

/** First free spot for a `type` card starting at `start`, stepping by `step` (flow coordinates). */
export function freeSpot(nodes, type, start, step) {
  const [w, h] = SIZE[type] || [400, 500]
  const hit = p => nodes.some(n => {
    const r = rect(n)
    return p.x < r.x + r.w + 30 && p.x + w + 30 > r.x && p.y < r.y + r.h + 30 && p.y + h + 30 > r.y
  })
  let p = { ...start }
  for (let i = 0; i < 80 && hit(p); i++) p = { x: p.x + step.x, y: p.y + step.y }
  return p
}
