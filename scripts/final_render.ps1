param([int]$first = 1, [int]$last = 1350, [int]$samples = 12, [string]$out = "E:\fable3ddemos\3ddemo\frames")
# Renders the film frames; restarts Blender if it dies, skips frames that already exist.
$p = "E:\fable3ddemos\3ddemo"
$b = "E:\Apps\Blender\blender-4.5.13-windows-x64\blender.exe"
$log = "$p\renders\final_log.txt"
New-Item -ItemType Directory -Force $out | Out-Null
for ($try = 1; $try -le 8; $try++) {
    $have = (Get-ChildItem "$out\f_*.png" -ErrorAction SilentlyContinue | Where-Object { $n = [int]($_.BaseName.Substring(2)); $n -ge $first -and $n -le $last }).Count
    $need = $last - $first + 1
    "[{0}] pass {1}: {2}/{3} frames present" -f (Get-Date -Format "HH:mm:ss"), $try, $have, $need | Tee-Object -FilePath $log -Append
    if ($have -ge $need) { break }
    & $b -b "$p\blend\moon_scene.blend" -P "$p\scripts\render.py" -- --range $first $last --res 1920x1080 --samples $samples --nojitter --nogi --volsamples 64 --volend 900 --out $out 2>&1 |
        Select-String -Pattern "^\[\d\d:\d\d:\d\d\] (frame|RENDER)|Error|Traceback|EXCEPTION" | ForEach-Object { $_.Line } | Tee-Object -FilePath $log -Append | Out-Null
}
"[{0}] FINAL RENDER SCRIPT END" -f (Get-Date -Format "HH:mm:ss") | Tee-Object -FilePath $log -Append
