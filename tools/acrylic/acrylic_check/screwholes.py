"""四隅にネジ穴（カット用の真円）を入れる。

・4 つとも同じ直径
・4 つとも角からの距離が同じ
になっていることを、書き込んだあとに実測して検証する。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import geometry as geo
from . import svgedit
from .svgdoc import SvgDocument

DEFAULT_LAYER_ID = "ネジ穴"


@dataclass
class HolePlan:
    rect_mm: tuple[float, float, float, float]   # x0, y0, x1, y1
    centers_mm: list[tuple[float, float]]
    diameter_mm: float
    inset_x_mm: float
    inset_y_mm: float
    source: str

    @property
    def corner_distance_mm(self) -> float:
        return math.hypot(self.inset_x_mm, self.inset_y_mm)


def reference_rect(doc: SvgDocument, mode: str = "outline") -> tuple[tuple[float, float, float, float], str]:
    """ネジ穴を配置する基準の矩形を mm で返す。"""
    if not doc.contours:
        raise ValueError("図形が 1 つも見つからないため基準矩形を決められません。")

    if mode == "outline":
        biggest = max(doc.contours, key=lambda c: abs(geo.signed_area(c.points)))
        x0, y0, x1, y1 = geo.bbox(biggest.points)
        return (x0, y0, x1, y1), f"最大面積の輪郭 {biggest.name}"

    if mode == "all":
        pts = np.vstack([c.points for c in doc.contours])
        x0, y0, x1, y1 = geo.bbox(pts)
        return (x0, y0, x1, y1), "全図形のバウンディングボックス"

    raise ValueError(f"不明な基準モード: {mode}")


def plan_holes(
    doc: SvgDocument,
    diameter_mm: float,
    inset_mm: float | None = None,
    inset_x_mm: float | None = None,
    inset_y_mm: float | None = None,
    rect_mm: tuple[float, float, float, float] | None = None,
    mode: str = "outline",
) -> HolePlan:
    if rect_mm is not None:
        rect = rect_mm
        source = "手入力の矩形"
    else:
        rect, source = reference_rect(doc, mode)

    ix = inset_x_mm if inset_x_mm is not None else inset_mm
    iy = inset_y_mm if inset_y_mm is not None else inset_mm
    if ix is None or iy is None:
        raise ValueError("角からの距離（inset）を指定してください。")

    x0, y0, x1, y1 = rect
    width = x1 - x0
    height = y1 - y0
    if 2 * ix + diameter_mm > width or 2 * iy + diameter_mm > height:
        raise ValueError(
            f"穴が基準矩形からはみ出します（矩形 {width:.2f}×{height:.2f}mm, "
            f"inset {ix}/{iy}mm, 直径 {diameter_mm}mm）。"
        )

    centers = [
        (x0 + ix, y0 + iy),
        (x1 - ix, y0 + iy),
        (x1 - ix, y1 - iy),
        (x0 + ix, y1 - iy),
    ]
    return HolePlan(rect, centers, diameter_mm, ix, iy, source)


def build_layer(doc: SvgDocument, plan: HolePlan, layer_id: str = DEFAULT_LAYER_ID,
                stroke: str = "#000000", stroke_width_user: float | None = None) -> str:
    """ネジ穴レイヤーの XML 断片。座標は元 SVG のユーザー単位に戻して書く。"""
    if abs(doc.mm_per_unit_x - doc.mm_per_unit_y) > 1e-9 * doc.mm_per_unit:
        raise ValueError(
            "SVG の X/Y の縮尺が違うため、真円のネジ穴を作れません。"
            "先に viewBox と width/height を揃えてください。"
        )
    per_unit = doc.mm_per_unit
    r_user = (plan.diameter_mm / 2.0) / per_unit
    sw = stroke_width_user if stroke_width_user is not None else max(r_user * 0.02, 1e-3)

    lines = [
        f'<g id="{layer_id}" fill="none" stroke="{stroke}" stroke-width="{sw:.4f}">'
    ]
    names = ["左上", "右上", "右下", "左下"]
    for (cx_mm, cy_mm), name in zip(plan.centers_mm, names):
        cx, cy = doc.mm_to_user(np.array([[cx_mm, cy_mm]]))[0]
        lines.append(
            f'<circle id="{layer_id}_{name}" cx="{cx:.6f}" cy="{cy:.6f}" r="{r_user:.6f}"/>'
        )
    lines.append("</g>")
    return "\n".join(lines)


def apply_to_file(
    src_text: str,
    doc: SvgDocument,
    plan: HolePlan,
    layer_id: str = DEFAULT_LAYER_ID,
    replace: bool = True,
    **layer_kwargs,
) -> str:
    text = src_text
    if replace:
        text, removed = svgedit.remove_group(text, layer_id)
        if removed:
            pass  # 既存のネジ穴レイヤーを貼り替える
    return svgedit.insert_before_root_close(text, build_layer(doc, plan, layer_id, **layer_kwargs))


def verify(doc: SvgDocument, layer_id: str = DEFAULT_LAYER_ID,
           rect_mm: tuple[float, float, float, float] | None = None) -> list[str]:
    """書き込み後の SVG を読み直して、4 穴が同一かを実測で確認する。"""
    holes = [c for c in doc.contours if c.element_id.startswith(f"{layer_id}_")]
    lines: list[str] = []
    if len(holes) != 4:
        lines.append(f"❌ ネジ穴が 4 つ見つかりません（{len(holes)} 個）。")
        return lines

    diameters = []
    centers = []
    for h in holes:
        # 円は「中心からの距離」で測る。外接矩形だと折れ線近似の分だけ
        # 小さく出てしまい、実際より 0.0003mm ほど小さい値になる。
        center = h.points.mean(axis=0)
        radii = np.hypot(h.points[:, 0] - center[0], h.points[:, 1] - center[1])
        diameters.append(2.0 * float(radii.mean()))
        centers.append(center)
        roundness = float(radii.max() - radii.min())
        if roundness > 1e-4:
            lines.append(
                f"⚠️ {h.element_id} が真円ではありません（半径のばらつき {roundness:.5f}mm）。"
            )

    d = np.array(diameters)
    lines.append(f"直径: {d.mean():.4f}mm（最大差 {d.max() - d.min():.6f}mm）")

    if rect_mm is None:
        pts = np.vstack([c.points for c in doc.contours if not c.element_id.startswith(f"{layer_id}_")])
        rect_mm = geo.bbox(pts)
    x0, y0, x1, y1 = rect_mm
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    dists = []
    for c in centers:
        nearest = min(corners, key=lambda k: math.hypot(c[0] - k[0], c[1] - k[1]))
        dists.append((abs(c[0] - nearest[0]), abs(c[1] - nearest[1])))
    dx = np.array([v[0] for v in dists])
    dy = np.array([v[1] for v in dists])
    lines.append(
        f"角からの距離: X {dx.mean():.4f}mm（最大差 {dx.max() - dx.min():.6f}mm） / "
        f"Y {dy.mean():.4f}mm（最大差 {dy.max() - dy.min():.6f}mm）"
    )
    if d.max() - d.min() < 1e-4 and dx.max() - dx.min() < 1e-4 and dy.max() - dy.min() < 1e-4:
        lines.append("✅ 4 つのネジ穴は同じ直径・同じ角からの距離です。")
    else:
        lines.append("❌ 4 つのネジ穴が揃っていません。")
    return lines
