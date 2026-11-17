"""Shared scene constants for the mechanical moon film. Everything is in Blender units (think metres).

World frame: Z up, sea level z = 0. The moon is built in MOON-LOCAL space (centre at origin) and
parented to an empty at MOON_C in the final assembly.
"""
import math
import numpy as np

# ---------------------------------------------------------------- film
FPS = 30
FRAMES = 1350            # 45 s
# ---------------------------------------------------------------- moon
R = 100.0                # mean outer radius of the rock crust
CRUST_T = 6.0            # rock crust thickness
HULL_R = 94.0            # outer radius of the built hull that sits under the crust (= R - CRUST_T)
HULL_T = 1.5             # hull plating thickness -> inner hull face at 92.5
HULL_IN = HULL_R - HULL_T
MOON_C = (0.0, 0.0, 130.0)   # moon centre in world space (bottom of the moon is 30 above the sea)

# the big break in the shell faces the main camera (which stands on the shore at -Y)
_o = np.array([0.291, -0.880, -0.375]); OPEN_DIR = _o / np.linalg.norm(_o)   # tilted down towards the shore camera, 25 deg to its right
_r = np.cross(OPEN_DIR, [0, 0, 1.0]); OPEN_RIGHT = _r / np.linalg.norm(_r)
OPEN_UP = np.cross(OPEN_RIGHT, OPEN_DIR)
OPEN_AZ = 54.0           # half width of the opening in degrees (horizontal)
OPEN_EL = 42.0           # half height of the opening in degrees (vertical)
CRUST_OPEN_F = 1.00      # crust is missing where open_field < this
HULL_OPEN_F = 0.93       # hull is missing where open_field < this (a band of hull shows past the rock edge)

# ---------------------------------------------------------------- interior mechanism envelope
GIMBAL_R = 66.0          # nothing static may enter the sphere of this radius (rotating rings live there)
SPIRE_TIP_Z = 66.0       # lower spire ends at z = -66, upper spire at z = +66 (moon-local); bearing sockets there
PIVOT_R = 1.2            # radius of the gimbal pivot axle that plugs into the spire-tip sockets (along Z)
CORE_R = 7.0             # glowing core orb radius

# ---------------------------------------------------------------- lighting baseline (final look is tuned in assemble)
CORE_COLOR = (1.0, 0.70, 0.40)
CORE_POWER = 4.0e5       # point light watts at the moon centre
MOONLIGHT_COLOR = (0.62, 0.76, 1.0)
MOONLIGHT_STRENGTH = 1.6
MOONLIGHT_DIR = (-0.55, -0.45, 0.70)   # direction TOWARDS the light (upper left, in front)

# ---------------------------------------------------------------- main camera position on the shore (world)
SHORE_CAM = (-40.0, -340.0, 9.0)
SHORE_CAM_TARGET = (0.0, 0.0, 122.0)


def open_field(d):
    """d: (N,3) unit directions in moon-local space. Returns f; f < 1 means inside the big opening."""
    from common import fbm3
    d = np.asarray(d, dtype=np.float64)
    x = d @ OPEN_RIGHT
    y = d @ OPEN_UP
    z = d @ OPEN_DIR
    az = np.degrees(np.arctan2(x, z))
    el = np.degrees(np.arcsin(np.clip(y, -1, 1)))
    f = np.sqrt((az / OPEN_AZ) ** 2 + (el / OPEN_EL) ** 2)
    f = f + 0.11 * fbm3(d * 2.3, 3, seed=11) + 0.05 * fbm3(d * 7.0, 2, seed=12)
    return f
