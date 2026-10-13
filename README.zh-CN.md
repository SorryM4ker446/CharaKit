# CharaKit

**用于编辑视觉小说角色立绘的 Codex 插件。** 支持表情差分、服装修改、配饰／道具编辑及静态对话姿势，将原图、候选版本、评审记录和最终选择保存在同一工作流程中。

[English](README.md) | **简体中文** · 开发版本 **0.1.34**

上传立绘，说明想改什么，查看结果，再选择采用的版本。CharaKit 使用 Codex 中可用的图像编辑工具生成图片，本地 Python 助手负责文件管理、对照预览、评审记录和导出。

## 功能

| 模块 | 支持的编辑 | 调用方式 |
| --- | --- | --- |
| Expressions | 十二种表情预设，以及静态张嘴／闭嘴差分 | `$charakit-expressions` |
| Outfits | 衣物改色、单件替换、整套换装、配饰／道具编辑 | `$charakit-outfits` |
| Poses | 自然站立、单手叉腰、抬手打招呼、摊手解释、手放胸前、双手身前交握、双手背后、双臂抱胸 | `$charakit-poses` |

Outfits 包含四种编辑类型：

| 类型 | 用途 | 示例 |
| --- | --- | --- |
| `recolor` | 修改衣物颜色，保留原款式 | 将裙子改成白色 |
| `replace` | 替换一件衣物 | 将长外套换成短夹克 |
| `outfit_replace` | 替换明确指定的整套服装 | 换成日系制服，同时更换鞋袜 |
| `prop_edit` | 添加、移除或替换指定配饰／道具 | 添加眼镜、移除武器 |

三个模块均支持限定用途的参考图、限轮重绘、人工评图和指定版本修订，使用独立项目；可以手动将导出 PNG 作为另一模块的新原图。Poses 支持八种静态对话动作；复杂姿势与持物互动仍在[规划中](plugins/charakit/ROADMAP.md)。真实姿势生成质量仍待验证。

## 安装

需要支持插件且具备可用图像编辑工具的 Codex 环境，以及供本地助手使用的 **Python 3.11+**、**Pillow** 和 **fonttools**。通过 `requirements.txt` 一并安装依赖。

克隆仓库并执行：

```shell
git clone https://github.com/SorryM4ker446/CharaKit.git
cd CharaKit
python -m pip install -r plugins/charakit/requirements.txt
codex plugin marketplace add .
codex plugin add charakit@charakit
```

已有本地仓库时，在仓库目录执行后面三条命令即可。确保 Codex 使用的 Python 环境已安装助手依赖，再开启新聊天加载 Skill。

也可以直接注册 Git 插件市场：

```shell
codex plugin marketplace add SorryM4ker446/CharaKit --ref main
codex plugin add charakit@charakit
```

采用这一方式时，通过安装目录中的 `requirements.txt` 安装助手依赖，并保留完整插件目录。`charakit@charakit` 表示来自 `charakit` 市场的 `charakit` 插件；市场配置详见 [OpenAI 官方插件打包说明](https://developers.openai.com/plugins/build/plugins)。

## 使用

在 Codex 聊天中附上原图，调用对应 Skill 并描述修改要求即可，无需自己执行助手命令。

### 表情差分

```text
使用 $charakit-expressions，生成这位角色开心和担忧的表情，
每种表情分别提供闭嘴和自然张嘴说话的版本。
保留人物面部设计、头发、衣物、姿势和原画风。
```

十二种预设包括平静、开心、难过、生气、惊讶、闭眼、害羞、困惑、无奈／苦笑、担忧／不安、得意／自信和哭泣。张嘴／闭嘴各是一张静态图片；未指定嘴部状态不等于默认闭嘴。

### 服装修改

```text
使用 $charakit-outfits，将这位角色换成日系制服：
深蓝色西装外套、白衬衫、红色蝴蝶结、百褶裙、白色短袜和棕色乐福鞋。
保留人物面部、表情、头发、姿势和背景。
```

整套换装时，说明所有需要更换的部件，包括鞋袜；未列出的衣物和独立装备继续受保护。只想改一处时，可以直接要求指定衣物改色或单件替换。

### 配饰与道具

```text
使用 $charakit-outfits，给这位角色添加细框眼镜。
保留原表情、五官设计、头发、衣物和姿势。
```

移除或替换物件时，也需要明确指出目标。服装修改不会默认授权修改独立配饰或武器。

### 姿势

```text
使用 $charakit-poses，让角色自身的右手抬到肩部附近、掌心朝外打招呼。
保持左臂、当前表情、嘴形、服装设计、角色身份和原画风。
```

左右侧以角色自身为准。Poses 允许动作必要的肢体、关节、衣褶与遮挡变化，保留受保护的设计；姿势参考只指导动作与结构。

交握、背手、抱胸属于双臂动作。这三种动作及手放胸前都会记录左右臂位置、接触和前后遮挡要求，并在重绘和人工修订中保留。动作需要隐藏的手不会被强制露出，姿势也不会自动改变表情。

三个模块都可以附加参考图。请说明每张图用于参考什么，例如只参考夹克版型、眼镜款式或手掌朝向；参考图指导这些属性，受保护的人物细节仍以原图为准。

助手识别并保存任务语言，优先尊重明确的语言偏好，简短或含糊的续问沿用上下文。报告、HTML 评图页和 PNG 预览共享完整且经过审阅的语言包，并自动继承任务语言，支持内置中英文以外的语言。新说明直接使用任务语言撰写；历史观察单独生成显示译文，保留原文、事实和分数。自定义名称覆盖继续保留，PNG 检查字体覆盖并自动换行，详见[显示语言](plugins/charakit/references/localization.md)。产物默认保存在工作区的 `art-output/<character-key>/`。

## 评审与交付

1. **明确修改范围。** Codex 查看原图，记录目标、允许修改的边界、保护内容和参考图用途。
2. **生成并检查。** 每个请求结果默认最多尝试三次，包含首次生成。检查未通过时，根据问题在预算内重绘；全部通过则提前停止。用户明确指定更小上限时遵循该限制。
3. **查看全部候选。** 内部通过或次数耗尽后，本地 HTML 评图页展示本批次所有可读取的候选及原图。全图默认可见，面部／目标部位局部图按需展开，大图支持与原图同步缩放和拖动。助手推荐与用户选择分开。
4. **采用或提出修改。** 可直接回复“采用 A”“B 需要修改：……”或“都不采用”，也可从页面复制反馈。修订在选中版本上启动新的限轮批次，保留已有成果，并与最初原图二次复查仍受保护的区域。修订预览默认比较前后版本，局部范围按当前任务设置，也可切换原图对照。失败候选同样可以评价或要求修订。
5. **获取结果。** 实际人工反馈后才生成最终评审报告。被采用且通过全部交付检查的候选，输出完整 PNG、对照预览、报告，以及按需生成的 ZIP。已记录的面部／目标区域也会作为独立检查图出现在最终报告中。

内部评审包含五个维度：目标达成、人物一致性、非目标保护、结构与交界、画面完成度。通过要求为**总分至少 80/100**、**每项至少 4/5**，并通过所有适用的专项、保真与文件检查。高总分或用户偏好不能覆盖阻塞项。次数耗尽后，Codex 会先说明未通过的原因，再交给人工评图。

评分来自 Codex 基于图像证据的视觉判断；助手校验记录和文件，不独立给图片打分。人工反馈前的报告是内部草稿。局部图和失败候选用于检查，不属于最终成品。

## 文档

| 主题 | 指南 |
| --- | --- |
| 表情预设与强度 | [表情指南](plugins/charakit/skills/charakit-expressions/references/expression-guidelines.md) |
| 静态对话嘴部状态 | [嘴部状态](plugins/charakit/skills/charakit-expressions/references/mouth-states.md) |
| 服装编辑 | [衣物改色](plugins/charakit/skills/charakit-outfits/references/recolor-guide.md) · [单件替换](plugins/charakit/skills/charakit-outfits/references/replacement-guide.md) · [整套换装](plugins/charakit/skills/charakit-outfits/references/full-outfit-guide.md) |
| 配饰与道具 | [物件编辑](plugins/charakit/skills/charakit-outfits/references/prop-edit-guide.md) |
| 参考图与保护范围 | [参考图准则](plugins/charakit/references/edit-references.md) · [编辑边界](plugins/charakit/references/edit-boundaries.md) |
| 静态对话姿势 | [动作、边界与专项检查](plugins/charakit/skills/charakit-poses/references/pose-guide.md) |
| 评审、重绘与人工修订 | [候选评审](plugins/charakit/references/candidate-review.md) · [质量准则](plugins/charakit/references/quality-review.md) |
| 报告与导出 | [交付报告](plugins/charakit/references/delivery-report.md) |
| 助手入口与独立插件使用 | [插件指南](plugins/charakit/README.md) |

技术指南目前以英文维护。版本历史见 [GitHub Releases](https://github.com/SorryM4ker446/CharaKit/releases)，兼容说明与旧工作流细节保留在对应指南中。

## 开发

插件代码位于 `plugins/charakit/`，使用合成图片的工作流测试位于 `tests/`，ZIP 构建工具位于 `tools/`。插件市场入口为 `.agents/plugins/marketplace.json`。

在仓库根目录执行：

```shell
python -m pip install -r plugins/charakit/requirements.txt
python -m unittest discover -s tests -v
python tools/build_plugin.py --output dist/charakit.zip
```

CI 检查 Linux 和 Windows。构建工具拒绝覆盖已有 ZIP，只打包插件文件。用户立绘、提示词、反馈与本地测试记录保存在 Git 忽略的产物目录中。

## 限制

- 生图依赖宿主提供的图像编辑工具。CharaKit 不自带图像模型、外部图像 API 或 MCP 服务。
- 编辑可能导致人物设计、姿势、位置或无关细节偏移。评审有助于发现问题，但不能保证像素级保留或减少返修。
- 最终 PNG 必须匹配原画布，并通过适用的透明度与完整性检查。尺寸不符的图片可用于评图，但阻止正式接受与导出；助手不会缩放或修补候选。
- 产物是完整静态立绘。动画、口型同步、跨模块自动生成、大幅朝向变化、坐姿、倚靠和持物互动姿势均未实现。
