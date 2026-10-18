"""Evaluator-only explicit GS material, kept outside publishable run directories."""
import hashlib
import os
import stat
from pathlib import Path

def fingerprints(raw):
    if len(raw) != 80:
        raise ValueError('Invalid encryption material size')
    return {name: hashlib.sha256(value).hexdigest() for name, value in
            [('message', raw[:32]), ('key', raw[32:64]), ('nonce', raw[64:])]}

def create(folder, task):
    folder = Path(folder)
    if folder.is_symlink() or stat.S_IMODE(folder.stat().st_mode) != 0o700:
        raise ValueError('Private directory mode must be 0700')
    raw = os.urandom(80)
    fd = os.open(folder / (str(task) + '.bin'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    return raw

def load(folder, task, expected):
    path = Path(folder) / (str(task) + '.bin')
    if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError('Private file mode must be 0600')
    raw = path.read_bytes()
    if fingerprints(raw) != expected:
        raise ValueError('Encryption state fingerprint changed')
    return raw

def provider(raw, device):
    import torch
    from utils.wm.gs_provider import GsProvider
    fingerprints(raw)
    return GsProvider(latent_shape=(1, 4, 64, 64), device=device, dtype=torch.float32,
                      message_width_in_bytes=32, num_replications=64, l=1, offset=0,
                      message=raw[:32], key=raw[32:64], nonce=raw[64:])
