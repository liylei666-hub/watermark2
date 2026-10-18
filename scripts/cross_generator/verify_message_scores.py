"""Evaluator-private CPU cross-check using vectorized bits and ChaCha20 majority vote."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':raise SystemExit('CPU visibility required')
import json,sys
from pathlib import Path
import numpy as np
import io_contract as c
from phase_contract import verify_predictions


def decode(value,raw):
    from scipy.stats import norm
    from cryptography.hazmat.primitives.ciphers import Cipher,algorithms
    bins=np.minimum((2*norm.cdf(value.astype(np.float64))).astype(np.uint8),1).ravel(order='C')
    if not np.array_equal(bins,value.ravel(order='C')>=0):raise ValueError('Quantizer mismatch')
    cipher=Cipher(algorithms.ChaCha20(raw[32:64],raw[64:]),mode=None).decryptor()
    plain=cipher.update(np.packbits(bins,bitorder='big').tobytes())+cipher.finalize()
    decoded=np.unpackbits(np.frombuffer(plain,dtype=np.uint8),bitorder='big').reshape(64,256).sum(axis=0)>32
    message=np.unpackbits(np.frombuffer(raw[:32],dtype=np.uint8),bitorder='big')
    return float(np.mean(decoded==message))


def main(source):
    source=Path(source);folder=source/'tests';status=c.read(folder/'status.json')
    verify_predictions(folder,status['prediction_seal_sha256'])
    from gs_batch import private_module,r
    private=private_module();private_folder=r.ROOT/'private_eval'/(source.name+'_tests')
    result=c.read(folder/'evaluation.json');count=0
    for row in result['rows']:
        split=row['split'];sid=row['sample_id'];i=c.SPLITS[split].index(sid)
        prefix='proxy' if split=='proxy_test' else 'target'
        original=folder/(prefix+'_generate_'+str(i//4))/sid;record=c.read(original/'record.json')
        raw=private.load(private_folder,sid,record['encryption_fingerprints'])
        paths={'original':original/'original_noise.npy',
               **{name:folder/(split+'_predictions')/(sid+'_'+name+'.npy') for name in ('baseline','corrected')}}
        for name,path in paths.items():
            score=decode(np.load(path,allow_pickle=False),raw)
            if score!=row['decoded_message_accuracy'][name]:raise ValueError('Independent message score differs')
            count+=1
    return dict(verified=True,official_scores_cross_checked=count,method='Independent vectorized CDF, ChaCha20 and strict majority vote',
                private_material_exported=False,models_loaded=False,gpu_used=False)


if __name__=='__main__':print(json.dumps(main(sys.argv[1]),indent=2))
