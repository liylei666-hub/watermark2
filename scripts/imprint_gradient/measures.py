"""Pure CPU arithmetic for comparing two gradients."""
def summarize_gradients(native, delivery):
    import numpy as np
    if native.shape != delivery.shape:
        raise ValueError('Gradient shapes differ')
    a = np.asarray(native, dtype=np.float64).reshape(-1)
    b = np.asarray(delivery, dtype=np.float64).reshape(-1)
    if not a.size or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Nonfinite or empty gradient')
    aa, bb, ab = float(a @ a), float(b @ b), float(a @ b)
    if aa <= 0 or bb <= 0:
        raise ValueError('Zero gradient')
    return dict(cosine=max(-1., min(1., ab / (aa * bb)**.5)),
        native_l2=aa**.5, delivery_l2=bb**.5, inner_product=ab,
        delivery_to_native_l2_ratio=(bb / aa)**.5,
        native_rms=(aa / a.size)**.5, delivery_rms=(bb / b.size)**.5,
        coordinates=int(a.size))
