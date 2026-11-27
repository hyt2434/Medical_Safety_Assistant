from module1_intake.manual_input.text_utils import compact, normalize


def test_normalize_vietnamese():
    assert normalize("  Viên   NÉN  Đau ") == "vien nen dau"
    assert normalize("Đông khô") == "dong kho"
    assert normalize(None) == "" and normalize("") == ""


def test_compact():
    assert compact("T-Esom 20") == compact("t esom20") == "tesom20"
