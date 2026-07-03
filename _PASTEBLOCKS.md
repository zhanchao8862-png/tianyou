== 汉化接入 完整决策记录 ==

时间: 2026-06-26 凌晨 约 1:55-2:14

核心需求: 原 load_translations 只支持 UTF-8 读 CSV。模组中文文件（GBK编码）加载后乱码。

改动清单:
1. load_translations (行84-109): binary read → 编码探测链 utf-8-sig/utf-8/gbk/gb18030 → decode → split('\n')
2. __init__ 翻译段 (行3442-3471): 
   a. 新增 self.item_cn_pl / self.imod_cn / self.imodbit_cn 三个字典
   b. 加载 item_modifiers.csv: imod_cn["imod_xxx"]="中文的%s", imodbit_cn["imodbit_xxx"]="中文"
3. _build_item_detail_panel (行3089-3093): 新增 modifier_cn 标签 (StringVar + Label blue anchor w)
4. _populate_item_detail 名 (行3123): raw_name 后追加 [中文]
5. _populate_item_detail modifier section (行3175-3191): modifier_cn 展开逻辑 调用 _resolve_imodbits_cn
6. _resolve_imodbits_cn (行3209-3237): 从 module_items.py 顶部解析 imodbits_* 集合常量定义，再查 imodbit_cn 翻译

执行过程中的坑:
- T0: patch_cn.py 脚本 UnicodeDecodeError (ASCII容错)
- T1: P1-P3部分生效, P4-P6未生效 (raw string 中 \u 是文本 而文件已解码)
- T2: 手动 edit 重写 P4-P6 后 P2 被覆盖 (imod_cn 初始化丢失) → 重新 edit __init__
- T3: _build_item_detail_panel 缺少 modifier_cn 控件声明 → edit 补上
- T4: load_translations 仍为旧版 utf-8-sig  → edit 替换

最终所有 5 项检查点全部通过，EXE 构建正常。用户下次启动应可见中文。
