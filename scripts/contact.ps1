param([string]$tag = "c1", [int]$w = 640, [int]$h = 360, [int]$samples = 8, [string]$shots = "")
# Renders first / middle / last frame of every shot and builds montage sheets.
$p = "E:\fable3ddemos\3ddemo"
$b = "E:\Apps\Blender\blender-4.5.13-windows-x64\blender.exe"
$cuts = @(0.0, 5.43, 9.91, 14.43, 17.45, 21.97, 24.98, 29.51, 33.99, 38.49, 41.53, 45.0)
$frames = @()
$sel = @()
if ($shots -ne "") { $sel = $shots.Split(",") | ForEach-Object { [int]$_ } }
for ($i = 0; $i -lt 11; $i++) {
    if ($sel.Count -gt 0 -and ($sel -notcontains ($i + 1))) { continue }
    $f0 = [int][math]::Round($cuts[$i] * 30) + 1
    $f1 = if ($i -lt 10) { [int][math]::Round($cuts[$i + 1] * 30) } else { 1350 }
    $frames += $f0; $frames += [int](($f0 + $f1) / 2); $frames += $f1
}
$out = "$p\renders\contact_$tag"
New-Item -ItemType Directory -Force $out | Out-Null
& $b -b "$p\blend\moon_scene.blend" -P "$p\scripts\render.py" -- --frames ($frames -join ",") --res "${w}x${h}" --samples $samples --out $out --jpg --nojitter --overwrite 2>&1 | Select-String -Pattern "RENDER DONE|Error|Traceback|line \d+"
# montage: 3 columns, rows of shots; split into sheets of 4 shots
$files = $frames | ForEach-Object { "$out\f_{0:D4}.jpg" -f $_ }
$n = 0
for ($s = 0; $s -lt $files.Count; $s += 12) {
    $chunk = $files[$s..([math]::Min($s + 11, $files.Count - 1))]
    $rows = [math]::Ceiling($chunk.Count / 3)
    $inputs = @(); foreach ($f in $chunk) { $inputs += "-i"; $inputs += $f }
    ffmpeg -y -loglevel error @inputs -filter_complex "concat=n=$($chunk.Count):v=1:a=0,tile=3x${rows}" -frames:v 1 -q:v 3 "$p\renders\sheet_${tag}_$n.jpg"
    $n++
}
"sheets: $n"
