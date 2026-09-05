"""ツールの回帰テスト。

    python3 tests/test_acrylic_check.py
    （pytest がある環境では pytest tests/ でも動く）
"""

from __future__ import annotations

import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from acrylic_check import geometry as geo  # noqa: E402
from acrylic_check import namecheck, screwholes, shapecheck, svgdoc, svgedit  # noqa: E402
from acrylic_check.units import parse_length  # noqa: E402

sys.path.insert(0, str(ROOT / "tests"))
import make_sample  # noqa: E402


def _rotate(pts, deg):
    a = math.radians(deg)
    r = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    return pts @ r.T


def _shape(n=300):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    r = 10 + 3 * np.cos(5 * t) + 1.2 * np.sin(2 * t) + 0.6 * np.cos(3 * t + 0.7)
    return np.column_stack([r * np.cos(t), r * np.sin(t)])


def test_units():
    assert abs(parse_length("210mm").to_mm() - 210.0) < 1e-9
    assert abs(parse_length("1in").to_mm() - 25.4) < 1e-9
    assert abs(parse_length("96").to_mm(96.0) - 25.4) < 1e-9
    assert parse_length("auto") is None
    assert parse_length("50%").is_percent


def test_cyclic_correlation_matches_definition():
    rng = np.random.default_rng(0)
    n = 32
    za = rng.normal(size=n) + 1j * rng.normal(size=n)
    zb = rng.normal(size=n) + 1j * rng.normal(size=n)
    brute = np.array([np.sum(za * np.conj(np.roll(zb, -m))) for m in range(n)])
    assert np.abs(brute - geo._cyclic_correlation(za, zb)).max() < 1e-10


def test_identical_shape_has_no_deviation():
    base = _shape()
    moved = _rotate(base, 37.0) + np.array([100.0, -40.0])
    fit = geo.fit_contours(base, moved)
    assert abs(fit.scale - 1.0) < 1e-6
    assert fit.max_dev < 1e-6
    assert not fit.mirrored


def test_scale_is_detected_and_reported_as_ratio():
    base = _shape()
    fit = geo.fit_contours(base, base * 1.02)
    assert abs(fit.scale - 1.02) < 1e-4
    assert fit.max_dev > 0.2          # 実寸のズレとして出る
    assert fit.max_dev_scaled < 1e-4  # 相似変換で消えるので「歪み」はゼロ


def test_mirror_is_detected_but_not_for_symmetric_shapes():
    base = _shape()
    assert geo.fit_contours(base, base * np.array([-1.0, 1.0])).mirrored

    t = np.linspace(0, 2 * np.pi, 300, endpoint=False)
    r = 10 + 3 * np.cos(5 * t)        # 左右対称
    sym = np.column_stack([r * np.cos(t), r * np.sin(t)])
    fit = geo.fit_contours(sym, _rotate(sym, 23.0), mirror_margin=0.05)
    assert not fit.mirrored


def test_distortion_survives_best_fit_scale():
    base = _shape()
    fit = geo.fit_contours(base, base * np.array([1.0, 1.03]))
    assert fit.max_dev_scaled > 0.1


def test_min_area_rect_is_rotation_invariant():
    sq = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=float)
    a = geo.min_area_rect(sq)[:2]
    b = geo.min_area_rect(_rotate(sq, 30.0))[:2]
    assert abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6


def test_pca_would_be_unstable_but_min_area_rect_is_not():
    """5 回対称の形は共分散が等方になり PCA の軸が定まらない。"""
    t = np.linspace(0, 2 * np.pi, 600, endpoint=False)
    r = 10 + 3 * np.cos(5 * t)
    pts = np.column_stack([r * np.cos(t), r * np.sin(t)])
    sizes = [geo.min_area_rect(_rotate(pts, d))[0] for d in (0, 7, 19, 41)]
    assert max(sizes) - min(sizes) < 1e-3


def test_point_in_polygon():
    sq = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=float)
    assert geo.point_in_polygon(np.array([5.0, 5.0]), sq)
    assert not geo.point_in_polygon(np.array([15.0, 5.0]), sq)


def _write_samples(tmp: Path):
    (tmp / "good.svg").write_text(make_sample.build(False), encoding="utf-8")
    (tmp / "bad.svg").write_text(make_sample.build(True), encoding="utf-8")


def test_document_uses_millimetres():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_samples(tmp)
        doc = svgdoc.load(str(tmp / "good.svg"))
        assert abs(doc.mm_per_unit - 300.0 / make_sample.VIEW) < 1e-9
        outline = max(doc.contours, key=lambda c: abs(geo.signed_area(c.points)))
        major, _, _ = geo.min_area_rect(outline.points)
        assert abs(major - 280.0) < 0.05      # 直径 140mm の円 = 280mm
        assert outline.depth == 0
        assert all(c.depth == 1 for c in doc.contours if c is not outline)


def test_clean_file_reports_no_ng():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_samples(tmp)
        doc = svgdoc.load(str(tmp / "good.svg"))
        report = shapecheck.analyze(doc)
        assert len(report.groups) == 2                  # 花と葉
        assert sorted(len(g.members) for g in report.groups) == [12, 20]
        assert report.ng_members == []


def test_injected_defects_are_all_found():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_samples(tmp)
        doc = svgdoc.load(str(tmp / "bad.svg"))
        report = shapecheck.analyze(doc)
        ng = {m.contour.name: m for m in report.ng_members}
        assert set(ng) == {"cut_sub005", "cut_sub009", "cut_sub013", "cut_sub017"}
        assert abs(ng["cut_sub005"].fit.scale - 1.015) < 1e-3   # 1.5% 拡大
        assert ng["cut_sub009"].fit.mirrored                     # 鏡像
        assert ng["cut_sub013"].fit.max_dev > 0.1                # 引き伸ばし
        assert ng["cut_sub017"].fit.max_dev > 0.1                # 局所変形


def test_bbox_only_comparison_would_miss_the_mirror():
    """バウンディングボックス比較では鏡像を検出できないことの確認。"""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_samples(tmp)
        doc = svgdoc.load(str(tmp / "bad.svg"))
        mirrored = next(c for c in doc.contours if c.name == "cut_sub009")
        good = next(c for c in doc.contours if c.name == "cut_sub008")
        a = geo.min_area_rect(mirrored.points)
        b = geo.min_area_rect(good.points)
        assert abs(a[0] - b[0]) < 1e-3 and abs(a[1] - b[1]) < 1e-3


def test_overlay_does_not_modify_original_geometry():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_samples(tmp)
        src = (tmp / "bad.svg").read_text(encoding="utf-8")
        doc = svgdoc.load(str(tmp / "bad.svg"))
        report = shapecheck.analyze(doc)
        merged = svgedit.insert_before_root_close(
            src, shapecheck.build_overlay(doc, report.ng_members)
        )
        assert src[: src.rfind("</svg>")] == merged[: src.rfind("</svg>")]
        out = tmp / "overlay.svg"
        out.write_text(merged, encoding="utf-8")
        again = svgdoc.load(str(out))
        assert len(again.contours) == len(doc.contours) + len(report.ng_members)


def test_screw_holes_are_identical_and_replaceable():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_samples(tmp)
        doc = svgdoc.load(str(tmp / "good.svg"))
        plan = screwholes.plan_holes(doc, diameter_mm=4.0, inset_mm=12.0)
        assert len(plan.centers_mm) == 4
        text = screwholes.apply_to_file(
            (tmp / "good.svg").read_text(encoding="utf-8"), doc, plan
        )
        out = tmp / "holes.svg"
        out.write_text(text, encoding="utf-8")

        checked = svgdoc.load(str(out))
        lines = screwholes.verify(checked, rect_mm=plan.rect_mm)
        assert any(line.startswith("✅") for line in lines), lines

        # 貼り替えても増殖しない
        again = screwholes.apply_to_file(text, checked, plan)
        assert again.count('id="ネジ穴"') == 1


def test_screw_holes_reject_out_of_bounds():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_samples(tmp)
        doc = svgdoc.load(str(tmp / "good.svg"))
        try:
            screwholes.plan_holes(doc, diameter_mm=4.0, inset_mm=200.0)
        except ValueError:
            return
        raise AssertionError("はみ出しを検出できていません")


def test_name_matching():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_samples(tmp)
        doc = svgdoc.load(str(tmp / "good.svg"))
        names, warnings = namecheck.extract_names(str(tmp / "good.svg"), to_mm=doc.to_mm)
        assert warnings == []
        assert len(names) == len(make_sample.SAMPLE_NAMES)

        roster = tmp / "roster.csv"
        roster.write_text("名前\n" + "\n".join(make_sample.SAMPLE_NAMES) + "\n", encoding="utf-8")
        report = namecheck.compare(names, namecheck.load_roster(str(roster), "名前"))
        assert report.ok

        short = make_sample.SAMPLE_NAMES[:-1] + ["Taro Yamada"]
        report = namecheck.compare(names, [namecheck.normalize(x) for x in short])
        assert report.missing == ["Taro Yamada"]
        assert report.extra == [namecheck.normalize(make_sample.SAMPLE_NAMES[-1])]


def test_name_matching_reports_outlined_text():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        svg = tmp / "no_text.svg"
        svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" '
            'viewBox="0 0 10 10"><path d="M0,0 L10,0 L10,10 Z"/></svg>',
            encoding="utf-8",
        )
        names, warnings = namecheck.extract_names(str(svg))
        assert names == []
        assert warnings and "焼き込まれている" in warnings[0]


def test_cli_exit_codes():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_samples(tmp)
        env = {"PYTHONPATH": str(ROOT)}
        good = subprocess.run(
            [sys.executable, "-m", "acrylic_check", "shapes", str(tmp / "good.svg")],
            cwd=ROOT, capture_output=True, text=True, env={**env, "PATH": "/usr/bin:/bin"},
        )
        assert good.returncode == 0, good.stdout + good.stderr
        bad = subprocess.run(
            [sys.executable, "-m", "acrylic_check", "shapes", str(tmp / "bad.svg")],
            cwd=ROOT, capture_output=True, text=True, env={**env, "PATH": "/usr/bin:/bin"},
        )
        assert bad.returncode == 1, bad.stdout + bad.stderr


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL {fn.__name__}: {exc.__class__.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
