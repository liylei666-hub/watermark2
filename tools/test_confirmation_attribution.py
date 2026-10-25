import unittest
from confirmation_attribution import parse_flickr_source as parse
class SourceIdentity(unittest.TestCase):
 def test_real_COCO_legacy_static(self):
  u='http://farm7.staticflickr.com/6116/6255196340_da26cf2c9e_z.jpg';r=parse(u)
  self.assertEqual(r['original_flickr_url'],u);self.assertEqual(r['flickr_photo_id'],'6255196340');self.assertIsNone(r['creator_account_from_source_url']);self.assertEqual(r['creator_status'],'unknown_not_in_original_metadata_URL')
 def test_modern_static(self):self.assertEqual(parse('https://live.staticflickr.com/7372/12502775644_acfd415fa7.jpg')['flickr_photo_id'],'12502775644')
 def test_author_page(self):
  r=parse('https://www.flickr.com/photos/12037949754@N01/155761353/');self.assertEqual(r['creator_account_from_source_url'],'12037949754@N01');self.assertEqual(r['flickr_photo_id'],'155761353')
 def test_pretty_account_page(self):self.assertEqual(parse('https://flickr.com/photos/example-name/123')['creator_account_from_source_url'],'example-name')
 def test_missing_or_wrong_type(self):
  for x in (None,'',[],42):self.assertIsNone(parse(x))
 def test_unknown_host_and_ambiguous_forms(self):
  for x in ('https://evil.example/1/123_abc_z.jpg','https://farm1.staticflickr.com.evil.example/1/123_abc_z.jpg','https://flickr.com/photos/me/123','https://flickr.com/photos/owner/not-a-photo','https://flickr.com/photos/owner/0','https://farm1.staticflickr.com/1/123.jpg'):
   self.assertIsNone(parse(x),x)
 def test_credentials_ports_queries_fragments_and_encoding_rejected(self):
  for x in ('https://u:p@flickr.com/photos/a/123','https://flickr.com:443/photos/a/123','https://flickr.com/photos/a/123?auth=x','https://flickr.com/photos/a/123#x','https://flickr.com/photos/a/%31%32%33','ftp://flickr.com/photos/a/123'):
   self.assertIsNone(parse(x),x)
 def test_source_page_and_static_share_same_photo_identity(self):self.assertEqual(parse('https://flickr.com/photos/a/6255196340')['photo_key'],parse('https://farm7.staticflickr.com/6116/6255196340_da26cf2c9e_z.jpg')['photo_key'])
if __name__=='__main__':unittest.main()
