"""Shot list: cut points follow the hits of the music excerpt (5.4, 9.9, 17.5, 29.5, 34.0, 41.5 s).
keys: (u in 0..1 along the shot, camera position, look-at target, focal length) in WORLD space."""
import math
import numpy as np
import config as C

MC = np.array(C.MOON_C)
OD = np.array(C.OPEN_DIR)
OR = np.array(C.OPEN_RIGHT)      # horizontal; points to the camera's LEFT when looking at the opening from outside
OU = np.array(C.OPEN_UP)


def W(v):
    return tuple(float(x) for x in v)


def nrm(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def fr(t):
    return int(round(t * C.FPS)) + 1


def on_sphere(a, b, c, r):
    """Point at radius r from the moon centre in direction a*OD + b*OR + c*OU."""
    return MC + nrm(a * OD + b * OR + c * OU) * r


# exterior orbit ring frame (must match build_mech: rotation ZXY (30, 14) deg, radius 146)
_rx, _ry = math.radians(30.0), math.radians(14.0)
RN = np.array([math.cos(_rx) * math.sin(_ry), -math.sin(_rx), math.cos(_rx) * math.cos(_ry)])
E_LOW = nrm(-np.array([0, 0, 1.0]) + RN[2] * RN)
E_TAN = np.cross(RN, E_LOW)


def ring_pt(phi_deg, r=146.0, up=0.0):
    p = math.radians(phi_deg)
    return MC + r * (math.cos(p) * E_LOW + math.sin(p) * E_TAN) + RN * up


def wall_pt(theta_deg, r, h):
    """Interior point: theta measured from the rose window direction (-OD) towards OR."""
    t = math.radians(theta_deg)
    return MC + r * (math.cos(t) * (-OD) + math.sin(t) * OR) + OU * h


CUTS = [0.0, 5.43, 9.91, 14.43, 17.45, 21.97, 24.98, 29.51, 33.99, 38.49, 41.53, 45.0]   # on the beats of the music excerpt (period ~1.507 s)

SHOTS = [
    # 1  dark sea, the glow of the moon coming into frame
    dict(name="01_sea", keys=[(0, (66, -300, 3.2), (44, -150, 4), 28), (1, (58, -262, 3.7), (20, -30, 64), 28)]),
    # 2  reveal from the shore
    dict(name="02_reveal", keys=[(0, (-86, -338, 12.6), (-10, -30, 44), 40), (1, (-80, -333, 17.5), (-6, -20, 86), 40)]),
    # 3  side: cratered crust in moonlight, the orbit ring sweeping past
    dict(name="03_side", keys=[(0, (-250, -150, 96), (-10, 0, 124), 32), (1, (-226, -196, 104), (-4, -6, 124), 32)]),
    # 4  glide over the crust towards the broken rim
    dict(name="04_crust", keys=[(0, W(on_sphere(0.20, 0.95, 0.22, 133)), W(on_sphere(0.80, 0.55, 0.10, 100)), 24),
                              (1, W(on_sphere(0.50, 0.84, 0.20, 127)), W(on_sphere(0.92, 0.36, 0.04, 96)), 24)]),
    # 5  fly in through the opening
    dict(name="05_flyin", keys=[(0, W(MC + OD * 168 + OU * 22 - OR * 14), W(MC + OD * 20), 24), (1, W(MC + OD * 96 + OU * 10 - OR * 6), W(MC - OD * 40), 24)]),
    # 6  the gimbal rings sweeping past, core half hidden
    dict(name="06_rings", keys=[(0, W(on_sphere(0.90, 0.36, 0.24, 76)), W(MC + OR * -10 + OU * -3), 40), (1, W(on_sphere(0.88, 0.44, 0.30, 76)), W(MC + OR * -8 + OU * -2), 40)]),
    # 7  along the gallery wall towards the rose window
    dict(name="07_galleries", keys=[(0, W(wall_pt(78, 75, -10)), W(wall_pt(12, 84, 4)), 22), (1, W(wall_pt(52, 75, -4)), W(wall_pt(4, 84, 6)), 22)]),
    # 8  from the sea, straight up into the mechanism
    dict(name="08_below", keys=[(0, (34, -128, 7.0), W(MC + OD * 40 + np.array([0, 0, 6])), 17), (1, (22, -104, 9.0), W(MC + OD * 34 + np.array([0, 0, 2])), 17)]),
    # 9  riding along the orbit ring
    dict(name="09_ring", keys=[(0, W(ring_pt(66, 173, 15)), W(MC + OD * 52 + OU * 4), 24), (1, W(ring_pt(55, 170, 12)), W(MC + OD * 52 + OU * 2), 24)]),
    # 10 wide three-quarter view from the sea: light pouring out of the opening
    dict(name="10_aerial", keys=[(0, (236, -276, 7.5), (0, -24, 100), 24), (1, (196, -262, 11.5), (0, -24, 106), 24)]),
    # 11 final wide, pulling back
    dict(name="11_final", keys=[(0, (-30, -350, 17.0), (22, -8, 76), 23), (1, (-38, -374, 24.0), (26, -8, 70), 20)]),
]
# per-shot key-light cheat: (direction TOWARDS the light, strength multiplier). Raking light for every camera position.
C_KEY = (-0.90, -0.18, 0.40)
KEY = {
    "03_side": ((-0.45, 0.78, 0.45), 1.0),
    "04_crust": ((-0.55, 0.25, 0.80), 1.15),
    "09_ring": ((0.60, -0.50, 0.62), 1.0),
    "10_aerial": ((-0.585, -0.627, 0.513), 1.0),
}
# per-shot grade: exposure (start, end), bloom threshold, bloom strength (scalars or (start, end))
GRADE = {
    "01_sea": ((-0.25, -0.25), 2.2, 0.32), "02_reveal": ((-0.4, -0.4), 2.2, 0.32), "03_side": ((-0.4, -0.4), 2.2, 0.30),
    "04_crust": ((-0.4, -0.4), 2.4, 0.30), "05_flyin": ((-0.45, -0.85), (4.5, 4.0), (0.28, 0.20)), "06_rings": ((-1.10, -1.10), 3.5, 0.20),
    "07_galleries": ((-0.78, -0.78), 8.0, 0.20), "08_below": ((-0.75, -0.75), 4.0, 0.22), "09_ring": ((-0.3, -0.3), 2.4, 0.30),
    "10_aerial": ((-0.2, -0.2), 2.4, 0.30), "11_final": ((-0.4, -0.4), 2.2, 0.32),
}
# per-shot core: (light multiplier, volume-scatter multiplier, centre emission, limb emission) at shot start / end.
# From the sea the core may blaze; seen from inside it is dimmed so the mechanism stays readable (no white veil).
CORE_OUT = (1.0, 1.0, 300.0, 18.0)
CORE_IN = (0.60, 0.29, 20.0, 1.5)
CORE = {
    "05_flyin": ((0.85, 0.60, 120.0, 8.0), CORE_IN),
    "06_rings": (CORE_IN, CORE_IN),
    "07_galleries": (CORE_IN, CORE_IN),
    "08_below": ((0.80, 0.50, 80.0, 10.0), (0.80, 0.50, 80.0, 10.0)),
}
# core surface look: (centre colour, limb colour, plasma noise scale, plasma range)
CORE_LOOK_OUT = ((1.0, 0.86, 0.62), (1.0, 0.36, 0.07), 0.33, (0.45, 1.35))
CORE_LOOK_IN = ((1.0, 0.72, 0.14), (1.0, 0.36, 0.03), 0.90, (0.30, 1.6))      # yellow-gold: AgX turns bright orange salmon, bright cream white
CORE_LOOK_SHOTS = ("05_flyin", "06_rings", "07_galleries")
for i, sh in enumerate(SHOTS):
    sh["frames"] = (fr(CUTS[i]), fr(CUTS[i + 1]) - 1 if i < len(SHOTS) - 1 else C.FRAMES)
    sh["grade"] = GRADE[sh["name"]]
    sh["rim"] = {"04_crust": 1.0, "09_ring": 0.6}.get(sh["name"], 1.0)
    sh["key"] = KEY.get(sh["name"], (C_KEY, 1.0))
    sh["core"] = CORE.get(sh["name"], (CORE_OUT, CORE_OUT))
    sh["core_look"] = CORE_LOOK_IN if sh["name"] in CORE_LOOK_SHOTS else CORE_LOOK_OUT
