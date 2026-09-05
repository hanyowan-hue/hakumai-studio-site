"""SVG のユーザー単位を mm に変換する。

アクリル入稿では「何 mm ずれているか」でしか判断できない。
ユーザー単位のままの数値比較は意味を持たないので、
すべての計測は最初に mm へ落としてから行う。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 1 ユーザー単位(px) = 1/96 inch = 25.4/96 mm （SVG 1.1 / CSS の既定）
MM_PER_PX_96DPI = 25.4 / 96.0

_LENGTH_RE = re.compile(
    r"^\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*"
    r"(px|pt|pc|mm|cm|in|q|Q|%|)\s*$"
)

_UNIT_TO_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "q": 0.25,
    "in": 25.4,
    "pt": 25.4 / 72.0,
    "pc": 25.4 / 6.0,
}


class UnitError(ValueError):
    pass


@dataclass(frozen=True)
class Length:
    value: float
    unit: str  # "" は単位なし（= px 相当のユーザー単位）

    @property
    def is_percent(self) -> bool:
        return self.unit == "%"

    def to_mm(self, dpi: float = 96.0) -> float:
        """絶対長を mm で返す。% は解決できないので例外。"""
        if self.is_percent:
            raise UnitError("パーセント指定は絶対長に変換できません")
        if self.unit in ("", "px"):
            return self.value * (25.4 / dpi)
        return self.value * _UNIT_TO_MM[self.unit.lower()]


def parse_length(text: str | None) -> Length | None:
    """'210mm' / '793.7' / '100%' などを Length にする。解釈できなければ None。"""
    if text is None:
        return None
    m = _LENGTH_RE.match(str(text))
    if not m:
        return None
    unit = m.group(2)
    if unit and unit not in ("%", "px") and unit.lower() not in _UNIT_TO_MM:
        return None
    return Length(float(m.group(1)), "%" if unit == "%" else unit.lower())
