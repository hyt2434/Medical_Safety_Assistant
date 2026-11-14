"""Autocomplete tên thuốc: khớp tiền tố -> gợi ý mờ dự phòng (Damerau-Levenshtein <= 2)."""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

from rapidfuzz import process
from rapidfuzz.distance import DamerauLevenshtein

from .dictionary import MedicationEntry
from .text_utils import compact, normalize

MIN_QUERY_LEN = 2
_BRAND, _INGREDIENT = 0, 1
_MAX_PREFIX_SCAN = 3000     # chặn số khóa quét cho truy vấn quá ngắn
_FUZZY_KEY_LIMIT = 100      # số khóa mờ tối đa lấy ra mỗi lần
_MAX_FUZZY_ENTRIES = 1500   # số sản phẩm tối đa được xét ở bước mờ


class MatchType(str, Enum):
    EXACT_PREFIX = "EXACT_PREFIX"
    FUZZY_MATCH = "FUZZY_MATCH"
    CUSTOM_FALLBACK = "CUSTOM_FALLBACK"


@dataclass(frozen=True)
class Suggestion:
    brand_name: str
    active_ingredient: list[str] | None
    strength: str | None
    dosage_form: str | None
    match_type: str
    medication_id: str | None  # mở rộng so với spec: để Module II tra thẳng sản phẩm

    def to_dict(self) -> dict:
        return {
            "brand_name": self.brand_name,
            "active_ingredient": self.active_ingredient,
            "strength": self.strength,
            "dosage_form": self.dosage_form,
            "match_type": self.match_type,
            "medication_id": self.medication_id,
        }


def _max_distance(length: int) -> int:
    """Ngưỡng sửa lỗi theo độ dài (luôn <= 2 theo spec); chuỗi ngắn không fuzzy để tránh gợi ý rác."""
    if length < 4:
        return 0
    return 1 if length < 6 else 2


class MedicationSuggester:
    def __init__(self, entries: list[MedicationEntry]):
        self._entries = list(entries)

        pairs: set[tuple[str, int, int]] = set()
        self._qual_text: list[str] = []   # brand + strength + dạng bào chế, dùng để ưu tiên hàm lượng/dạng
        self._brand_key: list[str] = []
        for i, e in enumerate(self._entries):
            self._qual_text.append(normalize(f"{e.brand_name} {e.strength or ''} {e.dosage_form or ''}"))
            self._brand_key.append(normalize(e.brand_name))
            if (k := compact(e.brand_name)):
                pairs.add((k, i, _BRAND))
            words = self._brand_key[i].split()
            if len(words) > 1 and len((k := compact(words[0]))) >= MIN_QUERY_LEN:
                pairs.add((k, i, _BRAND))  # "Essium 40 mg" -> thêm khóa "essium" (gõ sai từ đầu vẫn tìm ra)
            for name in (*e.active_ingredients, *e.alt_names):
                if (k := compact(name)):
                    pairs.add((k, i, _INGREDIENT))

        ordered = sorted(pairs)
        self._keys = [p[0] for p in ordered]                  # index đã sắp xếp (tìm tiền tố bằng bisect)
        self._owners = [(p[1], p[2]) for p in ordered]
        self._distinct = sorted(set(self._keys))              # khóa duy nhất cho bước mờ
        # Nhóm khóa theo ký tự đầu (pos 0) và ký tự thứ hai (pos 1) để bước mờ chỉ quét nhóm nhỏ
        self._buckets: dict[tuple[int, str], list[int]] = defaultdict(list)
        for kidx, k in enumerate(self._distinct):
            self._buckets[(0, k[0])].append(kidx)
            if len(k) > 1:
                self._buckets[(1, k[1])].append(kidx)
        self._trunc_cache: dict[tuple[tuple[int, str], int], list[str]] = {}

    # ------------------------------------------------------------------ public
    def suggest(self, query: str, limit: int = 5) -> list[Suggestion]:
        if not isinstance(query, str):
            raise TypeError("query phải là chuỗi")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ValueError("limit phải là số nguyên >= 1")

        qn = normalize(query)
        qc = compact(query)
        if len(qn) < MIN_QUERY_LEN or len(qc) < MIN_QUERY_LEN:
            return []

        tokens = qn.split()
        name_tok = compact(tokens[0]) if len(tokens) > 1 else ""
        qualifiers = tokens[1:]
        cands: dict[int, tuple] = {}

        def current() -> list[Suggestion]:
            return self._finalize(cands, limit)

        # Giai đoạn 1: tiền tố trên toàn bộ câu gõ
        self._prefix(qc, [], cands)
        out = current()

        # 1b: nếu nhập kèm hàm lượng/dạng ("amoxicillin 500"), tìm theo tên rồi ưu tiên theo phần kèm
        if len(out) < limit and len(name_tok) >= MIN_QUERY_LEN:
            self._prefix(name_tok, qualifiers, cands)
            out = current()

        # Giai đoạn 2: gợi ý mờ dự phòng.
        # Tầng 1: khóa cùng ký tự đầu. Tầng 2 (chỉ khi tầng 1 không ra gì): lỗi gõ ở chính ký tự đầu
        # (thay / xóa / chèn / đổi chỗ) luôn rơi vào các nhóm theo ký tự thứ nhất hoặc thứ hai.
        if len(out) < limit:
            for tier in (1, 2):
                self._fuzzy(qc, [], cands, self._buckets_for(qc, tier))
                if len(name_tok) >= MIN_QUERY_LEN:
                    self._fuzzy(name_tok, qualifiers, cands, self._buckets_for(name_tok, tier))
                out = current()
                if out:
                    break

        if not out:
            return [Suggestion(" ".join(query.split()), None, None, None,
                               MatchType.CUSTOM_FALLBACK.value, None)]
        return out

    # ----------------------------------------------------------------- internals
    @staticmethod
    def _buckets_for(q: str, tier: int) -> list[tuple[int, str]]:
        if tier == 1:
            return [(0, q[0])]
        return [b for b in dict.fromkeys([(1, q[1]), (1, q[0]), (0, q[1])]) if b != (0, q[0])]

    def _truncated(self, bucket: tuple[int, str], length: int) -> list[str]:
        """Các khóa trong nhóm, cắt còn `length` ký tự (cache lười; nhóm nhỏ nên dựng rất nhanh)."""
        cached = self._trunc_cache.get((bucket, length))
        if cached is None:
            cached = [self._distinct[i][:length] for i in self._buckets.get(bucket, ())]
            self._trunc_cache[(bucket, length)] = cached
        return cached

    def _qual_miss(self, idx: int, qualifiers: list[str]) -> int:
        text = self._qual_text[idx]
        return sum(1 for q in qualifiers if q not in text)

    def _offer(self, cands, idx, field, match_rank, dist, qualifiers, len_diff):
        e = self._entries[idx]
        score = (match_rank, dist, self._qual_miss(idx, qualifiers), field,
                 len_diff, not e.level2_qualified, self._brand_key[idx])
        old = cands.get(idx)
        if old is None or score < old:
            cands[idx] = score

    def _prefix(self, prefix: str, qualifiers: list[str], cands: dict) -> None:
        keys = self._keys
        i = bisect_left(keys, prefix)
        end = min(len(keys), i + _MAX_PREFIX_SCAN)
        while i < end and keys[i].startswith(prefix):
            idx, field = self._owners[i]
            self._offer(cands, idx, field, 0, 0, qualifiers, len(keys[i]) - len(prefix))
            i += 1

    def _fuzzy(self, q: str, qualifiers: list[str], cands: dict, buckets: list[tuple[int, str]]) -> None:
        max_d = _max_distance(len(q))
        if max_d == 0:
            return
        # So q với đầu khóa dài len(q) và len(q)+1: chịu được gõ thiếu/thừa một ký tự
        best: dict[int, int] = {}
        for bucket in buckets:
            ids = self._buckets.get(bucket)
            if not ids:
                continue
            for length in (len(q), len(q) + 1):
                for _, dist, pos in process.extract(
                    q, self._truncated(bucket, length), scorer=DamerauLevenshtein.distance,
                    score_cutoff=max_d, limit=_FUZZY_KEY_LIMIT,
                ):
                    kidx = ids[pos]
                    if dist < best.get(kidx, 99):
                        best[kidx] = dist
        budget = _MAX_FUZZY_ENTRIES
        for kidx, dist in sorted(best.items(), key=lambda kv: (kv[1], kv[0])):
            key = self._distinct[kidx]
            lo, hi = bisect_left(self._keys, key), bisect_right(self._keys, key)
            for j in range(lo, hi):
                idx, field = self._owners[j]
                self._offer(cands, idx, field, 1, dist, qualifiers, abs(len(key) - len(q)))
                budget -= 1
            if budget <= 0:
                break

    def _finalize(self, cands: dict[int, tuple], limit: int) -> list[Suggestion]:
        out: list[Suggestion] = []
        seen: set[tuple[str, str, str]] = set()
        for idx, score in sorted(cands.items(), key=lambda kv: kv[1]):
            e = self._entries[idx]
            dedupe = (self._brand_key[idx], normalize(e.strength), normalize(e.dosage_form))
            if dedupe in seen:  # cùng tên + hàm lượng + dạng bào chế: chỉ giữ bản xếp hạng cao nhất
                continue
            seen.add(dedupe)
            out.append(Suggestion(
                brand_name=e.brand_name,
                active_ingredient=list(e.active_ingredients) or None,
                strength=e.strength,
                dosage_form=e.dosage_form,
                match_type=(MatchType.EXACT_PREFIX if score[0] == 0 else MatchType.FUZZY_MATCH).value,
                medication_id=e.medication_id,
            ))
            if len(out) >= limit:
                break
        return out
