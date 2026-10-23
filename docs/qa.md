# 可重复运行的 QA

本流程把第28—32轮实验中有效的检查方式保留为项目工具、测试和开发规范。文件行为与图像观感分开验收；自动化通过不生成画质评分，也不代表用户采用。

## 日常代码回归

```shell
python -m pip install -r plugins/charakit/requirements.txt
python tools/qa.py run --output .dev-checks/qa-001
```

这一个入口执行全部单元/工作流测试、构建插件、校验压缩包，并从解压后的包运行三个模块的CLI和评审页/检查快照生成。每个阶段保存日志，最终写入`summary.json`。任一阶段失败都返回非零状态，后续成功不会覆盖失败。输出目录必须是新目录，以免覆盖失败证据。

浏览器检查为开发依赖，安装插件不需要：

```shell
python -m pip install -r tools/requirements-qa.txt
python -m playwright install chromium
python tools/qa.py run --output .dev-checks/qa-002 --browser
```

CI 在 Linux 和 Windows 运行相同入口；Linux 额外运行 Chromium。检查真正由助手生成的HTML，不依赖手写的替代页面。浏览器测试使用合成图片、独立临时项目、本地随机端口，下载的反馈带有`QA FIXTURE`标记且不提交到项目。断言失败、页面异常或图片加载失败都会导致失败。未启用浏览器检查时，汇总明确标记`not_run`。

页面模板保存在 Python 中：开发检查页由 `tools/qa_view.py` 渲染，插件评审页由 `lib/candidate_review.py` 渲染，无需独立 `.html` 模板。插件构建会拒绝打包 `.html` / `.htm` 文件；运行时生成的预览页属于输出产物，继续用于离线查看与交互。

## 使用真实素材检查

```shell
python tools/qa.py inspect --project art-output/my-character/expressions --output art-output/my-character-qa
```

默认只纳入各项目当前选中的版本，并加入各自原图。可以重复传入`--project`组合表情、换装、姿势；项目不必使用同一原图。加`--all-candidates`会保留全部版本，包括未通过或尚未评审的候选，便于检查回归；这些图片不会因此成为交付结果。

工具读取项目、校验原图与候选指纹，然后复制原始图片字节到独立快照。输入项目内不能作为输出目录，已有输出不会覆盖。快照包含：

- `index.html`：可离线打开，支持420/720高度、相同像素倍率、原始像素滚动查看、浅/深/棋盘底、手动切换和600ms循环。按Esc或切到后台会停止循环。
- `manifest.json`：项目状态指纹、原图/候选指纹、选中版本、原始尺寸、透明边界和已有状态。
- `observations.template.json`：未评分的检查模板。另存并填写实际用途、查看高度、目标/保护/接触遮挡/边缘/裁切/切换观察；没有看过的项目保留`not_reviewed`。

图片可加载、尺寸一致、透明包围盒正常或数字配准通过，都不能自动判定画质通过。重点参见[共享QA方法](../plugins/charakit/references/qa-methods.md)。特别检查新手势是否被裁切，以及口型对之外的身体漂移。此检查页不是游戏引擎测试、正式匿名评审页或动画编辑器。它不对原图进行配准、贴回头部、重采样或局部修复。

## 独立检查实际导出包

```shell
python tools/qa.py audit-export --project art-output/my-character/expressions --archive art-output/my-character/expressions/exports/my-character-expressions-v001.zip
```

默认对照**当前选中版本**。要审计早先导出的指定版本，显式传入重复的`--asset`：

```shell
python tools/qa.py audit-export --project art-output/my-character/expressions --archive art-output/older-export.zip --asset happy_v001 --asset sad_v002
```

检查器独立读取ZIP中的PNG，核对版本、完整字节、实际尺寸、源画布语义、尺寸提醒、重复槽/路径、未列出的sprite以及当前文件/评审证据门槛。不同分辨率应通过并有提醒；篡改PNG、清单尺寸写错、漏提醒、导出错版本、证据失效应失败。它不会重新导出，也不会改写项目。历史包如已失去可核验的源文件/证据，当前审计会报告失败，而不会假装已验证其历史状态。

## 口型连续性验收

`inspect` 另外生成 `mouth-continuity.template.json`：按同项目、同表情的张嘴/闭嘴帧建立配对。平静张嘴缺少闭嘴成图时可与原图配对，但必须目视确认原图是平静闭嘴，填写 `source_baseline` 的 passed 与具体证据；原图内容不会被自动认定。其他缺配对保留空项，不能通过验收。

另存模板为 `mouth-observations.json`，填写 `basis`（`assistant_visual_observation` 或 `human_visual_observation`）。逐对填写所有 `views`：420/720 统一高度、420/720 相同像素倍率、原像素细节、浅深底及交替切换。逐项记录嘴形、眼眉、头部身份、腰线裙摆、鞋位、边缘构图的 `status` 与具体 `evidence`。状态采用 passed/failed/uncertain/not_reviewed；只有完整且全部 passed 的记录才通过。保存比较截图，在每对 `evidence` 中登记相对记录文件的 `path` 和文件 `sha256`。

```shell
python tools/qa.py audit-mouth --inspection art-output/my-character-qa --record art-output/mouth-observations.json --output art-output/mouth-acceptance-001
```

输出独立 `results.json` 与 `report.md`；失败或证据不完整返回非零。验收校验帧对、原图/候选指纹、比较文件指纹、全部口型覆盖、观察范围与逐项结论，不以尺寸相同或像素差阈值自动判断视觉质量。缺观察、空证据、漏掉问题帧、换图、变更截图、failed/uncertain 均不能通过。静态单张导出资格保持独立，连续性失败须写入 QA 报告，不能描述为已通过说话动画。游戏引擎验收始终另测。

ZIP 审计同时核对项目当前语言下的完整提醒文字及解码得到的实际/原始尺寸。空白、错误类型、反义内容、尺寸倒置或错误语言的提醒均失败；同尺寸不应携带分辨率差异提醒。更换项目语言后审计历史包，应使用该包原有语言的项目快照。

## 回归矩阵

| 层次 | 必须保留的检查 | 自动化与人工边界 |
|---|---|---|
| 版本与反馈 | 旧版回选、重开、版本保留、拒绝清除选择、修订基线、查看不改选择 | 合成工作流测试与真实HTML交互 |
| 导出 | 同/异/混合尺寸、实际像素尺寸、字节指纹、选中版本、旧包不覆盖、损坏/缺透明/失效证据仍拦截 | 单元测试和独立ZIP审计 |
| 报告 | 当前交付状态一致、历史反馈不改写、尺寸提醒覆盖桌面/窄屏、反馈下载内容与剪贴板失败降级 | 单元测试与Chromium；原生剪贴板成功分支尚未纳入 |
| 图像质量 | 完整脸、目标、保护部位、接触遮挡、边缘、新手势裁切、正常尺寸观感 | 需要实际看图并记录证据，不能用脚本结果替代 |
| 成对切换 | 同显示高度与同像素倍率分别看；420/720诊断；静态口型与动画稳定性分开 | 控件/加载自动验证，图像漂移人工判断；实际引擎另测 |
| 原始记录 | 提示与输入绑定、保留失败样本、raw/derived分开、真实反馈与QA夹具分开 | 指纹检查加记录审查；不能把精选认可率当总体生成通过率 |

改变生成提示、输入路由或视觉处理时，另做固定预算、固定原图与检查范围的真实图像对照；保留所有尝试和未确定结论，不重复给同一图片评分来制造提升。普通流程改动使用既有素材回归即可，不需要为测试额外生图。
