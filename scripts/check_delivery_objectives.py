"""Synthetic algebra checks for stage26; no pretrained models or experiment inputs."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility must be empty')
import hashlib,json,sys,datetime
from pathlib import Path
import numpy as np

def main(protocol,output):
    protocol=Path(protocol);cfg=json.loads(protocol.read_text(encoding='utf-8'))
    digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    if digest(protocol)!=protocol.with_suffix('.sha256').read_text().strip():raise ValueError('Protocol changed')
    if digest(__file__)!=cfg['code_sha256']:raise ValueError('Code changed')
    rng=np.random.default_rng(cfg['seed']);results=[]
    # Linear generator and inverse: independently compare the analytical chain rule to finite differences.
    A=rng.normal(size=(3,5));B=rng.normal(size=(5,2));b=rng.normal(size=5);u=rng.normal(size=2);z=rng.normal(size=3)
    loss=lambda v:float(np.mean((A@(B@v+b)-z)**2))
    gx=2*A.T@(A@(B@u+b)-z)/3;gu=B.T@gx
    h=cfg['finite_difference_step'];fd=np.array([(loss(u+np.eye(2)[i]*h)-loss(u-np.eye(2)[i]*h))/(2*h) for i in range(2)])
    error=float(np.max(np.abs(gu-fd)));assert error<cfg['chain_rule_absolute_tolerance']
    eta=.01;dx=(B@(u-eta*gu)+b)-(B@u+b);pred=-eta*B@B.T@gx
    induced=float(np.max(np.abs(dx-pred)));assert induced<1e-12
    results.append(dict(name='linear_reparameterization',passed=True,gradient_max_error=error,induced_update_max_error=induced))
    # Same-condition, exact inverse is an explicit ideal assumption, not an SD claim.
    G=np.array([[2.,1.],[1.,1.]]);I=np.linalg.inv(G);zr=np.array([.75,-.25]);candidate=np.array([.2,.4])
    assert np.allclose(I@G,np.eye(2),atol=1e-14,rtol=0)
    composed=float(np.sum((I@G@candidate-zr)**2));direct=float(np.sum((candidate-zr)**2))
    baseline=float(np.sum((I@G@zr-zr)**2));assert abs(composed-direct)<1e-14 and baseline<1e-28
    results.append(dict(name='ideal_inverse_identity',passed=True,composed_loss=composed,direct_loss=direct,baseline_loss=baseline))
    # Restricting the range of a generator changes feasible candidates, not target information.
    B=np.array([[1.],[0.]]);u=np.array([0.]);target=np.array([0.,1.]);gx=2*(B@u-target);gu=B.T@gx
    assert np.array_equal(gu,np.zeros(1)) and float(np.sum((B@u-target)**2))==1
    results.append(dict(name='rank_restricted_stationary_point',passed=True,loss=1.,parameter_gradient=gu.tolist()))
    # Illustrative uint8 quantizer; PNG storage itself is lossless after this conversion.
    q=lambda x:np.floor(np.clip(x,0,1)*255)/255
    x=.501;t=.1;h=1e-7
    exact=((q(x+h)-t)**2-(q(x-h)-t)**2)/(2*h);relaxed=2*(x-t)
    assert exact==0 and relaxed!=0
    boundary=128/255
    boundary_fd=((q(boundary+h)-t)**2-(q(boundary-h)-t)**2)/(2*h)
    assert abs(boundary_fd)>100
    results.append(dict(name='quantized_delivery_gradient',passed=True,interior_difference=exact,relaxed_gradient=relaxed,boundary_difference=boundary_fd,
        interpretation='Local constant quantization and discontinuous boundaries; a relaxed backward path is not the exact derivative.'))
    report=dict(checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),protocol_sha256=digest(protocol),code_sha256=digest(__file__),
        seed=cfg['seed'],checks=results,passed=len(results),gpu_used=False,models_loaded=False,new_model_experiments_run=0,
        actual_diffusion_gradient_validated=False,novelty_established=False)
    with Path(output).open('x',encoding='utf-8',newline='\n') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main(*sys.argv[1:])
