from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import html
import shutil

ROOT = Path(__file__).resolve().parents[1]
SLIDES = ROOT / "slides"
FIGURES = ROOT / "outputs" / "figures"
OUT = SLIDES / "midterm_report.pptx"
BUILD = SLIDES / ".pptx_build"

SLIDE_W = 12192000
SLIDE_H = 6858000


def esc(text):
    return html.escape(text, quote=True)


def emu(inch):
    return int(inch * 914400)


def text_box(shape_id, x, y, w, h, text, font_size=24, bold=False, color="1F2937"):
    runs = []
    for line in text.split("\n"):
        runs.append(
            f"""
            <a:p>
              <a:r>
                <a:rPr lang="zh-CN" sz="{font_size * 100}"{' b="1"' if bold else ''}>
                  <a:solidFill><a:srgbClr val="{color}"/></a:solidFill>
                  <a:latin typeface="Arial"/><a:ea typeface="Microsoft YaHei"/>
                </a:rPr>
                <a:t>{esc(line)}</a:t>
              </a:r>
            </a:p>
            """
        )
    return f"""
    <p:sp>
      <p:nvSpPr><p:cNvPr id="{shape_id}" name="TextBox {shape_id}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
      <p:txBody><a:bodyPr wrap="square"/><a:lstStyle/>{''.join(runs)}</p:txBody>
    </p:sp>
    """


def bullet_box(shape_id, x, y, w, h, bullets, font_size=22):
    paragraphs = []
    for bullet in bullets:
        paragraphs.append(
            f"""
            <a:p>
              <a:pPr marL="342900" indent="-171450"><a:buChar char="•"/></a:pPr>
              <a:r><a:rPr lang="zh-CN" sz="{font_size * 100}"><a:solidFill><a:srgbClr val="374151"/></a:solidFill><a:latin typeface="Arial"/><a:ea typeface="Microsoft YaHei"/></a:rPr><a:t>{esc(bullet)}</a:t></a:r>
            </a:p>
            """
        )
    return f"""
    <p:sp>
      <p:nvSpPr><p:cNvPr id="{shape_id}" name="Bullets {shape_id}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
      <p:txBody><a:bodyPr wrap="square"/><a:lstStyle/>{''.join(paragraphs)}</p:txBody>
    </p:sp>
    """


def image_box(shape_id, rel_id, x, y, w, h):
    return f"""
    <p:pic>
      <p:nvPicPr><p:cNvPr id="{shape_id}" name="Picture {shape_id}"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
      <p:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
      <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
    </p:pic>
    """


def slide_xml(title, bullets=None, image=None, note=None):
    parts = [text_box(2, emu(0.55), emu(0.32), emu(12.2), emu(0.75), title, 30, True, "111827")]
    sid = 3
    if bullets:
        parts.append(bullet_box(sid, emu(0.75), emu(1.25), emu(6.0 if image else 11.6), emu(4.8), bullets, 20))
        sid += 1
    if image:
        parts.append(image_box(sid, "rId2", emu(6.9), emu(1.45), emu(5.6), emu(3.4)))
        sid += 1
    if note:
        parts.append(text_box(sid, emu(0.8), emu(5.9), emu(11.4), emu(0.55), note, 14, False, "6B7280"))
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    {''.join(parts)}
  </p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def title_slide_xml():
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    {text_box(2, emu(0.9), emu(1.65), emu(11.6), emu(1.5), '基于多源数据的个人贷款\n违约风险检测', 38, True, '111827')}
    {text_box(3, emu(1.0), emu(3.6), emu(10.8), emu(1.2), 'AI Data Foundation 中期汇报\n日期：2026-05-21', 22, False, '374151')}
    {text_box(4, emu(1.0), emu(5.5), emu(10.8), emu(0.6), '小组成员：请替换为实际姓名', 18, False, '6B7280')}
  </p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


slides = [
    {"title": "TITLE"},
    {"title": "研究动机：为什么需要多源风险检测", "bullets": ["个人贷款违约会造成金融机构坏账损失，也影响借款人信用定价。", "传统信用评估主要依赖个人信用与贷款记录，容易忽略环境因素。", "核心观点：违约风险不仅由个人决定，也受到地区经济与宏观金融周期影响。"]},
    {"title": "研究问题", "bullets": ["如何整合个人信贷、地区经济与宏观金融数据？", "如何解决多源异构数据在时间和空间粒度上的对齐问题？", "多源变量是否能提供比单一贷款数据更可靠、更可解释的风险洞察？"]},
    {"title": "相关工作与项目定位", "bullets": ["传统信用评分关注 FICO、收入、负债率和信用历史。", "机器学习违约预测强调分类效果，但解释性和数据来源常被弱化。", "本项目重点展示真实数据获取、清洗、融合、统计分析和可解释洞察。"]},
    {"title": "数据集与当前状态", "bullets": ["Lending Club：贷款状态、等级、利率、收入、州、发放时间；待手动下载。", "Home Credit：信贷申请人与历史特征；作为补充对照数据。", "ACS：州/县级收入、贫困率、就业等区域变量。", "Fed：利率、通胀等宏观变量。", "中期已完成脚本接入约定和样例多源流程。"]},
    {"title": "数据流水线", "bullets": ["数据获取：Kaggle 手动下载，ACS/Fed 外部数据后续接入。", "数据探索：规模、字段、缺失值、标签分布。", "数据清洗：字段标准化、缺失值统计、异常值检查。", "多源融合：按州连接区域经济数据，按年份连接宏观数据。", "SQL 聚合与可视化：输出表格和 PNG 图表。"]},
    {"title": "当前进度", "bullets": ["已建立可提交代码库结构和 README。", "已提供 Kaggle 数据放置说明。", "已实现 src/run_midterm_pipeline.py。", "无 Kaggle 数据时仍可生成样例融合数据、统计表和图表。", "放入贷款 CSV 后可自动生成贷款概览、缺失率和标签分布。"]},
    {"title": "样例结果：贷款等级与违约率", "bullets": ["按贷款等级聚合样例违约率。", "用于展示未来真实 Lending Club 数据中的信用等级风险分析方式。", "最终结论需在真实数据下载后重新运行生成。"], "image": "sample_default_rate_by_grade.png"},
    {"title": "样例结果：宏观金融指标趋势", "bullets": ["按年份组织联邦基金利率与通胀率。", "用于说明宏观环境如何进入贷款风险分析框架。", "后续将与真实贷款发放时间进行年度或季度级对齐。"], "image": "sample_macro_trends.png"},
    {"title": "样例结果：州级违约风险", "bullets": ["按州聚合样例贷款数量与违约率。", "使用 SQLite SQL 完成州级统计。", "后续将接入 ACS 收入、贫困率、失业率等真实区域变量。"], "image": "sample_region_risk.png"},
    {"title": "风险与备选方案", "bullets": ["Kaggle 数据下载慢：先展示样例流程，下载后补跑。", "数据量过大：先抽样分析，再保留抽样策略说明。", "多源粒度不一致：降到州级、年度/季度级对齐。", "模型效果不明显：强调解释性分析和多源变量贡献。"]},
    {"title": "后续计划", "bullets": ["5/22–5/26：下载 Lending Club / Home Credit，完成字段筛选和基础清洗。", "5/27–6/1：接入真实 ACS / Fed 数据，完成州级和时间级融合。", "6/2–6/6：完成统计分析、可视化和单源/多源对比。", "6/7–6/10：完成最终汇报 PPT 和展示材料。", "6/11–6/17：完成最终报告、代码整理和演示视频。"]},
    {"title": "小组分工与总结", "bullets": ["成员 A：贷款数据获取与清洗。", "成员 B：外部数据与多源融合。", "成员 C：可视化、汇报与答辩准备。", "中期已完成项目骨架、样例多源融合流水线和可展示图表。", "下一阶段重点是接入真实数据并形成可靠结论。"]},
]


def write_static_package(slide_count):
    (BUILD / "_rels").mkdir(parents=True)
    (BUILD / "docProps").mkdir()
    (BUILD / "ppt" / "slides" / "_rels").mkdir(parents=True)
    (BUILD / "ppt" / "_rels").mkdir()
    (BUILD / "ppt" / "media").mkdir()

    override_slides = "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, slide_count + 1)
    )
    (BUILD / "[Content_Types].xml").write_text(f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  {override_slides}
</Types>''', encoding="utf-8")

    (BUILD / "_rels" / ".rels").write_text('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>''', encoding="utf-8")

    (BUILD / "docProps" / "core.xml").write_text('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>基于多源数据的个人贷款违约风险检测</dc:title>
  <dc:creator>AI Data Foundation Project Team</dc:creator>
</cp:coreProperties>''', encoding="utf-8")
    (BUILD / "docProps" / "app.xml").write_text(f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Claude Code</Application><Slides>{slide_count}</Slides>
</Properties>''', encoding="utf-8")

    slide_ids = "".join(f'<p:sldId id="{255+i}" r:id="rId{i}"/>' for i in range(1, slide_count + 1))
    (BUILD / "ppt" / "presentation.xml").write_text(f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>''', encoding="utf-8")

    rels = "".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, slide_count + 1)
    )
    (BUILD / "ppt" / "_rels" / "presentation.xml.rels").write_text(f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>''', encoding="utf-8")


def build():
    if BUILD.exists():
        shutil.rmtree(BUILD)
    write_static_package(len(slides))

    media_id = 1
    for idx, slide in enumerate(slides, start=1):
        if slide["title"] == "TITLE":
            xml = title_slide_xml()
            rels = ''
        else:
            image_name = slide.get("image")
            xml = slide_xml(slide["title"], slide.get("bullets"), image_name)
            rels = ''
            if image_name:
                media_name = f"image{media_id}.png"
                shutil.copyfile(FIGURES / image_name, BUILD / "ppt" / "media" / media_name)
                rels = f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{media_name}"/>'
                media_id += 1
        (BUILD / "ppt" / "slides" / f"slide{idx}.xml").write_text(xml, encoding="utf-8")
        (BUILD / "ppt" / "slides" / "_rels" / f"slide{idx}.xml.rels").write_text(
            f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>''',
            encoding="utf-8",
        )

    if OUT.exists():
        OUT.unlink()
    with ZipFile(OUT, "w", ZIP_DEFLATED) as zf:
        for path in BUILD.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(BUILD).as_posix())
    shutil.rmtree(BUILD)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
