import unittest
from utils.oncotree import get_l1_l2_oncotree_data

class TestGetOncotreeData(unittest.TestCase):
   
    def test_get_l1_l2_oncotree_data(self):        
        level_1_list, mapping_11_l2 = get_l1_l2_oncotree_data()
        self.assertIsNotNone(level_1_list)
        self.assertIsNotNone(mapping_11_l2)

if __name__ == "__main__":
    unittest.main()