"""Pixel-gradient adapter, compatible with reentrant checkpoint backward."""
def objective_gradient(pixels, encoder, transform, reference):
    import torch
    if not torch.isfinite(pixels).all() or pixels.min()<0 or pixels.max()>1:
        raise ValueError('Expected finite RGB [0,1] pixels')
    x=pixels.detach().clone().requires_grad_(True)
    output=transform(encoder(x))
    if output.shape!=reference.shape or reference.requires_grad:
        raise ValueError('Expected a fixed matching reference')
    loss=torch.nn.functional.mse_loss(output,reference)
    loss.backward()
    if x.grad is None or not torch.isfinite(x.grad).all() or not torch.isfinite(loss):
        raise RuntimeError('Invalid pixel gradient')
    return float(loss.detach().cpu()),x.grad.detach().clone(),output.detach().clone()
