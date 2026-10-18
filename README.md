# Blood Rage: Digital Edition 简体中文汉化

Steam 版《血怒：数字版》(Blood Rage: Digital Edition, Unity 2019.4.26f1 Mono) 的非官方简体中文汉化工程。

## 仓库内容

| 目录/文件 | 说明 |
|---|---|
| `patch_game.py` | 一键补丁脚本：从 Steam 原版生成汉化后的资源文件 |
| `xliff_cn/` | 95 个中文 XLIFF 文件（最终写回游戏的版本，含全部 5 种语言的 target） |
| `xliff_orig/` | 95 个原始英文 XLIFF（提取存档，供对照） |
| `en_json/` | 按模块整理的英文原文（键 = XLIFF `<source>`，19 个模块共 1108 条） |
| `cn_json/` | 对应的中文译文（与 en_json 键一一对应） |
| `fonts/` | 思源黑体 Noto Sans SC（SIL OFL 授权，Regular/Medium/Bold 三个字重） |
| `GLOSSARY.md` | 桌游《血怒》术语表（氏族、首领、卡牌、神话名词的统一译名） |

## 使用方法

1. Steam 中"验证文件完整性"确保游戏为原版
2. 安装依赖：`pip install UnityPy TypeTreeGeneratorAPI`
3. 运行：`python patch_game.py "D:\Steam\steamapps\common\BloodRageDigitalEdition"`
4. 启动游戏（任意语言选项均为中文；游戏跟随 Steam 语言设置）

首次运行会自动把原版文件备份到 `<游戏根目录>/_localization_backup/`。
Steam 更新或验证完整性会还原文件，重新运行脚本即可。

## 汉化原理

### 文本
- 全部 UI 文本存放在 `resources.assets` 的 95 个 XLIFF 1.2 TextAsset 中（`<trans-unit>` 的 `<source>` 是键，`<target>` 是译文）
- 游戏按 Steam 语言选择加载对应文件，缺失时回退 en_US；因此把 5 种语言的 `<target>` 全部替换为中文，无论 Steam 语言设置如何都显示中文
- 富文本标签（`&lt;b&gt;`、`&lt;color=#{1}&gt;` 等）、占位符 `{N}`、换行 `\n` 均按原样保留

### 字体
游戏 TMP 字体资产只含拉丁字符集，需要支持中文：

1. **内嵌 Font 替换**：`sharedassets2.assets` 中 5 个 Unity `Font` 对象的 `m_FontData` 替换为思源黑体 OTF
2. **TMP 动态模式**：10 个 TMP_FontAsset 设置 `m_AtlasPopulationMode=1`（Dynamic）+ `m_SourceFontFile` 跨文件 PPtr 指向上一步的 Font，运行时由 FontEngine (FreeType) 按需把中文字形栅格化进图集
3. **图集重置**：原图集清空、放大（正文 4096²/48pt，装饰 2048²/64pt），并设置 `m_IsReadable=1`（动态栅格化需要 CPU 端像素访问）
4. **全局回退**：`resources.assets` 中 TMP Settings 的 `m_fallbackFontAssets` 指向 Rosetta ArekLatin-Regular SDF（动态化后即支持中文），兜住所有未显式指定字体的文本

### 踩过的坑（重要）

- **`PPtr.m_FileID` 从 1 开始计数**（0 = 本文件，N → externals[N-1]），写错会指向引擎内置资源里的随机对象，`FontEngine.LoadFontFace` 原生空指针崩溃
- **图集纹理必须 `m_IsReadable=1`**：不可读写的纹理在 `TryAddGlyphToTexture` 原生调用中拿到 NULL 像素指针直接崩溃（原版静态模式不写图集所以从未暴露）
- **必须从游戏原位置加载 .assets**：脱离游戏目录加载时 externals 无法解析，MonoScript 解引用失败，MonoBehaviour typetree 全部读不出来
- 修改后要同步图集纹理的 `m_Width/m_Height/m_CompleteImageSize/image_data/m_StreamData`

## 修改译文

1. 编辑 `cn_json/*.json`（或直接改 `xliff_cn/`）
2. 若改的是 json，需同步回 XLIFF：每个模块的 5 个语言文件 target 都要替换
3. 重新运行 `patch_game.py`（先 Steam 验证还原原版）

## 授权说明

- 译文为社区汉化，仅供学习交流，请支持正版
- 字体为 Google Noto Sans SC（思源黑体），SIL Open Font License 授权
