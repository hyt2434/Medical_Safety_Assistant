import pytest

from module1_intake.dictionary import DictionaryError, load_dictionary

from .synth import COMP_HEADER, small_dataset, write_csv


def test_load_small(tmp_path):
    small_dataset(tmp_path)
    by_id = {e.medication_id: e for e in load_dictionary(tmp_path)}
    assert "PC_9" not in by_id                      # thiếu brand -> bỏ qua
    assert len(by_id) == 8

    e1 = by_id["PC_1"]                              # 1 hoạt chất -> chỉ phần hàm lượng
    assert e1.active_ingredients == ("Esomeprazol",)
    assert e1.strength == "(dưới dạng Esomeprazol natri) 40mg"
    assert e1.level2_qualified is True
    assert e1.alt_names == ("esomeprazole",)        # tên chuẩn hóa chỉ để tìm kiếm

    e3 = by_id["PC_3"]                              # nhiều hoạt chất: sắp theo ordinal, khóa nối hỏng không làm lỗi
    assert e3.active_ingredients == ("Amoxicillin", "Acid clavulanic")
    assert e3.strength == "Amoxicillin 500mg + Acid clavulanic 125mg"

    e4 = by_id["PC_4"]                              # thiếu hoạt chất -> tuple rỗng, strength None
    assert e4.active_ingredients == () and e4.strength is None and e4.level2_qualified is False
    assert by_id["PC_5"].strength == "1100mg"


def test_missing_file_and_column(tmp_path):
    with pytest.raises(DictionaryError):
        load_dictionary(tmp_path)
    small_dataset(tmp_path)
    write_csv(tmp_path / "medication_ingredients.csv", COMP_HEADER[:3], [])
    with pytest.raises(DictionaryError, match="thiếu cột"):
        load_dictionary(tmp_path)


def test_ingredients_csv_optional(tmp_path):
    small_dataset(tmp_path)
    (tmp_path / "ingredients.csv").unlink()
    assert len(load_dictionary(tmp_path)) == 8
