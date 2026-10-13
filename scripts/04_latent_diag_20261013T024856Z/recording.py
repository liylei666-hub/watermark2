"""Observation-only wrappers; no model imports. CPU copies retain source dtype."""
import functools
import hashlib
import inspect
import json
from pathlib import Path
import numpy as np
from PIL import Image

COMMIT = "ca68950cd7b53b8438a49580f134b2a0db28d778"
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_json(path, data):
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class Recorder:
    def __init__(self, directory, config_hash, target_id):
        self.directory = Path(directory)
        self.config_hash = config_hash
        self.target_id = target_id
        self.step = None
        self.sampled_object = None
        self.records = {}
        self.images = {}
        self.counts = {"sampling": 0, "target_generate": 0, "proxy_generate": 0,
                       "target_invert": 0, "proxy_invert": 0, "validate": 0}
    def tensor(self, name, value, source, step):
        assert name not in self.records
        # Copy explicitly: never move/replace the tensor being used by the pipeline.
        cpu = value.detach().to(device="cpu", copy=True).contiguous()
        array = cpu.numpy()
        path = self.directory / (name + ".npy")
        with path.open("xb") as f: np.save(f, array, allow_pickle=False)
        restored = np.load(path, allow_pickle=False)
        equal = restored.dtype == array.dtype and restored.shape == array.shape and np.array_equal(restored, array)
        assert equal
        self.records[name] = dict(path=str(path), sha256=sha(path), shape=list(array.shape),
            dtype=str(array.dtype), role="target", source_commit=COMMIT, capture_source=source,
            step=step, reference_id="reference_0001", candidate_id="candidate_0001" if step==1 else None,
            config_sha256=self.config_hash, cpu_roundtrip_equal=equal)
    def bind_image(self, step, pil_before, path):
        with Image.open(path) as image:
            assert image.mode == "RGB"
            decoded = np.asarray(image).copy()
        assert np.array_equal(pil_before, decoded), "Validated pixels differ from saved PNG"
        self.images[str(step)] = dict(path=str(path), sha256=sha(path), shape=list(decoded.shape),
                                      validated_pixels_equal_saved_png=True)
        names = ["target_inverted_forged_zT"] if step==1 else ["target_original_wm_zT", "target_inverted_reference_zT"]
        for name in names:
            self.records[name]["image_path"] = str(path)
            self.records[name]["image_sha256"] = sha(path)
        write_json(self.directory / ("binding_step_" + str(step) + ".json"), self.images[str(step)])
    def finish(self):
        assert self.counts == {"sampling":1,"target_generate":1,"proxy_generate":1,
                               "target_invert":2,"proxy_invert":1,"validate":2}, self.counts
        assert len(self.records)==3 and len(self.images)==2
        write_json(self.directory/"tensor_manifest.json", dict(tensors=self.records,images=self.images,
            counts=self.counts,original_sampling_object_is_generation_input=True,config_sha256=self.config_hash))
        write_json(self.directory/"candidate_frozen.json", dict(candidate_id="candidate_0001",
            path=self.images["1"]["path"],sha256=self.images["1"]["sha256"],config_sha256=self.config_hash))

def wrap_sampling(original, recorder):
    @functools.wraps(original)
    def wrapped(*args, **kwargs):
        result = original(*args, **kwargs)
        recorder.counts["sampling"] += 1
        recorder.sampled_object = result["zT_torch"]
        return result
    return wrapped

def wrap_generate(original, recorder):
    @functools.wraps(original)
    def wrapped(provider, *args, **kwargs):
        target = provider.pretrained_model_name_or_path == recorder.target_id
        recorder.counts["target_generate" if target else "proxy_generate"] += 1
        if target:
            latent = inspect.signature(original).bind(provider,*args,**kwargs).arguments["latents"]
            assert latent is recorder.sampled_object
            recorder.tensor("target_original_wm_zT", latent,
                "run_reprompting.py:109-117; utils/pipe/pipe_provider.py:210-246 (generate input)", -1)
        return original(provider,*args,**kwargs)
    return wrapped

def wrap_invert(original, recorder):
    @functools.wraps(original)
    def wrapped(provider, *args, **kwargs):
        target = provider.pretrained_model_name_or_path == recorder.target_id
        recorder.counts["target_invert" if target else "proxy_invert"] += 1
        result = original(provider,*args,**kwargs)
        if target:
            assert recorder.step in (-1,1)
            name = "target_inverted_reference_zT" if recorder.step==-1 else "target_inverted_forged_zT"
            recorder.tensor(name,result["zT_torch"],
                "utils/imprint_utils.py:338-343 (existing validate inversion return)",recorder.step)
        return result
    return wrapped

def wrap_validate(original, recorder):
    @functools.wraps(original)
    def wrapped(*args, **kwargs):
        args_bound = inspect.signature(original).bind(*args,**kwargs).arguments
        step = args_bound["step"]
        assert step in (-1,1) and recorder.step is None
        pixels = np.asarray(args_bound["image_to_verify_PIL"]).copy()
        recorder.counts["validate"] += 1
        recorder.step = step
        try: result = original(*args,**kwargs)
        finally: recorder.step = None
        path = Path(args_bound["out_dir"]) / ("attack_instance_step=" + str(step) + ".png")
        recorder.bind_image(step,pixels,path)
        return result
    return wrapped

def wrap_download(original_function, expected, records):
    @functools.wraps(original_function)
    def wrapped(cls, model_id, *args, **kwargs):
        result = original_function(cls,model_id,*args,**kwargs)
        actual = str(Path(result).resolve())
        assert actual == str(Path(expected[model_id]).resolve()), "Unexpected actual snapshot"
        records.append(dict(model_id=model_id,actual_snapshot=actual,pipeline_class=cls.__name__))
        return result
    return wrapped

