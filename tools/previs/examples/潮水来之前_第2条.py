"""G2 previs v3 (全片视听设计): two gazes.
Shots 1/4/7 = his vantage on the island axis; 2/3/5/6 = her body, inner-sea side.
World: causeway along +Y from the island (y=0); outer sea +X, inner sea -X; bank slope y in [-6,0] up to z=3."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tools/previs/common.py
from common import *

OUT = sys.argv[sys.argv.index("--") + 1]
STILLS = "--stills" in sys.argv
sc = reset(30)

ROCK = (0.16, 0.14, 0.12)
STEP = (0.42, 0.40, 0.37)
ROAD = (0.36, 0.36, 0.36)
WALL = (0.28, 0.25, 0.20)
SEA = (0.13, 0.20, 0.25)

box("Road", -2.0, 2.0, 0, 400, -2, 0, ROAD)
box("WallL", -2.3, -2.0, 0, 400, -2, 0.5, WALL)
box("WallR", 2.0, 2.3, 0, 400, -2, 0.5, WALL)
verts = [(-60, 0.6, -6), (60, 0.6, -6), (60, 0.6, -0.3), (-60, 0.6, -0.3),
         (-60, -6, 3.0), (60, -6, 3.0), (-60, -80, 3.0), (60, -80, 3.0), (-60, -80, -6), (60, -80, -6)]
faces = [(0, 1, 2, 3), (3, 2, 5, 4), (4, 5, 7, 6), (6, 7, 9, 8), (8, 9, 1, 0), (0, 3, 4, 6, 8), (1, 9, 7, 5, 2)]
me = bpy.data.meshes.new("Bank")
me.from_pydata(verts, [], faces)
bank = bpy.data.objects.new("Bank", me)
bpy.context.collection.objects.link(bank)
bank.color = (*ROCK, 1)
box("LumpL", -9.0, -4.0, -12, -6.5, 2.9, 3.6, ROCK)
box("LumpR", 4.5, 10.0, -14, -7.0, 2.9, 3.8, ROCK)
for i in range(15):
    y1 = -0.4 * i
    box(f"Step{i:02d}", -2.0, 2.0, y1 - 0.4, y1, -6, 0.2 * (i + 1), STEP)

sea = box("Sea", -3000, 3000, -3000, 3000, -1, 0, SEA)
for t, z in [(0, 0.25), (8, 0.33), (14, 0.42), (16, 0.70), (20, 0.80), (25, 1.10), (30, 1.20)]:
    key(sea, t, loc=(0, 0, z - 0.5))

truck = box("Truck", -0.95, 0.95, 117.5, 122.5, 0, 1.8, (0.85, 0.85, 0.82))
lights = [box(f"Light{i}", x - 0.2, x + 0.2, 117.3, 117.5, 0.7, 0.95, (1.0, 0.75, 0.2)) for i, x in enumerate((-0.6, 0.6))]
key(truck, 0, loc=truck.location[:])
key(truck, 14.0, loc=truck.location[:])
key(truck, 15.5, loc=(0, 120, -2.5))
for l in lights:
    x, y, z = l.location[:]
    key(l, 0, loc=(x, y, z))
    key(l, 14.4, loc=(x, y, z))
    key(l, 14.8, loc=(x, y, -3))
wave = box("Wave", -6, 6, 108, 132, -4, 0, (0.95, 0.95, 0.95))
key(wave, 0, loc=(45, 120, -4), scale=(12, 24, 1))
key(wave, 12.5, loc=(30, 120, -2), scale=(12, 24, 2))
key(wave, 14.0, loc=(8, 120, 1.0), scale=(16, 26, 6))
key(wave, 15.5, loc=(-10, 120, 0.5), scale=(22, 28, 5))
key(wave, 17.5, loc=(-30, 120, -3), scale=(24, 28, 2))

# sweeping light: pivot high behind the island, on at 10 s, points straight along the road at 10.5 / 18.5 / 26.5 s,
# sweeping screen-left -> screen-right as seen looking along +Y
pivot = bpy.data.objects.new("BeamPivot", None)
bpy.context.collection.objects.link(pivot)
pivot.location = (0, -40, 25)
beam = box("Beam", -0.6, 0.6, 0, 300, -0.5, 0.5, (0.97, 0.97, 0.92))
beam.parent = pivot
beam.rotation_euler = (math.radians(-4.5), 0, 0)
key(pivot, 0, rot=(0, 0, 22.5), scale=(0, 0, 0))
key(pivot, 9.99, rot=(0, 0, 22.5), scale=(0, 0, 0))
key(pivot, 10.0, rot=(0, 0, 22.5), scale=(1, 1, 1))
key(pivot, 30.0, rot=(0, 0, 22.5 - 45 * 20), scale=(1, 1, 1))

lan = person("Lan", (0.85, 0.25, 0.10))
aim = bpy.data.objects.new("LanAim", None)
bpy.context.collection.objects.link(aim)


def zy(y):
    return 0.0 if y >= 0 else (-y * 0.5 if y > -6 else 3.0)


# cut ellipses are allowed: she jumps from y=26 (end of shot 4) to the foot of the steps (shot 5)
path = [(0, 100.0), (4, 91.0), (9, 66.0), (13, 47.0), (17.95, 26.0), (18.0, 0.4), (19.0, 0.0),
        (24, -6.2), (25, -6.6), (30, -6.6)]


def lan_y(t):
    for (t0, y0), (t1, y1) in zip(path, path[1:]):
        if t0 <= t <= t1:
            return y0 + (y1 - y0) * (t - t0) / (t1 - t0)
    return path[-1][1]


times = sorted(set([round(k * 0.25, 2) for k in range(121)] + [17.95]))
for t in times:
    y = lan_y(t)
    sway = 0.15 * math.sin(t * 3.0) if t < 18 else 0.0
    lean = 15 if t < 18 else (35 if t < 24 else 0)
    rz = 0 if t < 26 else (180 * (t - 26) / 2 if t < 28 else 180)
    key(lan, t, loc=(sway, y, zy(y)), rot=(-lean, 0, rz))
    key(aim, t, loc=(sway, y, zy(y) + 1.35))


def cam_at(name, lens, frames):
    """frames: list of (t, loc, rot); rot None means the camera tracks Lan's chest."""
    c = camera(lens)
    c.name = name
    if any(r is None for _, _, r in frames):
        con = c.constraints.new('TRACK_TO')
        con.target = aim
        con.track_axis = 'TRACK_NEGATIVE_Z'
        con.up_axis = 'UP_Y'
    for tt, loc, rot in frames:
        key(c, tt, loc=loc, rot=rot if rot else (90, 0, 0))
    return c


def wobble(t, amp=0.04):
    return (amp * math.sin(t * 7.1), amp * math.sin(t * 5.3 + 1), amp * math.sin(t * 6.2 + 2))


HIS = ((0, -14, 9), (83, 0, 0))  # his vantage: island high ground on the road axis, 85 mm
cams = []
cams.append((0, cam_at("C1", 85, [(0, *HIS), (4, *HIS)])))
cams.append((4, cam_at("C2", 50, [(tt, (-4.0, lan_y(tt) - 0.3, 1.1), (88, 0, -90)) for tt in (4, 5, 6, 7, 8, 9)])))
c3 = []
for k in range(17):
    tt = 9 + k * 0.25
    w = wobble(tt)
    c3.append((tt, (-1.3 + w[0], lan_y(tt) - 2.8 + w[1], 1.45 + w[2]), None))
cams.append((9, cam_at("C3", 85, c3)))
cams.append((13, cam_at("C4", 85, [(13, *HIS), (18, *HIS)])))
c5 = []
for k in range(13):
    tt = 18 + k * 0.25
    w = wobble(tt, 0.03)
    c5.append((tt, (-2.4 + w[0], -2.8 + w[1], 1.7 + w[2]), (70, 0, -45)))
cams.append((18, cam_at("C5", 50, c5)))
cams.append((21, cam_at("C6", 24, [(21, (-3.5, 2.0, 1.15), (102.3, 0, -156.4)), (24, (-3.5, 2.0, 1.15), (102.3, 0, -156.4))])))
cams.append((24, cam_at("C7", 35, [(24, (0, -13.5, 4.9), (82, 0, 0)), (30, (0, -13.5, 4.9), (82, 0, 0))])))

for t0, c in cams:
    m = sc.timeline_markers.new(c.name, frame=int(1 + t0 * FPS))
    m.camera = c
sc.camera = cams[0][1]

linear_all()
os.makedirs(OUT, exist_ok=True)
if STILLS:
    for f in [49, 169, 265, 337, 361, 457, 541, 625, 709]:
        t = (f - 1) / FPS
        sc.camera = [c for t0, c in cams if t0 <= t][-1]
        sc.frame_set(f)
        sc.render.filepath = f"{OUT}/still_{f:04d}.png"
        bpy.ops.render.render(write_still=True)
else:
    render(OUT)
