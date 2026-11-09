# -*- coding: utf-8 -*-
"""3D 视图侧栏面板。"""

import bpy

from .core import _collect_seam_vertices
from .operators import SEAMUNIFY_OT_unify, _selected_mesh_objects


class SEAMUNIFY_PT_panel(bpy.types.Panel):
    bl_label = "接缝顶点统一"
    bl_idname = "SEAMUNIFY_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "接缝统一"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.seam_unify_settings
        objects = _selected_mesh_objects(context)
        with_seam = [obj for obj in objects if _collect_seam_vertices(obj.data)]

        box = layout.box()
        box.label(
            text="选中网格物体：{} 个".format(len(objects)), icon="OBJECT_DATA"
        )
        box.label(
            text="有缝合边标记：{} 个".format(len(with_seam)), icon="EDGESEL"
        )
        if with_seam:
            total = sum(len(_collect_seam_vertices(obj.data)) for obj in with_seam)
            box.label(
                text="缝合边顶点共 {} 个（可跨物体）".format(total), icon="VERTEXSEL"
            )

        column = layout.column(align=True)
        column.prop(settings, "threshold")
        column.prop(settings, "unify_position")
        column.prop(settings, "unify_weights")
        column.prop(settings, "unify_shape_keys")
        column.prop(settings, "unify_normals")

        layout.separator()
        layout.operator(SEAMUNIFY_OT_unify.bl_idname, icon="AUTOMERGE_ON")
        layout.label(text="UV 与顶点数量、索引保持不变", icon="INFO")
        layout.label(text="支持多选物体：接缝点按世界位置匹配", icon="LINKED")

