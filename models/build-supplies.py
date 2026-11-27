"""Build the Lone Trail supply case from the April 2023 Case Investigation artwork.

Run with Blender 5.2 in background mode. Dimensions are proportional. The screen
printing is sampled from the archived official notice and packed into both models.
"""
import math
import re
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
NOTICE = ROOT / "references/鹰角公告/专项调查.png"
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def collection(name):
	group = bpy.data.collections.new(name)
	scene.collection.children.link(group)
	return group


def place(obj, name, mat=None):
	obj.name = name
	for owner in list(obj.users_collection):
		owner.objects.unlink(obj)
	group.objects.link(obj)
	if mat:
		obj.data.materials.append(mat)
	return obj


def material(name, rgb, metal=0, rough=.4, coat=0):
	mat = bpy.data.materials.new(name)
	mat.diffuse_color = (*rgb, 1)
	mat.use_nodes = True
	bsdf = mat.node_tree.nodes.get("Principled BSDF")
	for key, value in {"Base Color": (*rgb, 1), "Metallic": metal,
			"Roughness": rough, "Coat Weight": coat, "Coat Roughness": .26}.items():
		bsdf.inputs[key].default_value = value
	return mat


ivory = material("Warm ivory · moulded shell", (.89, .835, .69), rough=.32, coat=.16)
orange = material("Safety orange · end guards", (.83, .146, .013), rough=.34, coat=.13)
ink = material("Carbon · seals and pivot cheeks", (.010, .014, .017), rough=.46)
grip = material("Graphite · satin handgrip", (.020, .025, .032), rough=.32)
silver = material("Nickel · exposed edges", (.52, .57, .60), .83, .24)
gunmetal = material("Oxidised alloy", (.12, .145, .15), .76, .29)
black_print = material("Black ink", (.006, .010, .009), rough=.77)
white_print = material("Ivory ink", (.98, .90, .77), rough=.62)
orange_print = material("Vermilion ink", (.88, .126, .006), rough=.58)
glass = material("Smoked amber · visor", (.115, .015, .0025), .12, .27, .25)
glass.node_tree.nodes.get("Principled BSDF").inputs["Transmission Weight"].default_value = .20
bezel = material("Amber · recessed surround", (.21, .045, .009), .27, .29, .18)
screen = material("Amber · display under glass", (.065, .012, .002), rough=.40, coat=.055)
screen.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value=.16
phosphor=material("Amber · screen legend",(.70,.166,.041),rough=.65)
phosphor_bsdf=phosphor.node_tree.nodes["Principled BSDF"]
phosphor_bsdf.inputs["Emission Color"].default_value=(.65,.135,.018,1)
phosphor_bsdf.inputs["Emission Strength"].default_value=.32
palette_css = (ROOT / "theme.css").read_text(encoding="utf-8")
stripe_hex = dict(re.findall(r"--color-stripe-([a-z]+)\s*:\s*#([0-9a-fA-F]{6})\s*;", palette_css))


def stripe_material(name, color):
	# CSS stores sRGB; Blender's Base Color input expects scene-linear RGB.
	channels = bytes.fromhex(stripe_hex[color])
	srgb = (channel / 255 for channel in channels)
	linear = tuple(c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in srgb)
	return material(name, linear)


stripes = [
	stripe_material("Mint enamel", "green"),
	stripe_material("Yellow enamel", "yellow"),
	stripe_material("Brick enamel", "red"),
]


for paint in (ink, grip, black_print, white_print, orange_print, *stripes):
	paint.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = .15


def mesh_object(name, verts, faces, mat):
	mesh = bpy.data.meshes.new(name)
	mesh.from_pydata(verts, [], faces)
	mesh.update()
	return place(bpy.data.objects.new(name, mesh), name, mat)


def soften(obj, width, segments=3):
	if width:
		mod = obj.modifiers.new("Edge radius", "BEVEL")
		mod.width = width
		mod.segments = segments
		mod.harden_normals = True
		obj.modifiers.new("Face-weighted normals", "WEIGHTED_NORMAL")
	return obj


def block(name, center, size, mat, radius=0):
	bpy.ops.mesh.primitive_cube_add(size=1, location=center)
	obj = place(bpy.context.object, name, mat)
	obj.dimensions = size
	bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
	return soften(obj, radius)


def counterclockwise(points):
	area=sum(u*q-v*p for (u,v),(p,q) in zip(points,points[1:]+points[:1]))
	return points if area>=0 else list(reversed(points))


def slice_x(name, left, right, yz, mat):
	# Counterclockwise profile seen from +X. Curved walls share smooth normals.
	yz = counterclockwise(yz)
	n = len(yz)
	verts = [(x, y, z) for x in (left, right) for y, z in yz]
	faces = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
	faces.extend((i, (i+1) % n, n+(i+1) % n, n+i) for i in range(n))
	obj = mesh_object(name, verts, faces, mat)
	for p in list(obj.data.polygons)[2:]:
		p.use_smooth = True
	obj.data.set_sharp_from_angle(angle=math.radians(26))
	return obj


def arc(cy, cz, ry, rz, start, end, steps=12):
	return [(cy + ry * math.cos(a), cz + rz * math.sin(a))
		for a in np.linspace(math.radians(start), math.radians(end), steps+1)]


def cut(target, cutter):
	mod = target.modifiers.new("Machined opening", "BOOLEAN")
	mod.operation = "DIFFERENCE"
	mod.object = cutter
	bpy.context.view_layer.objects.active = target
	bpy.ops.object.modifier_apply(modifier=mod.name)
	bpy.data.objects.remove(cutter, do_unlink=True)
	if len(target.data.polygons)<4:
		raise RuntimeError(f"Cut removed all geometry from {target.name}")


def cut_boxes(target, boxes):
	# One disconnected cutter per housing panel; openings remain real in the GLB.
	verts, faces = [], []
	for (x, y, z), (w, d, h) in boxes:
		start = len(verts)
		for dz in (-1, 1):
			for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
				verts.append((x + dx*w/2, y + dy*d/2, z + dz*h/2))
		for face in ((3,2,1,0), (4,5,6,7), (0,1,5,4), (1,2,6,5), (2,3,7,6), (3,0,4,7)):
			faces.append(tuple(start+i for i in face))
	if boxes:
		cut(target, mesh_object("Opening tool", verts, faces, None))


def pin(name, axis, center, radius, depth, mat, edge=.003, sides=48):
	rotation = {"X": (0, math.pi/2, 0), "Y": (math.pi/2, 0, 0), "Z": (0, 0, 0)}
	bpy.ops.mesh.primitive_cylinder_add(vertices=sides, radius=radius, depth=depth,
		location=center, rotation=rotation[axis])
	obj = place(bpy.context.object, name, mat)
	for p in obj.data.polygons:
		p.use_smooth = abs(p.normal.z) < .5
	return soften(obj, edge)


def planar(name, xy, z, mat):
	return mesh_object(name, [(x, y, z) for x, y in counterclockwise(xy)], [tuple(range(len(xy)))], mat)


def capsule(name, x, y, width, height, z, mat, tilt=0):
	r = height/2
	points = arc((width-height)/2, 0, r, r, -90, 90)
	points += arc(-(width-height)/2, 0, r, r, 90, 270)
	c, s = math.cos(tilt), math.sin(tilt)
	return planar(name, [(x + c*u-s*v, y + s*u+c*v) for u, v in points], z, mat)


def text_mesh(name, content, x, y, z, width, height, mat, font=None, shear=0, offset=0):
	bpy.ops.object.text_add(location=(x, y, z))
	obj = place(bpy.context.object, name, mat)
	obj.data.body = content
	obj.data.shear = shear
	obj.data.offset = offset
	obj.data.resolution_u = 8
	if font:
		obj.data.font = font
	bpy.ops.object.convert(target="MESH")
	obj = bpy.context.object
	xs, ys = zip(*[(v.co.x, v.co.y) for v in obj.data.vertices])
	xmin,xmax,ymin,ymax=min(xs),max(xs),min(ys),max(ys)
	for vertex in obj.data.vertices:
		vertex.co.x = width*(vertex.co.x-xmin)/(xmax-xmin)
		vertex.co.y = height*(vertex.co.y-ymin)/(ymax-ymin)
	return obj


# Both large front radii are extruded sections, independent of the short end bevels.
group = collection("01 · Shell and shallow ribs")
shell_half_width = 2.755
top_curve = arc(-1.245, .79, .34, .31, 90, 180, 20)
upper = [(-1.585,.386), (1.55,.386), (1.55,.986)]
upper += arc(1.436, .986, .114, .114, 5, 90)
upper += top_curve
lower_rear = [(-1.474, .03), (1.44,.03)] + arc(1.44,.13,.103,.10,-85,0)
lower_front = [(-1.577,.132)] + arc(-1.474,.132,.103,.102,185,265)
lower = lower_rear + [(1.543,.365), (-1.577,.365)] + lower_front
# Keep the shell's parting-line seal recessed behind the side faces.
block("Split-line compression seal", (0,-.012,.375), (5.46,3.10,.065), ink,.025)
lid = slice_x("Upper moulding · rolled front lip", -shell_half_width, shell_half_width, upper, ivory)
cut_boxes(lid,[((-.13,-1.56,1.025),(1.49,.81,.99))])
# The parting lines on the front die away before reaching the printed medallion.
cut_boxes(lid,[((x,-1.535,.735),(.009,.68,.81)) for x in (-1.80,1.696)])
for x in (-2.60,2.59):
	cut(lid, pin("Bore", "Y", (x,-1.568,.484), .087,.18,None,0))
soften(lid,.004,3)
for i,(left,right) in enumerate(((-shell_half_width,-1.806),(-1.797,1.692),(1.701,shell_half_width))):
	soften(slice_x(f"Lower moulding {i+1}",left,right,lower,ivory),.012)
# Each rib has shallow bevelled shoulders. Sink its foot just into the intact
# moulding, including where it crosses the printed foil on the front.
rib_height = 0.01
def rib_row(name, centres, width, surface):
	verts, faces = [], []
	section = [(-.50,-.001),(.50,-.001),(.50,.001),(.32,rib_height),
		(-.32,rib_height),(-.50,.001)]
	n = len(section)
	for x in centres:
		start = len(verts)
		for y,z,ny,nz in surface:
			verts.extend((x+u*width,y+ny*h,z+nz*h) for u,h in section)
		faces.append(tuple(start+i for i in reversed(range(n))))
		for j in range(len(surface)-1):
			k = start+j*n
			faces.extend((k+i,k+(i+1)%n,k+n+(i+1)%n,k+n+i) for i in range(n))
		last = start+(len(surface)-1)*n
		faces.append(tuple(last+i for i in range(n)))
	return mesh_object(name,verts,faces,grip)

rib_row("Raised ribs · top",np.linspace(-2.10,2.04,82),.023,
	[(.049,1.10,0,1),(-.227,1.10,0,1)])
# Follow the same polygonal arc as the front lip, down to the flat face.
front_surface = []
for y,z in top_curve[-4:]:
	normal = Vector(((y+1.245)/.34**2,(z-.79)/.31**2)).normalized()
	front_surface.append((y,z,*normal))
y0,z0,ny0,nz0 = front_surface[0]
y1,z1,ny1,nz1 = front_surface[1]
fraction = (.8445-z0)/(z1-z0)
front_surface[0] = (y0+fraction*(y1-y0),.8445,ny0+fraction*(ny1-ny0),nz0+fraction*(nz1-nz0))
front_surface.append((-1.585,.5295,-1,0))
for label,start,end in (("left",-2.42,-1.59),("right",1.30,2.23)):
	rib_row("Raised ribs · front "+label,np.arange(start,end,.068),.039,front_surface)
for x in (-2.60,2.59):
	pin("Countersunk seat","Y",(x,-1.521,.484),.083,.07,ink)
	pin("Fastener head","Y",(x,-1.556,.484),.062,.024,gunmetal)
	slot = block("Recessed drive line",(x,-1.569,.484),(.081,.002,.012),ink,.001)
	slot.rotation_euler.y = -.53

case_height = max(z for _, z in upper) - min(z for _, z in lower)
guard_screw_radius = case_height * .43 / 2
guard_gap = .05
guard_inner_x = shell_half_width + guard_gap
guard_outer_x = guard_inner_x + .265


def guard_screw(side, y, z):
	# A single flat head with a narrow reflective bevel on the exposed rim.
	# The shallow drive is inferred; the announcement resolves only the face.
	profile = [(-.040, guard_screw_radius), (.009, guard_screw_radius), (.026, guard_screw_radius - .012)]
	segments = 64
	verts = []
	for axial, radius in profile:
		for i in range(segments):
			angle = math.tau * i / segments
			verts.append((side * (guard_outer_x + axial), y + radius * math.cos(angle),
				z + radius * math.sin(angle)))
	faces = [tuple(reversed(range(segments)))]
	for ring in range(len(profile) - 1):
		base = ring * segments
		for i in range(segments):
			j = (i + 1) % segments
			faces.append((base+i, base+j, base+segments+j, base+segments+i))
	faces.append(tuple(range(len(verts)-segments, len(verts))))
	if side < 0:
		faces = [tuple(reversed(face)) for face in faces]
	head = mesh_object("Guard screw · flat head", verts, faces, gunmetal)
	head.data.materials.append(silver)
	for face in head.data.polygons[1:-1]:
		face.use_smooth = True
		if face.index > segments:
			face.material_index = 1
	head.data.set_sharp_from_angle(angle=math.radians(25))
	drive = block("Drive cutter", (side*(guard_outer_x + .031), y, z), (.035, .282, .020), None)
	drive.rotation_euler.x = math.radians(24)
	cut(head, drive)
	soften(head, .0018, 2)


def round_guard_rim(guard, outer_x, radius, slot_walls=()):
	mesh = bmesh.new()
	mesh.from_mesh(guard.data)
	top_z = max(v.co.z for v in mesh.verts)
	rim_edges = []
	for edge in mesh.edges:
		if abs(edge.calc_face_angle(0) - math.pi/2) > .001:
			continue
		on_outer_face = all(abs(v.co.x - outer_x) < 1e-5 for v in edge.verts)
		at_slot_top = any(abs(v.co.z - top_z) < 1e-5 for v in edge.verts) and any(
			all(abs(v.co.y - wall) < 1e-5 for v in edge.verts) for wall in slot_walls)
		if on_outer_face or at_slot_top:
			rim_edges.append(edge)
	fillet = bmesh.ops.bevel(mesh, geom=rim_edges, offset=radius, segments=4, profile=.5, affect="EDGES")
	for face in fillet["faces"]:
		face.smooth = True
	mesh.to_mesh(guard.data)
	mesh.free()


group = collection("02 · End guards and identification bands")
guard_rim_radius = .01
channel_width = .1
# Follow the upper and lower silhouettes in one loop, omitting their internal mating faces.
guard_outline = lower_rear + upper[1:] + upper[:1] + lower_front
front_y = min(y for y, _ in upper)
rear_y, top_z = max(y for y, _ in upper), max(z for _, z in upper)
# Anchor the heads by their outer tangents so their original edge clearances survive resizing.
front_screw = (front_y + .09425 + guard_screw_radius, top_z - .06425 - guard_screw_radius)
# Centre the square land on the screw, anchored to the two outer case edges.
inset = guard_screw_radius + .0585
rear_screw = (rear_y - inset, top_z - inset)
land_left, land_bottom = rear_screw[0] - inset, rear_screw[1] - inset
channel_left, channel_bottom = land_left - channel_width, land_bottom - channel_width
front_limit, rear_limit = front_y - .03, rear_y + .03
# Align the lower opening with the far edge of the guide slot beside the front screw.
pocket_front = front_screw[0] + inset + channel_width
pocket_rear = rear_y - (rear_y - front_y) / 3
pocket_bottom = (channel_bottom + min(z for _, z in guard_outline)) / 2
# One through-cut exposes the shell behind the channel and both branches.
open_channel = [(front_limit, channel_bottom), (pocket_front, channel_bottom),
	(pocket_front, pocket_bottom), (pocket_rear, pocket_bottom),
	(pocket_rear, channel_bottom), (rear_limit, channel_bottom),
	(rear_limit, land_bottom), (land_left, land_bottom), (land_left, 1.13),
	(channel_left, 1.13), (channel_left, land_bottom), (front_limit, land_bottom)]
for side in (-1,1):
	lo, hi = sorted((side*guard_inner_x, side*guard_outer_x))
	# Inferred mounting pads: one behind the solid centre of each disconnected guard piece.
	for y, z, width, height in ((0,.77,.36,.14), (*rear_screw,.18,.12), (0,.13,.32,.08)):
		block("End guard · mounting pad", (side*(shell_half_width + guard_gap/2),y,z), (guard_gap + .020,width,height), ivory,.003)
	rail = slice_x("Orange end guard",lo,hi,guard_outline,orange)
	cut(rail, slice_x("Open side channel", lo - .01, hi + .01, open_channel, None))
	round_guard_rim(rail, side*guard_outer_x, guard_rim_radius, (channel_left, land_left))
	for y, z in (front_screw, rear_screw):
		cut(rail,pin("Guard screw seat","X",(side*guard_outer_x,y,z),guard_screw_radius + .006,.12,None,0))
		guard_screw(side,y,z)
	soften(rail,guard_rim_radius,4)
	# Exposed cut surfaces carry the same enamel as the rest of the guard.
	rail.data.materials.clear()
	rail.data.materials.append(orange)
	for face in rail.data.polygons:
		face.material_index = 0
	rail.modifiers["Edge radius"].material = 0

def ribbon(name, x, width, path, mat):
	verts = [(u,y,z) for y,z in path for u in (x,x+width)]
	faces = [(i*2,i*2+2,i*2+3,i*2+1) for i in range(len(path)-1)]
	obj = mesh_object(name,verts,faces,mat)
	for p in obj.data.polygons:
		p.use_smooth = True

# The foil follows the continuous shell underneath the raised front ribs.
for i, mat in enumerate(reversed(stripes)):
	x = -2.44 + .096*i
	w = .096
	upper_path = [(1.414,1.102)] + arc(-1.245,.79,.342,.312,90,180,20)
	upper_path.append((-1.587,.390))
	ribbon("Top band · "+mat.name,x,w,upper_path,mat)
	low_path = [(-1.579,.362),(-1.579,.132)] + arc(-1.474,.132,.105,.104,182,259)
	ribbon("Lower return · "+mat.name,x,w,low_path,mat)

# The screen has a machined metal rim, recessed sloped amber reveal, and glass.
group = collection("03 · Display, recess and visor")
def surround(name, cx, cy, profiles, mat):
	verts, faces = [], []
	for w,d,z in profiles:
		verts.extend((cx+sx*w/2,cy+sy*d/2,z) for sx,sy in ((-1,-1),(1,-1),(1,1),(-1,1)))
	for j in range(len(profiles)-1):
		for i in range(4):
			a=j*4+i
			b=j*4+(i+1)%4
			faces.append((a,b,b+4,a+4))
	return mesh_object(name,verts,faces,mat)

cx, cy = -.046, .787
block("Undercut display gasket",(cx,cy,1.110),(4.39,1.478,.067),ink,.032)
surround("Rolled nickel rim",cx,cy,[(4.39,1.48,1.128),(4.39,1.48,1.181),
	(4.365,1.455,1.200),(4.245,1.335,1.200),(4.218,1.308,1.166)],silver)
surround("Amber bevel under rim",cx,cy,[(4.226,1.318,1.181),(4.172,1.264,1.186),
	(3.842,.904,1.16),(3.818,.880,1.154)],bezel)
surround("Screen seal",cx,cy,[(3.828,.894,1.157),(3.795,.861,1.152)],ink)

# Boundaries in the rectified 640-by-160 artwork. Only these unambiguous legends
# are redrawn. Digits, fine marks and the boxed text keep the source silhouette.
legends=[
	("GET",36,22,73,45),
	("RHINE LAB",39,67,122,87),
	("PIONEER PROJECT",38,110,169,131),
	("HR MIN SEC",302,21,402,44),
	("HR MIN SEC",299,109,394,130),
]


def screen_print():
	# Project just the display aperture onto its own UV island. Threshold the red
	# channel to retain the real micrographics without baking highlights or metal.
	art = bpy.data.images.load(str(NOTICE))
	w,h = art.size
	data = np.empty(w*h*4,np.float32)
	art.pixels.foreach_get(data)
	red = data.reshape(h,w,4)[::-1,:,0]
	W,H = 640,160
	src = [(765.9,182.0),(988.0,259.7),(1007.4,227.0),(791.7,155.2)]
	unit = [(0,0),(1,0),(1,1),(0,1)]
	rows, values = [], []
	for (s,t),(x,y) in zip(unit,src):
		rows.extend([[s,t,1,0,0,0,-s*x,-t*x],[0,0,0,s,t,1,-s*y,-t*y]])
		values.extend([x,y])
	a,b,c,d,e,f,g,k = np.linalg.solve(rows,values)
	t,s = np.mgrid[0:H,0:W]
	s,t = (s+.5)/W,(t+.5)/H
	px,py = (a*s+b*t+c)/(g*s+k*t+1),(d*s+e*t+f)/(g*s+k*t+1)
	ix,iy = np.floor(px).astype(int),np.floor(py).astype(int)
	dx,dy = px-ix,py-iy
	value = ((1-dx)*(1-dy)*red[iy,ix]+dx*(1-dy)*red[iy,ix+1]
		+(1-dx)*dy*red[iy+1,ix]+dx*dy*red[iy+1,ix+1])
	mask = np.clip((value-.246)/.62,0,1)**.90
	for _,x0,y0,x1,y1 in legends:
		mask[H-y1-5:H-y0+6,x0-5:x1+5]=0
	rgb = np.array([.208,.073,.022]) + mask[:,:,None]*np.array([.72,.32,.105])
	red_lamps=(s>.89) & (t<.62)
	rgb[red_lamps,1]*=.61
	rgb[red_lamps,2]*=.55
	img = bpy.data.images.new("Case Investigation · display phosphor",width=W,height=H,alpha=False)
	pixels = np.concatenate((rgb,np.ones((H,W,1))),axis=2)
	img.pixels.foreach_set(pixels.astype(np.float32).ravel())
	img.pack()
	bpy.data.images.remove(art)
	tex=screen.node_tree.nodes.new("ShaderNodeTexImage")
	tex.image=img
	bsdf=screen.node_tree.nodes["Principled BSDF"]
	for socket in ("Base Color","Emission Color"):
		screen.node_tree.links.new(tex.outputs["Color"],bsdf.inputs[socket])
	bsdf.inputs["Emission Strength"].default_value=.22
	obj=planar("Display glass and original phosphor layout",
		[(cx+sx*1.900,cy+sy*.433) for sx,sy in ((-1,-1),(1,-1),(1,1),(-1,1))],1.153,screen)
	uv=obj.data.uv_layers.new(name="Screen")
	for i,coord in enumerate(unit):
		uv.data[i].uv=coord

screen_print()
for label,x0,y0,x1,y1 in legends:
	text_mesh("Phosphor · "+label,label,cx-1.9+3.8*x0/640,cy+.433-.866*y1/160,
		1.1534,3.8*(x1-x0)/640,.866*(y1-y0)/160,phosphor,shear=.08)
# Interleaved small knuckles share a real pin. The hinge root is the pivot
# origin, so adjusting the visor in the source scene moves its attached leaves.
hinge_y, hinge_z = 1.451,1.222
pin("Visor pivot","X",(cx,hinge_y,hinge_z),.024,4.16,bezel)
visor_root=bpy.data.objects.new("Visor · hinge axis",None)
group.objects.link(visor_root)
visor_root.location=(cx,hinge_y,hinge_z)
visor_root.rotation_euler.x=math.radians(20)
for i,(x,width) in enumerate(((-1.89,.25),(-1.57,.33),(0,.46),(1.57,.33),(1.89,.25))):
	obj=pin("Hinge knuckle","X",(cx+x,hinge_y,hinge_z),.033,width,bezel)
	if i%2:
		obj.parent=visor_root
		obj.location=(x,0,0)
	else:
		block("Fixed hinge foot",(cx+x,hinge_y-.029,1.186),(width,.09,.056),bezel,.012)
def visor_panel():
	# Slight taper and a polished cut edge, visible even when viewed edge-on.
	a,b,z=2.095,2.162,.64
	pts=[(-a,-.017,0),(a,-.017,0),(b,-.017,z),(-b,-.017,z),
		(-a,.017,0),(a,.017,0),(b,.017,z),(-b,.017,z)]
	faces=[(0,1,2,3),(7,6,5,4),(4,5,1,0),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
	obj=mesh_object("Smoked visor · cut acrylic",pts,faces,glass)
	obj.parent=visor_root
	obj.data.materials.append(bezel)
	for p in list(obj.data.polygons)[2:]:
		p.material_index=1
	soften(obj,.008)
visor_panel()

group = collection("04 · Clasp and folding grip")
block("Clasp pocket · inner wall",(-.13,-1.158,.795),(1.485,.06,.53),ink,.015)
block("Clasp pocket · floor",(-.13,-1.36,.548),(1.47,.41,.041),grip,.012)
for x in (-.828,.568):
	block("Clasp guide cheek",(x,-1.375,.765),(.060,.401,.43),gunmetal,.018)
pin("Catch · crossbar","X",(-.13,-1.337,.912),.053,1.39,gunmetal)
catch_profile=[(-1.58,.492),(-1.44,.495),(-1.348,.806),(-1.352,.875),
	(-1.405,.891),(-1.461,.847),(-1.577,.723)]
soften(slice_x("Folded nickel latch · lever",-.805,.545,catch_profile,silver),.018,4)
# Dark thumb lip breaks the reflection across the lower part of the clasp.
block("Clasp · thumb lip",(-.13,-1.583,.576),(1.14,.046,.064),ink,.022)
fixed_parts=set(group.objects)
for x in (-1.10,.94):
	foot=block("Handle mounting foot",(x,-1.576,.533),(.216,.160,.137),ink,.029)
	axle=pin("Handle pivot axle","X",(x,-1.594,.537),.071,.249,silver)
	fixed_parts.update((foot,axle))
	link_outline=[(-2.008,.367),(-1.889,.332),(-1.578,.452),(-1.528,.501),
		(-1.535,.585),(-1.617,.619),(-1.70,.592),(-1.974,.48),(-2.014,.437)]
	soften(slice_x("Handle link · rubber surround",x-.104,x+.104,link_outline,grip),.014)
	saddle=[(-1.972,.465),(-1.627,.591),(-1.614,.618),(-1.640,.618),
		(-1.716,.590),(-1.970,.486)]
	soften(slice_x("Handle link · nickel crown",x-.055,x+.055,saddle,silver),.005)
	for side in (-1,1):
		pin("Link pivot face","X",(x+side*.106,-1.596,.533),.051,.01,gunmetal)
		outline=[(-1.977,.379),(-1.919,.361),(-1.622,.475),(-1.591,.500),
			(-1.592,.570),(-1.629,.580),(-1.947,.461),(-1.984,.430)]
		lo,hi=sorted((x+side*.104,x+side*.119))
		soften(slice_x("Handle link · pressed metal cheek",lo,hi,outline,silver),.006)
pin("Grip · continuous metal core","X",(-.08,-1.944,.411),.058,2.15,silver)
handle=block("Black handgrip",(-.08,-1.947,.416),(1.82,.186,.156),grip,.066)
for x in (-1.00,.84):
	pin("Handle end ferrule","X",(x,-1.944,.413),.089,.035,gunmetal)

moving_parts=set(group.objects)-fixed_parts
handle_root=bpy.data.objects.new("Handle · hinge axis",None)
group.objects.link(handle_root)
handle_root.location=(-.08,-1.594,.537)
for pivot in (visor_root,handle_root):
	pivot.empty_display_type="ARROWS"
	pivot.empty_display_size=.19
bpy.context.view_layer.update()
for part in moving_parts:
	part.parent=handle_root
	part.matrix_parent_inverse=handle_root.matrix_world.inverted()

group = collection("05 · Surface printing and indicator lenses")
z=1.102
bold_path=Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
bold=bpy.data.fonts.load(str(bold_path)) if bold_path.exists() else None
text_mesh("Equipment name · first line","Technical Investigation",-1.50,-.712,z,2.13,.209,black_print,bold,.12)
text_mesh("Equipment name · second line","Supplies",-1.50,-.925,z,.79,.208,black_print,bold,.12)
for i,mat in enumerate(stripes):
	x=-.69+i*.427
	planar("Nameplate signal bar",[(x,-.877),(x+.427,-.877),(x+.427,-.809),(x,-.809)],z,mat)
capsule("Foundation imprint",-1.17,-.349,1.70,.135,z,orange_print)
for x in (-1.91,-.43):
	pin("Imprint terminal","Z",(x,-.349,z+.001),.016,.001,white_print,0,20)
text_mesh("Foundation imprint · legend","Maylander Foundation",-1.752,-.384,z+.001,.99,.071,white_print,bold,.06)

def disc(name,x,y,r,z,mat):
	pt=[(x+r*math.cos(a),y+r*math.sin(a)) for a in np.linspace(0,2*math.pi,65)[:-1]]
	return planar(name,pt,z,mat)

# Fit the two glyphs separately in units of the disc diameter. The original
# uses knocked-out strokes that meet the circumference, including the 6's bowl.
badge_x, badge_y, badge_radius = -1.826, -.704, .233
disc("Foundation emblem · disc",badge_x,badge_y,badge_radius,z,orange_print)


badge_font_path = bold_path.with_name("Futura.ttc")
badge_font = bpy.data.fonts.load(str(badge_font_path)) if badge_font_path.exists() else bold


def badge_digit(digit, left, top, width, height, lean, weight, cuts):
	diameter = 2 * badge_radius
	obj = text_mesh("Foundation emblem · " + digit, digit,
		badge_x + (left - .5) * diameter, badge_y + (.5 - top - height) * diameter,
		z + .001, width * diameter, height * diameter, ivory, badge_font, offset=weight)
	mesh = bmesh.new()
	mesh.from_mesh(obj.data)
	for v in mesh.verts:
		v.co.x += lean * diameter * (v.co.y / (height * diameter) - .5)
	# The reference has flat terminals. Each cut is a plane measured from the
	# disc centre in diameters; its normal points towards the ink to discard.
	center = Vector((badge_x - obj.location.x, badge_y - obj.location.y, 0))

	def trim(nx, ny, distance):
		normal = Vector((nx, ny, 0))
		bmesh.ops.bisect_plane(mesh, geom=[*mesh.verts, *mesh.edges, *mesh.faces],
			plane_co=center + distance * normal, plane_no=normal, clear_outer=True, dist=1e-8)

	for nx, ny, offset in cuts:
		trim(nx, ny, offset * diameter)
	apothem = badge_radius * math.cos(math.pi / 64)
	for i in range(64):
		angle = (i + .5) * math.tau / 64
		trim(math.cos(angle), math.sin(angle), apothem)
	mesh.to_mesh(obj.data)
	mesh.free()


# The 7 turns vertically at x = 50% before the diagonal. Its foot ends
# horizontally at 82% of the disc height; the 6 starts at 17% from the top.
badge_digit("7", .020, .170, .595, .728, -.098, .024, [(1, 0, .000), (0, -1, .320)])
badge_digit("6", .484, .100, .524, .758, .003, .030, [(0, 1, .330)])
disc("Small index roundel",.736,-.584,.059,z,orange_print)
text_mesh("Small index · knockout","1",.719,-.614,z+.001,.034,.062,ivory,bold,.12)
planar("Black maker tile",[(1.69,-.900),(2.079,-.900),(2.079,-.462),(1.69,-.462)],z,black_print)
# All three strokes share a cap line. The dot sits on the short stroke's
# centreline, level with the feet of the two long strokes in the notice.
for x, y, length in ((1.802, -.684, .200), (1.886, -.684, .200), (1.991, -.651, .124)):
	capsule("Maker tile · stroke", x, y, length, .060, z+.001, white_print, math.radians(60))
disc("Maker tile · dot", 1.935, -.748, .029, z+.001, white_print)
# Small dark/lit contacts on the lower right face are visible on the inventory icon.
block("Lower status badge",(2.24,-1.577,.193),(.438,.023,.110),ivory,.021)
for cap_x,mat in ((2.066,ink),(2.414,stripes[-1])):
	pin("Status badge · terminal","Y",(cap_x,-1.590,.193),.049,.010,mat,.002,32)
block("Status badge · ivory centre",(2.24,-1.596,.193),(.335,.006,.092),white_print,.003)
for i,mat in enumerate((ink,gunmetal,orange_print)):
	pin("Lower status lens","Y",(2.137+i*.100,-1.601,.193),.022,.008,mat,.003,32)

# The export selection excludes all studio objects. Text is already mesh geometry.
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=str(MODELS/"technical-investigation-supplies.glb"),
	export_format="GLB",use_selection=True,export_apply=True,export_cameras=False,export_lights=False)

group = collection("Studio · cameras and lighting")
def aim(obj,target):
	obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()

def softbox(name,loc,power,size,target,size_y=None):
	bpy.ops.object.light_add(type="AREA",location=loc)
	obj=place(bpy.context.object,name)
	obj.data.energy=power
	obj.data.shape="RECTANGLE"
	obj.data.size=size
	obj.data.size_y=size_y or size
	aim(obj,target)

softbox("Key · upper left",(-4.4,-2.2,7.8),625,4.2,(0,0,.6))
softbox("Fill · front right",(5,-4,3.8),105,4,(0,0,.6))
softbox("Rim · top edge",(.5,3.8,6.0),620,5.3,(0,.4,.7),1.6)
def camera(name,location,target,scale,orthographic=True):
	bpy.ops.object.camera_add(location=location)
	cam=place(bpy.context.object,name)
	aim(cam,target)
	if orthographic:
		cam.data.type="ORTHO"
		cam.data.ortho_scale=scale
	else:
		cam.data.lens=scale
	return cam

hero=camera("Camera · announcement",(6.4,-11.9,10.65),(0,-.12,.73),79,False)
plan=camera("Camera · plan",(0,-.14,12),(0,-.14,0),6.78)
detail=camera("Camera · clasp and grip",(2.0,-8.0,4.27),(-.10,-1.40,.66),3.78)
scene.world=bpy.data.worlds.new("Neutral studio")
scene.world.use_nodes=True
scene.world.node_tree.nodes["Background"].inputs[0].default_value=(.19,.205,.22,1)
scene.render.engine="CYCLES"
scene.cycles.samples=48
scene.cycles.use_denoising=True
scene.view_settings.view_transform="Khronos PBR Neutral"
scene.render.film_transparent=True
scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"

def setup(cam,width,height,name):
	scene.camera=cam
	scene.render.resolution_x=width
	scene.render.resolution_y=height
	scene.render.filepath="//../assets/"+name

setup(hero,1560,1080,"supplies.png")
bpy.context.preferences.filepaths.save_version=0
for area in bpy.context.screen.areas:
	if area.type=="VIEW_3D":
		space=area.spaces.active
		space.region_3d.view_perspective="CAMERA"
		space.region_3d.view_distance=8
		space.region_3d.view_location=(0,0,.65)
		space.shading.color_type="MATERIAL"
		space.overlay.show_overlays=False
bpy.ops.object.select_all(action="DESELECT")
bpy.context.view_layer.objects.active=handle
bpy.ops.wm.save_as_mainfile(filepath=str(MODELS/"technical-investigation-supplies.blend"))
bpy.ops.render.render(write_still=True)
setup(plan,1400,930,"supplies-plan.png")
bpy.ops.render.render(write_still=True)
setup(detail,1280,720,"supplies-clasp.png")
bpy.ops.render.render(write_still=True)
