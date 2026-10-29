"""PG-SMF losses and spectral preconditioners. Pure torch, CPU-testable, no I/O."""
import torch
import torch.nn.functional as F

SQRT2 = 1.4142135623730951
MARGIN_TAU = 0.65
BETA = 3.0
CONF_SCALE = 0.8
CH_W = (1.20, 1.05, 0.80, 0.95)          # ch0 > ch1 > ch3 > ch2 (Stage31 transfer order)
W_PROBIT, W_MARGIN, W_HUBER = 0.55, 0.30, 0.15


def channel_weights(device, dtype):
    return torch.tensor(CH_W, device=device, dtype=dtype).view(1, 4, 1, 1)


def radial_weight(n=64, r_low=6.0, r_mid=16.0, w_low=1.0, w_mid=0.60, w_high=0.25,
                  device=None, dtype=torch.float32):
    """Centered radial mask on the n x n FFT grid (DC at n//2)."""
    i = torch.arange(n, device=device, dtype=dtype)
    j = torch.arange(n, device=device, dtype=dtype)
    r = torch.sqrt((i.view(-1, 1) - n // 2) ** 2 + (j.view(1, -1) - n // 2) ** 2)
    w = torch.full((n, n), w_high, device=device, dtype=dtype)
    w = torch.where(r <= r_mid, torch.full_like(w, w_mid), w)
    w = torch.where(r <= r_low, torch.full_like(w, w_low), w)
    return w


def spec_filter(x, w):
    """Ideal radial filter applied to (...,4,64,64) via 2D FFT."""
    Fx = torch.fft.fftshift(torch.fft.fft2(x, dim=(-2, -1)), dim=(-2, -1))
    Fx = Fx * w.to(x.device, torch.complex64 if x.dtype == torch.float32 else x.dtype)
    return torch.real(torch.fft.ifft2(torch.fft.ifftshift(Fx, dim=(-2, -1)), dim=(-2, -1)))


def loss_pg_margin(inv, tgt, w=None, spectral_residual=False, rad=None):
    """PG-Margin: bounded probit alignment + confidence-weighted soft-margin sign loss.

    inv, tgt: (1,4,64,64).  tgt is the detached proxy-space z_T of the reference image.
    """
    if w is None:
        w = channel_weights(inv.device, inv.dtype)
    p_inv = torch.erf(inv / SQRT2)
    p_tgt = torch.erf(tgt / SQRT2)
    if spectral_residual:
        if rad is None:
            rad = radial_weight(64, device=inv.device, dtype=inv.dtype)
        d = p_inv - p_tgt
        d = spec_filter(d, rad)
        l_probit = d ** 2
    else:
        l_probit = (p_inv - p_tgt) ** 2

    s_tgt = torch.sign(tgt)
    conf = torch.tanh(tgt.abs() / CONF_SCALE)
    l_margin = conf * F.softplus(BETA * (MARGIN_TAU - s_tgt * inv)) / BETA

    l_huber = F.smooth_l1_loss(inv, tgt, beta=1.0, reduction='none')

    total = (w * (W_PROBIT * l_probit + W_MARGIN * l_margin + W_HUBER * l_huber)).mean()
    return total, dict(probit=float(l_probit.mean().detach()),
                       margin=float(l_margin.mean().detach()),
                       huber=float(l_huber.mean().detach()))


def loss_native_mse(inv, tgt, w=None, spectral_residual=False, rad=None):
    """Reference baseline: the untouched Stage31 objective, for sanity A/B."""
    return F.mse_loss(inv, tgt), dict(probit=0.0, margin=0.0, huber=float(F.mse_loss(inv, tgt)))


LOSSES = {'pg_margin': loss_pg_margin, 'native': loss_native_mse}
