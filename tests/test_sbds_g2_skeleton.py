"""SBDS G2スケルトンのimport確認テスト"""
import unittest


class TestSBDSG2Skeleton(unittest.TestCase):
    def test_g2_init_importable(self):
        import src.sbds_g2

    def test_g2_version_defined(self):
        import src.sbds_g2
        self.assertEqual(src.sbds_g2.G2_VERSION, '2.0.0-skeleton')

    def test_ar_guide_importable(self):
        import src.sbds_g2.ar_guide

    def test_multi_building_importable(self):
        import src.sbds_g2.multi_building

    def test_mgmt_api_importable(self):
        import src.sbds_g2.mgmt_api

    def test_pwa_importable(self):
        import src.sbds_g2.pwa

    def test_shared_importable(self):
        import src.sbds_g2.shared

    def test_g1_not_broken_by_g2(self):
        # G1モジュールが正常にインポートできることを確認
        import src.sbds.tms_set_001
        import src.sbds.tms_drv_001


if __name__ == '__main__':
    unittest.main()
