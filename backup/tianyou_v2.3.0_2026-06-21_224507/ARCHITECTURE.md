# 天佑战团源码编辑器 — 架构规范

## 基线版本

| 文件 | 版本 | 行数 | 大小 |
|------|------|------|------|
| `tianyou_editor.py` | v2.3.0 | ~3600 | ~155 KB |
| `tianyou_editor.exe` | v2.3.0 | — | ~8.0 MB |

基线快照存放于 `baseline/`，任何回退以该版本为准。

## 功能模块化规则

### 原则一：零耦合增量

新功能**不修改主文件** `tianyou_editor.py`。每个功能独立为一个文件，放在 `plugins/` 目录下。

### 原则二：插件接口

```
plugins/
├── __init__.py          # 插件注册表（自动发现）
├── _base.py             # BasePlugin 抽象基类
├── example_feature.py   # 新功能 → 新建文件，不碰 tianyou_editor.py
```

BasePlugin 提供统一钩子：
- `on_load(editor)` — 编辑器初始化后调用
- `on_troop_select(editor, troop)` — 兵种切换后调用
- `on_save(editor)` — 保存后调用
- `on_menu(editor, menubar)` — 注册菜单项

### 原则三：编辑器仅暴露只读 API

`tianyou_editor.py` 对外暴露稳定接口，插件通过这些接口与编辑器交互：
- `editor.troops_entries` — 兵种数据（只读引用）
- `editor.get_selected_troop()` → troop dict / None
- `editor.status(msg)` — 状态栏输出
- `editor.refresh_list()` — 刷新兵种列表
- 严禁插件直接修改 `editor._*` 私有成员

### 原则四：配置独立

插件自己的配置存 `plugins/<name>_config.json`，不与编辑器 `tianyou_config.json` 耦合。

### 开发流程

1. 确定新功能 → 在 `plugins/` 新建 `feature_name.py`
2. 继承 `BasePlugin`，实现所需钩子
3. 注册到 `plugins/__init__.py`
4. 编辑器启动时 `_load_plugins()` 自动加载
5. **主文件 `tianyou_editor.py` 不上代码，只上注册入口**

## 示例：添加一个"兵种统计"插件

```python
# plugins/troop_stats.py
from ._base import BasePlugin

class TroopStatsPlugin(BasePlugin):
    name = "兵种统计"
    version = "1.0.0"

    def on_menu(self, editor, menubar):
        menubar.add_command(label="兵种统计", command=lambda: self._show(editor))

    def _show(self, editor):
        total = len(editor.troops_entries)
        editor.status("共 {} 个兵种".format(total))
```

## 红线

- 禁止在主文件里直接写新功能逻辑
- 禁止插件之间循环依赖
- 禁止插件修改编辑器私有成员（`_` 前缀）
- 新功能上线须先在插件化架构下运行验证
