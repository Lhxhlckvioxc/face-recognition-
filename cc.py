import bpy
import os
import sys
import json
from math import radians
import numpy as np
from mathutils import Matrix

# Step 1: Load Camera Calibration Data
try:
    idx = sys.argv.index('--')
except ValueError:
    print('Usage: blender -P %s -- calib.json' % sys.argv[0])
    sys.exit(-1)

if idx == len(sys.argv):
    print('Usage: blender -P %s -- calib.json' % sys.argv[0])
    sys.exit(-1)

calib_file = sys.argv[idx+1]
calib_dir = os.path.split(calib_file)[0]
calibration_data = json.load(open(calib_file, 'rt'))

# Step 2: Set Blender Scene Resolution
scene = bpy.context.scene
W, H = calibration_data['image_resolution']
scene.render.resolution_x = W
scene.render.resolution_y = H

# Step 3: Create Chessboard Object
chessboard_points = np.array(calibration_data['chessboard_points'], 'float32')
chessboard_mesh = bpy.data.meshes.new(name='chessboard_corners')
chessboard_mesh.vertices.add(chessboard_points.shape[0])
chessboard_mesh.vertices.foreach_set('co', chessboard_points.flatten())
chessboard_mesh.update()
chessboard_object = bpy.data.objects.new(name='chessboard_corners', object_data=chessboard_mesh)
scene.collection.objects.link(chessboard_object)

# Step 4: Create Textured Quad
spacing = calibration_data['chessboard_spacing_m']
corners = calibration_data['chessboard_inner_corners']
vertices = np.array([
    -spacing, -spacing, 0,
    spacing * corners[0], -spacing, 0,
    spacing * corners[0], spacing * corners[1], 0,
    -spacing, spacing * corners[1], 0
], 'float32')
indices = np.array([0, 1, 2, 3], 'uint32')
loop_start = np.array([0], 'uint32')
loop_total = np.array([4], 'uint32')
uvs = np.array([
    0, 0,
    1, 0,
    1, 1,
    0, 1
], 'float32')

quad_mesh = bpy.data.meshes.new(name='textured_quad')
quad_mesh.vertices.add(4)
quad_mesh.vertices.foreach_set('co', vertices)
quad_mesh.loops.add(4)
quad_mesh.loops.foreach_set('vertex_index', indices)
quad_mesh.polygons.add(1)
quad_mesh.polygons.foreach_set('loop_start', loop_start)
quad_mesh.polygons.foreach_set('loop_total', loop_total)
uv_layer = quad_mesh.uv_layers.new(name='uvs')
uv_layer.data.foreach_set('uv', uvs)
quad_mesh.update()

# Create Material for Textured Quad
quad_material = bpy.data.materials.new('textured_quad')
quad_material.use_nodes = True
nodes = quad_material.node_tree.nodes
nodes.clear()
texcoord = nodes.new(type='ShaderNodeTexCoord')
texcoord.location = 0, 300
mapping = nodes.new(type='ShaderNodeMapping')
mapping.location = 200, 300
mapping.inputs['Scale'].default_value = (corners[0] + 1, corners[1] + 1, 1)
checktex = nodes.new(type='ShaderNodeTexChecker')
checktex.location = 400, 300
checktex.inputs['Color2'].default_value = 0, 0, 0, 1
checktex.inputs['Scale'].default_value = 1.0
emission = nodes.new(type='ShaderNodeEmission')
emission.location = 600, 300
node_output = nodes.new(type='ShaderNodeOutputMaterial')
node_output.location = 800, 300
links = quad_material.node_tree.links
links.new(texcoord.outputs['UV'], mapping.inputs['Vector'])
links.new(mapping.outputs['Vector'], checktex.inputs['Vector'])
links.new(checktex.outputs['Color'], emission.inputs['Color'])
links.new(emission.outputs['Emission'], node_output.inputs['Surface'])

# Assign Material to Textured Quad
quad_mesh.materials.append(quad_material)

# Create Textured Quad Object
quad_object = bpy.data.objects.new(name='textured_quad', object_data=quad_mesh)
scene.collection.objects.link(quad_object)

# Step 5: Create and Position Cameras
camera_collection = bpy.data.collections.new('Cameras')
scene.collection.children.link(camera_collection)

for img_file, values in calibration_data['chessboard_orientations'].items():
    # Create Camera
    cam_data = bpy.data.cameras.new(name=img_file)
    cam_obj = bpy.data.objects.new(img_file, cam_data)
    scene.collection.objects.link(cam_obj)

    # Set Camera Parameters
    if 'sensor_size_mm' in calibration_data:
        cam_data.sensor_fit = 'HORIZONTAL'
        cam_data.sensor_width = calibration_data['sensor_size_mm'][0]

    if 'fov_degrees' in calibration_data:
        cam_data.lens_unit = 'FOV'
        cam_data.angle = radians(calibration_data['fov_degrees'][0])

    # Set Camera Transformation
    translation = values['translation']
    rotation_matrix = Matrix(values['rotation_matrix'])
    cam_obj.matrix_world = (Matrix.Rotation(radians(180), 4, 'X') @
                            Matrix.Translation(translation) @
                            rotation_matrix.to_4x4()).inverted()

    # Set Background Image on Camera
    img_path = os.path.join(calib_dir, img_file)
    if os.path.isfile(img_path):
        bg_image = bpy.data.images.load(img_path)
        if bg_image:
            cam_data.show_background_images = True
            bg = cam_data.background_images.new()
            bg.image = bg_image

