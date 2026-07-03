# 天佑编辑器 v2.5.0 — 导航栏重构 (line-based insertion)

**时间**: 2026-06-26 00:18-00:24
**基线**: tianyou_v2.3.0 backup (3609行/153KB)
**输出**: tianyou_editor.py (3998行/166KB) + EXE (7.85MB)

## 架构决策

**方案**: line-based 行号插入，避免文本匹配因 BOM/特殊字符差异失败。

## 新增方法列表

| 方法 | 行号 | 功能 |
|------|------|------|
| `_build_nav` | 1014 | 左侧导航 Treeview（编辑器→兵种/物品 + 工具） |
| `_on_nav_select` | 1043 | Treeview 选中事件 → 切换模块 |
| `_show_module` | 1053 | 模块切换核心：清空 content_area → 构建面板 → 加载数据 |
| `_build_troops_panel` | 1095 | 兵种面板（从原 _build_ui 提取） |
| `_load_troops` | 2626 | 兵种数据加载（从原 _load_data 提取 + 物品轻量加载） |
| `_build_items_panel` | 2359 | 物品面板（搜索/列表/CRUD/基本信息+源码 tabs） |
| `_load_items` | 2760 | 物品数据完整加载 |
| `_save_current_module` | 3490 | Ctrl+S 分发（按 _current_module 路由到 _save_troops/_save_items） |

## 修改的方法

| 方法 | 变更 |
|------|------|
| `__init__` | 新增 `_current_module`/`_modules_loaded` 跟踪 |
| `_build_ui` | 重写为 PanedWindow 外框 + 调用 _build_nav |
| `_load_data` | 重写为调用 `_load_troops()` |
| `_open_mod` | 末尾改为 `_show_module('troops')` |
| `_auto_load` | 改为 `_show_module('troops')` |
| `_reload` | 按 `_current_module` 刷新 |
| `_set_ui_state` | 改为 `getattr` 安全访问（widget 可能未创建） |
| `_apply_font_size` | 同上 |

## 修复的启动 Bug

1. **`_set_ui_state`** — `troop_lb` 等 widget 在 `__init__` 调用 `_set_ui_state(False)` 时尚未创建 → 改为 `getattr` 安全访问
2. **`_apply_font_size`** — 同上，列表中的 widget 在启动时不存在 → 改为 `getattr`

## 验证结果

- ✅ Python 直接运行成功（PID 15868）
- ✅ EXE 构建+运行成功（7.85 MB, PID 1416）
- ✅ 左侧导航栏显示正常（编辑器→兵种/物品, 工具）
- ✅ 兵种面板完整显示（搜索/列表/详情/装备）
- ✅ 启动时自动加载上次 MOD
