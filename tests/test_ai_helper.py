import unittest
from utils.ai_helper import get_child_level_diagnoses_from_condition

class TestAITasks(unittest.TestCase):

    def setUp(self):
        self.nct_condition = 'Colorectal Cancer'
        self.child_nodes_oncotree_list = ['Signet Ring Cell Adenocarcinoma of the Colon and Rectum', 'Colon Adenocarcinoma In Situ', 'Small Bowel Well-Differentiated Neuroendocrine Tumor', 'Gastrointestinal Neuroendocrine Tumors', 'Well-Differentiated Neuroendocrine Tumor of the Rectum', 'Small Bowel Cancer', 'Anal Squamous Cell Carcinoma', 'Anorectal Mucosal Melanoma', 'Low-grade Appendiceal Mucinous Neoplasm', 'Medullary Carcinoma of the Colon', 'Goblet Cell Adenocarcinoma of the Appendix', 'Mucinous Adenocarcinoma of the Appendix', 'Appendiceal Adenocarcinoma', 'Small Intestinal Carcinoma', 'Well-Differentiated Neuroendocrine Tumor of the Appendix', 'Signet Ring Cell Type of the Appendix', 'Colorectal Adenocarcinoma', 'High-Grade Neuroendocrine Carcinoma of the Colon and Rectum', 'Colonic Type Adenocarcinoma of the Appendix', 'Anal Gland Adenocarcinoma', 'Rectal Adenocarcinoma', 'Mucinous Adenocarcinoma of the Colon and Rectum', 'Duodenal Adenocarcinoma', 'Colon Adenocarcinoma', 'Tubular Adenoma of the Colon']

   
    def test_get_child_level_diagnoses_from_condition(self):
        oncotree_diagnoses_dict = get_child_level_diagnoses_from_condition("", set(self.child_nodes_oncotree_list), self.nct_condition)
        self.assertIsNotNone(oncotree_diagnoses_dict, msg="faield to get child level diagnoses")

if __name__ == "__main__":
    unittest.main()