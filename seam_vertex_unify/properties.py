# -*- coding: utf-8 -*-
"""插件参数。"""

import bpy


class SEAMUNIFY_PG_settings(bpy.types.PropertyGroup):
    threshold: bpy.props.FloatProperty(
        name="距离阈值",
        description="世界空间位置距离不超过该值的缝合边顶点视为同一点（可跨物体）",
        default=0.0001,
        min=0.0,
        precision=6,
    )
    unify_position: bpy.props.BoolProperty(name="统一位置", default=True)
    unify_weights: bpy.props.BoolProperty(
        name="统一顶点组权重（按组名跨物体映射）", default=True
    )
    unify_shape_keys: bpy.props.BoolProperty(
        name="统一形态键（仅同名 key）", default=True
    )
    unify_normals: bpy.props.BoolProperty(name="统一法线", default=True)

