param([string]$blend = "moon_scene_v2.blend", [string]$ranges = "434-524,1021-1155", [int]$samples = 12,
      [string]$out = "E:\fable3ddemos\3ddemo\frames", [string]$logname = "v2_log.txt", [switch]$overwrite)
# Renders frame ranges from a given scene file into the frame folder (restart-safe; skips existing unless -overwrite).
$p = "E:\fable3ddemos\3ddemo"
$b = "E:\Apps\Blender\blender-4.5.13-windows-x64\blender.exe"
$log = "$p\renders\$logname"
New-Item -ItemType Directory -Force $out | Out-Null
foreach ($r in $ranges.Split(",")) {
    $a, $z = $r.Split("-") | ForEach-Object { [int]$_ }
    for ($try = 1; $try -le 5; $try++) {
        $have = 0
        if (-not $overwrite -or $try -gt 1) {
            $have = (Get-ChildItem "$out\f_*.png" -ErrorAction SilentlyContinue | Where-Object { $n = [int]($_.BaseName.Substring(2)); $n -ge $a -and $n -le $z }).Count
        }
        "[{0}] range {1}-{2} pass {3}: {4}/{5} present" -f (Get-Date -Format "HH:mm:ss"), $a, $z, $try, $have, ($z - $a + 1) | Tee-Object -FilePath $log -Append
        if ($have -ge ($z - $a + 1)) { break }
        $extra = @()
        if ($overwrite -and $try -eq 1) { $extra = @("--overwrite") }
        & $b -b "$p\blend\$blend" -P "$p\scripts\render.py" -- --range $a $z --res 1920x1080 --samples $samples --nojitter --nogi --volsamples 64 --volend 900 --out $out @extra 2>&1 |
            Select-String -Pattern "^\[\d\d:\d\d:\d\d\] (frame|RENDER)|Error|Traceback|EXCEPTION" | ForEach-Object { $_.Line } | Tee-Object -FilePath $log -Append | Out-Null
    }
}
"[{0}] RANGE RENDER END" -f (Get-Date -Format "HH:mm:ss") | Tee-Object -FilePath $log -Append
