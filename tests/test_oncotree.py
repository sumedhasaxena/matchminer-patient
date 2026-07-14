import unittest
from pprint import pprint

from utils.oncotree import (
    _get_level_columns,
    _parse_level_value,
    _read_oncotree_rows,
    get_all_oncotree_data,
    get_l1_l2_oncotree_data,
    get_children_of_term,
    resolve_diagnosis_hierarchy,
    build_diagnosis_result_from_path,
    canonicalize_term,
)


class TestOncotree(unittest.TestCase):

    def test_get_level_columns(self):
        fieldnames = ["level_3", "level_1", "metamaintype", "level_2"]
        self.assertEqual(_get_level_columns(fieldnames), ["level_1", "level_2", "level_3"])

    def test_parse_level_value(self):
        self.assertEqual(_parse_level_value("Breast (BREAST)"), "Breast")
        self.assertEqual(_parse_level_value(""), "")
        self.assertEqual(_parse_level_value(None), "")

    def test_read_oncotree_rows(self):
        rows, level_columns = _read_oncotree_rows()
        self.assertGreater(len(rows), 0)
        self.assertEqual(level_columns[0], "level_1")
        self.assertEqual(len(level_columns), 6)

    def test_get_all_oncotree_data(self):
        level_1_list, mapping_l1_all = get_all_oncotree_data()
        self.assertIn("Breast", level_1_list)
        self.assertGreater(len(mapping_l1_all["Breast"]), 0)
        self.assertIn("APL with PML-RARA", mapping_l1_all["Myeloid"])
        self.assertIn("Glioblastoma, IDH-Wildtype", mapping_l1_all["CNS/Brain"])

    def test_get_l1_l2_oncotree_data(self):
        level_1_list, mapping_l1_l2 = get_l1_l2_oncotree_data()
        pprint(sorted(level_1_list))
        self.assertIn("Breast", level_1_list)
        self.assertGreater(len(mapping_l1_l2["Breast"]), 0)
        self.assertIn("Diffuse Glioma", mapping_l1_l2["CNS/Brain"])

    def test_get_children_of_term(self):
        children = get_children_of_term("Diffuse Glioma")
        self.assertIn("Adult-Type Diffuse Glioma", children)

        leaf_children = get_children_of_term("Gliosarcoma")
        self.assertEqual(leaf_children, [])

    def test_resolve_diagnosis_hierarchy_level3(self):
        result = resolve_diagnosis_hierarchy("Colon Adenocarcinoma")
        self.assertIsNotNone(result)
        self.assertEqual(result["primary_diagnosis"], "Colon Adenocarcinoma")
        self.assertEqual(result["level3"], "Colon Adenocarcinoma")
        self.assertGreaterEqual(len(result["path"]), 3)

    def test_resolve_diagnosis_hierarchy_level4(self):
        result = resolve_diagnosis_hierarchy("Glioblastoma, IDH-Wildtype")
        self.assertIsNotNone(result)
        self.assertEqual(result["primary_diagnosis"], "Glioblastoma, IDH-Wildtype")
        self.assertEqual(result["level1"], "CNS/Brain")
        self.assertEqual(result["level2"], "Diffuse Glioma")
        self.assertEqual(result["level3"], "Adult-Type Diffuse Glioma")
        self.assertEqual(len(result["path"]), 4)

    def test_resolve_diagnosis_hierarchy_case_insensitive(self):
        result = resolve_diagnosis_hierarchy("glioblastoma, idh-wildtype")
        self.assertIsNotNone(result)
        self.assertEqual(result["primary_diagnosis"], "Glioblastoma, IDH-Wildtype")

    def test_build_diagnosis_result_from_path(self):
        result = build_diagnosis_result_from_path(["Lung", "Non-Small Cell Lung Cancer"])
        self.assertEqual(result["primary_diagnosis"], "Non-Small Cell Lung Cancer")
        self.assertEqual(result["level1"], "Lung")
        self.assertEqual(result["level2"], "Non-Small Cell Lung Cancer")
        self.assertIsNone(result["level3"])

    def test_canonicalize_term(self):
        self.assertEqual(canonicalize_term("breast", {"Breast", "Lung"}), "Breast")
        self.assertIsNone(canonicalize_term("Unknown", {"Breast", "Lung"}))


if __name__ == "__main__":
    unittest.main()
