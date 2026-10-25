import json,time,datetime
from pathlib import Path
root=Path('/data0/liyanlei/watermark_research/runs/31_native_calibration_20261024T190323Z')
while True:
    try:
        state=json.loads((root/'scheduler_status.json').read_text()); rows={}
        for folder in sorted(root.glob('attack_*')):
            log=folder/'stdout.log'
            if log.exists():
                lines=[x for x in log.read_text(errors='replace').splitlines() if x.startswith('NATIVE_UPDATE')]
                rows[folder.name]=dict(actual_updates=int(lines[-1].split()[1]) if lines else 0,completed=(folder/'execution.json').exists())
        print(json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),state=state,progress=rows)),flush=True)
        if state['state'] in ('stopped','completed'):break
    except FileNotFoundError:print('WAITING_STATUS',flush=True)
    time.sleep(45)
