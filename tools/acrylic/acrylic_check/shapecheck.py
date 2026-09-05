"""同じ形であるべきパーツどうしのカット線を突き合わせる。

判定は 3 つに分けて出す:
  拡大縮小  … 最適スケールが 1 からどれだけ離れているか
  歪み      … 相似変換では消せない残差（実寸 mm）
  鏡像      … 裏返さないと合わない（= 同じ穴にはまらない）
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import geometry as geo
from .svgdoc import Contour, SvgDocument

DEFAULT_SHAPE_TOL = 0.02      # グルーピング用（無次元）
DEFAULT_DEV_TOL_MM = 0.10     # 実寸のズレ許容量
DEFAULT_SCALE_TOL = 0.002     # 0.2%
DEFAULT_MAX_SCALE_RATIO = 1.25


@dataclass
class MemberResult:
    contour: Contour
    fit: geo.FitResult
    major_mm: float
    minor_mm: float
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


@dataclass
class ShapeGroup:
    number: int
    depth: int
    reference: Contour
    members: list[MemberResult]
    cohesion: float               # グループ内の最大形状距離（大きいと分類が怪しい）

    @property
    def ng(self) -> list[MemberResult]:
        return [m for m in self.members if not m.ok]


@dataclass
class ShapeReport:
    groups: list[ShapeGroup]
    singles: list[ShapeGroup]
    warnings: list[str]

    @property
    def ng_members(self) -> list[MemberResult]:
        out: list[MemberResult] = []
        for g in self.groups:
            out.extend(g.ng)
        return out


def _prefilter(a: Contour, b: Contour, max_ratio: float) -> bool:
    """全ペアで位置合わせを回すのは無駄なので、寸法比で明らかに違うものを落とす。"""
    pa = geo.perimeter(a.points)
    pb = geo.perimeter(b.points)
    if pa <= 0 or pb <= 0:
        return False
    ratio = max(pa / pb, pb / pa)
    return ratio <= max_ratio


def _union_find(n: int):
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    return find, union


def analyze(
    doc: SvgDocument,
    shape_tol: float = DEFAULT_SHAPE_TOL,
    dev_tol_mm: float = DEFAULT_DEV_TOL_MM,
    scale_tol: float = DEFAULT_SCALE_TOL,
    max_scale_ratio: float = DEFAULT_MAX_SCALE_RATIO,
    allow_mirror: bool = False,
    group_by_depth: bool = True,
    samples: int = geo.DEFAULT_SAMPLES,
) -> ShapeReport:
    contours = [c for c in doc.contours if len(c.points) >= 3]
    warnings: list[str] = list(doc.warnings)
    n = len(contours)
    if n == 0:
        return ShapeReport([], [], warnings + ["比較できる閉じた輪郭がありません。"])

    resampled = [
        geo.resample_closed(geo.normalize_orientation(c.points), samples) for c in contours
    ]

    dist = np.full((n, n), math.inf)
    np.fill_diagonal(dist, 0.0)
    find, union = _union_find(n)

    for i in range(n):
        for j in range(i + 1, n):
            if group_by_depth and contours[i].depth != contours[j].depth:
                continue
            if not _prefilter(contours[i], contours[j], max_scale_ratio):
                continue
            d = _shape_distance(resampled[i], resampled[j])
            dist[i, j] = dist[j, i] = d
            if d <= shape_tol:
                union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)

    groups: list[ShapeGroup] = []
    singles: list[ShapeGroup] = []
    for number, idxs in enumerate(
        sorted(clusters.values(), key=lambda v: (-len(v), v[0])), start=1
    ):
        sub = dist[np.ix_(idxs, idxs)]
        finite = np.where(np.isfinite(sub), sub, 0.0)
        medoid_local = int(np.argmin(finite.sum(axis=1)))
        ref_idx = idxs[medoid_local]
        cohesion = float(finite.max()) if len(idxs) > 1 else 0.0

        members: list[MemberResult] = []
        for k in idxs:
            fit = geo.fit_contours(
                contours[ref_idx].points, contours[k].points,
                n=samples, allow_mirror=True, mirror_margin=dev_tol_mm,
            )
            major, minor, _ = geo.min_area_rect(contours[k].points)
            issues: list[str] = []
            if k != ref_idx:
                if abs(fit.scale - 1.0) > scale_tol:
                    issues.append(
                        f"拡大縮小 {(fit.scale - 1.0) * 100:+.3f}%（許容 ±{scale_tol * 100:.3f}%）"
                    )
                if fit.max_dev > dev_tol_mm:
                    issues.append(
                        f"形のズレ 最大 {fit.max_dev:.3f}mm（許容 {dev_tol_mm:.3f}mm）"
                    )
                if fit.mirrored and not allow_mirror:
                    issues.append("鏡像（裏返し）")
            members.append(MemberResult(contours[k], fit, major, minor, issues))

        group = ShapeGroup(number, contours[ref_idx].depth, contours[ref_idx], members, cohesion)
        (singles if len(idxs) == 1 else groups).append(group)
        if len(idxs) > 1 and cohesion > shape_tol * 1.5:
            warnings.append(
                f"形{number}: グループ内の形状差が大きめです（最大 {cohesion:.4f}）。"
                "NG のパーツが混ざっているか、別の形が同じグループに入っています。"
            )

    for i, g in enumerate(groups, start=1):
        g.number = i
    for i, g in enumerate(singles, start=len(groups) + 1):
        g.number = i

    return ShapeReport(groups, singles, warnings)


def _shape_distance(pa: np.ndarray, pb: np.ndarray) -> float:
    """サイズ非依存の形状距離。位置合わせ済み配列を受け取る軽量版。"""
    za = pa[:, 0] + 1j * pa[:, 1]
    zb = pb[:, 0] + 1j * pb[:, 1]
    za = za - za.mean()
    zb = zb - zb.mean()
    ref = float(np.sqrt(np.mean(np.abs(za) ** 2)))
    if ref <= 1e-12:
        return math.inf

    best = math.inf
    for cand in (zb, np.conj(zb[::-1]).copy()):
        corr = np.fft.fft(np.fft.fft(za) * np.conj(np.fft.fft(cand))) / len(za)
        idx = int(np.argmax(np.abs(corr)))
        denom = float(np.sum(np.abs(cand) ** 2))
        if denom <= 1e-18:
            continue
        alpha = corr[idx] / denom
        shifted = np.roll(cand, -idx)
        diff = np.abs(za - alpha * shifted)
        best = min(best, float(diff.max()) / ref)
    return best


# ---------------------------------------------------------------------------
# NG 位置の確認用オーバーレイ
# ---------------------------------------------------------------------------

def build_overlay(doc: SvgDocument, ng: list[MemberResult], layer_id: str = "検査結果_NG") -> str:
    """NG 箇所を赤で重ねるレイヤーの XML 断片を作る。

    元データのパスは一切書き換えず、上に重ねるだけにする。
    （サブパスを分解して d を書き直すと、丸め誤差で
      検査対象そのものを変えてしまうため）
    """
    parts = [
        f'<g id="{layer_id}" fill="none" stroke="#ff0000" '
        f'stroke-width="1" stroke-linejoin="round" vector-effect="non-scaling-stroke">'
    ]
    for m in ng:
        user_pts = doc.mm_to_user(m.contour.points)
        d = "M " + " L ".join(f"{x:.4f},{y:.4f}" for x, y in user_pts) + " Z"
        title = f"{m.contour.name}: " + " / ".join(m.issues)
        parts.append(f'<path id="NG_{m.contour.index:03d}" d="{d}"><title>{_esc(title)}</title></path>')
    parts.append("</g>")
    return "\n".join(parts)


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
