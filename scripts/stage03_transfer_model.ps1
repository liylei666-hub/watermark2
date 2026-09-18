$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = Split-Path -Parent $PSScriptRoot
$key = Join-Path $env:USERPROFILE '.ssh\ceramic_249_ed25519'
$remote = '/data0/liyanlei/instance_authentication_research'
$repo = 'stabilityai/stable-diffusion-xl-base-1.0'
$revision = '462165984030d82259a11f4367a4eed129e94a7b'
$meta = Invoke-RestMethod -Uri "https://huggingface.co/api/models/$repo/revision/${revision}?blobs=true" -TimeoutSec 30
$names = @('model_index.json', 'scheduler/scheduler_config.json')
foreach ($component in @('text_encoder','text_encoder_2','unet','vae')) {
    $names += "$component/config.json"
    if ($component.StartsWith('text')) { $names += "$component/model.fp16.safetensors" }
    else { $names += "$component/diffusion_pytorch_model.fp16.safetensors" }
}
foreach ($component in @('tokenizer','tokenizer_2')) {
    foreach ($name in @('merges.txt','vocab.json','special_tokens_map.json','tokenizer_config.json')) { $names += "$component/$name" }
}
$files = @($names | ForEach-Object { $name=$_; $meta.siblings | Where-Object rfilename -eq $name })
if ($files.Count -ne $names.Count) { throw 'Required file missing from official repository' }
$total = ($files | Measure-Object -Property size -Sum).Sum
if ($total -gt 15000000000) { throw 'Download selection exceeds 15 GB' }
$out = Join-Path $root 'outputs/stage03'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$recordPath = Join-Path $out 'generator_files.json'
if (Test-Path -LiteralPath $recordPath) {
    $old = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
    if ($old.revision -ne $meta.sha) { throw 'Revision changed; retain pinned run' }
}
$record = [ordered]@{model_id=$repo;revision=$meta.sha;selected_bytes=$total;status='downloading';files=@();local_path="weights/stage03_sdxl/$($meta.sha)";route='Official HTTPS download on local host; SCP; SHA256 verified on server'}
$transferBytes = 0L
$staging = Join-Path $root "weights/stage03_sdxl/$($meta.sha)"
$budgetPath = Join-Path $out 'download_budget.json'
if (Test-Path -LiteralPath $budgetPath) { $transferBytes = [long](Get-Content -LiteralPath $budgetPath -Raw | ConvertFrom-Json).transferred_bytes }
# Account for bytes saved before an interrupted process could update its ledger.
$savedBytes = [long](Get-ChildItem -LiteralPath $staging -Recurse -File | Measure-Object -Property Length -Sum).Sum
$transferBytes = [Math]::Max($transferBytes, $savedBytes)
foreach ($file in $files) {
    $name = $file.rfilename
    $dst = Join-Path $staging $name
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
    $existing = if (Test-Path -LiteralPath $dst) { (Get-Item -LiteralPath $dst).Length } else { 0L }
    if ($existing -lt $file.size) {
        $url = "https://huggingface.co/$repo/resolve/$($meta.sha)/${name}?download=true"
        # Reserve the full response size even if the server declines a Range request.
        if ($transferBytes + $file.size -gt 15000000000) { throw 'Transfer budget exhausted' }
        [ordered]@{transferred_bytes=($transferBytes+$file.size);limit_bytes=15000000000;selected_bytes=$total;dependency_download_bytes=0;pending_reservation=$name} | ConvertTo-Json | Set-Content -LiteralPath $budgetPath -Encoding utf8
        Invoke-WebRequest -Uri $url -OutFile $dst -Resume -TimeoutSec 1800
        # Conservatively charge the full file; resume traffic may be smaller.
        $transferBytes += [long]$file.size
        [ordered]@{transferred_bytes=$transferBytes;limit_bytes=15000000000;selected_bytes=$total;dependency_download_bytes=0;accounting='conservative upper bound including full-file resume reservations'} | ConvertTo-Json | Set-Content -LiteralPath $budgetPath -Encoding utf8
    }
    if ((Get-Item -LiteralPath $dst).Length -ne $file.size) { throw "Size mismatch: $name" }
    $sha = (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($file.lfs.sha256 -and $sha -ne $file.lfs.sha256) { throw "Official SHA mismatch: $name" }
    $remoteFile = "$remote/weights/stage03_sdxl/$($meta.sha)/$name"
    $remoteDir = $remoteFile.Substring(0,$remoteFile.LastIndexOf('/'))
    $existingHash = & ssh -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -i $key liyanlei@172.18.185.249 "if test -f $remoteFile; then sha256sum $remoteFile; fi"
    $alreadyTransferred = $LASTEXITCODE -eq 0 -and $existingHash -and $existingHash.StartsWith($sha)
    if (!$alreadyTransferred) {
    & ssh -o ConnectTimeout=15 -i $key liyanlei@172.18.185.249 "mkdir -p $remoteDir"
    if ($LASTEXITCODE -ne 0) { throw 'Remote mkdir failed' }
    & scp -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -i $key $dst "liyanlei@172.18.185.249:$remoteFile"
    if ($LASTEXITCODE -ne 0) { throw 'SCP failed' }
    }
    $verify = & ssh -i $key liyanlei@172.18.185.249 "sha256sum $remoteFile"
    if ($LASTEXITCODE -ne 0 -or !$verify.StartsWith($sha)) { throw 'Server SHA mismatch' }
    $record.files += [ordered]@{rfilename=$name;size=$file.size;sha256=$sha;official_lfs_sha256=$file.lfs.sha256;path="weights/stage03_sdxl/$($meta.sha)/$name"}
    $record | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $recordPath -Encoding utf8
    Write-Output "$name $($file.size) verified"
}
$record.status='complete'
$record | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $recordPath -Encoding utf8
& scp -i $key $recordPath (Join-Path $out 'download_budget.json') "liyanlei@172.18.185.249:$remote/outputs/stage03/"
if ($LASTEXITCODE -ne 0) { throw 'Registry transfer failed' }
