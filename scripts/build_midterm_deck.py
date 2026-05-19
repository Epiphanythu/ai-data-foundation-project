from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
SLIDES = ROOT / "slides"
FIGURES = ROOT / "outputs" / "figures"
OUT = SLIDES / "midterm_report.pptx"

SLIDE_ITEMS = [
    {"kind": "title"},
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


def add_title(slide, title):
    box = slide.shapes.add_textbox(Inches(0.55), Inches(0.32), Inches(12.2), Inches(0.7))
    frame = box.text_frame
    frame.clear()
    p = frame.paragraphs[0]
    p.text = title
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = RGBColor(17, 24, 39)


def add_bullets(slide, bullets, has_image=False):
    width = Inches(6.0 if has_image else 11.8)
    box = slide.shapes.add_textbox(Inches(0.75), Inches(1.25), width, Inches(4.9))
    frame = box.text_frame
    frame.word_wrap = True
    frame.clear()
    for index, bullet in enumerate(bullets):
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        p.text = bullet
        p.level = 0
        p.font.size = Pt(19 if len(bullets) <= 5 else 17)
        p.font.color.rgb = RGBColor(55, 65, 81)
        p.space_after = Pt(8)


def add_image(slide, image_name):
    path = FIGURES / image_name
    if path.exists():
        slide.shapes.add_picture(str(path), Inches(6.9), Inches(1.55), width=Inches(5.6))


def add_footer(slide, idx):
    box = slide.shapes.add_textbox(Inches(0.55), Inches(7.0), Inches(12.2), Inches(0.25))
    frame = box.text_frame
    frame.clear()
    p = frame.paragraphs[0]
    p.text = f"AI Data Foundation 中期汇报 · {idx}"
    p.alignment = PP_ALIGN.RIGHT
    p.font.size = Pt(9)
    p.font.color.rgb = RGBColor(107, 114, 128)


def build():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    for idx, item in enumerate(SLIDE_ITEMS, start=1):
        slide = prs.slides.add_slide(blank)
        background = slide.background.fill
        background.solid()
        background.fore_color.rgb = RGBColor(255, 255, 255)

        if item.get("kind") == "title":
            title_box = slide.shapes.add_textbox(Inches(0.95), Inches(1.6), Inches(11.5), Inches(1.6))
            tf = title_box.text_frame
            tf.text = "基于多源数据的个人贷款\n违约风险检测"
            for p in tf.paragraphs:
                p.font.size = Pt(38)
                p.font.bold = True
                p.font.color.rgb = RGBColor(17, 24, 39)
            sub = slide.shapes.add_textbox(Inches(1.0), Inches(3.75), Inches(11.0), Inches(1.0))
            stf = sub.text_frame
            stf.text = "AI Data Foundation 中期汇报\n日期：2026-05-21"
            for p in stf.paragraphs:
                p.font.size = Pt(22)
                p.font.color.rgb = RGBColor(55, 65, 81)
            members = slide.shapes.add_textbox(Inches(1.0), Inches(5.65), Inches(10.8), Inches(0.5))
            mtf = members.text_frame
            mtf.text = "小组成员：请替换为实际姓名"
            mtf.paragraphs[0].font.size = Pt(16)
            mtf.paragraphs[0].font.color.rgb = RGBColor(107, 114, 128)
        else:
            add_title(slide, item["title"])
            add_bullets(slide, item.get("bullets", []), bool(item.get("image")))
            if item.get("image"):
                add_image(slide, item["image"])
            add_footer(slide, idx)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
