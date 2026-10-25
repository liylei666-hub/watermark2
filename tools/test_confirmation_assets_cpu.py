import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import io,sys,unittest
from PIL import Image
from prepare_confirmation100_assets import allowed_url,RedirectGuard,textsha,image_features
class Rules(unittest.TestCase):
 def test_official_origin_and_no_credentials_or_queries(self):
  self.assertTrue(allowed_url('https://images.cocodataset.org/val2017/000000000139.jpg'))
  for url in ['http://images.cocodataset.org/a','https://example.org/a','https://user:pass@images.cocodataset.org/a','https://images.cocodataset.org/a?key=x']:
   self.assertFalse(allowed_url(url))
 def test_no_cross_origin_redirect_or_downgrade(self):
  for url in ['https://example.org/login','http://images.cocodataset.org/a']:
   with self.assertRaises(RuntimeError):RedirectGuard().redirect_request(None,None,302,'',{},url)
 def test_caption_dedup_unicode_case_and_whitespace(self):
  self.assertEqual(textsha('Ａ CAT\tstands. '),textsha('a cat stands.'))
  self.assertNotEqual(textsha('a cat stands.'),textsha('a dog stands.'))
 def test_lossless_pixel_dedup_and_no_model_import(self):
  image=Image.new('RGB',(120,80),'red');features,canonical=image_features(image);data=io.BytesIO();image.save(data,format='PNG');data.seek(0)
  with Image.open(data) as reread:again,_=image_features(reread)
  self.assertEqual(features,again);self.assertEqual(canonical.size,(512,512));self.assertEqual(canonical.mode,'RGB')
  self.assertFalse(any(n in sys.modules for n in ('torch','diffusers','transformers','lpips')))
if __name__=='__main__':unittest.main()
