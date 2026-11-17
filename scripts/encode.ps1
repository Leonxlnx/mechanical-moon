param([string]$frames = "E:\fable3ddemos\3ddemo\frames", [string]$audio = "E:\fable3ddemos\3ddemo\audio\mix_v1.wav",
      [string]$out = "E:\fable3ddemos\3ddemo\out\mechanical_moon.mp4", [int]$start = 1, [int]$count = 1350, [int]$crf = 17, [int]$grain = 3,
      [switch]$nograde, [string]$still = "")
# Image sequence -> final grade (gentle filmic S-curve, cool shadows / warm highlights, vignette, fine grain, fades) -> H.264 + AAC.
$dur = $count / 30.0
$fadeOut = [math]::Round($dur - 1.15, 3)
$grade = "format=gbrp," +
         "curves=all='0/0 0.10/0.075 0.50/0.51 0.88/0.92 1/1'," +
         "colorbalance=rs=-0.035:bs=0.045:rm=0.0:bm=0.0:rh=0.03:bh=-0.035," +
         "eq=saturation=1.07," +
         "unsharp=5:5:0.35:5:5:0.0," +
         "vignette=angle=0.50:eval=init," +
         "noise=c0s=${grain}:allf=t"
if ($nograde) { $grade = "null" }
$vf = "$grade,fade=t=in:st=0:d=0.9,fade=t=out:st=${fadeOut}:d=1.15,format=yuv420p"
if ($still -ne "") {
    ffmpeg -y -hide_banner -loglevel error -start_number $start -i "$frames\f_%04d.png" -frames:v 1 -vf "$grade,format=yuv420p" -q:v 2 $still
    return
}
New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
ffmpeg -y -hide_banner -loglevel error -framerate 30 -start_number $start -i "$frames\f_%04d.png" -i $audio `
    -frames:v $count -vf $vf -c:v libx264 -preset slow -crf $crf -pix_fmt yuv420p -profile:v high -level 4.2 `
    -color_primaries bt709 -color_trc bt709 -colorspace bt709 -movflags +faststart `
    -c:a aac -b:a 320k -ar 48000 -shortest -t $dur $out
ffprobe -v error -show_entries format=duration,size,bit_rate -show_entries stream=codec_name,width,height,r_frame_rate,nb_frames -of default=nw=1 $out
