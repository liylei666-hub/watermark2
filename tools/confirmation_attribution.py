"""Parse source identity; URL syntax never establishes redistribution permission."""
import re,urllib.parse
STATIC=re.compile(r'/\d+/([1-9]\d*)_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)?\.(?:jpg|jpeg|png|gif)')
PAGE=re.compile(r'/photos/([A-Za-z0-9_@-]+)/([1-9]\d*)/?')
def parse_flickr_source(value):
 if not isinstance(value,str) or not value or len(value)>2048:return None
 try:
  u=urllib.parse.urlsplit(value)
  if u.scheme not in ('http','https') or u.username or u.password or u.port is not None or u.query or u.fragment or '%' in u.path:return None
 except ValueError:return None
 owner=None;kind=None;ident=None
 if u.hostname=='live.staticflickr.com' or re.fullmatch(r'farm[1-9]\d*\.staticflickr\.com',u.hostname or ''):
  m=STATIC.fullmatch(u.path)
  if m:ident=m[1];kind='static_photo_URL'
 elif u.hostname in ('flickr.com','www.flickr.com'):
  m=PAGE.fullmatch(u.path)
  if m and m[1].lower()!='me':owner=m[1];ident=m[2];kind='public_photo_page_URL'
 if ident is None:return None
 return dict(original_flickr_url=value,flickr_photo_id=ident,photo_key=ident,creator_account_from_source_url=owner,creator_display_name=None,source_form=kind,creator_status='account_present_in_source_not_independently_verified' if owner else 'unknown_not_in_original_metadata_URL',redistribution_status='not_cleared_do_not_publish_image',source_syntax_is_not_license_or_current_rights_verification=True)
