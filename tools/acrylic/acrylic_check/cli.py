"""コマンドライン入口。

  python -m acrylic_check shapes 入稿.svg
  python -m acrylic_check holes  入稿.svg -o 入稿_ネジ穴.svg --diameter 4 --inset 10
  python -m acrylic_check names  入稿.svg --roster 参列者.xlsx --column 名前
  python -m acrylic_check info   入稿.svg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import geometry as geo
from . import namecheck, screwholes, shapecheck, svgdoc


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("svg", help="対象の SVG ファイル")
    parser.add_argument("--dpi", type=float, default=96.0,
                        help="単位のない座標を px とみなすときの解像度（既定 96）")
    parser.add_argument("--layer", default=None,
                        help="対象レイヤー名の正規表現（例: 'カット|cut'）")


def _load(args) -> svgdoc.SvgDocument:
    doc = svgdoc.load(args.svg, dpi=args.dpi, layer_pattern=getattr(args, "layer", None))
    if doc.warnings:
        print("── 注意 ──")
        for w in dict.fromkeys(doc.warnings):
            print(f"  ⚠️ {w}")
        print()
    return doc


# ---------------------------------------------------------------------------

def cmd_info(args) -> int:
    doc = _load(args)
    print(f"ファイル: {args.svg}")
    print(f"縮尺: 1 ユーザー単位 = {doc.mm_per_unit:.6f} mm")
    print(f"閉じた輪郭: {len(doc.contours)} 本")
    if not doc.contours:
        return 1
    import numpy as np
    x0, y0, x1, y1 = geo.bbox(np.vstack([c.points for c in doc.contours]))
    print(f"全体サイズ: {x1 - x0:.3f} × {y1 - y0:.3f} mm")
    print()
    print(f"{'No':>4}  {'名前':<28} {'深さ':>3} {'長辺mm':>9} {'短辺mm':>9} {'周長mm':>9}")
    for c in doc.contours:
        major, minor, _ = geo.min_area_rect(c.points)
        print(f"{c.index:>4}  {c.name:<28} {c.depth:>3} {major:>9.3f} {minor:>9.3f} "
              f"{geo.perimeter(c.points):>9.3f}")
    return 0


def cmd_shapes(args) -> int:
    doc = _load(args)
    report = shapecheck.analyze(
        doc,
        shape_tol=args.shape_tol,
        dev_tol_mm=args.dev_tol,
        scale_tol=args.scale_tol / 100.0,
        max_scale_ratio=args.max_scale_ratio,
        allow_mirror=args.allow_mirror,
        group_by_depth=not args.ignore_depth,
        samples=args.samples,
    )

    print("========== 同形パーツのカット線チェック ==========")
    print(f"許容: 形のズレ {args.dev_tol}mm / 拡大縮小 ±{args.scale_tol}% / "
          f"鏡像 {'許可' if args.allow_mirror else '不可'}")
    print()

    for group in report.groups:
        print(f"---------- 形{group.number}（{len(group.members)} 個, 入れ子の深さ {group.depth}） ----------")
        ref = next(m for m in group.members if m.contour.index == group.reference.index)
        print(f"基準: {ref.contour.name}  {ref.major_mm:.3f} × {ref.minor_mm:.3f} mm")
        print(f"{'':4}{'名前':<28} {'倍率':>9} {'ズレ最大mm':>11} {'ズレRMSmm':>10} {'鏡像':>5}  判定")
        for m in group.members:
            mark = "OK" if m.ok else "❌ " + " / ".join(m.issues)
            if m.contour.index == group.reference.index:
                mark = "基準"
            print(f"{'':4}{m.contour.name:<28} {m.fit.scale:>9.5f} {m.fit.max_dev:>11.4f} "
                  f"{m.fit.rms_dev:>10.4f} {'あり' if m.fit.mirrored else '':>5}  {mark}")
        print()

    if report.singles:
        print(f"---------- 単独の形（{len(report.singles)} 個） ----------")
        for group in report.singles:
            m = group.members[0]
            print(f"    {m.contour.name:<28} {m.major_mm:>9.3f} × {m.minor_mm:.3f} mm "
                  f"（深さ {m.contour.depth}）")
        print("  ※ 同じ形が他にないため比較していません。板の外形やネジ穴はここに出ます。")
        print()

    ng = report.ng_members
    print("========== まとめ ==========")
    print(f"輪郭数: {len(doc.contours)} / 形の種類: {len(report.groups) + len(report.singles)}")
    print(f"NG: {len(ng)} 件")
    for w in dict.fromkeys(report.warnings):
        print(f"  ⚠️ {w}")

    if ng:
        print()
        for m in ng:
            print(f"  ❌ {m.contour.name}: " + " / ".join(m.issues))
    else:
        print("  ✅ 同じ形のパーツはすべて同一のカット線です（拡大縮小・歪み・鏡像なし）。")

    if args.overlay and ng:
        from . import svgedit
        src = Path(args.svg).read_text(encoding="utf-8")
        fragment = shapecheck.build_overlay(doc, ng)
        out = Path(args.overlay)
        out.write_text(svgedit.insert_before_root_close(src, fragment), encoding="utf-8")
        print(f"\nNG 位置を赤で重ねた確認用 SVG を書き出しました: {out}")

    if args.json:
        payload = {
            "file": args.svg,
            "mm_per_unit": doc.mm_per_unit,
            "groups": [
                {
                    "number": g.number,
                    "depth": g.depth,
                    "count": len(g.members),
                    "reference": g.reference.name,
                    "cohesion": g.cohesion,
                    "members": [
                        {
                            "name": m.contour.name,
                            "scale": m.fit.scale,
                            "max_dev_mm": m.fit.max_dev,
                            "rms_dev_mm": m.fit.rms_dev,
                            "distortion_mm": m.fit.max_dev_scaled,
                            "mirrored": m.fit.mirrored,
                            "major_mm": m.major_mm,
                            "minor_mm": m.minor_mm,
                            "issues": m.issues,
                        }
                        for m in g.members
                    ],
                }
                for g in report.groups + report.singles
            ],
            "ng_count": len(ng),
            "warnings": list(dict.fromkeys(report.warnings)),
        }
        Path(args.json).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"JSON を書き出しました: {args.json}")

    return 1 if ng else 0


def cmd_holes(args) -> int:
    doc = _load(args)
    rect = None
    if args.rect:
        values = [float(v) for v in args.rect.split(",")]
        if len(values) != 4:
            print("--rect は x,y,幅,高さ を mm で指定してください。", file=sys.stderr)
            return 2
        x, y, w, h = values
        rect = (x, y, x + w, y + h)

    plan = screwholes.plan_holes(
        doc,
        diameter_mm=args.diameter,
        inset_mm=args.inset,
        inset_x_mm=args.inset_x,
        inset_y_mm=args.inset_y,
        rect_mm=rect,
        mode=args.rect_mode,
    )

    x0, y0, x1, y1 = plan.rect_mm
    print("========== ネジ穴の配置 ==========")
    print(f"基準矩形: {plan.source}")
    print(f"          x {x0:.3f} → {x1:.3f} / y {y0:.3f} → {y1:.3f} "
          f"（{x1 - x0:.3f} × {y1 - y0:.3f} mm）")
    print(f"直径: {plan.diameter_mm:.3f} mm")
    print(f"角からの距離: X {plan.inset_x_mm:.3f} mm / Y {plan.inset_y_mm:.3f} mm "
          f"（対角距離 {plan.corner_distance_mm:.3f} mm）")
    for name, (cx, cy) in zip(["左上", "右上", "右下", "左下"], plan.centers_mm):
        print(f"  {name}: ({cx:.3f}, {cy:.3f}) mm")

    src = Path(args.svg).read_text(encoding="utf-8")
    result = screwholes.apply_to_file(
        src, doc, plan, layer_id=args.layer_id, replace=True, stroke=args.stroke
    )
    out = Path(args.output)
    out.write_text(result, encoding="utf-8")
    print(f"\n書き出し: {out}")

    print("\n---------- 書き出したファイルを読み直して実測 ----------")
    check = svgdoc.load(str(out), dpi=args.dpi)
    for line in screwholes.verify(check, args.layer_id, plan.rect_mm):
        print(f"  {line}")
    return 0


def cmd_names(args) -> int:
    doc = svgdoc.load(args.svg, dpi=args.dpi)
    names, warnings = namecheck.extract_names(
        args.svg, to_mm=doc.to_mm, strip_spaces=args.strip_spaces
    )
    print("========== 名前の照合 ==========")
    print(f"SVG 内のテキスト: {len(names)} 件")
    for w in warnings:
        print(f"  ⚠️ {w}")

    if not args.roster:
        for n in names:
            pos = f"({n.position_mm[0]:.1f}, {n.position_mm[1]:.1f})mm" if n.position_mm else "位置不明"
            print(f"  {n.normalized:<28} {pos}")
        return 0 if names else 1

    roster = namecheck.load_roster(args.roster, args.column, strip_spaces=args.strip_spaces)
    print(f"名簿: {len(roster)} 件（{args.roster}）")
    report = namecheck.compare(names, roster)
    print()

    if report.missing:
        print(f"❌ 名簿にあるのに SVG にない: {len(report.missing)} 件")
        for x in report.missing:
            print(f"    {x}")
    if report.extra:
        print(f"❌ SVG にあるのに名簿にない: {len(report.extra)} 件")
        for x in report.extra:
            print(f"    {x}")
    if report.duplicated_in_svg:
        print("⚠️ SVG 内で重複している名前:")
        for name, count in report.duplicated_in_svg:
            print(f"    {name} × {count}")
    if report.duplicated_in_roster:
        print("⚠️ 名簿内で重複している名前（同姓同名なら問題ありません）:")
        for name, count in report.duplicated_in_roster:
            print(f"    {name} × {count}")

    if report.ok:
        print("✅ SVG の名前と名簿は完全に一致しています。")
        return 0
    return 1


# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="acrylic_check", description="アクリル入稿 SVG の検査・加工"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="輪郭の一覧と実寸を表示")
    _common(p_info)
    p_info.set_defaults(func=cmd_info)

    p_shape = sub.add_parser("shapes", help="同じ形のパーツのカット線を突き合わせる")
    _common(p_shape)
    p_shape.add_argument("--dev-tol", type=float, default=shapecheck.DEFAULT_DEV_TOL_MM,
                         help="形のズレの許容量 mm（既定 0.10）")
    p_shape.add_argument("--scale-tol", type=float, default=shapecheck.DEFAULT_SCALE_TOL * 100,
                         help="拡大縮小の許容量 %%（既定 0.2）")
    p_shape.add_argument("--shape-tol", type=float, default=shapecheck.DEFAULT_SHAPE_TOL,
                         help="同じ形とみなす閾値・無次元（既定 0.02）")
    p_shape.add_argument("--max-scale-ratio", type=float,
                         default=shapecheck.DEFAULT_MAX_SCALE_RATIO,
                         help="同じ形として比較する寸法比の上限（既定 1.25）")
    p_shape.add_argument("--allow-mirror", action="store_true",
                         help="鏡像（裏返し）を OK とする")
    p_shape.add_argument("--ignore-depth", action="store_true",
                         help="入れ子の深さを無視してグループ化する")
    p_shape.add_argument("--samples", type=int, default=geo.DEFAULT_SAMPLES,
                         help="輪郭のサンプリング点数（既定 512）")
    p_shape.add_argument("--overlay", default=None, help="NG 箇所を赤で重ねた SVG の出力先")
    p_shape.add_argument("--json", default=None, help="結果を JSON で出力するパス")
    p_shape.set_defaults(func=cmd_shapes)

    p_holes = sub.add_parser("holes", help="四隅にネジ穴を追加")
    _common(p_holes)
    p_holes.add_argument("-o", "--output", required=True, help="出力 SVG")
    p_holes.add_argument("--diameter", type=float, required=True, help="穴の直径 mm")
    p_holes.add_argument("--inset", type=float, default=None, help="角（辺）からの距離 mm")
    p_holes.add_argument("--inset-x", type=float, default=None, help="左右の辺からの距離 mm")
    p_holes.add_argument("--inset-y", type=float, default=None, help="上下の辺からの距離 mm")
    p_holes.add_argument("--rect", default=None, help="基準矩形を x,y,幅,高さ の mm で直接指定")
    p_holes.add_argument("--rect-mode", choices=["outline", "all"], default="outline",
                         help="基準矩形の決め方（outline=最大面積の輪郭 / all=全体）")
    p_holes.add_argument("--layer-id", default=screwholes.DEFAULT_LAYER_ID, help="追加するレイヤー id")
    p_holes.add_argument("--stroke", default="#000000", help="カット線の色")
    p_holes.set_defaults(func=cmd_holes)

    p_names = sub.add_parser("names", help="SVG の名前と名簿を突き合わせる")
    _common(p_names)
    p_names.add_argument("--roster", default=None, help="名簿の xlsx / csv")
    p_names.add_argument("--column", default=None, help="名簿の列名、または 0 始まりの列番号")
    p_names.add_argument("--strip-spaces", action="store_true",
                         help="姓名間の空白を無視して照合する")
    p_names.set_defaults(func=cmd_names)

    return parser


def main(argv: list[str] | None = None) -> int:
    try:  # head などにパイプしたときに BrokenPipeError で落ちないように
        import signal
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (ImportError, AttributeError, ValueError):
        pass
    args = build_parser().parse_args(argv)
    if getattr(args, "column", None) is not None:
        try:
            args.column = int(args.column)
        except ValueError:
            pass
    try:
        return args.func(args)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
