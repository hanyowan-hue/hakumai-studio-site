"""閉輪郭どうしを「実寸で」突き合わせるための幾何処理。

考え方
------
輪郭を弧長で等間隔に N 点サンプリングし、複素数列 z[k] とみなす。
2 つの輪郭 a, b の間の最適な相似変換（平行移動・回転・拡大縮小）と
始点のズレ（巡回シフト）は、巡回相互相関の最大値として閉形式で求まる。

    C[m] = Σ_k z_a[k] · conj(z_b[k+m])

|C[m]| を最大にする m が最適な始点合わせ、
α = C[m] / Σ|z_b|² が最適な「スケール×回転」（|α| がスケール、arg(α) が回転角）。

これにより
  * ぴったり重ねたときの最大ズレ量（mm）  → 歪みの検出
  * 最適スケール |α|                      → 拡大縮小の検出
  * 鏡像かどうか                          → 裏返しパーツの検出
を分離して報告できる。バウンディングボックスの寸法比較では
歪み・鏡像を検出できないため、この方法を採る。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

DEFAULT_SAMPLES = 512


# ---------------------------------------------------------------------------
# 基本量
# ---------------------------------------------------------------------------

def signed_area(pts: np.ndarray) -> float:
    """閉多角形の符号付き面積。正 = 反時計回り（y 上向き座標系での定義）。"""
    if len(pts) < 3:
        return 0.0
    x = pts[:, 0]
    y = pts[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def perimeter(pts: np.ndarray, closed: bool = True) -> float:
    if len(pts) < 2:
        return 0.0
    d = np.diff(pts, axis=0)
    total = float(np.sum(np.hypot(d[:, 0], d[:, 1])))
    if closed:
        total += float(np.hypot(*(pts[0] - pts[-1])))
    return total


def bbox(pts: np.ndarray) -> tuple[float, float, float, float]:
    return (
        float(pts[:, 0].min()),
        float(pts[:, 1].min()),
        float(pts[:, 0].max()),
        float(pts[:, 1].max()),
    )


def normalize_orientation(pts: np.ndarray) -> np.ndarray:
    """常に反時計回りに揃える。鏡像判定を意味のあるものにするため。"""
    return pts if signed_area(pts) >= 0 else pts[::-1].copy()


def resample_closed(pts: np.ndarray, n: int = DEFAULT_SAMPLES) -> np.ndarray:
    """閉輪郭を弧長で等間隔に n 点へ再サンプリングする。

    svgpathtools の point(t) は「セグメントごとの等パラメータ」であって
    等弧長ではない。そのまま点対応を取ると、セグメント数や
    分割位置の違うパスどうしで対応がずれるので、必ずここを通す。
    """
    if len(pts) < 3:
        return np.empty((0, 2))
    closed_pts = np.vstack([pts, pts[0]])
    seg = np.hypot(*np.diff(closed_pts, axis=0).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    if total <= 0:
        return np.empty((0, 2))
    targets = np.linspace(0.0, total, n, endpoint=False)
    x = np.interp(targets, cum, closed_pts[:, 0])
    y = np.interp(targets, cum, closed_pts[:, 1])
    return np.column_stack([x, y])


def min_area_rect(pts: np.ndarray) -> tuple[float, float, float]:
    """回転キャリパーによる最小面積外接矩形 (長辺, 短辺, 角度rad)。

    PCA の固有ベクトルは、5 弁の花のような回転対称に近い形では
    共分散行列がほぼ等方になり、向きが数値誤差で暴れる。
    そのため PCA ではなく凸包＋回転キャリパーを使う。
    """
    hull = convex_hull(pts)
    if len(hull) < 3:
        w = float(np.ptp(pts[:, 0]))
        h = float(np.ptp(pts[:, 1]))
        return max(w, h), min(w, h), 0.0

    edges = np.roll(hull, -1, axis=0) - hull
    angles = np.arctan2(edges[:, 1], edges[:, 0])
    angles = np.unique(np.mod(angles, np.pi / 2))

    best = None
    for a in angles:
        c, s = math.cos(-a), math.sin(-a)
        rot = hull @ np.array([[c, -s], [s, c]]).T
        w = float(np.ptp(rot[:, 0]))
        h = float(np.ptp(rot[:, 1]))
        area = w * h
        if best is None or area < best[0]:
            best = (area, max(w, h), min(w, h), float(a))
    return best[1], best[2], best[3]


def convex_hull(pts: np.ndarray) -> np.ndarray:
    """Andrew's monotone chain。"""
    if len(pts) < 3:
        return pts.copy()
    p = np.unique(np.round(pts, 9), axis=0)
    p = p[np.lexsort((p[:, 1], p[:, 0]))]
    if len(p) < 3:
        return p

    def half(points):
        stack: list[np.ndarray] = []
        for pt in points:
            while len(stack) >= 2:
                o, a = stack[-2], stack[-1]
                cross = (a[0] - o[0]) * (pt[1] - o[1]) - (a[1] - o[1]) * (pt[0] - o[0])
                if cross <= 0:
                    stack.pop()
                else:
                    break
            stack.append(pt)
        return stack

    lower = half(p)
    upper = half(p[::-1])
    return np.array(lower[:-1] + upper[:-1])


def point_in_polygon(point: np.ndarray, poly: np.ndarray) -> bool:
    """レイキャスティング。輪郭の入れ子（穴）判定に使う。"""
    x, y = float(point[0]), float(point[1])
    xs = poly[:, 0]
    ys = poly[:, 1]
    xs2 = np.roll(xs, -1)
    ys2 = np.roll(ys, -1)
    crosses = (ys > y) != (ys2 > y)
    with np.errstate(divide="ignore", invalid="ignore"):
        xints = xs + (y - ys) * (xs2 - xs) / (ys2 - ys)
    hit = crosses & (x < xints)
    return bool(np.count_nonzero(hit) % 2 == 1)


# ---------------------------------------------------------------------------
# 位置合わせ
# ---------------------------------------------------------------------------

@dataclass
class FitResult:
    """b を a に最良で重ねたときの結果。長さの単位は入力と同じ（本ツールでは mm）。"""

    scale: float          # b が a の何倍か（1.0 なら拡大縮小なし）
    angle_deg: float      # 最適回転角
    mirrored: bool        # 鏡像にしないと合わないか
    max_dev: float        # 拡大縮小を許さず重ねたときの最大ズレ
    rms_dev: float        # 同 RMS
    max_dev_scaled: float # 最適スケールを掛けて重ねたときの最大ズレ（= 純粋な歪み量）
    rms_dev_scaled: float
    shift: float          # 始点のズレ（サンプル数単位）

    @property
    def scale_ppm(self) -> float:
        return (self.scale - 1.0) * 1e6


def _cyclic_correlation(za: np.ndarray, zb: np.ndarray) -> np.ndarray:
    """C[m] = Σ_k za[k] · conj(zb[k+m]) を FFT で求める。"""
    n = len(za)
    fa = np.fft.fft(za)
    fb = np.fft.fft(zb)
    return np.fft.fft(fa * np.conj(fb)) / n


def _fractional_shift(z: np.ndarray, delta: float) -> np.ndarray:
    """帯域制限補間で z を delta サンプルだけ巡回シフトする。"""
    n = len(z)
    f = np.fft.fft(z)
    freqs = np.fft.fftfreq(n) * n
    return np.fft.ifft(f * np.exp(2j * np.pi * freqs * delta / n))


def _refine_peak(mag: np.ndarray, idx: int) -> float:
    """|C| のピーク位置をパラボラ補間でサブサンプル精度にする。"""
    n = len(mag)
    y0 = mag[(idx - 1) % n]
    y1 = mag[idx]
    y2 = mag[(idx + 1) % n]
    denom = y0 - 2.0 * y1 + y2
    if abs(denom) < 1e-15:
        return float(idx)
    return float(idx + 0.5 * (y0 - y2) / denom)


def _fit_one(za: np.ndarray, zb: np.ndarray) -> tuple[float, float, float, np.ndarray]:
    """1 通りの向きについて最適合わせを行い (スケール, 回転rad, シフト, 変換後zb) を返す。"""
    corr = _cyclic_correlation(za, zb)
    mag = np.abs(corr)
    idx = int(np.argmax(mag))
    shift = _refine_peak(mag, idx)

    zb_shifted = _fractional_shift(zb, shift)
    denom = float(np.sum(np.abs(zb_shifted) ** 2))
    if denom <= 1e-18:
        return 1.0, 0.0, shift, zb_shifted
    alpha = complex(np.vdot(zb_shifted, za)) / denom  # vdot は第1引数を共役
    # alpha は「b を a に合わせる」係数なので、報告用は逆数（b が a の何倍か）にする
    size_ratio = 1.0 / abs(alpha) if abs(alpha) > 1e-18 else float("inf")
    return size_ratio, float(np.angle(alpha)), shift, zb_shifted


def fit_contours(
    a: np.ndarray,
    b: np.ndarray,
    n: int = DEFAULT_SAMPLES,
    allow_mirror: bool = True,
    mirror_margin: float = 0.0,
) -> FitResult:
    """輪郭 b を輪郭 a に重ね、ズレ量・スケール・鏡像を求める。

    mirror_margin: そのままの向きでこの値（mm）以内に収まっているなら、
        たとえ鏡像のほうが数値的にわずかに良くても「鏡像ではない」と判定する。
        左右対称なパーツ（葉など）を鏡像と誤判定しないためのもの。
    """
    pa = resample_closed(normalize_orientation(a), n)
    pb = resample_closed(normalize_orientation(b), n)
    if len(pa) != n or len(pb) != n:
        return FitResult(1.0, 0.0, False, math.inf, math.inf, math.inf, math.inf, 0.0)

    za = pa[:, 0] + 1j * pa[:, 1]
    zb = pb[:, 0] + 1j * pb[:, 1]
    za = za - za.mean()
    zb = zb - zb.mean()

    candidates = [(False, zb)]
    if allow_mirror:
        # 鏡像は複素共役。向きが反転するので順序も反転して CCW に戻す。
        candidates.append((True, np.conj(zb[::-1]).copy()))

    results: list[FitResult] = []
    for mirrored, cand in candidates:
        size_ratio, angle, shift, cand_shifted = _fit_one(za, cand)
        rot = np.exp(1j * angle)
        inv_scale = 1.0 / size_ratio if size_ratio not in (0.0, float("inf")) else 1.0
        # スケールを 1 に固定した剛体当てはめ（実際に「はまるか」はこちら）
        diff_rigid = np.abs(za - rot * cand_shifted)
        # 最適スケールも許した当てはめ（残差 = 相似変換で消せない歪み）
        diff_scaled = np.abs(za - inv_scale * rot * cand_shifted)
        result = FitResult(
            scale=size_ratio,
            angle_deg=math.degrees(angle),
            mirrored=mirrored,
            max_dev=float(diff_rigid.max()),
            rms_dev=float(np.sqrt(np.mean(diff_rigid ** 2))),
            max_dev_scaled=float(diff_scaled.max()),
            rms_dev_scaled=float(np.sqrt(np.mean(diff_scaled ** 2))),
            shift=shift,
        )
        results.append(result)

    non_mirror = results[0]
    if len(results) < 2:
        return non_mirror
    mirror = results[1]
    # 左右対称なパーツは鏡像にしても一致する。そのままの向きで十分合っているなら
    # 鏡像とは呼ばない。明確に鏡像のほうが良いときだけ倒す。
    if non_mirror.max_dev > mirror_margin and mirror.max_dev < non_mirror.max_dev * 0.5:
        return mirror
    return non_mirror


def shape_distance(a: np.ndarray, b: np.ndarray, n: int = DEFAULT_SAMPLES) -> float:
    """グルーピング用の「形だけ」の距離（サイズ非依存の無次元量）。

    相似変換を許した残差を、輪郭の代表寸法で割って正規化する。
    """
    fit = fit_contours(a, b, n=n, allow_mirror=True)
    pa = resample_closed(normalize_orientation(a), n)
    if len(pa) == 0:
        return math.inf
    za = pa[:, 0] + 1j * pa[:, 1]
    scale_ref = float(np.sqrt(np.mean(np.abs(za - za.mean()) ** 2)))
    if scale_ref <= 1e-12:
        return math.inf
    return fit.max_dev_scaled / scale_ref
