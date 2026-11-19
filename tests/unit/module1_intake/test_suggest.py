import pytest
from dataclasses import replace

from module1_intake.manual_input.dictionary import MedicationEntry, load_dictionary
from module1_intake.manual_input.suggest import MedicationSuggester

from .synth import small_dataset


@pytest.fixture(scope="module")
def sg(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    small_dataset(d)
    return MedicationSuggester(load_dictionary(d))


def brands(res):
    return [r.brand_name for r in res]


def test_short_or_empty_query(sg):
    assert sg.suggest("") == [] and sg.suggest("  ") == [] and sg.suggest("a") == []


def test_exact_prefix_and_output_fields(sg):
    r = sg.suggest("essium")[0]
    assert r.brand_name == "Essium 40 mg" and r.match_type == "EXACT_PREFIX"
    assert r.active_ingredient == ["Esomeprazol"] and r.dosage_form == "Bột đông khô"
    assert r.medication_id == "PC_1"
    assert set(r.to_dict()) == {"brand_name", "active_ingredient", "strength",
                                "dosage_form", "match_type", "medication_id"}


def test_no_diacritics_and_case(sg):
    assert brands(sg.suggest("  AUGMENTIN  "))[0] == "Augmentin 625mg"


def test_compact_forms(sg):
    for q in ("t-esom", "t esom 20", "tesom20", "T Esom"):
        assert brands(sg.suggest(q))[0] == "T-Esom20", q


def test_search_by_ingredient_including_alt_name(sg):
    assert "Essium 40 mg" in brands(sg.suggest("esomeprazol"))
    assert "Essium 40 mg" in brands(sg.suggest("esomeprazole"))   # tên chuẩn hóa
    assert "Natribicarbonat Stada" in brands(sg.suggest("natri bic"))


def test_fuzzy_typos(sg):
    for q in ("esium 40", "agumentin", "augmentn", "essuim", "amoxicilin"):
        res = sg.suggest(q)
        assert res and res[0].match_type in ("FUZZY_MATCH", "EXACT_PREFIX"), q
    assert brands(sg.suggest("augmetin"))[0] == "Augmentin 625mg"
    assert sg.suggest("augmetin")[0].match_type == "FUZZY_MATCH"


def test_qualifier_ranks_strength(sg):
    res = sg.suggest("amoxicillin 500", limit=5)
    assert res[0].strength == "Amoxicillin 500mg" or "500" in res[0].brand_name


def test_distinct_product_ids_keep_identical_display_and_ranking(sg):
    results = sg.suggest("amoxicillin stada 500", limit=5)
    same_name = [row.medication_id for row in results if row.brand_name == 'Amoxicillin Stada 500']
    assert same_name == ['PC_7', 'PC_8']  # qualified product remains first; both are selectable
    assert sg.suggest('amoxicillin stada 500', limit=1) == results[:1]


def test_duplicate_rows_and_aliases_emit_each_product_id_once():
    entry = MedicationEntry('PRODUCT_A', 'Example', 'Viên nén', ('Example ingredient',), '10mg', True)
    other = replace(entry, medication_id='PRODUCT_B', level2_qualified=False)
    suggester = MedicationSuggester([entry, replace(entry, alt_names=('Example alias',)), other])
    assert [row.medication_id for row in suggester.suggest('example', limit=100)] == ['PRODUCT_A', 'PRODUCT_B']


def test_level2_ranked_first_but_not_hidden(sg):
    res = sg.suggest("thinmcz")
    assert brands(res) == ["Thinmcz-100"]           # chưa đạt Level 2 vẫn hiện


def test_limit(sg):
    assert len(sg.suggest("am", limit=2)) <= 2
    with pytest.raises(ValueError):
        sg.suggest("am", limit=0)
    with pytest.raises(TypeError):
        sg.suggest(None)


def test_custom_fallback(sg):
    res = sg.suggest("  zzqxwv   thuoc ")
    assert len(res) == 1
    assert res[0].match_type == "CUSTOM_FALLBACK" and res[0].brand_name == "zzqxwv thuoc"
    assert res[0].medication_id is None and res[0].active_ingredient is None
