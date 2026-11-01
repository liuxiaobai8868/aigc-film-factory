import bpy, math

FPS = 24


def reset(seconds):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start = 1
    sc.frame_end = int(seconds * FPS)
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.render.resolution_percentage = 100
    try:
        sc.render.engine = 'BLENDER_WORKBENCH'
    except TypeError as e:
        print(e)
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'OBJECT'
    sh.show_shadows = True
    sh.show_cavity = False
    w = bpy.data.worlds.new("W")
    sc.world = w
    w.color = (0.55, 0.58, 0.62)
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = 'PNG'
    return sc


def box(name, x0, x1, y0, y1, z0, z1, color):
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.object
    o.name = name
    o.scale = (x1 - x0, y1 - y0, z1 - z0)
    o.location = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    o.color = (*color, 1)
    return o


def cyl(name, r, h, loc, color, verts=24):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, vertices=verts, location=loc)
    o = bpy.context.object
    o.name = name
    o.color = (*color, 1)
    return o


def person(name, color, height=1.65):
    """Cylinder + sphere head proxy; front (dark patch) faces -Y at rotation 0."""
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    hd = 0.2 * height
    body_h = height - hd
    b = cyl(name + "_body", 0.12 * height, body_h, (0, 0, body_h / 2), color)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=hd / 2, location=(0, 0, body_h + hd / 2))
    h = bpy.context.object
    h.name = name + "_head"
    h.color = (*color, 1)
    m = box(name + "_front", -0.08, 0.08, -0.12 * height - 0.03, -0.12 * height + 0.02,
            body_h * 0.55, body_h * 0.85, (0.05, 0.05, 0.05))
    nose = box(name + "_face", -0.04, 0.04, -hd / 2 - 0.03, -hd / 2 + 0.03,
               body_h + hd * 0.4, body_h + hd * 0.6, (0.05, 0.05, 0.05))
    for o in (b, h, m, nose):
        o.parent = root
    return root


def key(obj, t, loc=None, rot=None, scale=None):
    f = 1 + t * FPS
    if loc is not None:
        obj.location = loc
        obj.keyframe_insert("location", frame=f)
    if rot is not None:
        obj.rotation_euler = [math.radians(a) for a in rot]
        obj.keyframe_insert("rotation_euler", frame=f)
    if scale is not None:
        obj.scale = scale
        obj.keyframe_insert("scale", frame=f)


def camera(lens_mm):
    cd = bpy.data.cameras.new("Cam")
    cd.lens = lens_mm
    cd.sensor_width = 36
    cd.clip_end = 5000
    c = bpy.data.objects.new("Cam", cd)
    bpy.context.collection.objects.link(c)
    bpy.context.scene.camera = c
    return c


def linear_all():
    for o in bpy.data.objects:
        ad = o.animation_data
        if not ad or not ad.action:
            continue
        try:
            curves = ad.action.fcurves
        except AttributeError:
            curves = [fc for layer in ad.action.layers for strip in layer.strips
                      for bag in strip.channelbags for fc in bag.fcurves]
        for fc in curves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


def render(out_dir, frames=None):
    sc = bpy.context.scene
    if frames:
        for f in frames:
            sc.frame_set(f)
            sc.render.filepath = f"{out_dir}/still_{f:04d}.png"
            bpy.ops.render.render(write_still=True)
    else:
        sc.render.filepath = f"{out_dir}/f_"
        bpy.ops.render.render(animation=True)
