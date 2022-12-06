import bpy
import math
import numpy as np
from mathutils import Matrix
from bpy_extras.io_utils import axis_conversion

export_normals = True
export_uvs = True
export_vert_colors = True
export_tangents = False

obj = bpy.data.objects['skinMesh']
rig = bpy.data.objects['Armature']
rigmesh = bpy.data.objects['skinMeshRigged']

def main():
    export_props()
    
def export_props():
    groups = [x.name for x in rigmesh.vertex_groups]
    indices = get_gltf_export_indices(rigmesh)

    obj['boneMats'] = dict()
    obj['boneWeights'] = dict()
    
    # blender z-up to babylon y-up
    R1 = Matrix.Rotation(math.radians(180), 4, 'Y')
    R2 = Matrix.Rotation(math.radians(-90), 4, 'X')

    # Our rig has -Y as forward, R1 switches it to +Y
    axis_basis_change = axis_conversion(
        from_forward='Y', from_up='Z',
        to_forward='Z', to_up='Y'
    ).to_4x4() @ R1



    FRAMES = 101
    for i in range(1, FRAMES):
        mat_list = []
        bpy.context.scene.frame_set(i)
        for name in groups:
            inverse_bind_pose = (
                rig.matrix_world @ 
                rig.pose.bones[name].bone.matrix_local
            ).inverted_safe()

            bone_matrix = (
                rig.matrix_world @
                rig.pose.bones[name].matrix
            )
            
            # Read right to left
            # 1. convert axis basis, 
            # 2. inverse rest pose (go to origin), 
            # 3. move to actual bone transform
            # 4. R2 ?? TODO(ranjian0) Investigate
            mat = R2 @ bone_matrix @ inverse_bind_pose @ axis_basis_change
            
            mat = [round(mat[j][i], 4) for i in range(4) for j in range(4)]            
            mat_list.append(mat)
            
        obj['boneMats'][str(i)] = mat_list
        
        
    tmp_map = dict()
    for v in rigmesh.data.vertices:
        groups = sorted(v.groups, key=lambda x: -x.weight)[:4]
        total_weight = sum((x.weight for x in groups), 0.0) or 1.0
        bones = ([x.group for x in groups] + [0, 0, 0, 0])[:4]
        weights = ([x.weight / total_weight for x in groups] + [0.0, 0.0, 0.0, 0.0])[:4]
        
        all_weights = [0.0] * len(rig.data.bones)
        for idx, bone in enumerate(rig.data.bones):
            if bone.name not in rigmesh.vertex_groups:
                continue
            
            vg = rigmesh.vertex_groups[bone.name]
            if vg.index in bones:
                all_weights[idx] = weights[bones.index(vg.index)]
        
        tmp_map[v.index] = all_weights

    for i in range(len(indices)):   
        obj['boneWeights'][str(i)] = tmp_map[indices[i]]

### Reverse engineer gltf exporter indices
### basically allow converting blender per-loop data into per-vert data

def get_gltf_export_indices(obj):
    me = obj.data
    armature = None
    blender_mesh = me
    blender_object = None
    export_settings = {}
    tex_coord_max = len(me.uv_layers)
    color_max = len(blender_mesh.vertex_colors)
    colors_attributes = []
    rendered_color_idx = blender_mesh.attributes.render_color_index

    if color_max > 0:
        colors_attributes.append(rendered_color_idx)
        # Then find other ones
        colors_attributes.extend([
            i for i in range(len(blender_mesh.color_attributes)) if i != rendered_color_idx \
                and blender_mesh.vertex_colors.find(blender_mesh.color_attributes[i].name) != -1
        ])
    

    dot_fields = [('vertex_index', np.uint32)]
    if export_normals:
        dot_fields += [('nx', np.float32), ('ny', np.float32), ('nz', np.float32)]
    if export_tangents:
        dot_fields += [('tx', np.float32), ('ty', np.float32), ('tz', np.float32), ('tw', np.float32)]
    for uv_i in range(tex_coord_max):
        dot_fields += [('uv%dx' % uv_i, np.float32), ('uv%dy' % uv_i, np.float32)]
    for col_i, _ in enumerate(colors_attributes):
        dot_fields += [
            ('color%dr' % col_i, np.float32),
            ('color%dg' % col_i, np.float32),
            ('color%db' % col_i, np.float32),
            ('color%da' % col_i, np.float32),
        ]


    dots = np.empty(len(me.loops), dtype=np.dtype(dot_fields))
    vidxs = np.empty(len(me.loops))
    me.loops.foreach_get('vertex_index', vidxs)
    dots['vertex_index'] = vidxs
    del vidxs    
    
    if export_normals:
        kbs = []
        normals, morph_normals = __get_normals(
            blender_mesh, kbs, armature, blender_object, export_settings
        )
        dots['nx'] = normals[:, 0]
        dots['ny'] = normals[:, 1]
        dots['nz'] = normals[:, 2]
        del normals

    if export_tangents:
        tangents = __get_tangents(blender_mesh, armature, blender_object, export_settings)
        dots['tx'] = tangents[:, 0]
        dots['ty'] = tangents[:, 1]
        dots['tz'] = tangents[:, 2]
        del tangents
        signs = __get_bitangent_signs(blender_mesh, armature, blender_object, export_settings)
        dots['tw'] = signs
        del signs

    for uv_i in range(tex_coord_max):
        uvs = __get_uvs(blender_mesh, uv_i)
        dots['uv%dx' % uv_i] = uvs[:, 0]
        dots['uv%dy' % uv_i] = uvs[:, 1]
        del uvs

    colors_types = []
    for col_i, blender_col_i in enumerate(colors_attributes):
        colors, colors_type, domain = __get_colors(blender_mesh, col_i, blender_col_i)
        if domain == "POINT":
            colors = colors[dots['vertex_index']]
        colors_types.append(colors_type)
        dots['color%dr' % col_i] = colors[:, 0]
        dots['color%dg' % col_i] = colors[:, 1]
        dots['color%db' % col_i] = colors[:, 2]
        dots['color%da' % col_i] = colors[:, 3]
        del colors


    # Calculate triangles and sort them into primitives.

    me.calc_loop_triangles()
    loop_indices = np.empty(len(me.loop_triangles) * 3, dtype=np.uint32)
    me.loop_triangles.foreach_get('loops', loop_indices)

    prim_indices = {}  # maps material index to TRIANGLES-style indices into dots

    # Bucket by material index.

    tri_material_idxs = np.empty(len(me.loop_triangles), dtype=np.uint32)
    me.loop_triangles.foreach_get('material_index', tri_material_idxs)
    loop_material_idxs = np.repeat(tri_material_idxs, 3)  # material index for every loop
    unique_material_idxs = np.unique(tri_material_idxs)
    del tri_material_idxs

    for material_idx in unique_material_idxs:
        prim_indices[material_idx] = loop_indices[loop_material_idxs == material_idx]


    prim_dots = dots[prim_indices[0]]
    prim_dots, indices = np.unique(prim_dots, return_inverse=True)
    result = [d[0] for d in prim_dots]
    return result


def __get_normals(blender_mesh, key_blocks, armature, blender_object, export_settings):
    """Get normal for each loop."""
    if key_blocks:
        normals = key_blocks[0].relative_key.normals_split_get()
        normals = np.array(normals, dtype=np.float32)
    else:
        normals = np.empty(len(blender_mesh.loops) * 3, dtype=np.float32)
        blender_mesh.calc_normals_split()
        blender_mesh.loops.foreach_get('normal', normals)

    normals = normals.reshape(len(blender_mesh.loops), 3)

    morph_normals = []
    for key_block in key_blocks:
        ns = np.array(key_block.normals_split_get(), dtype=np.float32)
        ns = ns.reshape(len(blender_mesh.loops), 3)
        morph_normals.append(ns)

    # Transform for skinning
    if armature and blender_object:
        apply_matrix = (armature.matrix_world.inverted_safe() @ blender_object.matrix_world)
        apply_matrix = apply_matrix.to_3x3().inverted_safe().transposed()
        normal_transform = armature.matrix_world.to_3x3() @ apply_matrix

        normals[:] = __apply_mat_to_all(normal_transform, normals)
        __normalize_vecs(normals)
        for ns in morph_normals:
            ns[:] = __apply_mat_to_all(normal_transform, ns)
            __normalize_vecs(ns)

    for ns in [normals, *morph_normals]:
        # Replace zero normals with the unit UP vector.
        # Seems to happen sometimes with degenerate tris?
        is_zero = ~ns.any(axis=1)
        ns[is_zero, 2] = 1

    # glTF stores deltas in morph targets
    for ns in morph_normals:
        ns -= normals

    return normals, morph_normals


def __get_tangents(blender_mesh, armature, blender_object, export_settings):
    """Get an array of the tangent for each loop."""
    tangents = np.empty(len(blender_mesh.loops) * 3, dtype=np.float32)
    blender_mesh.loops.foreach_get('tangent', tangents)
    tangents = tangents.reshape(len(blender_mesh.loops), 3)

    # Transform for skinning
    if armature and blender_object:
        apply_matrix = armature.matrix_world.inverted_safe() @ blender_object.matrix_world
        tangent_transform = apply_matrix.to_quaternion().to_matrix()
        tangents = __apply_mat_to_all(tangent_transform, tangents)
        __normalize_vecs(tangents)

    return tangents


def __get_bitangent_signs(blender_mesh, armature, blender_object, export_settings):
    signs = np.empty(len(blender_mesh.loops), dtype=np.float32)
    blender_mesh.loops.foreach_get('bitangent_sign', signs)

    # Transform for skinning
    if armature and blender_object:
        # Bitangent signs should flip when handedness changes
        # TODO: confirm
        apply_matrix = armature.matrix_world.inverted_safe() @ blender_object.matrix_world
        tangent_transform = apply_matrix.to_quaternion().to_matrix()
        flipped = tangent_transform.determinant() < 0
        if flipped:
            signs *= -1

    # No change for Zup -> Yup

    return signs


def __get_uvs(blender_mesh, uv_i):
    layer = blender_mesh.uv_layers[uv_i]
    uvs = np.empty(len(blender_mesh.loops) * 2, dtype=np.float32)
    layer.data.foreach_get('uv', uvs)
    uvs = uvs.reshape(len(blender_mesh.loops), 2)

    # Blender UV space -> glTF UV space
    # u,v -> u,1-v
    uvs[:, 1] *= -1
    uvs[:, 1] += 1

    return uvs


def __get_colors(blender_mesh, color_i, blender_color_i):
    if blender_mesh.color_attributes[blender_color_i].domain == "POINT":
        colors = np.empty(len(blender_mesh.vertices) * 4, dtype=np.float32) #POINT
    else:
        colors = np.empty(len(blender_mesh.loops) * 4, dtype=np.float32) #CORNER
    blender_mesh.color_attributes[blender_color_i].data.foreach_get('color', colors)
    colors = colors.reshape(-1, 4)
    # colors are already linear, no need to switch color space
    return colors, blender_mesh.color_attributes[blender_color_i].data_type, blender_mesh.color_attributes[blender_color_i].domain


def __apply_mat_to_all(matrix, vectors):
    """Given matrix m and vectors [v1,v2,...], computes [m@v1,m@v2,...]"""
    # Linear part
    m = matrix.to_3x3() if len(matrix) == 4 else matrix
    res = np.matmul(vectors, np.array(m.transposed()))
    # Translation part
    if len(matrix) == 4:
        res += np.array(matrix.translation)
    return res


def __normalize_vecs(vectors):
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    np.divide(vectors, norms, out=vectors, where=norms != 0)



if __name__ == '__main__':
    main()