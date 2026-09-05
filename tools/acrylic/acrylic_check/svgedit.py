"""SVG への追記編集。

入稿データを触るので、XML を再シリアライズして全体を書き換えることはしない。
（ElementTree で書き戻すと名前空間接頭辞や数値表記が変わり、
  検査対象そのものが変質する）
必要な断片だけをテキストとして差し込む。
"""

from __future__ import annotations

import re


class SvgEditError(RuntimeError):
    pass


def _root_close_pos(text: str) -> int:
    pos = text.rfind("</svg>")
    if pos < 0:
        raise SvgEditError("</svg> が見つかりません。SVG ファイルではない可能性があります。")
    return pos


def insert_before_root_close(text: str, fragment: str) -> str:
    pos = _root_close_pos(text)
    return text[:pos] + fragment + "\n" + text[pos:]


def remove_group(text: str, group_id: str) -> tuple[str, bool]:
    """id が一致する <g> …（対応する）… </g> を丸ごと取り除く。

    本ツールが自分で追記したレイヤーの貼り直しにだけ使う。
    """
    start_re = re.compile(r"<g\b[^>]*\bid\s*=\s*[\"']" + re.escape(group_id) + r"[\"'][^>]*>")
    m = start_re.search(text)
    if not m:
        return text, False
    if m.group(0).rstrip().endswith("/>"):
        return text[: m.start()] + text[m.end():], True

    depth = 1
    pos = m.end()
    token = re.compile(r"<g\b[^>]*?(/?)>|</g\s*>")
    while depth > 0:
        t = token.search(text, pos)
        if not t:
            raise SvgEditError(f"<g id={group_id!r}> の対応する </g> が見つかりません。")
        pos = t.end()
        if t.group(0).startswith("</g"):
            depth -= 1
        elif not t.group(1):
            depth += 1
    return text[: m.start()] + text[pos:], True
