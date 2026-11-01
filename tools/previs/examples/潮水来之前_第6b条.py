"""G6b previs: stone house window faces +Y (toward the drowned causeway); camera pulls back over the sea and rises."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tools/previs/common.py
from common import *

OUT = sys.argv[sys.argv.index("--") + 1]
STILLS = "--stills" in sys.argv
sc = reset(15)
sc.world.color = (0.10, 0.11, 0.14)

STONE = (0.22, 0.22, 0.24)
ROCK = (0.10, 0.10, 0.10)
SEA = (0.06, 0.09, 0.12)
WARM = (0.95, 0.62, 0.25)

box("Island", -14, 16, -30, 1.5, -6, 0, ROCK)
box("IslandLow", -20, 22, -36, 4.0, -6, -1.2, ROCK)
box("Sea", -3000, 3000, -3000, 3000, -10, -1.8, SEA)
# front wall (y=0) with a window opening x[-1.4,-0.2], z[1.0,2.0]
box("WallFrontL", -3.5, -1.4, -0.4, 0, 0, 3, STONE)
box("WallFrontR", -0.2, 3.5, -0.4, 0, 0, 3, STONE)
box("WallFrontB", -1.4, -0.2, -0.4, 0, 0, 1.0, STONE)
box("WallFrontT", -1.4, -0.2, -0.4, 0, 2.0, 3, STONE)
box("WallSideL", -3.5, -3.1, -5, 0, 0, 3, STONE)
box("WallSideR", 3.1, 3.5, -5, 0, 0, 3, STONE)
box("WallBack", -3.5, 3.5, -5, -4.6, 0, 3, WARM)  # lamp-lit back wall seen through the window
box("Roof", -3.8, 3.8, -5.3, 0.3, 3, 3.6, (0.15, 0.15, 0.16))
# interior: table, lamp, two seated figures left (nearer) and right (farther)
box("Table", -1.3, -0.5, -3.3, -2.5, 0, 0.75, (0.35, 0.22, 0.12))
box("Lamp", -0.9, -0.7, -3.0, -2.8, 0.75, 1.05, (1.0, 0.85, 0.4))
# camera looks -Y, so world +X is screen left: nearer figure screen left, farther figure screen right
for name, x, y in (("Near", -0.3, -2.3), ("Far", -1.5, -3.5)):
    cyl(name, 0.22, 1.25, (x, y, 0.62), (0.18, 0.12, 0.08))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.13, location=(x, y, 1.38))
    bpy.context.object.color = (0.18, 0.12, 0.08, 1)
# lighthouse behind the house; lamp room above frame top at the start
cyl("Tower", 1.4, 20, (1.5, -12, 10), (0.12, 0.12, 0.13))

cam = camera(20)


def smooth(u):
    return u * u * (3 - 2 * u)


p0, p1 = (-0.8, 2.2, 1.5), (-0.8, 22.0, 9.5)
r0, r1 = 90.0, 68.0
t = 0.0
while t <= 15.0001:
    u = smooth(min(max((t - 4) / 7, 0), 1))
    loc = tuple(a + (b - a) * u for a, b in zip(p0, p1))
    key(cam, t, loc=loc, rot=(r0 + (r1 - r0) * u, 0, 180))
    t += 0.25

linear_all()
os.makedirs(OUT, exist_ok=True)
render(OUT, frames=[1, 97, 169, 241, 265, 360] if STILLS else None)
