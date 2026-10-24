import math,unittest
from analyze_native_calibration import aggregate
class Aggregation(unittest.TestCase):
    def test_per_image_db_and_aggregate_mse_are_distinct(self):
        a=aggregate([dict(mse_rgb01=.01),dict(mse_rgb01=.0001)])
        self.assertAlmostEqual(a['mean_per_image_psnr_db'],30)
        self.assertAlmostEqual(a['aggregate_mse_psnr_db'],-10*math.log10(.00505))
        self.assertGreater(a['mean_per_image_psnr_db'],a['aggregate_mse_psnr_db'])
    def test_identical_and_mixed_images_have_explicit_infinity(self):
        a=aggregate([dict(mse_rgb01=0),dict(mse_rgb01=0)]);self.assertTrue(a['aggregate_psnr_infinite']);self.assertIsNone(a['aggregate_mse_psnr_db'])
        b=aggregate([dict(mse_rgb01=0),dict(mse_rgb01=.02)]);self.assertIsNone(b['mean_per_image_psnr_db']);self.assertAlmostEqual(b['aggregate_mse_psnr_db'],20)
if __name__=='__main__':unittest.main()
