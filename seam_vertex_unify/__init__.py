# -*- coding: utf-8 -*-
"""接缝顶点统一（Seam Vertex Unify）。"""

bl_info = {
    "name": "接缝顶点统一 (Seam Vertex Unify)",
    "author": "dsh",
    "version": (1, 1, 1),
    "blender": (4, 2, 0),
    "location": "3D 视图 > 侧栏(N) > 接缝统一",
    "description": "统一缝合边(seam)上同位置顶点的位置/权重/形态键/法线，支持多物体，UV 保持不变",
    "doc_url": "https://github.com/v4806/SeamVertexUnify",
    "tracker_url": "https://github.com/v4806/SeamVertexUnify/issues",
    "support": "COMMUNITY",
    "category": "Mesh",
}

import bpy

from .operators import SEAMUNIFY_OT_select_seam, SEAMUNIFY_OT_unify
from .panels import SEAMUNIFY_PT_panel
from .properties import SEAMUNIFY_PG_settings


CLASSES = (
    SEAMUNIFY_PG_settings,
    SEAMUNIFY_OT_unify,
    SEAMUNIFY_OT_select_seam,
    SEAMUNIFY_PT_panel,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.seam_unify_settings = bpy.props.PointerProperty(
        type=SEAMUNIFY_PG_settings
    )


def unregister():
    del bpy.types.Scene.seam_unify_settings
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()

