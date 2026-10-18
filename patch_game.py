# -*- coding: utf-8 -*-
"""
Blood Rage: Digital Edition 简体中文汉化补丁生成脚本
====================================================

用法（游戏必须是 Steam 原版或已还原原版的状态）:
    pip install UnityPy TypeTreeGeneratorAPI
    python patch_game.py <游戏根目录>            # 例如  D:\\Steam\\steamapps\\common\\BloodRageDigitalEdition

流程:
  1. 首次运行时把 4 个原始资源文件备份到 <游戏根目录>/_localization_backup/
  2. sharedassets2.assets : 5 个内嵌 Font 对象的字体数据替换为 fonts/ 下的思源黑体
  3. sharedassets0/1.assets : 10 个 TMP 字体资产改为动态模式 (按需栅格化中文字形),
     清空静态字符表, 放大图集纹理并置为可读写
  4. resources.assets : 95 个 XLIFF TextAsset 替换为 xliff_cn/ 下的中文版,
     并给 TMP Settings 设置全局回退字体

Steam 更新或"验证文件完整性"会还原游戏文件, 重新运行本脚本即可。
"""
import copy
import glob
import os
import shutil
import sys

import UnityPy
from UnityPy.helpers import TypeTreeGenerator

UNITY_VERSION = "2019.4.26f1"

HERE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------- 字体配置 --
# sharedassets2.assets 中内嵌 Font 对象的 pathID -> Noto Sans SC 字重
NOTO_STYLES = {1151: "Bold", 1152: "Bold", 1153: "Bold", 1154: "Regular", 1155: "Medium"}
NOTO_PID = {"Regular": 1154, "Medium": 1155, "Bold": 1153}

# TMP 字体资产: pathID -> (图集宽, 图集高, 采样点尺寸, 图集边距, 源字体pathID, 字重)
# 正文字体 4096^2 / 48pt, 装饰字体 2048^2 / 64pt (BlackSirkka 96pt)
FONT_CONFIGS = {
    "sharedassets0.assets": {
        1845: (2048, 2048, 64, 5, 1154, "Regular"),   # AbrilFatface
        1846: (2048, 2048, 64, 5, 1154, "Regular"),   # arial
        1849: (2048, 2048, 64, 5, 1154, "Regular"),   # GOTHIC
        1850: (4096, 4096, 48, 5, 1154, "Regular"),   # Rosetta ArekLatin-Regular
        1851: (2048, 2048, 64, 5, 1153, "Bold"),      # impact
        1910: (4096, 4096, 48, 5, 1154, "Regular"),   # LiberationSans (TMP 默认字体)
    },
    "sharedassets1.assets": {
        23992: (2048, 2048, 96, 5, 1153, "Bold"),     # BlackSirkka
        23993: (2048, 2048, 64, 5, 1153, "Bold"),     # GOTHICB
        23994: (2048, 2048, 64, 5, 1155, "Medium"),   # GOTHICI
        23995: (4096, 4096, 48, 5, 1153, "Bold"),     # Rosetta ArekLatin-Bold
    },
}

# TMP Settings 全局回退字体: resources.assets externals[1] = sharedassets0.assets,
# PPtr.m_FileID 从 1 开始计数 (0 = 本文件), 所以 sharedassets0 -> m_FileID = 2
TMP_FALLBACK = {"m_FileID": 2, "m_PathID": 1850}  # Rosetta ArekLatin-Regular SDF


def face_info(point_size, style):
    """Noto Sans SC 字体度量 (upem=1000, hhea asc=1160 desc=-288)。"""
    P = point_size
    return {
        "m_FaceIndex": 0, "m_FamilyName": "Noto Sans SC", "m_StyleName": style,
        "m_PointSize": int(P), "m_Scale": 1.0,
        "m_LineHeight": round(1.448 * P, 6), "m_AscentLine": round(1.16 * P, 6),
        "m_CapLine": round(0.733 * P, 6), "m_MeanLine": round(0.543 * P, 6),
        "m_Baseline": 0.0, "m_DescentLine": round(-0.288 * P, 6),
        "m_SuperscriptOffset": round(1.16 * P, 6), "m_SuperscriptSize": 0.5,
        "m_SubscriptOffset": round(-0.1 * P, 6), "m_SubscriptSize": 0.5,
        "m_UnderlineOffset": round(-0.125 * P, 6), "m_UnderlineThickness": round(0.05 * P, 6),
        "m_StrikethroughOffset": round(0.325 * P, 6), "m_StrikethroughThickness": round(0.05 * P, 6),
        "m_TabWidth": round(0.9 * P, 6),
    }


def load_env(data_dir, filename, gen):
    # 必须从游戏原位置加载, 否则 externals (globalgamemanagers 等) 解析失败,
    # MonoScript 无法解引用, MonoBehaviour typetree 读取会全部报错
    env = UnityPy.load(os.path.join(data_dir, filename))
    env.typetree_generator = gen
    return env


def patch_sharedassets2(data_dir):
    """步骤 2: 内嵌 Font 对象字体数据 -> Noto Sans SC。"""
    name = "sharedassets2.assets"
    noto_data = {
        style: open(os.path.join(HERE, "fonts", f"NotoSansSC-{style}.otf"), "rb").read()
        for style in set(NOTO_STYLES.values())
    }
    env = load_env(data_dir, name, None)
    patched = 0
    for obj in env.objects:
        if obj.type.name != "Font" or obj.path_id not in NOTO_STYLES:
            continue
        d = obj.read()
        d.m_FontData = noto_data[NOTO_STYLES[obj.path_id]]
        d.save()
        patched += 1
    assert patched == len(NOTO_STYLES), f"Font 对象只找到 {patched}/{len(NOTO_STYLES)}"
    save_to(os.path.join(data_dir, name), env)
    print(f"[OK] {name}: {patched} 个 Font 对象替换为 Noto Sans SC")


def save_to(path, env):
    # 注意: 必须先在内存中完成序列化再落盘。UnityPy 保存时会从源文件惰性读取数据,
    # 如果直接对加载中的源文件 open('wb') 会先截断它, 导致所有对象数据丢失
    data = env.file.save()
    with open(path, "wb") as f:
        f.write(data)


def patch_tmp_fonts(data_dir, filename, gen):
    """步骤 3: TMP 字体资产动态化 + 空白可读写大图集。"""
    env = load_env(data_dir, filename, gen)
    sf = env.file

    # 找到 (或新增) 指向 sharedassets2.assets 的 external, PPtr.m_FileID = 0-based 索引 + 1
    ext0 = next((i for i, e in enumerate(sf.externals) if e.path == "sharedassets2.assets"), None)
    if ext0 is None:
        new_ext = copy.deepcopy(sf.externals[0])
        new_ext.path = "sharedassets2.assets"
        sf.externals.append(new_ext)
        ext0 = len(sf.externals) - 1
    file_id = ext0 + 1

    cfg = FONT_CONFIGS[filename]
    atlas_map = {}
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if not isinstance(tree, dict) or "m_AtlasTextures" not in tree or obj.path_id not in cfg:
            continue
        W, H, P, pad, src_pid, style = cfg[obj.path_id]
        tree["m_AtlasPopulationMode"] = 1  # Dynamic
        tree["m_SourceFontFile"] = {"m_FileID": file_id, "m_PathID": src_pid}
        tree["m_SourceFontFileGUID"] = ""
        tree["m_CharacterTable"] = []
        tree["m_GlyphTable"] = []
        tree["m_UsedGlyphRects"] = []
        tree["m_FreeGlyphRects"] = [{"m_X": 0, "m_Y": 0, "m_Width": W, "m_Height": H}]
        tree["m_KerningTable"] = {"kerningPairs": []}
        tree["m_FontFeatureTable"] = {"m_GlyphPairAdjustmentRecords": []}
        tree["m_FaceInfo"] = face_info(P, style)
        tree["m_AtlasWidth"] = W
        tree["m_AtlasHeight"] = H
        tree["m_AtlasPadding"] = pad
        tree["m_IsMultiAtlasTexturesEnabled"] = 0
        tree["m_ClearDynamicDataOnBuild"] = 0
        obj.save_typetree(tree)
        atlas_map[tree["m_AtlasTextures"][0]["m_PathID"]] = (W, H)

    assert len(atlas_map) == len(cfg), f"TMP 字体只找到 {len(atlas_map)}/{len(cfg)}"
    for obj in env.objects:
        if obj.type.name == "Texture2D" and obj.path_id in atlas_map:
            W, H = atlas_map[obj.path_id]
            d = obj.read()
            d.m_Width = W
            d.m_Height = H
            d.m_CompleteImageSize = W * H
            d.m_IsReadable = 1  # 动态栅格化必须有 CPU 端像素访问, 否则原生层空指针崩溃
            d.image_data = b"\x00" * (W * H)
            d.m_StreamData.path = ""
            d.m_StreamData.offset = 0
            d.m_StreamData.size = 0
            d.save()

    save_to(os.path.join(data_dir, filename), env)
    print(f"[OK] {filename}: {len(cfg)} 个 TMP 字体资产动态化 (external fileID={file_id})")


def patch_resources(data_dir, gen):
    """步骤 4: XLIFF 汉化 + TMP Settings 回退字体。"""
    name = "resources.assets"
    env = load_env(data_dir, name, gen)

    new_content = {}
    for f in glob.glob(os.path.join(HERE, "xliff_cn", "*.xml")):
        new_content[os.path.basename(f)[:-4]] = open(f, encoding="utf-8").read()

    n = 0
    for obj in env.objects:
        if obj.type.name == "TextAsset":
            d = obj.read()
            if d.m_Name in new_content:
                d.m_Script = new_content[d.m_Name]
                d.save()
                n += 1
    assert n == len(new_content), f"XLIFF 只替换了 {n}/{len(new_content)}"

    exts = [e.path for e in env.file.externals]
    assert exts[1] == "sharedassets0.assets", f"externals 结构异常: {exts}"
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if isinstance(tree, dict) and tree.get("m_Name") == "TMP Settings":
            tree["m_fallbackFontAssets"] = [TMP_FALLBACK]
            obj.save_typetree(tree)
            break
    else:
        raise RuntimeError("未找到 TMP Settings")

    save_to(os.path.join(data_dir, name), env)
    print(f"[OK] {name}: {n} 个 XLIFF 替换为中文, TMP Settings 回退字体已设置")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    game_root = os.path.abspath(sys.argv[1])
    data_dir = os.path.join(game_root, "BloodRage_Data")
    assert os.path.isfile(os.path.join(data_dir, "resources.assets")), "游戏目录不对"

    # 首次运行备份原版
    backup_dir = os.path.join(game_root, "_localization_backup")
    if not os.path.isdir(backup_dir):
        os.makedirs(backup_dir)
        for name in ["resources.assets", "sharedassets0.assets", "sharedassets1.assets", "sharedassets2.assets"]:
            shutil.copy2(os.path.join(data_dir, name), os.path.join(backup_dir, name))
        print(f"[OK] 原版文件已备份到 {backup_dir}")

    gen = TypeTreeGenerator.TypeTreeGenerator(UNITY_VERSION)
    gen.load_local_game(game_root)

    patch_sharedassets2(data_dir)
    patch_tmp_fonts(data_dir, "sharedassets0.assets", gen)
    patch_tmp_fonts(data_dir, "sharedassets1.assets", gen)
    patch_resources(data_dir, gen)
    print("\n完成! 启动游戏即可看到中文。")


if __name__ == "__main__":
    main()
