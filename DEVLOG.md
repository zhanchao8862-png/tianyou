# 天佑战团源码编辑器 — 开发日志

> 开发者: 李天佑  |  技术栈: Python 2.7 + Tkinter + PyInstaller 3.6

---

## v2.3.0 (2026-06-21)

### 技能面板重构
- 42技能全部使用 Spinbox+Label 两列垂直布局
- `knows_xxx_N` 表达式 ↔ Spinbox 双向同步（parse_skill_values / build_skill_expr）
- 汉化名对齐，SKL_LABELS 覆盖全部42技能
- 三区域独立滚轮（root级 bind_all + 鼠标坐标定位）

### 升级树可视化
- 从 module_troops.py 尾部解析 150 条 upgrade()/upgrade2() 调用
- 合并内嵌字段，总计 161 条升级记录、59 分支、最长 5 级深度
- F14/F15 均用 SearchableCombobox 替代 ttk.Combobox
- 显示格式: `trp_xxx (中文名)`，下拉宽度 400px
- 保存时自动同步：_rebuild_footer_upgrades 清理旧调用 + 重新生成

### 脸型码解析
- `_parse_face_keys()` 从 header_troops.py 头部解析 86 个常量定义
- 支持链式引用（最多10次迭代）
- 显示时解析为 hex 值，保存直接写 hex

### 装备系统重构
- F7 装备槽位：分类双 Listbox 展示（安装物品 / 武器）
- 加载 module_items.py 时解析 itp_type_xxx 标志建立 item_category 映射
- 双击装备自动跳转到右侧装备面板对应位置
- "拥有物品"面板：取消数量限制，改用滚动条 Listbox
- 拖拽边框调整装备面板高度（6px Canvas，sb_v_double_arrow 光标）
- 悬停滚轮滚动
- 允许重复 ID 添加

### UI / 交互优化
- 详情面板按钮简化："应用修改到当前"（暂存）+ "还原"（重新解析）
- 左侧"保存"按钮自动应用详情修改后写入文件
- Ctrl+S 键盘绑定
- SearchableCombobox 自定义组件（Toplevel + Listbox）
- 下拉框 popup：-topmost、动态高度 ≤300px、<FocusOut> 自动关闭
- 背景色递归修复：_apply_bg_to_containers 跳过交互控件

### Bug 修复
- 解析器 split/depth bug：条目数从 ~1079 恢复 1746
- 装备 ID 统一 `itm_` 前缀存储，修复显示/刷新/保存三联 bug
- raw tab guard 防覆盖
- End/Home 键按下后列表消失（`<<ListboxSelect>>` 与默认滚动时序冲突）
- 字段索引修正（F13 删除后 F14/F15 → 13/14）

### 构建
- PyInstaller 3.6 + Python 2.7.18 → 单文件 EXE 约 8.0 MB

---

## v2.2.0 (2026-06-21)

- 兵种详情面板标签页：基础信息、属性(5项)、熟练度(7项)、Flags(20项分组UI)、技能(42槽下拉框2列布局)、阵营(OptionMenu)
- 文本级撤销/重做(Ctrl+Z/Y，按焦点区分)
- 插件系统(BasePlugin + 3 钩子)
- 自动加载上次 MOD (tianyou_config.json 持久化)
- line-based 解析器 + 缩进感知，绕过 `],]` 括号陷阱

---

## v2.1.0 (2026-06-21)

- 修复 raw 文本编辑与兵种级 undo 独立冲突
- _commit_raw_text() 自动提交机制
- 装备管理面板固定上方，修复切标签页跳动
- Ctrl+Z/Y 文本级撤销优先
- 撤销栈跨兵种不清空

---

## v2.0.0 (2026-06-21)

- 全新 line-based 解析器 + 缩进感知
- 撤销/重做快照系统(50步)
- 兵种增删复制、排序移动、搜索过滤
- 装备选择对话框
- MOD 自动检测与配置持久化
- 汉化联动
- 编译菜单
