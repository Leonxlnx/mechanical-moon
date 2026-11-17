"""Build the film soundtrack with ffmpeg from the downloaded music + SFX (nothing is synthesised).
python3 mix_audio.py [out.wav]"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUD = os.path.join(ROOT, "audio")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AUD, "mix_v1.wav")
M = json.load(open(os.path.join(AUD, "manifest.json"), encoding="utf-8"))
INFO = {}
for it in M["sfx"] + M["music_ranked"]:
    INFO[os.path.basename(it["path"]).split("_")[1] if it["category"] != "music" else os.path.basename(it["path"])] = it
DUR = 45.0
CUT = [0.0, 5.43, 9.91, 14.43, 17.45, 21.97, 24.98, 29.51, 33.99, 38.49, 41.53, 45.0]


def env(points):
    """Piecewise-linear gain (dB) over film time -> ffmpeg expression in linear gain."""
    pts = sorted(points)
    expr = "%.4f" % (10 ** (pts[-1][1] / 20))
    for (t0, d0), (t1, d1) in reversed(list(zip(pts[:-1], pts[1:]))):
        g0, g1 = 10 ** (d0 / 20), 10 ** (d1 / 20)
        seg = "(%.4f+(%.4f)*(t-%.3f)/%.3f)" % (g0, g1 - g0, t0, max(t1 - t0, 1e-3))
        expr = "if(lt(t,%.3f),%s,%s)" % (t1, seg, expr)
    return "if(lt(t,%.3f),%.4f,%s)" % (pts[0][0], 10 ** (pts[0][1] / 20), expr)


def steps(levels, ramp=0.5):
    """levels: per-shot dB list (11 shots) -> breakpoints with short ramps centred on the cuts."""
    pts = [(0.0, levels[0])]
    for i in range(1, 11):
        pts.append((CUT[i] - ramp / 2, levels[i - 1]))
        pts.append((CUT[i] + ramp / 2, levels[i]))
    pts.append((DUR, levels[-1]))
    return pts


CUES = []   # (key, film_start, src_offset, dur, gain_db, fade_in, fade_out, envelope_points or None, extra filter)


def cue(key, start, src=0.0, dur=None, gain=0.0, fi=0.02, fo=0.3, envp=None, extra=None, lufs=None):
    it = INFO[key]
    if dur is None:
        dur = it["duration_s"] - src
    dur = min(dur, DUR - start + 0.2, it["duration_s"] - src)
    if lufs is not None:                       # place the file at an absolute loudness instead of a relative gain
        gain = lufs - it.get("integrated_LUFS", it.get("analysis", {}).get("integrated_LUFS", -20.0))
    CUES.append((it["abs_path"], start, src, dur, gain, fi, fo, envp, extra))


def hit(key, t, gain, dur=None, fo=1.0, fi=0.02, src=None, lead=None):
    """Align the file's loudest moment with film time t."""
    it = INFO[key]
    peak = it.get("loudest_50ms_at_s", 0.0)
    s = 0.0 if src is None else src
    cue(key, max(0.0, t - (peak - s)), src=s, dur=dur, gain=gain, fi=fi, fo=fo)


# ------------------------------------------------------------------ music
cue("ScottBuckley_PassageOfTime.mp3", 0.0, src=140.0, dur=45.2, gain=-0.5, fi=1.0, fo=0.1,
    envp=[(0, 0), (41.9, 0), (43.4, -7), (45.0, -40)])
# ------------------------------------------------------------------ beds
#                shots:  1    2    3    4    5     6     7    8    9    10   11
cue("574542", 0.0, src=30.0, dur=45.2, lufs=-22.5, fi=0.4, envp=steps([0, -1, -7, -9, -12, -24, -24, -2, -9, -1, 0]))
cue("82271", CUT[1] - 0.3, src=12.0, dur=CUT[2] - CUT[1] + 0.8, lufs=-27.0, fi=0.5, fo=0.8)
cue("82271", CUT[10] - 0.3, src=18.0, dur=3.8, lufs=-26.0, fi=0.5, fo=0.5)
cue("616222", 0.0, src=40.0, dur=45.2, lufs=-29.0, fi=0.5, envp=steps([-2, -1, 2, 3, -6, -18, -18, -2, 3, -1, 0]))
cue("321812", 0.0, src=2.0, dur=7.2, lufs=-23.0, fi=1.5, fo=2.2)
cue("321812", 27.6, src=4.0, dur=7.6, lufs=-27.0, fi=1.8, fo=2.5)
# interior: clockwork, giant tick, reactor hum, choir, groaning metal
cue("524027", 17.9, src=20.0, dur=12.0, lufs=-25.5, fi=1.2, fo=1.4)
cue("128245", 19.6, src=0.0, dur=10.2, lufs=-27.0, fi=1.5, fo=1.5)
cue("785817", 17.6, src=10.0, dur=12.3, lufs=-28.0, fi=1.2, fo=1.6)
cue("434700", 20.8, src=15.0, dur=9.2, lufs=-30.0, fi=2.2, fo=1.8)
cue("172411", 22.2, src=0.0, dur=6.6, lufs=-26.0, fi=0.6, fo=1.5)
cue("514306", 10.4, src=0.0, dur=4.4, lufs=-27.0, fi=0.4, fo=1.2)           # the orbit ring groaning past (side shot)
cue("323051", CUT[1], src=10.0, dur=4.6, lufs=-31.0, fi=1.0, fo=1.2)        # core shimmer on the reveal
cue("323051", CUT[10], src=20.0, dur=3.5, lufs=-30.0, fi=0.8, fo=1.0)
# ------------------------------------------------------------------ one-shots
hit("218354", CUT[1], gain=-11.0, fo=1.5)                                   # swell into the reveal
hit("647712", CUT[1], gain=-6.5, dur=6.0, fo=3.0)                           # braam on the reveal
hit("194364", 8.45, gain=-9.0, src=16.5, dur=6.5, fo=3.5)                   # thunder after flash 1 (8.15 s)
hit("558827", CUT[2], gain=-8.0)                                            # whoosh into the side shot
hit("529535", 12.45, gain=-5.0, src=34.3, dur=6.0, fo=3.5)                  # thunder after flash 2 (12.10 s)
hit("169867", CUT[3], gain=-6.0)
hit("264777", CUT[4], gain=-13.0, fo=0.4)                                   # long swoosh building into the fly-in
hit("522691", CUT[4], gain=3.0, fo=2.0)                                     # dark whoosh + impact as we enter
hit("558826", CUT[5], gain=-8.0)
hit("160757", 23.3, gain=15.0)                                              # ring sweeping past the lens
hit("197436", CUT[6], gain=-15.0, dur=4.2, fo=2.2)                          # heavy ratchet / chains on the gallery cut
hit("334525", CUT[7], gain=-14.0, fo=0.25)                                  # riser into the climax
hit("581842", CUT[7], gain=-10.0, dur=8.0, fo=4.0)                           # braam horn on the climax
hit("496836", 31.6, gain=-12.0, fo=1.5)                                     # groan of the hull overhead
hit("558827", CUT[8], gain=-9.0)
hit("553418", CUT[8], gain=-7.5, fo=2.5)
hit("558826", CUT[9], gain=-8.0)
hit("431316", CUT[10], gain=-9.5, dur=3.6, fo=2.6)
hit("127140", 41.95, gain=-6.0, src=8.8, dur=3.3, fo=1.6)                   # thunder after flash 3 (41.62 s)

STEM = os.environ.get("STEM", "")
if STEM == "music":
    CUES = CUES[:1]
elif STEM == "sfx":
    CUES = CUES[1:]
cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
flt = []
for i, (path, start, src, dur, gain, fi, fo, envp, extra) in enumerate(CUES):
    cmd += ["-i", path]
    chain = "[%d:a]atrim=start=%.3f:duration=%.3f,asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo" % (i, src, dur)
    chain += ",afade=t=in:st=0:d=%.3f,afade=t=out:st=%.3f:d=%.3f" % (fi, max(dur - fo, 0), fo)
    chain += ",volume=%.2fdB" % gain
    if extra:
        chain += "," + extra
    chain += ",adelay=%d:all=1" % int(round(start * 1000))
    if envp:
        chain += ",volume=eval=frame:volume='%s'" % env(envp)
    chain += "[a%d]" % i
    flt.append(chain)
mix = "".join("[a%d]" % i for i in range(len(CUES)))
flt.append(mix + "amix=inputs=%d:normalize=0:duration=longest,atrim=0:%.3f,highpass=f=24,"
           "acompressor=threshold=-16dB:ratio=2.5:attack=25:release=350:makeup=1,"
           "afade=t=in:st=0:d=0.35,afade=t=out:st=%.3f:d=1.25[mix]" % (len(CUES), DUR, DUR - 1.25))
pre = OUT.replace(".wav", "_pre.wav")
subprocess.run(cmd + ["-filter_complex", ";".join(flt), "-map", "[mix]", "-ar", "48000", "-c:a", "pcm_s24le", pre], check=True)
# measure, then set the level with a static gain + true-peak limiter (no pumping loudness normaliser)
r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", pre, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
tail = r.stderr[r.stderr.rfind("Summary:"):]
I = float(tail.split("I:")[1].split("LUFS")[0])
TARGET = -14.5
g = TARGET - I
if STEM:
    g = float(os.environ.get("STEM_GAIN", "0"))
subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", pre, "-af",
                "volume=%.2fdB,alimiter=limit=0.84:attack=4:release=120:level=false" % g, "-ar", "48000", "-c:a", "pcm_s24le", OUT], check=True)
r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", OUT, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
tail = r.stderr[r.stderr.rfind("Summary:"):]
if not STEM:
    used, lines = [], []
    for c in CUES:
        if c[0] not in used:
            used.append(c[0])
    byp = {it["abs_path"]: it for it in M["sfx"] + M["music_ranked"]}
    lines.append("MECHANICAL MOON - audio credits (all audio downloaded, nothing synthesised)")
    lines.append("")
    for pth in used:
        it = byp[pth]
        lines.append("%s: \"%s\" by %s - %s - %s" % ("Music" if it["category"] == "music" else "SFX", it["title"], it["author"], it["license"], it["source_page_url"]))
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    open(os.path.join(ROOT, "out", "CREDITS.txt"), "w", encoding="utf-8").write(chr(10).join(lines) + chr(10))
print("cues:", len(CUES), "pre-gain I=%.1f LUFS, applied %.1f dB" % (I, g))
print(tail.strip())
# short-term loudness per 3 s for a sanity check of the dynamics
st = [l for l in r.stderr.splitlines() if " S:" in l and "t:" in l]
vals = {}
for l in st:
    try:
        t = float(l.split("t:")[1].split()[0])
        s = float(l.split(" S:")[1].split()[0])
        vals[int(t)] = s
    except Exception:
        pass
print("short-term LUFS by second:", " ".join("%d:%.0f" % (k, vals[k]) for k in sorted(vals) if k % 2 == 0))
