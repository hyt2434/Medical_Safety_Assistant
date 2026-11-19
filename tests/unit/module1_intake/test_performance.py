"""Kiểm tra SLA <= 20ms/lần gõ và hit rate trên dữ liệu GIẢ LẬP (cần đo lại trên dữ liệu thật)."""
import random
import time

import pytest

from module1_intake.manual_input.dictionary import load_dictionary
from module1_intake.manual_input.suggest import MedicationSuggester

from .synth import synthetic_dataset


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    d = tmp_path_factory.mktemp("synth")
    brands = synthetic_dataset(d)
    t0 = time.perf_counter()
    sg = MedicationSuggester(load_dictionary(d))
    print(f"\n[init] dựng index {time.perf_counter() - t0:.2f}s")
    return sg, brands


def typo(s, rng):
    """Một lỗi gõ nhẹ: xóa / thay / chèn / đổi chỗ hai ký tự liền nhau (kể cả ký tự đầu)."""
    s = list(s)
    kind = rng.choice("dsit")
    i = rng.randrange(0, len(s) - 1)
    if kind == "d":
        del s[i]
    elif kind == "s":
        s[i] = rng.choice("abcdefghklmnoprstuvxz")
    elif kind == "i":
        s.insert(i, rng.choice("aeiou"))
    else:
        s[i], s[i + 1] = s[i + 1], s[i]
    return "".join(s)


def run(sg, queries, targets):
    lat, hits, total = [], 0, 0
    for q, t in zip(queries, targets):
        t0 = time.perf_counter()
        res = sg.suggest(q, 5)
        lat.append((time.perf_counter() - t0) * 1000)
        if t is not None:
            total += 1
            hits += any(r.brand_name == t for r in res)
    return sorted(lat), (hits / total if total else None)


def stats(lat):
    return lat[len(lat) // 2], lat[int(len(lat) * 0.95)], lat[-1]


def test_latency_and_hit_rate(env):
    sg, brands = env
    rng = random.Random(1)
    sample = rng.sample(brands, 400)

    # A) người dùng gõ cả tên thuốc nhưng sai chính tả nhẹ (tình huống mà tiêu chí hit rate nhắm tới)
    lat_a, hit_a = run(sg, [typo(b.lower(), rng) for b in sample], sample)
    # B) gõ dở dang (5+ ký tự) và sai chính tả: nhiều tên cùng tiền tố nên top-5 có thể không chứa đúng tên
    partial = [typo(b.lower()[: rng.randint(5, len(b))], rng) for b in sample]
    lat_b, hit_b = run(sg, partial, sample)
    # C) truy vấn ngắn / rác: tốn thời gian nhất (quét nhiều tiền tố hoặc quét toàn từ điển)
    short = ["pa", "ba", "co", "ma", "ra", "se", "ti", "tra", "pre", "bac", "zzzzq", "qqqqqqqq", "xx"]
    lat_c, _ = run(sg, short, [None] * len(short))

    for name, lat in (("A tên đầy đủ+lỗi", lat_a), ("B dở dang+lỗi", lat_b), ("C ngắn/rác", lat_c)):
        p50, p95, mx = stats(lat)
        print(f"\n[latency {name}] p50={p50:.1f}ms p95={p95:.1f}ms max={mx:.1f}ms")
    print(f"\n[hit rate top-5] A (tên đầy đủ + 1 lỗi gõ) = {hit_a:.1%} | B (gõ dở dang + 1 lỗi gõ) = {hit_b:.1%}")

    assert stats(lat_a)[1] <= 20 and stats(lat_b)[1] <= 20 and stats(lat_c)[1] <= 20
    assert hit_a >= 0.85
