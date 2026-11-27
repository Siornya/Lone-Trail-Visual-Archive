# 「孤星」字体与游戏内用途

## 孤星专用

本节记录《孤星》活动画面中的字体线索。原有[字体笔记](research/孤星字体笔记.txt)列出了 Helvetica、ITC Avant Garde Gothic 和 Acumin Pro Semibold，未标注对应画面。

| 字体 | 在《孤星》中的使用处 |
| --- | --- |
| Helvetica | 具体位置待核实。档案馆复现时将它作为西文首选，详见下方的项目字体设置。 |
| ITC Avant Garde Gothic | 具体位置待核实。现有笔记没有将它对应到「LONE TRAIL」标题或其他字样。 |
| Acumin Pro Semibold | 具体位置待核实。笔记明确记录了 Semibold 字重，未注明使用它的栏目或标签。 |
| Novecento Wide（字形推测） | 活动大厅左下角「专案联络处」旁的计数 `186`。按相同字高对照 Novecento Wide、Helvetica 和 Bender，Novecento Wide 的 `6` 上端斜直、`8` 上下两圈圆滑，与实机最接近。字体名仍待确认，这次比对仅涵盖该处计数。[大厅实机截图](参考资料/游戏画面/大厅实机-孤星.png) |

### 档案馆的字体设置

首页、海报和 A4 调查图版共用以下设置。浏览器逐字选择字体：Helvetica 已经覆盖的英文和数字继续使用 Helvetica，缺字或设备上没有该字体时才依次回退。

| 文字用途 | 字体顺序 |
| --- | --- |
| 常规正文 | Helvetica → 中文回退 |
| 界面读数、时间和导航符号 | Helvetica → Bender → 中文回退 |
| 英文栏题和展示文字 | Helvetica → Novecento Wide → 中文回退 |
| 正式英文与署名 | Helvetica → Times New Roman → Georgia → 中文回退 |

中文回退顺序为思源宋体（Source Han Serif CN）→ 宋体-简（Songti SC）→ 中易宋体（SimSun）→ 系统衬线字体。思源宋体使用常规（400）和粗体（700）两个字重，优先读取本机字体，缺少时加载项目随附的 OTF。加载期间先显示回退字体，字体就绪后再替换。其余命名字体使用设备上已安装的版本。

## 明日方舟通用

下表整理国服界面的社区字体考据。能对应到具体元素的写明元素，仅有概括描述的保留原有范围。

| 字体 | 游戏内使用处 | 依据 |
| --- | --- | --- |
| 思源黑体（Source Han Sans） | 常规中文正文。干员「档案资料一」至「档案资料四」的长段落很可能沿用这一字族。考据称游戏内文常见 Light 字重，档案页的具体字体配置仍待核实。 | [游戏字体考据 · 内文字体][notes] |
| 方正特雅宋、方正准雅宋 | 中文标题和按钮文字。考据将常见样式识别为特雅宋，也记录了准雅宋的用例。 | [游戏字体考据 · 标题字体][notes] |
| 思源宋体（Source Han Serif CN） | 较正式的中文词句。现有资料未指明具体页面。 | [社区字体整理][fonts] |
| Novecento Wide | 现代感较强的英文展示文字，尤其是全大写英文标题。标题常见粗体。 | [游戏字体考据 · 标题字体][notes]、[社区字体整理][fonts] |
| Bender | 界面中突出的数字读数及其他 UI 字样。 | [社区字体整理][fonts] |
| Times New Roman | 较正式的英文单词或句子。 | [社区字体整理][fonts] |
| Georgia | 社区整理将其归入与 Times New Roman 相近的正式英文场景，两者分别对应的画面仍待核实。 | [社区字体整理][fonts] |

[notes]: https://holonic.ink/notes/%E6%98%8E%E6%97%A5%E6%96%B9%E8%88%9F%20%E5%AD%97%E4%BD%93
[fonts]: https://github.com/TimWangZi/The-font-of-Arknights#字体列表
