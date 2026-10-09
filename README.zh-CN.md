# CharaKit

[English](README.md) | **简体中文**

**CharaKit** 是面向视觉小说角色美术的模块化 Codex 插件。当前可用的 **CharaKit Expressions** 表情模块，可基于已有立绘生成完整的表情差分图。

当前表情模块由专注表情编辑的 Skill 和本地 Python 助手组成。Codex 使用当前环境提供的 OpenAI 图像编辑工具生成图片；本地助手负责保留版本、检查文件、制作整图与整个面部的对比预览，以及导出选定资源。

开发版本：**0.1.3**。

版本更新说明发布在 GitHub Releases 中。

## 模块

| 模块 | Skill 标识 | 状态 |
| --- | --- | --- |
| CharaKit Expressions | `charakit-expressions` | 已实现：完整表情差分 |
| CharaKit Outfits | `charakit-outfits` | 计划中：服饰编辑与整套换装 |
| CharaKit Poses | `charakit-poses` | 计划中：静态动作与姿势编辑 |

插件安装标识为 `charakit`；当前表情模块使用 `$charakit-expressions` 调用。服饰与姿势模块的名称已在[模块定义](plugins/charakit/modules.json)中预留，尚未打包相应 Skill，当前不能调用。开发顺序见[模块规划（英文）](plugins/charakit/ROADMAP.md)。

## 当前表情功能

- 生成平静、开心、难过、生气、惊讶和闭眼版本。
- 保留整个面部的细节、原画风、角色设计、姿势和整体和谐性。
- 单独重做一个表情，保留其他候选和历史版本。
- 在浅色、深色或棋盘背景上对比完整立绘和面部放大区域。
- 检查原画布尺寸、实际 PNG 格式、透明背景和文件指纹。
- 将用户已认可、技术检查通过的 PNG 与清单一起导出为 ZIP。

每个表情差分都是一张完整图片。插件不提取五官部件、不把生成的脸拼回原图，也不包含数据库、外部图像 API、ComfyUI 接入、MCP 服务或独立应用。

## 环境要求

- 支持插件／Skill，且具备图像编辑工具的 Codex 环境。
- 本地助手需要 Python 3.11+ 和 Pillow。

安装插件不会补充环境中缺失的图像工具，也不会切换底层模型。生成时使用宿主当前提供的工具；工具未返回型号时，将模型记录为 `unknown`。

## 安装

对于已克隆到本地的仓库，在仓库根目录运行：

```shell
codex plugin marketplace add .
codex plugin add charakit@charakit
```

发布到 GitHub 后，用户也可以通过仓库安装。请将 `YOUR_GITHUB_OWNER/CharaKit` 替换为实际仓库：

```shell
codex plugin marketplace add YOUR_GITHUB_OWNER/CharaKit --ref main
codex plugin add charakit@charakit
```

市场和插件都使用 `charakit` 标识。安装参数 `charakit@charakit` 表示来自 `charakit` 市场的 `charakit` 插件，本地源和 Git 仓库源使用相同标识。安装后刷新或重启 Codex，并打开新聊天。

在需要使用的 Python 环境中安装本地助手依赖：

```shell
python -m pip install -r plugins/charakit/requirements.txt
```

## 使用

在 Codex 中附上原始立绘，然后提出要求：

```text
使用 $charakit-expressions 为这张角色立绘生成开心、难过、生气、
惊讶和闭眼版本。保留整个面部的细节、原画风、原设计和整体和谐性。
```

可以指定表情强度、只修改某个版本，或选择需要导出的图片。

**插件会按你使用的语言回复。** 进度更新、表情名称、生成提示词、检查说明、限制说明和交付说明都会跟随当前请求的语言或你明确指定的语言。CLI 参数、JSON 字段、文件名和状态／错误代码保持固定的英文标识。预览标签可通过 `--labels-file` 本地化。

默认输出目录为 `art-output/<character-key>/`。用户美术和实验记录被 Git 忽略，也不会进入发布包。

## 本地助手示例

在仓库根目录执行。请根据实际立绘替换图片路径和面部区域坐标：

```shell
python plugins/charakit/skills/charakit-expressions/scripts/studio.py init --project art-output/my-character --source character.png --character my-character
python plugins/charakit/skills/charakit-expressions/scripts/studio.py add --project art-output/my-character --expression angry --image generated-angry.png --prompt-file prompt.txt
python plugins/charakit/skills/charakit-expressions/scripts/studio.py preview --project art-output/my-character --output art-output/my-character/preview/comparison-v001.png --face-box 100 100 200 200 --background light
python plugins/charakit/skills/charakit-expressions/scripts/studio.py review --project art-output/my-character --asset angry_v001 --status accepted --note "用户选中了此版本。"
python plugins/charakit/skills/charakit-expressions/scripts/studio.py export --project art-output/my-character
```

`add` 检查失败时会返回退出码 2 和结构化报告，同时保留候选图片。技术检查通过不代表美术已获认可；正式导出需要技术合格和用户认可同时满足。

如果用户认可某张图的效果，但它未通过技术检查，应单独保留用户反馈。技术检查通过前，助手不会将该候选的状态设为 `accepted`。

## 仓库结构

```text
README.md                           英文项目说明
README.zh-CN.md                     简体中文项目说明
.agents/plugins/marketplace.json     本地／Git 市场入口
.github/workflows/ci.yml             测试与插件包验证
plugins/charakit/
  plugin.json                       插件清单
  README.md                         独立插件使用说明
  modules.json                      已实现与计划中模块的定义
  ROADMAP.md                        模块范围与开发顺序
  requirements.txt                  助手依赖
  skills/charakit-expressions/
    SKILL.md                        工作流与语言规则
    references/                     表情与检查指南
    scripts/studio.py               本地文件助手
tests/test_studio.py                 使用合成图片的工作流测试
tools/build_plugin.py               插件 ZIP 构建脚本
```

## 开发

```shell
python -m pip install -r plugins/charakit/requirements.txt
python -m unittest discover -s tests -v
python tools/build_plugin.py --output dist/charakit-0.1.3.zip
```

测试使用合成图片，不需要第三方角色美术。CI 在 Linux 和 Windows 上运行。构建脚本不会覆盖已存在的 ZIP。

插件 ZIP 仅包含插件自身文件。请勿将用户图片、提示词、本地反馈、缓存、凭据和个人设备路径加入提交。

## 当前限制

表情编辑可能改变面部以外的细节，或生成不同尺寸的画布。角色身份、面部细节、原画风和位置对齐需要人工检查，仅靠提示词无法保证一致性。

自动检查覆盖文件格式、画布尺寸、透明背景和文件完整性，不评价美术质量或游戏中的表情切换效果。正式导出需要通过技术检查，并在人工检查后确认采用。

更多说明见[插件指南](plugins/charakit/README.md)。
