# -*- coding: utf-8 -*-
"""接缝顶点聚类与属性复制。"""

import bmesh
from mathutils import kdtree


def _collect_seam_vertices(mesh):
    """返回被标记为缝合边（seam）的顶点索引集合。"""
    vertices = set()
    for edge in mesh.edges:
        if edge.use_seam:
            vertices.add(int(edge.vertices[0]))
            vertices.add(int(edge.vertices[1]))
    return vertices


def _collect_seam_entries(objects):
    """收集所有物体的缝合边顶点（含世界坐标），按物体顺序 + 顶点索引排序。"""
    entries = []
    for order, obj in enumerate(objects):
        mesh = obj.data
        matrix = obj.matrix_world
        for index in sorted(_collect_seam_vertices(mesh)):
            entries.append(
                {
                    "order": order,
                    "obj": obj,
                    "index": int(index),
                    "world": matrix @ mesh.vertices[index].co,
                }
            )
    return entries


def _cluster_entries(entries, threshold):
    """按世界坐标距离聚类（并查集），返回只含 >=2 个成员的簇：{根: [成员索引...]}。"""
    count = len(entries)
    if count < 2:
        return {}
    parent = list(range(count))

    def find(value):
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    tree = kdtree.KDTree(count)
    for index, entry in enumerate(entries):
        tree.insert(entry["world"], index)
    tree.balance()

    for index, entry in enumerate(entries):
        for _co, other, _distance in tree.find_range(entry["world"], threshold):
            other = int(other)
            if other == index:
                continue
            root_a, root_b = find(index), find(other)
            if root_a == root_b:
                continue
            if root_a < root_b:
                parent[root_b] = root_a
            else:
                parent[root_a] = root_b

    clusters = {}
    for index in range(count):
        root = find(index)
        clusters.setdefault(root, []).append(index)
    return {root: members for root, members in clusters.items() if len(members) > 1}


def _world_normal(obj, index):
    """顶点法线转换到世界空间（法线用逆转置矩阵）。"""
    normal = obj.data.vertices[index].normal
    matrix = obj.matrix_world.to_3x3().inverted().transposed()
    return (matrix @ normal).normalized()


def _local_normal(obj, world_normal):
    matrix = obj.matrix_world.to_3x3().inverted().transposed()
    return (matrix @ world_normal).normalized()


def _ensure_group_index(obj, name):
    """确保 obj 有指定名字的顶点组，返回组索引。"""
    group = obj.vertex_groups.get(name)
    if group is None:
        group = obj.vertex_groups.new(name=name)
    return group.index


def _apply_pairs_to_object(obj, pairs, entries, flags):
    """把同一目标物体上的统一对写入 mesh（位置 / 权重），返回统一数量。"""
    object_pairs = []
    for rep_entry_index, target_entry_index in pairs:
        rep_entry = entries[rep_entry_index]
        target_entry = entries[target_entry_index]
        if target_entry["obj"] != obj:
            continue
        object_pairs.append((rep_entry, target_entry))
    if not object_pairs:
        return 0

    matrix_inverted = obj.matrix_world.inverted()

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        try:
            deform_layer = bm.verts.layers.deform.active
        except Exception:
            deform_layer = None

        # 跨物体权重按组名映射：先算好「源组名 -> 目标组索引」
        group_name_to_index = {}
        unified = 0
        for rep_entry, target_entry in object_pairs:
            rep_obj = rep_entry["obj"]
            target_index = int(target_entry["index"])
            rep_index = int(rep_entry["index"])
            vertex = bm.verts[target_index]
            if flags["position"]:
                vertex.co = matrix_inverted @ rep_entry["world"].copy()
            if flags["weights"] and deform_layer is not None:
                weights = vertex[deform_layer]
                weights.clear()
                rep_vertex = rep_obj.data.vertices[rep_index]
                for group_element in rep_vertex.groups:
                    if float(group_element.weight) <= 0.0:
                        continue
                    source_name = rep_obj.vertex_groups[group_element.group].name
                    target_group_index = group_name_to_index.get(source_name)
                    if target_group_index is None:
                        target_group_index = _ensure_group_index(obj, source_name)
                        group_name_to_index[source_name] = target_group_index
                    weights[target_group_index] = float(group_element.weight)
            unified += 1
        bm.to_mesh(obj.data)
    finally:
        bm.free()
    obj.data.update()

    # 形态键：只复制同名 key 的位移（按世界空间换算到目标物体本地）
    if flags["shape_keys"]:
        target_keys = getattr(obj.data.shape_keys, "key_blocks", None)
        if target_keys is not None:
            target_key_names = {block.name: block for block in target_keys}
            matrix3_inverted = obj.matrix_world.to_3x3().inverted()
            for rep_entry, target_entry in object_pairs:
                rep_obj = rep_entry["obj"]
                rep_keys = getattr(rep_obj.data.shape_keys, "key_blocks", None)
                if rep_keys is None:
                    continue
                rep_index = int(rep_entry["index"])
                target_index = int(target_entry["index"])
                rep_base = rep_obj.data.vertices[rep_index].co
                target_base = obj.data.vertices[target_index].co
                rep_matrix3 = rep_obj.matrix_world.to_3x3()
                for rep_key in rep_keys:
                    target_key = target_key_names.get(rep_key.name)
                    if target_key is None:
                        continue
                    delta_world = rep_matrix3 @ (rep_key.data[rep_index].co - rep_base)
                    target_key.data[target_index].co = target_base + (
                        matrix3_inverted @ delta_world
                    )
            obj.data.update()

    # 法线：把统一顶点的所有 loop 法线设为代表顶点的世界法线（转回目标物体本地）
    if flags["normals"]:
        _apply_object_normals(obj, object_pairs)
    return unified


def _apply_object_normals(obj, object_pairs):
    target_to_rep_world_normal = {}
    for rep_entry, target_entry in object_pairs:
        rep_obj = rep_entry["obj"]
        rep_index = int(rep_entry["index"])
        target_to_rep_world_normal[int(target_entry["index"])] = _world_normal(
            rep_obj, rep_index
        )

    mesh = obj.data
    loop_count = len(mesh.loops)
    if loop_count == 0:
        return
    loop_vertex = [0] * loop_count
    mesh.loops.foreach_get("vertex_index", loop_vertex)
    loop_normals = [0.0] * (loop_count * 3)
    mesh.loops.foreach_get("normal", loop_normals)
    for loop_index, vertex_index in enumerate(loop_vertex):
        world_normal = target_to_rep_world_normal.get(int(vertex_index))
        if world_normal is None:
            continue
        normal = _local_normal(obj, world_normal)
        offset = loop_index * 3
        loop_normals[offset] = normal.x
        loop_normals[offset + 1] = normal.y
        loop_normals[offset + 2] = normal.z
    mesh.normals_split_custom_set(
        [tuple(loop_normals[i : i + 3]) for i in range(0, loop_count * 3, 3)]
    )
    mesh.update()


def unify_objects_seam_vertices(
    objects, threshold=0.0001, representative_object=None, **flags
):
    """对多个物体的缝合边顶点做属性统一（跨物体按世界位置匹配）。

    flags: position / weights / shape_keys / normals（默认全开）。
    representative_object: 作为数据来源的物体；提供时仅处理包含该物体的位置簇。
    返回统计 dict。
    """
    options = {
        "position": bool(flags.get("position", True)),
        "weights": bool(flags.get("weights", True)),
        "shape_keys": bool(flags.get("shape_keys", True)),
        "normals": bool(flags.get("normals", True)),
    }
    mesh_objects = [obj for obj in objects if obj is not None and obj.type == "MESH"]
    if not mesh_objects:
        return {"error": "no mesh objects", "objects": 0}
    representative_id = (
        id(representative_object) if representative_object is not None else None
    )
    if representative_id is not None and not any(
        id(obj) == representative_id for obj in mesh_objects
    ):
        return {
            "error": "representative object is not a mesh in objects",
            "objects": 0,
        }
    entries = _collect_seam_entries(mesh_objects)
    clusters = _cluster_entries(entries, float(threshold))
    if representative_id is not None:
        clusters = {
            root: members
            for root, members in clusters.items()
            if any(id(entries[index]["obj"]) == representative_id for index in members)
        }
    stats = {
        "objects": len(mesh_objects),
        "seam_vertex_count": len(entries),
        "cluster_count": len(clusters),
        "unified_count": 0,
        "cross_object_pairs": 0,
        "switches": _switch_text(options),
    }
    if not clusters:
        return stats

    pairs = []
    for members in clusters.values():
        members = sorted(
            members, key=lambda i: (entries[i]["order"], entries[i]["index"])
        )
        if representative_id is None:
            representative = members[0]
        else:
            source_members = [
                index
                for index in members
                if id(entries[index]["obj"]) == representative_id
            ]
            representative = min(
                source_members, key=lambda index: entries[index]["index"]
            )
        for member in members:
            if member == representative:
                continue
            pairs.append((representative, member))
            if entries[member]["obj"] != entries[representative]["obj"]:
                stats["cross_object_pairs"] += 1

    by_object = {}
    for rep_index, target_index in pairs:
        target_obj = entries[target_index]["obj"]
        by_object.setdefault(id(target_obj), (target_obj, []))[1].append(
            (rep_index, target_index)
        )

    for _key, (obj, object_pairs) in by_object.items():
        stats["unified_count"] += _apply_pairs_to_object(
            obj, object_pairs, entries, options
        )
    return stats


def unify_seam_vertices(obj, threshold=0.0001, **flags):
    """单物体入口（保持向后兼容）。"""
    return unify_objects_seam_vertices([obj], threshold=threshold, **flags)


def _switch_text(options):
    parts = []
    if options.get("position"):
        parts.append("位置")
    if options.get("weights"):
        parts.append("权重")
    if options.get("shape_keys"):
        parts.append("形态键")
    if options.get("normals"):
        parts.append("法线")
    return "+".join(parts) if parts else "无"

