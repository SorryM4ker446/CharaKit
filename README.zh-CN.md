# CharaKit

[English](README.md) | **简体中文**

**CharaKit** 是面向视觉小说角色美术的模块化 Codex 插件。**CharaKit Expressions** 生成完整表情差分，**CharaKit Outfits** 为指定的一件现有衣物改色。

两个模块各有独立 Skill，共用本地 Python 文件助手。Codex 使用当前环境提供的 OpenAI 图像编辑工具生成图片；本地助手负责保留版本、检查文件、制作整图与局部对比预览，以及导出选定资源。

开发版本：**0.1.15**。

每次生图／修订结束默认交付[成品 PNG、最终版 preview 与完整报告](plugins/charakit/references/delivery-report.md)。共用 `report` 命令可汇总表情、mouth 和 outfits，包含请求、逐轮评分、专项检查、失败原因和过程证据，只复制门禁通过的最终 PNG，保留原字节。全部失败时只输出报告，不生成成品图或 preview；不新增生图、不重新评分、不自动验收。需要 0.1.15 或更新助手。

可启用[评审驱动的限次修订](plugins/charakit/references/refinement.md)：每个表情／mouth 状态或衣物／颜色方案最多三轮（首版＋两次修订）。未通过时根据具体评审问题，在上一版完整图上定向改进，同时用原图约束身份、设计和材质；通过即停止，只交付最终通过版本，过程图保留可查看。三轮仍不合格就停止并报告原因，不把最高分失败图当作合格资产。实际生图和视觉评审仍由 Codex 与宿主图像工具执行，本地助手记录预算与执行门禁。宿主原生生图预览可能仍自动出现。

新版评分使用 rubric 1.1：总分至少 **80/100**、每项至少 **4/5**，所有专项通过且无严重缺陷或不确定问题。细微笔触差异可视为 4 分的小瑕疵，不要求像素相等；错表情／mouth／部件、面部改设计、明显越界或缺失仍拦截。旧版 rubric 1.0 审核保留 85 分门槛和原记录。需使用 0.1.14 或更新助手。

新审核必须填写当前模块／状态的专项检查，不能只给整图总分：表情、明确嘴部状态、服饰改色分别检查；衣物再按实际部件的材质、结构与交界细化。任一项失败或无法确认，即使总分 100 也阻止交付。需使用 0.1.13 或更高助手；旧审核只读兼容，不补写虚构专项结论。

分辨率暂时不参与视觉评分和预览交付拦截。真实尺寸不匹配仍记录，交付时作为提示返回；其他质量、保真与技术门槛继续执行。正式接受与 ZIP 导出仍要求源画布尺寸。此例外需使用 0.1.12 或更新助手。

后续开发与交付遵循统一的[内部质量审核基准](plugins/charakit/references/quality-review.md)。新候选依据实际对照记录四项评分，并通过总分、各项下限、专项、技术与适用保真门禁才进入交付。评分来自模型查看图像后的判断，不是客观自动相似度模型；内部通过仍不代替用户认可。旧记录保留，旧项目继续生成前启用质量策略。

所有已实现模块遵循共同的[编辑边界规则](plugins/charakit/references/edit-boundaries.md)：明确目标、允许变化的属性、目标内部不变量，以及边界和其余区域的保护要求。未请求的部件与属性默认受保护。提示词和检查由请求、部件领域及实际原图推导，历史测试角色不成为通用模板。Outfits 提供[服饰专项规则](plugins/charakit/skills/charakit-outfits/references/garment-domains.md)；Expressions 分别限定表情动作和嘴部状态，不因此扩大其他部件的编辑范围。

结果质量优先于提示词长度。原有属性从原图继承，包括每只眼睛的色彩分布和设计，不擅自指定猜测的瞳色。表情提示词完整说明区分情绪所需的协调动作及可见效果，生成后分别检查目标表现、细节保护与文件技术状态。

版本更新说明发布在 GitHub Releases 中。

## 模块

| 模块 | Skill 标识 | 状态 |
| --- | --- | --- |
| CharaKit Expressions | `charakit-expressions` | 已实现：完整表情差分 |
| CharaKit Outfits | `charakit-outfits` | 已实现：单件衣物改色；整套换装仍在规划中 |
| CharaKit Poses | `charakit-poses` | 计划中：静态动作与姿势编辑 |

插件安装标识为 `charakit`；表情与静态嘴部状态使用 `$charakit-expressions`，指定衣物改色使用 `$charakit-outfits`。姿势模块仍在规划中，尚不能调用。详见[模块定义](plugins/charakit/modules.json)与[模块规划（英文）](plugins/charakit/ROADMAP.md)。

## 当前表情功能

- 支持十二种固定表情：平静、开心、难过、生气、惊讶、闭眼、害羞、困惑、无奈／苦笑、担忧／不安、得意／自信和哭泣。
- 保留整个面部的细节、原画风、角色设计、姿势和整体和谐性。
- 单独重做一个表情，保留其他候选和历史版本。
- 同一表情的静态张嘴／闭嘴版本独立保存、选择和导出。
- 在浅色、深色或棋盘背景上对比完整立绘和面部放大区域。
- 检查原画布尺寸、实际 PNG 格式、透明背景和文件指纹。
- 将用户已认可、技术检查通过的 PNG 与清单一起导出为 ZIP。

新增表情的固定标识如下，可通过助手的 `presets` 命令查看全部预设与生成方向：

| 表情 | 标识 | 表现重点 |
| --- | --- | --- |
| 害羞 | `shy` | 适度脸红与害羞的目光 |
| 困惑 | `confused` | 疑问与不理解，区别于惊讶 |
| 无奈／苦笑 | `wry_smile` | 克制的尴尬或无奈笑容，区别于开心 |
| 担忧／不安 | `worried` | 关切与紧张，区别于难过 |
| 得意／自信 | `confident` | 符合角色气质的自信目光与笑意 |
| 哭泣 | `crying` | 可见眼泪，保留眼部与面部细节 |

十二种预设与静态张嘴／闭嘴状态已具备文件工作流支持和生成指引，实际生图效果仍需逐张检查。每个“表情＋嘴部状态”独立保留版本和选择，可同时导出同一表情的两种状态。视线状态仍在规划中。详见[嘴部状态说明](plugins/charakit/skills/charakit-expressions/references/mouth-states.md)。

未指定嘴部状态时使用 `default`，不把旧图片自动判定成闭嘴。旧项目可直接读取；首次加入明确张嘴／闭嘴状态时，会备份旧记录并升级到 schema 1.1，源图、历史候选和选择保留。升级后的项目需使用 0.1.5 或更高兼容版本。

每个表情差分都是一张完整图片。插件不提取五官部件、不把生成的脸拼回原图，也不包含数据库、外部图像 API、ComfyUI 接入、MCP 服务或独立应用。

## 指定衣物改色

```text
使用 $charakit-outfits，只把这张立绘的外套面料改成深蓝色。
保留饰边、纽扣、材质、衣褶、明暗，以及领带、裙子、头发、
整个面部、表情、嘴部状态和姿势。生成两张候选，preview 中对比两张，
同时放大面部与外套区域。
```

本阶段仅支持一件现有衣物的颜色变化，整套换装、配饰增减、穿脱状态及自动组合管理仍在规划中。实际生图的改色范围和细节保留需要人工检查，工作流测试通过不等于美术验收。

服饰使用独立项目，例如 `art-output/my-character/outfits/`，保留自己的不可变源图。助手记录方案标识、目标衣物与颜色；每个“目标衣物＋颜色”方案独立保留版本和选择。单张修订沿用原目标与颜色，改变定义时另建方案标识。

服饰项目与导出清单使用 schema 1.2。现有表情项目仍用 1.0／1.1，入口、标识和导出文件名保留。完整插件包含共用的 `lib/studio_core.py`，请与两个 Skill 一起保留。详见[服饰 Skill](plugins/charakit/skills/charakit-outfits/SKILL.md)。

生成前，`prepare` 保存允许改色的边界、保护区域描述和原图局部参考。默认只提交一张完整原图，按部件领域组织完整提示词，说明允许改色、内部不变量、排除项、其余内容保留及输出要求。结果质量优先于提示词长度，必要细节同时保留在提交指令与检查说明中；仅在目标识别含糊或用户请求参考图对照、且工具支持时提交局部参考。最终美术修改仍全部由宿主图像工具完成；局部图不是蒙版、像素锁定或最终资源。

对比整图、整个面部、目标衣物，以及武器、头发轮廓、手部和邻近装备等相关非目标细节。可重复使用 `preview --detail-box`，以不同输出路径放大这些区域。非目标区域重绘仍是已知限制；提示词的规范与完整性不能替代工具的像素保护能力。

查看结果后，`fidelity` 分别记录“目标改色”和“保护区域保留”的人工观察：通过、失败或不确定，并说明观察依据。它不会自动认可候选。关联编辑说明的候选需要两项观察通过，同时满足技术检查与真实用户认可，才能选择／导出。旧记录不改写，也不推断历史检查；新门槛需使用 0.1.7 或更新助手，旧助手不会执行这些门槛。

```shell
python plugins/charakit/skills/charakit-outfits/scripts/studio.py init --project art-output/my-character/outfits --source character.png --character my-character
python plugins/charakit/skills/charakit-outfits/scripts/studio.py prepare --project art-output/my-character/outfits --outfit coat_navy --target "外套面料" --color "深蓝色" --boundary "只改主体布料，排除里衬、饰边与纽扣" --protect "整个面部、表情、头发与姿势" --protect "其他衣物和配饰" --target-box 80 250 280 500
python plugins/charakit/skills/charakit-outfits/scripts/studio.py add --project art-output/my-character/outfits --outfit coat_navy --target "外套面料" --color "深蓝色" --image generated-coat-navy.png --prompt-file prompt.txt --brief-file art-output/my-character/outfits/briefs/coat_navy_v001.json
python plugins/charakit/skills/charakit-outfits/scripts/studio.py preview --project art-output/my-character/outfits --outfit coat_navy --output art-output/my-character/outfits/preview/coat-navy-v001.png --face-box 100 100 200 200 --detail-box 80 250 280 500
python plugins/charakit/skills/charakit-outfits/scripts/studio.py fidelity --project art-output/my-character/outfits --asset coat_navy_v001 --target-check passed --protection-check uncertain --note "目标颜色可见；面部与附近饰边尚需检查，保护区域暂不确定"
```

请替换为实际路径与预览区域坐标。反馈、选择与导出沿用表情助手的同名命令。完整 PNG 导出到 `sprites/<character>/outfits/<outfit-id>.png`，保持候选字节不变；技术失败候选仍不能正式导出。

上面的保真命令只演示“不确定”结果，不能照抄为实际验收。依据真实对比记录观察；修订沿用编辑说明，但不继承上一张的检查结论。边界需要进一步明确时可准备新版说明。

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

例如：「只生成害羞、困惑和哭泣三个版本」，随后要求「哭泣版本的眼泪少一点」。单张重做会保留其他表情的版本和选择。

静态说话状态仍使用同一个 Skill，例如：

```text
使用 $charakit-expressions 生成开心和担忧的表情，
每种分别生成闭嘴和自然张嘴说话的状态，每个状态两张，preview 中对比两张。
```

这里交付完整的静态立绘，不包含口型同步或动画帧。

**插件会按你使用的语言回复。** 进度更新、表情名称、生成提示词、检查说明、限制说明和交付说明都会跟随当前请求的语言或你明确指定的语言。CLI 参数、JSON 字段、文件名和状态／错误代码保持固定的英文标识。预览标签可通过 `--labels-file` 本地化。

默认输出目录为 `art-output/<character-key>/`。用户美术和实验记录被 Git 忽略，也不会进入发布包。

## 本地助手示例

在仓库根目录执行。请根据实际立绘替换图片路径和面部区域坐标：

```shell
python plugins/charakit/skills/charakit-expressions/scripts/studio.py presets
python plugins/charakit/skills/charakit-expressions/scripts/studio.py init --project art-output/my-character --source character.png --character my-character
python plugins/charakit/skills/charakit-expressions/scripts/studio.py add --project art-output/my-character --expression angry --image generated-angry.png --prompt-file prompt.txt
python plugins/charakit/skills/charakit-expressions/scripts/studio.py add --project art-output/my-character --expression happy --mouth-state closed --image happy-closed.png
python plugins/charakit/skills/charakit-expressions/scripts/studio.py add --project art-output/my-character --expression happy --mouth-state open --image happy-open.png
python plugins/charakit/skills/charakit-expressions/scripts/studio.py preview --project art-output/my-character --output art-output/my-character/preview/comparison-v001.png --face-box 100 100 200 200 --background light
python plugins/charakit/skills/charakit-expressions/scripts/studio.py preview --project art-output/my-character --output art-output/my-character/preview/comparison-dark-v001.png --face-box 100 100 200 200 --background dark
python plugins/charakit/skills/charakit-expressions/scripts/studio.py quality --project art-output/my-character --asset angry_v001 --assessment-file assessment.json --comparison art-output/my-character/preview/comparison-v001.png --comparison art-output/my-character/preview/comparison-dark-v001.png
python plugins/charakit/skills/charakit-expressions/scripts/studio.py deliver --project art-output/my-character --asset angry_v001
python plugins/charakit/skills/charakit-expressions/scripts/studio.py review --project art-output/my-character --asset angry_v001 --status accepted --note "用户选中了此版本。"
python plugins/charakit/skills/charakit-expressions/scripts/studio.py export --project art-output/my-character
```

`add` 检查失败时会返回退出码 2 和结构化报告，同时保留候选图片。按[质量评分结构](plugins/charakit/references/quality-review.md)根据实际查看的对照填写 `assessment.json`，不使用默认满分模板。技术检查通过不代表美术已获认可；正式导出需要技术、适用内部质量／保真门槛和用户认可同时满足。

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
  lib/studio_core.py                两个模块共用的文件工作流
  skills/charakit-expressions/
    SKILL.md                        工作流与语言规则
    references/                     表情与检查指南
    scripts/studio.py               本地文件助手
  skills/charakit-outfits/
    SKILL.md                        指定衣物改色工作流
    references/recolor-guide.md     改色与检查指南
    references/garment-domains.md    部件、材质与界面专项规则
    scripts/studio.py               服饰文件助手入口
  references/edit-boundaries.md     跨模块共用的编辑范围规则
  references/quality-review.md      后续开发基准与内部交付评分
tests/test_studio.py                 使用合成图片的工作流测试
tests/test_outfits.py                改色与打包工作流测试
tests/test_outfit_fidelity.py        原图局部参考与人工保真检查测试
tests/test_quality.py                内部审核、交付与旧项目兼容门槛测试
tools/build_plugin.py               插件 ZIP 构建脚本
```

## 开发

```shell
python -m pip install -r plugins/charakit/requirements.txt
python -m unittest discover -s tests -v
python tools/build_plugin.py --output dist/charakit-0.1.15.zip
```

测试使用合成图片，不需要第三方角色美术。CI 在 Linux 和 Windows 上运行。构建脚本不会覆盖已存在的 ZIP。

插件 ZIP 仅包含插件自身文件。请勿将用户图片、提示词、本地反馈、缓存、凭据和个人设备路径加入提交。

## 当前限制

表情或衣物编辑可能改变未请求的细节，或生成不同尺寸的画布。角色身份、面部细节、原画风和位置对齐需要人工检查，仅靠提示词无法保证一致性。

自动检查覆盖文件格式、画布尺寸、透明背景和文件完整性，不评价美术质量或游戏中的表情切换效果。正式导出需要通过技术检查，并在人工检查后确认采用。

更多说明见[插件指南](plugins/charakit/README.md)。
