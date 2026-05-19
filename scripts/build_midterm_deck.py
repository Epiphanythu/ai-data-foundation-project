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
    {"title": "研究动机：贷款违约不只是个人问题", "bullets": ["个人贷款违约会造成金融机构坏账损失，也影响借款人信用定价。", "同样收入和信用等级的人，在不同地区经济环境、利率周期下可能有不同违约概率。", "核心问题：能否用个人信贷 + 地区经济 + 宏观金融数据，形成更可靠、更可解释的风险洞察？"]},
    {"title": "项目挑战：真实金融数据为什么难", "bullets": ["数据规模大：Lending Club accepted 数据 2,260,701 条、151 个字段。", "标签复杂：Current 等未完结贷款不能简单视为不违约。", "多源融合难：贷款是个人/时间粒度，ACS 是地区粒度，Fed 是宏观时间序列。", "解释性要求高：不仅要算出结果，还要讲清楚为什么。"]},
    {"title": "相关工作与局限", "bullets": ["传统信用评分：FICO、收入、负债率，解释性强但偏重个体信息。", "机器学习违约预测：Logistic Regression、Random Forest、XGBoost，预测强但容易黑盒化。", "多源金融风险分析：加入地区收入、失业率、利率、通胀，但数据对齐和口径一致性困难。", "本项目定位：先完成真实数据清洗、融合、统计分析和可解释洞察。"]},
    {"title": "数据集与中期状态", "bullets": ["Lending Club：已下载并完成真实数据初步分析。", "Home Credit：Kaggle competition 需网页端接受 rules 后继续下载。", "ACS 区域经济数据：下一阶段接入州/县级收入、贫困率、就业等变量。", "Fed 宏观金融数据：下一阶段接入利率、通胀、失业率等变量。"]},
    {"title": "数据流水线", "bullets": ["Kaggle 原始数据下载到 data/raw，不上传 GitHub。", "字段检查与缺失率统计。", "贷款状态过滤：保留 Fully Paid / Charged Off / Default 等可判断最终结果的状态。", "按等级、年份、州、利率、收入、DTI、FICO 聚合违约率。", "输出 CSV 统计表与 PNG 图表，下一阶段接入 ACS/Fed。"]},
    {"title": "当前进度：已经从框架推进到真实数据", "bullets": ["GitHub 仓库、README、数据说明和运行脚本已完成。", "已读取 2,260,701 条 Lending Club accepted 贷款记录。", "筛选 1,367,578 条已完结记录用于违约率统计。", "已生成真实统计表和图表：等级、利率、FICO、年份、州。", "当前节点：完成单一真实信贷数据源分析，下一步进入多源融合。"]},
    {"title": "真实发现 1：贷款等级与违约率", "bullets": ["贷款等级风险呈明显梯度。", "A 等级违约率约 6.57%。", "G 等级违约率约 51.57%。", "说明平台等级体系对违约风险有强区分力，是后续多源分析的个体风险基准。"], "image": "lc_default_rate_by_grade.png"},
    {"title": "真实发现 2：利率与违约率", "bullets": ["利率越高，违约率越高。", "<8% 利率分箱违约率约 6.38%。", ">=24% 利率分箱违约率约 48.56%。", "说明定价包含风险补偿，但高风险贷款仍有明显违约集中。"], "image": "lc_default_rate_by_interest_bin.png"},
    {"title": "真实发现 3：FICO 与违约率", "bullets": ["FICO 分数越低，违约率通常越高。", "传统信用评分仍有明显解释力。", "多源数据的价值不是替代 FICO，而是补充地区经济和宏观环境信息。"], "image": "lc_default_rate_by_fico_bin.png"},
    {"title": "真实发现 4：时间趋势", "bullets": ["按发放年份统计违约率，可以观察不同信贷周期下的风险变化。", "后续将与 Fed 利率、通胀、失业率做年度/季度级对齐。", "目标：解释宏观环境是否能解释时间维度的风险波动。"], "image": "lc_default_rate_by_year.png"},
    {"title": "真实发现 5：州级差异", "bullets": ["州级违约率存在明显地区差异。", "样本量超过 1000 的州中，MS 违约率最高，约 28.37%。", "后续将接入 ACS 收入、贫困率、就业等指标解释地区差异。"], "image": "lc_default_rate_top_states.png"},
    {"title": "哪些尝试奏效，哪些没有", "bullets": ["奏效：Lending Club 大型 CSV 已成功流式处理，避免一次性加载内存。", "奏效：贷款状态过滤避免把 Current 等未完结状态误判为不违约。", "奏效：真实数据图表已可直接用于中期汇报。", "受阻：Home Credit 需要先网页端接受 Kaggle competition rules。", "待完成：ACS/Fed 真实外部数据尚未融合。"]},
    {"title": "项目甘特图与当前节点", "bullets": ["4/20–4/30：开题与问题定义 — 已完成。", "5/15–5/18：项目仓库与数据说明 — 已完成。", "5/18–5/19：Lending Club 下载与初步 EDA — 已完成，当前节点。", "5/20–5/27：Home Credit / ACS / Fed 接入 — 进行中。", "5/27–6/3：多源融合与对比分析 — 未开始。", "6/3–6/17：最终可视化、报告、视频和提交 — 未开始。"]},
    {"title": "后续计划", "bullets": ["5/20–5/22：完成 Home Credit 授权下载；若仍失败，作为补充项。", "5/22–5/27：下载 ACS/Fed 数据，统一州代码和年份/季度口径。", "5/27–6/3：Lending Club 与 ACS/Fed 做州级、时间级融合。", "6/3–6/8：完成最终可视化、核心结论和报告初稿。", "6/8–6/17：打磨最终 PPT、报告、视频和代码仓库。"]},
    {"title": "风险与备选方案", "bullets": ["Home Credit 需网页授权：先以 Lending Club + ACS + Fed 完成主线。", "ACS/Fed 粒度不一致：降到州级、年度/季度级对齐。", "本地处理大文件慢：继续使用流式 CSV 统计和抽样分析。", "多源变量提升不明显：强调解释性洞察，报告变量边际贡献和局限。"]},
    {"title": "总结", "bullets": ["中期阶段已经完成真实 Lending Club 数据分析。", "当前已有可复现代码、GitHub 仓库、统计表和真实图表。", "核心初步结论：等级、利率、FICO、地区都与违约风险存在显著关联。", "下一阶段重点：接入 ACS/Fed，解释地区和宏观环境如何影响违约风险。"]},
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
