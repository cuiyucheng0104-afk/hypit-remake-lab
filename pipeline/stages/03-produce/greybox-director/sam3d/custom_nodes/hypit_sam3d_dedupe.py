"""SAM3D Body 去重影节点（hypit-remake-lab）。

SAM3 视频追踪在快动作时，旧追踪的遮罩跟不上，新检测与它的重叠不到 50% 就被当成新人加入，
同一个人于是被追成多条轨迹（T2 群战 57 帧里平均每帧 61 个人偶，实际约 7 人），渲染出重影；
跟丢后留在原地的旧轨迹就是残影。

本节点放在 Smooth 之后、Render 之前：
1. 用每个人偶的 2D 关键点算出它在画面里的框。
2. 每一帧里，RT-DETR 找到的每个真人框只认领一个最贴合的人偶（重叠至少 min_detection_iou），叠在同一个人身上的其余人偶不要。
3. 检测器漏掉某帧时（动作模糊），若这条轨迹前后 hold_frames 帧内都被认领过，且不和已保留的人偶重叠，就补回这一帧，避免闪烁。
跟丢后留下的残影往后不会再被认领，所以不会被补回。
（不按「重叠就合并」做轨迹分组：那样会连锁，群戏里所有人会被并成一个，实测踩过。）

只改渲染用的数据；导出 GLB 请接去重前的数据，保持每个人的编号前后一致。
"""
import logging

import numpy as np


def _kp_box(person):
    kp = person.get("pred_keypoints_2d")
    if kp is not None:
        kp = np.asarray(kp, dtype=np.float32).reshape(-1, 2)
        kp = kp[np.isfinite(kp).all(axis=1)]
        if len(kp) >= 4:
            b = np.array([kp[:, 0].min(), kp[:, 1].min(), kp[:, 0].max(), kp[:, 1].max()], dtype=np.float32)
            if b[2] > b[0] and b[3] > b[1]:
                return b
    bb = person.get("bbox")
    return None if bb is None else np.asarray(bb, dtype=np.float32).reshape(4)


def _iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return float(inter / ua) if ua > 0 else 0.0


class SAM3DBodyDedupe:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mhr_pose_data": ("MHR_POSE_DATA",),
                "overlap_iou": ("FLOAT", {"default": 0.45, "min": 0.05, "max": 0.95, "step": 0.05,
                                          "tooltip": "补帧时，候选人偶与已保留人偶的框重叠超过这个比例就不补（防止补回重影）。"}),
                "min_detection_iou": ("FLOAT", {"default": 0.3, "min": 0.05, "max": 0.9, "step": 0.05,
                                                "tooltip": "人偶的框与真人框重叠至少这么多，才算被这个真人认领。重影多就调高，漏人就调低。"}),
                "hold_frames": ("INT", {"default": 4, "min": 0, "max": 30,
                                        "tooltip": "检测器漏掉某帧时，前后各这么多帧内这条轨迹都被认领过，就把这一帧补回来。人偶闪烁就调大。"}),
            },
            "optional": {
                "bboxes": ("BOUNDING_BOX", {"tooltip": "接 RT-DETR Detect 的 bboxes（逐帧真人框）。不接时退化为按框大小去重。"}),
            },
        }

    RETURN_TYPES = ("MHR_POSE_DATA",)
    RETURN_NAMES = ("mhr_pose_data",)
    FUNCTION = "run"
    CATEGORY = "image/detection"
    DESCRIPTION = "每个真人框只认领一个人偶，去掉重影和残影；检测器偶尔漏帧时按轨迹补回，不闪烁。"

    def run(self, mhr_pose_data, overlap_iou, min_detection_iou, hold_frames, bboxes=None):
        from comfy_extras.nodes_sam3d_body import _per_frame_bboxes_from_detections

        frames = mhr_pose_data["frames"]
        F = len(frames)
        dets = _per_frame_bboxes_from_detections(bboxes, F) if bboxes else None
        boxes = [[None if p is None else _kp_box(p) for p in persons] for persons in frames]
        before = sum(b is not None for fb in boxes for b in fb)

        kept = [set() for _ in range(F)]
        for fi in range(F):
            fb = boxes[fi]
            if dets is not None:
                # each detected person claims the single best-fitting figure
                det = dets[fi].cpu().numpy()
                for d in det:
                    best, best_iou = None, min_detection_iou
                    for pid, b in enumerate(fb):
                        if b is not None and pid not in kept[fi]:
                            v = _iou(b, d)
                            if v >= best_iou:
                                best, best_iou = pid, v
                    if best is not None:
                        kept[fi].add(best)
            else:
                # no detector: plain NMS, larger figure wins
                order = sorted((pid for pid, b in enumerate(fb) if b is not None),
                               key=lambda k: (fb[k][2] - fb[k][0]) * (fb[k][3] - fb[k][1]), reverse=True)
                for pid in order:
                    if all(_iou(fb[pid], fb[j]) <= overlap_iou for j in kept[fi]):
                        kept[fi].add(pid)

        claimed = [set(k) for k in kept]
        filled = 0
        if dets is not None and hold_frames > 0:
            # bridge detector misses: a track claimed both before and after this frame stays, unless it lands on a kept figure
            for fi in range(F):
                for pid, b in enumerate(boxes[fi]):
                    if b is None or pid in kept[fi]:
                        continue
                    before_ok = any(pid in claimed[j] for j in range(max(0, fi - hold_frames), fi))
                    after_ok = any(pid in claimed[j] for j in range(fi + 1, min(F, fi + hold_frames + 1)))
                    if before_ok and after_ok and all(_iou(b, boxes[fi][j]) <= overlap_iou for j in kept[fi]):
                        kept[fi].add(pid); filled += 1

        out_frames = [[frames[fi][pid] for pid in sorted(kept[fi])] for fi in range(F)]
        after = sum(len(f) for f in out_frames)
        logging.info("SAM3D dedupe: %d frames, figures %d -> %d (%.1f per frame, %d bridged)",
                     F, before, after, after / max(F, 1), filled)
        out = dict(mhr_pose_data)
        out["frames"] = out_frames
        return (out,)


NODE_CLASS_MAPPINGS = {"HypitSAM3DBodyDedupe": SAM3DBodyDedupe}
NODE_DISPLAY_NAME_MAPPINGS = {"HypitSAM3DBodyDedupe": "SAM3D 人偶去重影（Hypit）"}
