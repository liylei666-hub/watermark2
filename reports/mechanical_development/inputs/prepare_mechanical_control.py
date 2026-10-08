"""Deterministic ROI color integrity control; independent of detector scores."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import time
import numpy as np
from PIL import Image, ImageDraw

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True)
    ap.add_argument('--config', required=True)
    ap.add_argument('--bbox', type=int, nargs=4, required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    out = Path(args.output)
    assert not out.exists(), 'Never overwrite variants'
    out.mkdir(parents=True)
    cfg = json.loads(Path(args.config).read_text())
    image = Image.open(args.source).convert('RGB')
    assert image.size == (512, 512)
    rgb = np.array(image)
    hsv = np.array(image.convert('HSV'))
    rule = cfg['edit_rule']
    mask = ((hsv[:,:,0] <= rule['red_hue_max']) | (hsv[:,:,0] >= rule['red_hue_min_wrap'])) & (
        hsv[:,:,1] >= rule['saturation_min']) & (hsv[:,:,2] >= rule['value_min'])
    rectangle = np.zeros((512,512), bool)
    x0,y0,x1,y1 = args.bbox
    assert 0 <= x0 < x1 <= 512 and 0 <= y0 < y1 <= 512
    rectangle[y0:y1,x0:x1] = True
    mask &= rectangle
    assert mask.sum() >= 5000, 'Insufficient color support; preserve failure'
    Image.fromarray(mask.astype('uint8') * 255).save(out / 'region_mask.png')
    products = {'source': image}
    # Both members use identical RGB -> HSV -> RGB roundtrip on the same pixels.
    for condition in ('control','edit'):
        modified = hsv.copy()
        shift = rule['hue_shift_' + condition]
        modified[:,:,0][mask] = ((modified[:,:,0][mask].astype('int16') + shift) % 256).astype('uint8')
        converted = np.array(Image.fromarray(modified, 'HSV').convert('RGB'))
        result = rgb.copy()
        result[mask] = converted[mask]
        assert np.array_equal(result[~mask], rgb[~mask])
        products[condition] = Image.fromarray(result)
    hashes = {}
    grid = Image.new('RGB', (3*512,3*536),'white')
    draw = ImageDraw.Draw(grid)
    for row, condition in enumerate(('source','control','edit')):
        for col, processing in enumerate(cfg['processing']):
            product = products[condition]
            name = condition + '_' + processing
            if processing == 'jpeg70':
                buf = io.BytesIO()
                product.save(buf,format='JPEG',**cfg['jpeg'])
                (out / (condition + '_jpeg70.jpg')).write_bytes(buf.getvalue())
                product = Image.open(io.BytesIO(buf.getvalue())).convert('RGB')
            elif processing == 'resize05':
                product = product.resize((256,256),Image.Resampling.BICUBIC).resize((512,512),Image.Resampling.BICUBIC)
            else:
                assert processing == 'original'
            product.save(out / (name + '.png'))
            hashes[name + '.png'] = sha(out / (name + '.png'))
            grid.paste(product,(col*512,row*536+24))
            draw.text((col*512+10,row*536+6),name,fill='black')
    grid.save(out / 'review_grid.png')
    recipe = {'config_sha256':sha(args.config),'constructor_sha256':sha(__file__),
        'source_sha256':sha(args.source),'bbox_xyxy':args.bbox,'mask_pixels':int(mask.sum()),
        'mask_fraction':float(mask.mean()),'mask_sha256':sha(out/'region_mask.png'),
        'outside_mask_exactly_unchanged':True,'image_hashes':hashes,
        'control_max_pixel_delta':int(np.abs(np.array(products['control']).astype(int)-rgb).max()),
        'edit_kind':'mechanical integrity control, not natural semantic attack',
        'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    (out/'recipe.json').write_text(json.dumps(recipe,indent=2)+'\n',encoding='utf8')
    (out/'visual_review.template.json').write_text(json.dumps({
        'reviewed_before_scoring':False,'valid_fact_change':False,'control_fact_unchanged':False,
        'all_processing_facts_reviewed':False,'image_hashes':hashes,
        'fact_before':cfg['fact_before'],'fact_after':cfg['fact_after'],
        'reviewer':'pending','reviewed_utc':None},indent=2)+'\n',encoding='utf8')
    print(json.dumps(recipe,indent=2))

if __name__ == '__main__':
    main()
