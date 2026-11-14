"""Dữ liệu CSV giả lập, dùng đúng tên cột của dữ liệu thật (chỉ các cột Module I cần + vài cột phụ)."""
import csv
import random
from pathlib import Path

MED_HEADER = ["id", "source_ref", "brand_name", "dosage_form", "route_status", "level2_qualified"]
COMP_HEADER = ["id", "medication_id", "ordinal", "original_name_candidate",
               "ingredient_text_raw", "accepted_ingredient_id", "identity_verified"]
ING_HEADER = ["id", "accepted_normalized_name", "source_name"]


def write_csv(path: Path, header, rows, bom=False):
    with path.open("w", newline="", encoding="utf-8-sig" if bom else "utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def small_dataset(d: Path):
    """Bộ nhỏ có các tình huống đặc biệt của dữ liệu thật."""
    write_csv(d / "medications.csv", MED_HEADER, [
        ["PC_1", "{}", "Essium 40 mg", "Bột đông khô", "NOT_EXPLICITLY_SUPPORTED", "TRUE"],
        ["PC_2", "{}", "T-Esom20", "Viên nang cứng", "NOT_EXPLICITLY_SUPPORTED", "TRUE"],
        ["PC_3", "{}", "Augmentin 625mg", "Viên nén bao phim", "NOT_EXPLICITLY_SUPPORTED", "TRUE"],
        ["PC_4", "{}", "Thinmcz-100", "Bột pha tiêm", "NOT_EXPLICITLY_SUPPORTED", "FALSE"],
        ["PC_5", "{}", "Natribicarbonat Stada", "Viên nén", "NOT_EXPLICITLY_SUPPORTED", "TRUE"],
        ["PC_6", "{}", "Amoxicillin Stada 250", "Viên nang", "NOT_EXPLICITLY_SUPPORTED", "TRUE"],
        ["PC_7", "{}", "Amoxicillin Stada 500", "Viên nang", "NOT_EXPLICITLY_SUPPORTED", "TRUE"],
        ["PC_8", "{}", "Amoxicillin Stada 500", "Viên nang", "NOT_EXPLICITLY_SUPPORTED", "FALSE"],  # trùng -> dedupe
        ["PC_9", "{}", "", "Viên", "", "TRUE"],  # thiếu brand -> bỏ qua
    ], bom=True)
    write_csv(d / "medication_ingredients.csv", COMP_HEADER, [
        ["CC_1", "PC_1", "1", "Esomeprazol", "Esomeprazol (dưới dạng Esomeprazol natri) 40mg", "LI_ESO", "TRUE"],
        ["CC_2", "PC_2", "1", "Esomeprazol", "Esomeprazol 20mg", "LI_ESO", "TRUE"],
        ["CC_3b", "PC_3", "2", "Acid clavulanic", "Acid clavulanic 125mg", "KHONG_TON_TAI", "FALSE"],
        ["CC_3a", "PC_3", "1", "Amoxicillin", "Amoxicillin 500mg", "LI_AMX", "TRUE"],
        ["CC_4", "PC_4", "1", "", "", "", "FALSE"],  # không có hoạt chất
        ["CC_5", "PC_5", "1", "Natri bicarbonat", "Natri bicarbonat 1100mg", "LI_NAH", "TRUE"],
        ["CC_6", "PC_6", "1", "Amoxicillin", "Amoxicillin 250mg", "LI_AMX", "TRUE"],
        ["CC_7", "PC_7", "1", "Amoxicillin", "Amoxicillin 500mg", "LI_AMX", "TRUE"],
        ["CC_8", "PC_8", "1", "Amoxicillin", "Amoxicillin 500mg", "LI_AMX", "TRUE"],
    ])
    write_csv(d / "ingredients.csv", ING_HEADER, [
        ["LI_ESO", "esomeprazole", "Esomeprazol"],
        ["LI_AMX", "amoxicillin", "Amoxicillin"],
        ["LI_NAH", "sodium bicarbonate", "Natri bicarbonat"],
    ])


_SYL = ["ba", "co", "de", "fi", "ga", "he", "ki", "lo", "ma", "ne", "pa", "ra", "se", "ti", "vo", "xa", "zu", "pre", "tra", "cla"]


def synthetic_dataset(d: Path, n=10670, seed=7):
    """~10.7k sản phẩm tên ngẫu nhiên, tên hoạt chất dùng chung (giống phân bố thật: 1 hoạt chất -> nhiều sản phẩm)."""
    rng = random.Random(seed)
    words = ["".join(rng.choice(_SYL) for _ in range(rng.randint(2, 4))) for _ in range(1900)]
    forms = ["Viên nén", "Viên nang", "Bột pha tiêm", "Dung dịch uống", "Viên nén bao phim"]
    meds, comps, brands = [], [], []
    for i in range(n):
        brand = f"{rng.choice(words).capitalize()}{rng.choice(['', '-', ' '])}{rng.choice(words)[:3]} {rng.choice([10, 20, 40, 100, 250, 500])}"
        brands.append(brand)
        meds.append([f"PC_{i}", "{}", brand, rng.choice(forms), "", "TRUE" if rng.random() < 0.82 else "FALSE"])
        for k in range(1 if rng.random() < 0.85 else 2):
            w = rng.choice(words).capitalize()
            comps.append([f"CC_{i}_{k}", f"PC_{i}", str(k + 1), w, f"{w} {rng.choice([5, 50, 500])}mg", "", "TRUE"])
    write_csv(d / "medications.csv", MED_HEADER, meds)
    write_csv(d / "medication_ingredients.csv", COMP_HEADER, comps)
    return brands
