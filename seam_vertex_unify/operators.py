# -*- coding: utf-8 -*-
"""Blender 操作器。"""

import bpy

from .core import _collect_seam_vertices, unify_objects_seam_vertices


def _selected_mesh_objects(context):
    objects = [obj for obj in context.selected_objects if obj and obj.type == "MESH"]
    if not objects:
        active = context.view_layer.objects.active
        if active is not None and active.type == "MESH":
            objects = [active]
    return objects


class SEAMUNIFY_OT_unify(bpy.types.Operator):
    """以活动物体为来源，统一选中物体接缝上的同位置顶点数据"""

    bl_idname = "seamunify.unify"
    bl_label = "统一缝合边顶点数据"
    bl_description = (
        "以活动物体为数据来源，把被标记为缝合边（seam）的世界空间同位置顶点数据"
        "复制到其他选中网格；UV 与顶点数量、索引保持不变"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.seam_unify_settings
        active = context.view_layer.objects.active
        objects = _selected_mesh_objects(context)
        if not objects:
            self.report({"ERROR"}, "请先选中至少一个网格物体")
            return {"CANCELLED"}
        if active is None or active.type != "MESH":
            self.report({"ERROR"}, "请把一个带缝合边的网格物体设为活动物体")
            return {"CANCELLED"}
        with_seam = [obj for obj in objects if _collect_seam_vertices(obj.data)]
        if not with_seam:
            self.report(
                {"WARNING"},
                "选中的物体都没有缝合边标记：请先编辑模式选中接缝边 → Ctrl+E → 标记缝合边",
            )
            return {"CANCELLED"}
        if active not in with_seam:
            self.report(
                {"ERROR"},
                "活动物体必须是已选中且带有缝合边的网格物体",
            )
            return {"CANCELLED"}
        result = unify_objects_seam_vertices(
            with_seam,
            threshold=settings.threshold,
            representative_object=active,
            position=settings.unify_position,
            weights=settings.unify_weights,
            shape_keys=settings.unify_shape_keys,
            normals=settings.unify_normals,
        )
        if result.get("error"):
            self.report({"ERROR"}, str(result["error"]))
            return {"CANCELLED"}
        self.report(
            {"INFO"},
            "接缝统一完成：代表 {source} / 物体 {objects} 个 / "
            "缝合边顶点 {seam} 个 / 位置簇 {clusters} 个 / "
            "统一 {unified} 个（其中跨物体 {cross} 对；{switches}；UV 未改动）".format(
                source=active.name,
                objects=result["objects"],
                seam=result["seam_vertex_count"],
                clusters=result["cluster_count"],
                unified=result["unified_count"],
                cross=result["cross_object_pairs"],
                switches=result["switches"],
            ),
        )
        return {"FINISHED"}


class SEAMUNIFY_OT_select_seam(bpy.types.Operator):
    """在编辑模式选中选中物体的所有缝合边"""

    bl_idname = "seamunify.select_seam_edges"
    bl_label = "选中所有缝合边"
    bl_description = "进入编辑模式并选中所有标记为缝合边的边"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objects = _selected_mesh_objects(context)
        if not objects:
            self.report({"ERROR"}, "请先选中网格物体")
            return {"CANCELLED"}
        active = context.view_layer.objects.active or objects[0]
        context.view_layer.objects.active = active
        previous_mode = active.mode
        if previous_mode != "EDIT":
            bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.object.mode_set(mode="OBJECT")
        for obj in objects:
            for edge in obj.data.edges:
                edge.select = bool(edge.use_seam)
        bpy.ops.object.mode_set(mode="EDIT")
        self.report({"INFO"}, "已选中 {} 个物体的所有缝合边".format(len(objects)))
        return {"FINISHED"}

