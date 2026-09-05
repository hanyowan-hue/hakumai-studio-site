"""SVG を読み、すべての図形を「mm 単位の閉輪郭」として取り出す。

入稿データの検査なので、次を守る:
  * viewBox と width/height から実寸(mm)へ換算してから測る
  * 祖先の transform をすべて合成した CTM を適用する
  * 元ファイルは書き換えない（検査は読み取り専用）
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import numpy as np
from svgpathtools import parse_path

from .units import parse_length

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"

# セグメント 1 本あたりの折れ線分割数の目安（曲率の高いパスでも十分な密度）
FLATTEN_PER_SEGMENT = 48


def strip_ns(tag: str) -> str:
    return tag.split("}")[-1]


def identity() -> np.ndarray:
    return np.eye(3)


_TRANSFORM_RE = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)")


def parse_transform(text: str | None) -> np.ndarray:
    if not text:
        return identity()
    result = identity()
    for command, args in _TRANSFORM_RE.findall(text):
        values = [float(v) for v in re.split(r"[\s,]+", args.strip()) if v]
        m = identity()
        if command == "matrix" and len(values) == 6:
            a, b, c, d, e, f = values
            m = np.array([[a, c, e], [b, d, f], [0, 0, 1]], dtype=float)
        elif command == "translate" and values:
            tx = values[0]
            ty = values[1] if len(values) > 1 else 0.0
            m = np.array([[1, 0, tx], [0, 1, ty], [0, 0, 1]], dtype=float)
        elif command == "scale" and values:
            sx = values[0]
            sy = values[1] if len(values) > 1 else sx
            m = np.array([[sx, 0, 0], [0, sy, 0], [0, 0, 1]], dtype=float)
        elif command == "rotate" and values:
            ang = math.radians(values[0])
            c, s = math.cos(ang), math.sin(ang)
            rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)
            if len(values) >= 3:
                cx, cy = values[1], values[2]
                t1 = np.array([[1, 0, cx], [0, 1, cy], [0, 0, 1]], dtype=float)
                t2 = np.array([[1, 0, -cx], [0, 1, -cy], [0, 0, 1]], dtype=float)
                m = t1 @ rot @ t2
            else:
                m = rot
        elif command == "skewX" and values:
            m = np.array([[1, math.tan(math.radians(values[0])), 0], [0, 1, 0], [0, 0, 1]])
        elif command == "skewY" and values:
            m = np.array([[1, 0, 0], [math.tan(math.radians(values[0])), 1, 0], [0, 0, 1]])
        result = result @ m
    return result


def apply_matrix(points: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    if len(points) == 0:
        return points
    hom = np.column_stack([points, np.ones(len(points))])
    return (hom @ matrix.T)[:, :2]


@dataclass
class Contour:
    """図形 1 つ（複合パスならサブパス 1 本）。座標はすべて mm。"""

    index: int
    element_id: str
    tag: str
    sub_index: int | None
    label_path: tuple[str, ...]
    points: np.ndarray
    closed: bool
    depth: int = 0                    # 入れ子の深さ（0 = 一番外側）
    parent: int | None = None
    children: list[int] = field(default_factory=list)

    @property
    def name(self) -> str:
        base = self.element_id or self.tag
        if self.sub_index is None:
            return base
        return f"{base}_sub{self.sub_index:03d}"


@dataclass
class SvgDocument:
    path: str
    tree: ET.ElementTree
    root: ET.Element
    mm_per_unit_x: float
    mm_per_unit_y: float
    to_mm: np.ndarray            # ユーザー単位 → mm の変換行列
    contours: list[Contour]
    warnings: list[str]

    @property
    def mm_per_unit(self) -> float:
        return (self.mm_per_unit_x + self.mm_per_unit_y) / 2.0

    def mm_to_user(self, points_mm: np.ndarray) -> np.ndarray:
        """mm 座標を元 SVG のユーザー単位へ戻す（確認用レイヤーの描画に使う）。"""
        return apply_matrix(np.asarray(points_mm, dtype=float), np.linalg.inv(self.to_mm))


def _viewport_scale(root: ET.Element, dpi: float, warnings: list[str]) -> tuple[float, float]:
    """ユーザー単位 1 あたりの mm を求める。"""
    vb = root.attrib.get("viewBox")
    w = parse_length(root.attrib.get("width"))
    h = parse_length(root.attrib.get("height"))

    if vb:
        nums = [float(v) for v in re.split(r"[\s,]+", vb.strip()) if v]
        if len(nums) == 4 and nums[2] > 0 and nums[3] > 0:
            sx = sy = None
            if w is not None and not w.is_percent:
                sx = w.to_mm(dpi) / nums[2]
            if h is not None and not h.is_percent:
                sy = h.to_mm(dpi) / nums[3]
            if sx is None and sy is None:
                warnings.append(
                    "width/height が絶対長でないため、viewBox の 1 単位 = 1px として mm 換算しました。"
                )
                return 25.4 / dpi, 25.4 / dpi
            sx = sx if sx is not None else sy
            sy = sy if sy is not None else sx
            if abs(sx - sy) > 1e-6 * max(abs(sx), abs(sy)):
                warnings.append(
                    f"viewBox と width/height の縦横比が一致していません "
                    f"(X {sx:.6f} mm/unit, Y {sy:.6f} mm/unit)。データが縦横で異なる倍率で"
                    "表示される可能性があります。"
                )
            return sx, sy
        warnings.append("viewBox の値が不正なため 1 単位 = 1px として扱います。")

    return 25.4 / dpi, 25.4 / dpi


def _flatten_path(d: str) -> list[tuple[np.ndarray, bool]]:
    """path の d をサブパスごとの折れ線に展開する。"""
    out: list[tuple[np.ndarray, bool]] = []
    path_obj = parse_path(d)
    for subpath in path_obj.continuous_subpaths():
        pts: list[list[float]] = []
        for seg in subpath:
            for i in range(FLATTEN_PER_SEGMENT):
                z = seg.point(i / FLATTEN_PER_SEGMENT)
                pts.append([z.real, z.imag])
        if not pts:
            continue
        end = subpath[-1].point(1.0)
        pts.append([end.real, end.imag])
        arr = np.asarray(pts, dtype=float)
        # 終点と始点が一致していれば重複を落とす
        if len(arr) > 1 and np.allclose(arr[0], arr[-1], atol=1e-9):
            arr = arr[:-1]
        out.append((arr, bool(subpath.isclosed())))
    return out


def _rounded_rect(x, y, w, h, rx, ry) -> np.ndarray:
    if rx <= 0 and ry <= 0:
        return np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=float)
    rx = min(rx if rx > 0 else ry, w / 2.0)
    ry = min(ry if ry > 0 else rx, h / 2.0)
    steps = 16
    pts: list[list[float]] = []
    corners = [
        (x + w - rx, y + ry, -math.pi / 2, 0.0),
        (x + w - rx, y + h - ry, 0.0, math.pi / 2),
        (x + rx, y + h - ry, math.pi / 2, math.pi),
        (x + rx, y + ry, math.pi, 3 * math.pi / 2),
    ]
    for cx, cy, a0, a1 in corners:
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            pts.append([cx + rx * math.cos(a), cy + ry * math.sin(a)])
    return np.asarray(pts, dtype=float)


def _ellipse(cx, cy, rx, ry, steps=256) -> np.ndarray:
    th = np.linspace(0, 2 * np.pi, steps, endpoint=False)
    return np.column_stack([cx + rx * np.cos(th), cy + ry * np.sin(th)])


def _num(elem: ET.Element, key: str, default: float = 0.0) -> float:
    length = parse_length(elem.attrib.get(key))
    return length.value if length is not None else default


def _label(elem: ET.Element) -> str:
    return (
        elem.attrib.get(f"{{{INKSCAPE_NS}}}label")
        or elem.attrib.get("id")
        or ""
    )


def _hidden(elem: ET.Element) -> bool:
    if elem.attrib.get("display") == "none":
        return True
    style = elem.attrib.get("style", "")
    return "display:none" in style.replace(" ", "")


def load(
    svg_path: str,
    dpi: float = 96.0,
    layer_pattern: str | None = None,
    include_open: bool = False,
) -> SvgDocument:
    """SVG を読み込み、mm 単位の輪郭一覧を返す。

    layer_pattern: 祖先グループ名 / 要素 id に対する正規表現。
                   指定すると一致した図形だけを対象にする（例: 'カット|cut'）。
    """
    warnings: list[str] = []
    tree = ET.parse(svg_path)
    root = tree.getroot()
    mm_x, mm_y = _viewport_scale(root, dpi, warnings)

    # viewBox のオフセットも考慮した、ユーザー単位 → mm の行列
    vb = root.attrib.get("viewBox")
    ox = oy = 0.0
    if vb:
        nums = [float(v) for v in re.split(r"[\s,]+", vb.strip()) if v]
        if len(nums) == 4:
            ox, oy = nums[0], nums[1]
    to_mm = np.array([[mm_x, 0, -ox * mm_x], [0, mm_y, -oy * mm_y], [0, 0, 1]], dtype=float)

    by_id: dict[str, ET.Element] = {}
    for elem in root.iter():
        eid = elem.attrib.get("id")
        if eid:
            by_id.setdefault(eid, elem)

    pattern = re.compile(layer_pattern) if layer_pattern else None
    contours: list[Contour] = []
    counter = [0]

    def matches_layer(labels: tuple[str, ...], eid: str) -> bool:
        if pattern is None:
            return True
        return any(pattern.search(x) for x in (*labels, eid) if x)

    def add(points_user, closed, elem, ctm, labels, sub_index=None):
        if len(points_user) < 3:
            return
        if not closed and not include_open:
            warnings.append(
                f"開いたパスをスキップしました: id={elem.attrib.get('id','')!r} "
                f"sub={sub_index}（カット線は閉じている必要があります）"
            )
            return
        pts = apply_matrix(np.asarray(points_user, dtype=float), to_mm @ ctm)
        counter[0] += 1
        contours.append(
            Contour(
                index=counter[0],
                element_id=elem.attrib.get("id", ""),
                tag=strip_ns(elem.tag),
                sub_index=sub_index,
                label_path=labels,
                points=pts,
                closed=closed,
            )
        )

    def walk(elem: ET.Element, ctm: np.ndarray, labels: tuple[str, ...], depth: int):
        if depth > 64:
            warnings.append("use の参照が深すぎるため打ち切りました。")
            return
        tag = strip_ns(elem.tag)
        if tag in ("defs", "symbol", "clipPath", "mask", "marker") and depth == 0:
            return
        if _hidden(elem):
            return

        ctm = ctm @ parse_transform(elem.attrib.get("transform"))
        if tag == "g":
            name = _label(elem)
            if name:
                labels = (*labels, name)

        eid = elem.attrib.get("id", "")

        if tag == "path":
            d = elem.attrib.get("d", "")
            if d.strip() and matches_layer(labels, eid):
                try:
                    for i, (pts, closed) in enumerate(_flatten_path(d), start=1):
                        add(pts, closed, elem, ctm, labels, sub_index=i)
                except Exception as exc:  # パス構文エラーは握りつぶさず報告する
                    warnings.append(f"path 解析エラー id={eid!r}: {exc}")
        elif tag == "rect" and matches_layer(labels, eid):
            add(
                _rounded_rect(
                    _num(elem, "x"), _num(elem, "y"),
                    _num(elem, "width"), _num(elem, "height"),
                    _num(elem, "rx", -1.0), _num(elem, "ry", -1.0),
                ),
                True, elem, ctm, labels,
            )
        elif tag == "circle" and matches_layer(labels, eid):
            r = _num(elem, "r")
            add(_ellipse(_num(elem, "cx"), _num(elem, "cy"), r, r), True, elem, ctm, labels)
        elif tag == "ellipse" and matches_layer(labels, eid):
            add(
                _ellipse(_num(elem, "cx"), _num(elem, "cy"), _num(elem, "rx"), _num(elem, "ry")),
                True, elem, ctm, labels,
            )
        elif tag in ("polygon", "polyline") and matches_layer(labels, eid):
            nums = [float(v) for v in re.split(r"[\s,]+", elem.attrib.get("points", "").strip()) if v]
            if len(nums) >= 6:
                arr = np.asarray(nums[: len(nums) // 2 * 2], dtype=float).reshape(-1, 2)
                add(arr, tag == "polygon", elem, ctm, labels)
        elif tag == "use":
            href = (
                elem.attrib.get(f"{{{XLINK_NS}}}href")
                or elem.attrib.get("href")
                or ""
            )
            target = by_id.get(href.lstrip("#")) if href.startswith("#") else None
            if target is None:
                warnings.append(f"use の参照先が見つかりません: {href!r}")
            else:
                offset = np.array(
                    [[1, 0, _num(elem, "x")], [0, 1, _num(elem, "y")], [0, 0, 1]], dtype=float
                )
                walk(target, ctm @ offset, labels, depth + 1)

        for child in list(elem):
            walk(child, ctm, labels, depth + 1)

    walk(root, identity(), (), 0)
    _build_nesting(contours)
    return SvgDocument(svg_path, tree, root, mm_x, mm_y, to_mm, contours, warnings)


def _build_nesting(contours: list[Contour]) -> None:
    """輪郭の入れ子関係（外形と穴）を求める。

    「一番外側の板の外形」と「パーツ」と「パーツに開いた穴」を
    同列に比較してしまう事故を防ぐため。
    """
    from .geometry import point_in_polygon, signed_area

    areas = [abs(signed_area(c.points)) for c in contours]
    order = sorted(range(len(contours)), key=lambda i: areas[i], reverse=True)

    for pos, i in enumerate(order):
        ci = contours[i]
        # 自分より面積の大きい輪郭のうち、最も小さいものが親
        best = None
        best_area = math.inf
        for j in order[:pos]:
            cj = contours[j]
            x0, y0, x1, y1 = (
                cj.points[:, 0].min(), cj.points[:, 1].min(),
                cj.points[:, 0].max(), cj.points[:, 1].max(),
            )
            p = ci.points[0]
            if not (x0 <= p[0] <= x1 and y0 <= p[1] <= y1):
                continue
            if point_in_polygon(p, cj.points) and areas[j] < best_area:
                best = j
                best_area = areas[j]
        if best is not None:
            ci.parent = contours[best].index
            ci.depth = contours[best].depth + 1
            contours[best].children.append(ci.index)
