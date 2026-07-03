# -*- coding: utf-8 -*-
"""
F4 Capabilities structure for item detail panel.
Categories derived from actual module_items.py data analysis.
"""
from flag_dict import ITC_TEMPLATES, ITC_TEMPLATE_LABELS

# ============================================================
# F4 itcf_ flags — categorized by function
# Derived from actual F4 tokens found in Native1175 module_items.py
# ============================================================

ITCF_CATEGORIES = [
    (u'\u643a\u5e26\u4f4d\u7f6e (Carry)', [
        # Shields
        ('itcf_carry_round_shield', u'\u5706\u76fe'),
        ('itcf_carry_kite_shield', u'\u9e22\u5f62\u76fe'),
        ('itcf_carry_board_shield', u'\u5927\u76fe'),
        # Swords on hip
        ('itcf_carry_sword_left_hip', u'\u5251\u5de6\u814b'),
        ('itcf_carry_katana', u'\u592a\u5200\u5de6\u814b'),
        ('itcf_carry_wakizashi', u'\u80c1\u5dee\u5de6\u814b'),
        ('itcf_carry_mace_left_hip', u'\u9524\u5de6\u814b'),
        # Swords on back
        ('itcf_carry_sword_back', u'\u5251\u80cc\u540e'),
        # Axes
        ('itcf_carry_axe_left_hip', u'\u65a7\u5de6\u814b'),
        ('itcf_carry_axe_back', u'\u65a7\u80cc\u540e'),
        # Daggers
        ('itcf_carry_dagger_front_left', u'\u5315\u9996\u5de6\u524d'),
        ('itcf_carry_dagger_front_right', u'\u5315\u9996\u53f3\u524d'),
        # Bows / Crossbows
        ('itcf_carry_bow_back', u'\u5f13\u80cc\u540e'),
        ('itcf_carry_bowcase_left', u'\u5f13\u888b\u5de6\u814b'),
        ('itcf_carry_crossbow_back', u'\u5f29\u80cc\u540e'),
        # Arrows / Bolts
        ('itcf_carry_quiver_back', u'\u7bad\u888b\u80cc\u540e'),
        ('itcf_carry_quiver_back_right', u'\u7bad\u888b\u53f3\u540e'),
        ('itcf_carry_quiver_right_vertical', u'\u7bad\u888b\u53f3\u5782\u76f4'),
        # Spear
        ('itcf_carry_spear', u'\u957f\u67aa'),
    ]),
    (u'\u5c04\u51fb (Shoot)', [
        ('itcf_shoot_bow', u'\u5c04\u5f13'),
        ('itcf_shoot_crossbow', u'\u5c04\u5f29'),
        ('itcf_shoot_pistol', u'\u5c04\u624b\u67aa'),
    ]),
    (u'\u6295\u63b7 (Throw)', [
        ('itcf_throw_stone', u'\u6295\u77f3'),
        ('itcf_throw_knife', u'\u6295\u5200'),
        ('itcf_throw_axe', u'\u6295\u65a7'),
        ('itcf_throw_javelin', u'\u6295\u6807\u67aa'),
    ]),
    (u'\u88c5\u586b & \u88c5\u9970 (Reload & Cosmetic)', [
        ('itcf_reload_pistol', u'\u624b\u67aa\u88c5\u586b'),
        ('itcf_show_holster_when_drawn', u'\u62d4\u5251\u65f6\u663e\u9732\u5200\u9798'),
    ]),
]
