"""検査ツールの動作確認用に、わざと欠陥を入れたサンプル SVG を作る。

実データと同じく「1 本の複合パスに全カット線が入っている」構造にする。
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

MM = 300.0                 # 板は 300mm 角
VIEW = 1133.858267717      # 300mm を 96dpi の px で表した値
UNIT = VIEW / MM           # 1mm あたりのユーザー単位


def flower(radius=13.0, petals=5, depth=3.0, n=240):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    r = radius + depth * np.cos(petals * t) + 0.8 * np.sin(2 * t)
    return np.column_stack([r * np.cos(t), r * np.sin(t)])


def leaf(length=26.0, width=11.0, n=200):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    x = length / 2 * np.cos(t)
    y = width / 2 * np.sin(t) * (1 - 0.35 * np.cos(t))
    return np.column_stack([x, y])


def circle(radius, n=360):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.column_stack([radius * np.cos(t), radius * np.sin(t)])


def rotate(pts, deg):
    a = math.radians(deg)
    r = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    return pts @ r.T


def to_d(pts_mm):
    """mm 座標をユーザー単位に直して d 文字列にする。"""
    pts = np.asarray(pts_mm) * UNIT
    head = f"M {pts[0][0]:.5f},{pts[0][1]:.5f}"
    body = " ".join(f"L {x:.5f},{y:.5f}" for x, y in pts[1:])
    return f"{head} {body} Z"


def build(defective: bool) -> str:
    subpaths = []
    center = np.array([MM / 2, MM / 2])

    # 板の外形（一番外側）
    subpaths.append(to_d(circle(140.0) + center))

    # 花 20 個をリング状に。すべて同じ形・同じ大きさが正解。
    for i in range(20):
        a = 360.0 / 20 * i
        pos = center + np.array([math.cos(math.radians(a)), math.sin(math.radians(a))]) * 110.0
        pts = rotate(flower(), a * 1.7)          # 回転しているだけ = OK であるべき
        if defective:
            if i == 3:
                pts = pts * 1.015                # 1.5% 拡大
            elif i == 7:
                pts = pts * np.array([-1.0, 1.0])  # 鏡像
            elif i == 11:
                pts = pts * np.array([1.0, 1.02])  # 縦だけ引き伸ばし（歪み）
            elif i == 15:
                pts = pts.copy()
                pts[40:60] += np.array([0.0, 0.35])  # 局所的な変形
        subpaths.append(to_d(pts + pos))

    # 葉 12 枚
    for i in range(12):
        a = 360.0 / 12 * i + 15
        pos = center + np.array([math.cos(math.radians(a)), math.sin(math.radians(a))]) * 72.0
        pts = rotate(leaf(), a)
        subpaths.append(to_d(pts + pos))

    d = " ".join(subpaths)
    text_layer = "\n".join(
        f'    <text id="name_{i:02d}" x="{(center[0]) * UNIT:.3f}" '
        f'y="{(center[1] + i) * UNIT:.3f}" font-size="10">{name}</text>'
        for i, name in enumerate(SAMPLE_NAMES)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" version="1.1"
     width="{MM}mm" height="{MM}mm" viewBox="0 0 {VIEW:.6f} {VIEW:.6f}">
  <g id="カット線" fill="none" stroke="#000000" stroke-width="1">
    <path id="cut" d="{d}"/>
  </g>
  <g id="名前">
{text_layer}
  </g>
</svg>
"""


SAMPLE_NAMES = [
    "Yuta Takano", "Manami Moriyama", "Airi Takano", "Keiko Moriyama",
    "Hiroshi Moriyama", "Naomi Takano", "Haruna Takano", "Taiga Takano",
]


if __name__ == "__main__":
    out = Path(__file__).parent / "sample"
    out.mkdir(exist_ok=True)
    (out / "good.svg").write_text(build(False), encoding="utf-8")
    (out / "bad.svg").write_text(build(True), encoding="utf-8")
    roster = out / "roster.csv"
    roster.write_text(
        "名前\n" + "\n".join(SAMPLE_NAMES) + "\n", encoding="utf-8"
    )
    print("生成:", out / "good.svg", out / "bad.svg", roster)
