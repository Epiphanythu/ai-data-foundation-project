// 基于多源数据的个人贷款违约风险检测 - 中期学术汇报 PPT V2
// 改进版：更好的排版、字体和布局

const PptxGenJS = require("pptxgenjs");
const path = require("path");
const fs = require("fs");

// 改进的颜色方案 - 更专业
const COLORS = {
    navy: "1F4E79",      // 主色
    midBlue: "2E75B6",   // 强调色
    lightBlue: "D9E1F2", // 浅蓝背景
    white: "FFFFFF",     // 背景
    gray: "5A5A5A",      // 正文文字
    lightGray: "F5F5F5", // 辅助背景
    coral: "C0504D",     // 警示/重点（更柔和）
    green: "4B7561"      // 成功/确认
};

// 尺寸常量
const SIZES = {
    slideWidth: 10,
    slideHeight: 5.625,
    margin: 0.5,
    contentWidth: 9,
    titleHeight: 0.8
};

// 图表路径
const FIGURES_PATH = "/Users/bytedance/Desktop/DB/outputs/figures";

// 创建演示文稿
const pres = new PptxGenJS();

pres.defineLayout({ name: "16x9", width: 10, height: 5.625 });
pres.layout = "16x9";
pres.author = "贷款违约风险检测项目组";
pres.company = "数据科学课程项目";
pres.title = "基于多源数据的个人贷款违约风险检测 - 中期汇报";

// 幻灯片内容
const slides = [
    // 标题页
    {
        type: "title",
        title: "基于多源数据的个人贷款违约风险检测",
        subtitle: "中期汇报 | 多源数据融合与可解释风险分析",
        authors: ["汇报人A", "汇报人B"],
        date: "2026年5月21日",
        course: "数据科学课程项目"
    },
    // 研究动机
    { type: "section", title: "研究动机" },
    {
        type: "question",
        title: "核心问题",
        question: "如果两个人收入相同、信用评分相同，一个住在密西西比州，一个住在加州；一个在2008年贷款，一个在2015年贷款；他们的违约风险会一样吗？",
        points: [
            "同样收入和信用评分的人，在不同地区违约风险相同吗？",
            "不同经济周期（如2008金融危机vs2015年）下风险有何差异？",
            "传统模型只看个人特征，忽略了地区经济和宏观周期"
        ]
    },
    {
        type: "twoCol",
        title: "研究价值：兼顾科学意义与实际应用",
        leftCol: {
            heading: "科学意义",
            points: ["验证三层风险模型：违约风险 = 个人特征 + 地区经济 + 宏观周期", '回答"地区经济和宏观环境是否独立影响个人违约风险"的学术问题', "为多源数据融合提供方法论基础"]
        },
        rightCol: {
            heading: "实际价值",
            points: ["帮助金融机构降低坏账损失", "改善风险定价公平性", "为借款人提供更合理的信用定价"]
        }
    },
    {
        type: "challenges",
        title: "三大技术挑战",
        challenges: [
            { title: "挑战一：数据规模大", desc: "Lending Club 2.8GB CSV文件，226万条记录，151个字段，一次性读取导致内存溢出" },
            { title: "挑战二：标签复杂", desc: "贷款状态有10多种（Fully Paid, Charged Off, Current, Late...），未完结状态无法判断最终违约" },
            { title: "挑战三：多源数据粒度不一致", desc: "个人级别贷款数据 + 50州级平均数据 + 国家宏观时间序列，如何有效融合？" }
        ]
    },
    // 相关工作
    { type: "section", title: "相关工作" },
    {
        type: "table",
        title: "三类现有方法各有优势，但均存在明显局限",
        headers: ["方法类型", "代表技术", "优点", "局限"],
        rows: [
            ["传统信用评分", "FICO、收入、负债率", "解释性强，易于理解", "只看个人，忽略环境和周期"],
            ["机器学习预测", "LR、RF、XGBoost、神经网络", "预测能力强，准确率高", "黑盒化，缺乏可解释性"],
            ["多源风险分析", "地区收入、失业率、利率", "视角全面，贴近实际", "数据对齐困难，缺乏控制变量分析"]
        ]
    },
    {
        type: "positioning",
        title: "本研究定位",
        points: ["不是取代传统方法，而是补充地区经济和宏观周期维度", "先做好数据清洗、融合、可解释统计分析，再考虑预测模型", "强调多源数据的增量价值和可解释洞察，而非单纯追求预测准确率"]
    },
    // 数据与方法
    { type: "section", title: "数据与方法" },
    {
        type: "dataSources",
        title: "四源数据融合：覆盖个人、州级、宏观三个维度",
        sources: [
            { name: "Lending Club", scale: "226万条，151字段", desc: "个体贷款记录、违约标签" },
            { name: "FRED 宏观", scale: "47季度，3指标", desc: "联邦基金利率、CPI、失业率" },
            { name: "USDA ERS", scale: "50州，3指标", desc: "州级收入、贫困率、失业率" },
            { name: "Home Credit", scale: "30万条，122字段", desc: "补充信贷场景对照" }
        ]
    },
    {
        type: "metrics",
        title: "数据融合成果",
        metrics: [
            { label: "已完结样本", value: "1,367,578 条", desc: "排除Current等未完结状态" },
            { label: "州级覆盖", value: "50 个州", desc: "完整州级匹配" },
            { label: "时间跨度", value: "47 季度", desc: "2007-Q2 至 2018-Q4" }
        ]
    },
    {
        type: "method",
        title: "方法一：流式处理解决大规模数据加载问题",
        problem: "2.8GB CSV文件一次性读取导致内存溢出",
        solution: "使用 pandas.read_csv(chunksize=10000) 逐块处理，每次只读1万条，处理完成后丢弃，再读下一万条",
        result: "内存占用始终保持在低水平"
    },
    {
        type: "method",
        title: "方法二：严格违约标签构造确保结论可靠性",
        problem: "贷款状态有10多种，Current（正在还款）将来是否违约未知",
        solution: "只保留已完结状态：Fully Paid（全额还款）、Charged Off（核销）、Default（违约）",
        result: "从226万条筛选出136万条已完结样本，标签质量显著提高"
    },
    {
        type: "method",
        title: "方法三：时间对齐匹配贷款发放时的宏观环境",
        problem: "贷款数据跨越2007-2018年，FRED数据为月度频率",
        solution: "FRED月度数据取季度最后一个月值，与贷款发放季度对齐",
        result: "匹配发放时的宏观环境，避免使用未来数据"
    },
    {
        type: "method",
        title: "方法四：残差分析证明地区经济的独立解释力",
        problem: "观察到贫困率高的州违约率高，但可能是因为这些州高风险贷款更多",
        solution: "残差分析法：①建立利率→违约率模型 ②计算预期违约率 ③残差=实际-预期 ④分析残差与贫困率相关性",
        result: "控制利率后相关性从0.398降至0.362，仍然显著，证明地区经济有独立解释力"
    },
    // 核心发现
    { type: "section", title: "核心发现" },
    {
        type: "chart",
        title: "发现一：贷款等级强区分违约风险，A与G相差8倍",
        chart: "lc_default_rate_by_grade.png",
        findings: ["A等级违约率仅6.57%，G等级高达51.57%，相差近8倍", "违约率随等级上升呈明显单调递增趋势", "Lending Club的风险定价体系是有效的"]
    },
    {
        type: "chart",
        title: "发现二：利率与违约高度相关，反映平台风险定价能力",
        chart: "lc_default_rate_by_interest_bin.png",
        findings: ["低利率（<8%）违约率6.38%，高利率（≥24%）违约率48.56%", "违约率随利率上升几乎呈线性增长", "利率定价已包含风险判断"]
    },
    {
        type: "chart",
        title: "发现三：宏观金融环境与违约率季度相关系数达0.844",
        chart: "lc_fred_quarterly_overlay.png",
        findings: ["联邦基金利率与违约率的季度相关系数为0.844", "两条曲线趋势高度一致，反映宏观周期对个人违约的系统性影响", "【重要】此为相关性分析，不能简单解释为因果关系"]
    },
    {
        type: "chart",
        title: "发现四：地区经济具有独立于个人特征的解释力",
        chart: "lc_state_default_residual_interest_vs_poverty.png",
        findings: ["原始相关（贫困率vs违约率）：r = 0.398", "控制州级平均利率后：r = 0.362，仍然显著", "控制州级平均FICO后：r = 0.459，相关性反而更强", "结论：地区经济有独立于个人特征的解释力"]
    },
    {
        type: "chart",
        title: "发现五：组合风险分层识别超高风险人群",
        chart: "lc_top_risk_grade_purpose_segments.png",
        findings: ["G等级 × debt_consolidation（债务整合）违约率高达52.99%", "每两笔此类贷款就有一笔违约，属于极高风险组合", "实际应用：风控部门可直接识别此类组合进行严格审核"]
    },
    // 进度汇报
    { type: "section", title: "进度汇报" },
    {
        type: "gantt",
        title: "项目进展：各阶段均按计划完成",
        tasks: [
            { phase: "开题与问题定义", time: "4/20–4/30", status: "✅ 完成" },
            { phase: "项目仓库搭建", time: "5/15–5/18", status: "✅ 完成" },
            { phase: "Lending Club EDA", time: "5/18–5/19", status: "✅ 完成" },
            { phase: "FRED/ERS 数据融合", time: "5/19–5/20", status: "✅ 完成" },
            { phase: "风险分层分析", time: "5/20", status: "✅ 完成" },
            { phase: "Home Credit 数据下载", time: "5/20", status: "✅ 当前节点" },
            { phase: "控制变量建模", time: "5/21–5/27", status: "🔄 进行中" },
            { phase: "最终可视化", time: "5/27–6/3", status: "⏳ 计划中" },
            { phase: "最终报告与答辩", time: "6/3–6/17", status: "⏳ 计划中" }
        ]
    },
    {
        type: "successes",
        title: "奏效部分：四项关键技术成功落地",
        items: [
            { title: "大型CSV流式处理", desc: "使用chunksize=10000逐块处理" },
            { title: "贷款状态过滤", desc: "排除Current等未完结状态" },
            { title: "多源数据融合", desc: "州代码映射和时间对齐" },
            { title: "可视化成果", desc: "生成28张图表和45+张统计表" }
        ]
    },
    {
        type: "challenges",
        title: "受阻部分与应对方案",
        challenges: [
            { title: "Home Credit需要网页授权", desc: "问题：Kaggle API返回403 | 解决：手动接受规则后成功下载 | 影响：不影响主线" },
            { title: "当前为相关性分析，非因果推断", desc: "问题：无法从相关性推断因果关系 | 解决：下一阶段加入控制变量模型" }
        ]
    },
    // 后续计划
    { type: "section", title: "后续计划" },
    {
        type: "timeline",
        title: "后续计划：三个阶段推进项目完成",
        phases: [
            { time: "5/21-5/27", task: "多源控制变量建模", owner: "同学B", output: "模型结果、增量贡献分析" },
            { time: "5/27-6/3", task: "最终可视化与结论提炼", owner: "同学A", output: "报告图表、核心结论" },
            { time: "6/3-6/17", task: "PPT/报告/视频打磨", owner: "同学B", output: "最终提交物" }
        ]
    },
    {
        type: "risks",
        title: "风险管理：每个风险均有备选方案",
        risks: [
            { risk: "Home Credit授权受限", backup: "已有LC+FRED+ERS主线" },
            { risk: "相关性≠因果", backup: "加入控制变量模型" },
            { risk: "时间紧张", backup: "保证多源分析完整性" }
        ]
    },
    // 结论
    {
        type: "conclusions",
        title: "结论：违约风险是个人、地区与宏观的复合结果",
        conclusions: [
            { title: "等级是强风险分层工具", stat: "A等级6.57% vs G等级51.57%" },
            { title: "宏观环境与违约高度相关", stat: "季度相关系数0.844" },
            { title: "地区经济有独立解释力", stat: "控制后贫困率仍相关0.362" },
            { title: "多源融合能精确识别高风险", stat: "G×debt_consolidation违约率52.99%" }
        ]
    },
    // 结束页
    {
        type: "ending",
        title: "感谢聆听，欢迎提问",
        repo: "github.com/Epiphanythu/ai-data-foundation-project"
    }
];

// 幻灯片构建函数
function buildSlides() {
    slides.forEach((data, index) => {
        const slide = pres.addSlide();

        switch (data.type) {
            case "title":
                buildTitleSlide(slide, data);
                break;
            case "section":
                buildSectionSlide(slide, data);
                break;
            case "question":
                buildQuestionSlide(slide, data);
                break;
            case "twoCol":
                buildTwoColSlide(slide, data);
                break;
            case "challenges":
                buildChallengesSlide(slide, data);
                break;
            case "table":
                buildTableSlide(slide, data);
                break;
            case "positioning":
                buildPositioningSlide(slide, data);
                break;
            case "dataSources":
                buildDataSourcesSlide(slide, data);
                break;
            case "metrics":
                buildMetricsSlide(slide, data);
                break;
            case "method":
                buildMethodSlide(slide, data);
                break;
            case "chart":
                buildChartSlide(slide, data);
                break;
            case "gantt":
                buildGanttSlide(slide, data);
                break;
            case "successes":
                buildSuccessesSlide(slide, data);
                break;
            case "timeline":
                buildTimelineSlide(slide, data);
                break;
            case "risks":
                buildRisksSlide(slide, data);
                break;
            case "conclusions":
                buildConclusionsSlide(slide, data);
                break;
            case "ending":
                buildEndingSlide(slide, data);
                break;
        }
    });
}

// 标题页
function buildTitleSlide(slide, data) {
    // 装饰条
    slide.addShape(pres.ShapeType.rect, {
        x: 0, y: 0, w: 10, h: 0.1,
        fill: { color: COLORS.navy }
    });

    // 主标题
    slide.addText(data.title, {
        x: 1, y: 1.8, w: 8, h: 1,
        fontSize: 32, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy, align: "center", valign: "middle"
    });

    // 副标题
    slide.addText(data.subtitle, {
        x: 1, y: 2.8, w: 8, h: 0.5,
        fontSize: 18, fontFace: "Microsoft YaHei",
        color: COLORS.midBlue, align: "center", valign: "middle"
    });

    // 课程信息
    slide.addText(data.course, {
        x: 1, y: 3.5, w: 8, h: 0.4,
        fontSize: 14, fontFace: "Microsoft YaHei",
        color: COLORS.gray, align: "center"
    });

    // 汇报人
    slide.addText(`汇报人：${data.authors.join("、")}`, {
        x: 1, y: 4.2, w: 8, h: 0.4,
        fontSize: 16, fontFace: "Microsoft YaHei",
        color: COLORS.navy, align: "center"
    });

    // 日期
    slide.addText(data.date, {
        x: 1, y: 4.6, w: 8, h: 0.4,
        fontSize: 16, fontFace: "Microsoft YaHei",
        color: COLORS.navy, align: "center"
    });
}

// 章节页
function buildSectionSlide(slide, data) {
    slide.background = { color: COLORS.navy };

    slide.addText(data.title, {
        x: 0.5, y: 2.3, w: 9, h: 1,
        fontSize: 36, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.white, align: "center", valign: "middle"
    });

    // 装饰线
    slide.addShape(pres.ShapeType.rect, {
        x: 3.5, y: 3.5, w: 3, h: 0.05,
        fill: { color: COLORS.white }
    });
}

// 问题页
function buildQuestionSlide(slide, data) {
    // 标题
    slide.addText(data.title, {
        x: 0.5, y: 0.4, w: 9, h: 0.5,
        fontSize: 26, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy
    });

    // 问题框
    slide.addShape(pres.ShapeType.rect, {
        x: 0.7, y: 1.2, w: 8.6, h: 1.5,
        fill: { color: COLORS.lightBlue },
        line: { color: COLORS.midBlue, width: 2 }
    });

    slide.addText(data.question, {
        x: 1, y: 1.4, w: 8, h: 1.1,
        fontSize: 18, fontFace: "Microsoft YaHei",
        color: COLORS.navy, align: "justify"
    });

    // 要点
    data.points.forEach((point, i) => {
        slide.addText(`• ${point}`, {
            x: 1, y: 3 + i * 0.6, w: 8, h: 0.5,
            fontSize: 16, fontFace: "Microsoft YaHei",
            color: COLORS.gray
        });
    });
}

// 双栏页
function buildTwoColSlide(slide, data) {
    slide.addText(data.title, {
        x: 0.5, y: 0.4, w: 9, h: 0.5,
        fontSize: 24, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy
    });

    // 左栏
    slide.addShape(pres.ShapeType.rect, {
        x: 0.6, y: 1.1, w: 4.2, h: 4.2,
        fill: { color: COLORS.lightBlue },
        line: { color: COLORS.midBlue, width: 1 }
    });

    slide.addText(data.leftCol.heading, {
        x: 0.8, y: 1.25, w: 3.8, h: 0.4,
        fontSize: 18, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy
    });

    data.leftCol.points.forEach((point, i) => {
        slide.addText(`• ${point}`, {
            x: 0.8, y: 1.75 + i * 0.75, w: 3.8, h: 0.7,
            fontSize: 14, fontFace: "Microsoft YaHei",
            color: COLORS.gray
        });
    });

    // 右栏
    slide.addShape(pres.ShapeType.rect, {
        x: 5.2, y: 1.1, w: 4.2, h: 4.2,
        fill: { color: "FFF4E6" },
        line: { color: "E6AA00", width: 1 }
    });

    slide.addText(data.rightCol.heading, {
        x: 5.4, y: 1.25, w: 3.8, h: 0.4,
        fontSize: 18, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy
    });

    data.rightCol.points.forEach((point, i) => {
        slide.addText(`• ${point}`, {
            x: 5.4, y: 1.75 + i * 0.75, w: 3.8, h: 0.7,
            fontSize: 14, fontFace: "Microsoft YaHei",
            color: COLORS.gray
        });
    });
}

// 挑战页
function buildChallengesSlide(slide, data) {
    slide.addText(data.title, {
        x: 0.5, y: 0.4, w: 9, h: 0.5,
        fontSize: 24, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy
    });

    data.challenges.forEach((challenge, i) => {
        const y = 1.15 + i * 1.35;

        slide.addText(challenge.title, {
            x: 0.7, y: y, w: 8.6, h: 0.35,
            fontSize: 16, fontFace: "Microsoft YaHei", bold: true,
            color: COLORS.coral
        });

        slide.addText(challenge.desc, {
            x: 0.7, y: y + 0.4, w: 8.6, h: 0.85,
            fontSize: 14, fontFace: "Microsoft YaHei",
            color: COLORS.gray
        });
    });
}

// 表格页
function buildTableSlide(slide, data) {
    slide.addText(data.title, {
        x: 0.5, y: 0.4, w: 9, h: 0.5,
        fontSize: 22, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy
    });

    const tableData = [data.headers, ...data.rows];
    slide.addTable(tableData, {
        x: 0.7, y: 1.15, w: 8.6,
        border: { pt: 1, color: "CCCCCC" },
        colW: [1.8, 2.2, 2.3, 2.3],
        fontSize: 13, fontFace: "Microsoft YaHei",
        color: "333333",
        fill: { color: "E8E8E8" },
        margin: 8,
        valign: "top"
    });
}

// 定位页
function buildPositioningSlide(slide, data) {
    slide.addText(data.title, {
        x: 0.5, y: 0.4, w: 9, h: 0.5,
        fontSize: 24, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy
    });

    slide.addShape(pres.ShapeType.rect, {
        x: 0.7, y: 1.1, w: 8.6, h: 4.2,
        fill: { color: COLORS.lightBlue },
        line: { color: COLORS.midBlue, width: 2 }
    });

    data.points.forEach((point, i) => {
        slide.addText(`${i + 1}. ${point}`, {
            x: 1, y: 1.4 + i * 1.1, w: 8, h: 1,
            fontSize: 16, fontFace: "Microsoft YaHei",
            color: COLORS.navy
        });
    });
}

// 数据源页
function buildDataSourcesSlide(slide, data) {
    slide.addText(data.title, {
        x: 0.5, y: 0.4, w: 9, h: 0.5,
        fontSize: 22, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy
    });

    data.sources.forEach((source, i) => {
        const x = (i % 2) * 4.6 + 0.6;
        const y = 1.15 + Math.floor(i / 2) * 1.4;

        slide.addShape(pres.ShapeType.rect, {
            x: x, y: y, w: 4.2, h: 1.2,
            fill: { color: i % 2 === 0 ? COLORS.lightBlue : "FFF4E6" },
            line: { color: COLORS.midBlue, width: 1 }
        });

        slide.addText(`✅ ${source.name}`, {
            x: x + 0.2, y: y + 0.15, w: 3.8, h: 0.35,
            fontSize: 15, fontFace: "Microsoft YaHei", bold: true,
            color: COLORS.navy
        });

        slide.addText(`${source.scale}\n${source.desc}`, {
            x: x + 0.2, y: y + 0.55, w: 3.8, h: 0.55,
            fontSize: 12, fontFace: "Microsoft YaHei",
            color: COLORS.gray
        });
    });
}

// 指标页
function buildMetricsSlide(slide, data) {
    slide.addText(data.title, {
        x: 0.5, y: 0.4, w: 9, h: 0.5,
        fontSize: 24, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy
    });

    data.metrics.forEach((metric, i) => {
        const x = (i % 3) * 3.1 + 0.7;
        const y = 1.3 + Math.floor(i / 3) * 2;

        slide.addText(metric.value, {
            x: x, y: y, w: 2.9, h: 0.6,
            fontSize: 28, fontFace: "Microsoft YaHei", bold: true,
            color: COLORS.coral, align: "center"
        });

        slide.addText(metric.label, {
            x: x, y: y + 0.65, w: 2.9, h: 0.35,
            fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
            color: COLORS.navy, align: "center"
        });

        slide.addText(metric.desc, {
            x: x, y: y + 1.05, w: 2.9, h: 0.4,
            fontSize: 11, fontFace: "Microsoft YaHei",
            color: COLORS.gray, align: "center"
        });
    });
}

// 方法页
function buildMethodSlide(slide, data) {
    slide.addText(data.title, {
        x: 0.5, y: 0.4, w: 9, h: 0.6,
        fontSize: 20, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy
    });

    // 问题
    slide.addShape(pres.ShapeType.rect, {
        x: 0.6, y: 1.15, w: 8.8, h: 0.75,
        fill: { color: "FFE6E6" },
        line: { color: COLORS.coral, width: 1 }
    });
    slide.addText("问题", {
        x: 0.8, y: 1.25, w: 0.7, h: 0.3,
        fontSize: 13, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.coral
    });
    slide.addText(data.problem, {
        x: 0.8, y: 1.55, w: 8.4, h: 0.35,
        fontSize: 12, fontFace: "Microsoft YaHei",
        color: COLORS.gray
    });

    // 解决方案
    slide.addShape(pres.ShapeType.rect, {
        x: 0.6, y: 2.05, w: 8.8, h: 1.3,
        fill: { color: COLORS.lightBlue },
        line: { color: COLORS.midBlue, width: 1 }
    });
    slide.addText("解决方案", {
        x: 0.8, y: 2.15, w: 1, h: 0.3,
        fontSize: 13, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.midBlue
    });
    slide.addText(data.solution, {
        x: 0.8, y: 2.5, w: 8.4, h: 0.85,
        fontSize: 12, fontFace: "Microsoft YaHei",
        color: COLORS.gray
    });

    // 结果
    slide.addShape(pres.ShapeType.rect, {
        x: 0.6, y: 3.5, w: 8.8, h: 0.75,
        fill: { color: "E8F5E9" },
        line: { color: COLORS.green, width: 1 }
    });
    slide.addText("结果", {
        x: 0.8, y: 3.6, w: 0.7, h: 0.3,
        fontSize: 13, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.green
    });
    slide.addText(data.result, {
        x: 0.8, y: 3.9, w: 8.4, h: 0.35,
        fontSize: 12, fontFace: "Microsoft YaHei",
        color: COLORS.gray
    });
}

// 图表页
function buildChartSlide(slide, data) {
    const imgPath = path.join(FIGURES_PATH, data.chart);
    const imgExists = fs.existsSync(imgPath);

    slide.addText(data.title, {
        x: 0.5, y: 0.35, w: 9, h: 0.6,
        fontSize: 20, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy
    });

    if (imgExists) {
        // 图片在左侧
        slide.addImage({
            path: imgPath,
            x: 0.5, y: 1.1, w: 5.2, h: 4.3,
            sizing: { type: "contain", w: 5.2, h: 4.3 }
        });

        // 右侧发现框
        slide.addShape(pres.ShapeType.rect, {
            x: 5.9, y: 1.1, w: 3.6, h: 4.3,
            fill: { color: COLORS.lightGray },
            line: { color: COLORS.midBlue, width: 1 }
        });

        slide.addText("核心发现", {
            x: 6.1, y: 1.25, w: 3.2, h: 0.3,
            fontSize: 15, fontFace: "Microsoft YaHei", bold: true,
            color: COLORS.navy
        });

        data.findings.forEach((finding, i) => {
            slide.addText(`• ${finding}`, {
                x: 6.1, y: 1.65 + i * 0.95, w: 3.2, h: 0.9,
                fontSize: 11, fontFace: "Microsoft YaHei",
                color: COLORS.gray
            });
        });
    }
}

// 甘特图页
function buildGanttSlide(slide, data) {
    slide.addText(data.title, {
        x: 0.5, y: 0.4, w: 9, h: 0.5,
        fontSize: 22, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy
    });

    const tableData = [
        [{ text: "阶段", options: { fontSize: 12, fontFace: "Microsoft YaHei", bold: true, color: COLORS.white, fill: { color: COLORS.navy } } },
         { text: "时间", options: { fontSize: 12, fontFace: "Microsoft YaHei", bold: true, color: COLORS.white, fill: { color: COLORS.navy } } },
         { text: "状态", options: { fontSize: 12, fontFace: "Microsoft YaHei", bold: true, color: COLORS.white, fill: { color: COLORS.navy } } }],
        ...data.tasks.map(task => [
            task.phase,
            task.time,
            { text: task.status, options: { fontSize: 11, fontFace: "Microsoft YaHei", color: task.status.includes("✅") ? COLORS.green : task.status.includes("🔄") ? "E6AA00" : COLORS.gray } }
        ])
    ];

    slide.addTable(tableData, {
        x: 0.7, y: 1.05, w: 8.6,
        border: { pt: 1, color: "DDDDDD" },
        colW: [3.5, 2.5, 2.6],
        fontSize: 11, fontFace: "Microsoft YaHei",
        color: "333333",
        margin: 6
    });
}

// 成功页
function buildSuccessesSlide(slide, data) {
    slide.addText(data.title, {
        x: 0.5, y: 0.4, w: 9, h: 0.5,
        fontSize: 22, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy
    });

    data.items.forEach((item, i) => {
        const x = (i % 2) * 4.6 + 0.6;
        const y = 1.15 + Math.floor(i / 2) * 1.3;

        slide.addShape(pres.ShapeType.rect, {
            x: x, y: y, w: 4.2, h: 1.1,
            fill: { color: "E8F5E9" },
            line: { color: COLORS.green, width: 1 }
        });

        slide.addText(`✓ ${item.title}`, {
            x: x + 0.2, y: y + 0.15, w: 3.8, h: 0.35,
            fontSize: 15, fontFace: "Microsoft YaHei", bold: true,
            color: COLORS.green
        });

        slide.addText(item.desc, {
            x: x + 0.2, y: y + 0.55, w: 3.8, h: 0.45,
            fontSize: 12, fontFace: "Microsoft YaHei",
            color: COLORS.gray
        });
    });
}

// 时间线页
function buildTimelineSlide(slide, data) {
    slide.addText(data.title, {
        x: 0.5, y: 0.4, w: 9, h: 0.5,
        fontSize: 22, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy
    });

    data.phases.forEach((phase, i) => {
        const y = 1.15 + i * 1.25;

        slide.addShape(pres.ShapeType.rect, {
            x: 0.6, y: y, w: 1.2, h: 1.05,
            fill: { color: COLORS.midBlue },
            line: { color: COLORS.midBlue, width: 1 }
        });

        slide.addText(phase.time.replace(/(\d+\/\d+)-(\d+\/\d+)/, "$1\n~\n$2"), {
            x: 0.7, y: y + 0.15, w: 1, h: 0.75,
            fontSize: 11, fontFace: "Microsoft YaHei", bold: true,
            color: COLORS.white, align: "center"
        });

        slide.addText(phase.task, {
            x: 2, y: y + 0.1, w: 2.5, h: 0.35,
            fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
            color: COLORS.navy
        });

        slide.addText(`负责人: ${phase.owner}`, {
            x: 2, y: y + 0.45, w: 2, h: 0.25,
            fontSize: 11, fontFace: "Microsoft YaHei",
            color: COLORS.gray
        });

        slide.addText(`产出: ${phase.output}`, {
            x: 2, y: y + 0.7, w: 7, h: 0.3,
            fontSize: 11, fontFace: "Microsoft YaHei",
            color: COLORS.gray
        });
    });
}

// 风险页
function buildRisksSlide(slide, data) {
    slide.addText(data.title, {
        x: 0.5, y: 0.4, w: 9, h: 0.5,
        fontSize: 22, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.navy
    });

    data.risks.forEach((risk, i) => {
        const y = 1.1 + i * 1.25;

        slide.addShape(pres.ShapeType.rect, {
            x: 0.6, y: y, w: 8.8, h: 1.1,
            fill: { color: COLORS.lightGray },
            line: { color: "CCCCCC", width: 1 }
        });

        slide.addText(`风险: ${risk.risk}`, {
            x: 0.8, y: y + 0.1, w: 8.4, h: 0.3,
            fontSize: 13, fontFace: "Microsoft YaHei", bold: true,
            color: COLORS.coral
        });

        slide.addText(`备选方案: ${risk.backup}`, {
            x: 0.8, y: y + 0.45, w: 8.4, h: 0.55,
            fontSize: 12, fontFace: "Microsoft YaHei",
            color: COLORS.gray
        });
    });
}

// 结论页
function buildConclusionsSlide(slide, data) {
    slide.background = { color: COLORS.navy };

    slide.addText(data.title, {
        x: 0.5, y: 0.5, w: 9, h: 0.7,
        fontSize: 28, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.white, align: "center"
    });

    data.conclusions.forEach((concl, i) => {
        const y = 1.5 + i * 0.85;

        slide.addText(concl.title, {
            x: 0.7, y: y, w: 8.6, h: 0.35,
            fontSize: 15, fontFace: "Microsoft YaHei",
            color: COLORS.white
        });

        slide.addText(concl.stat, {
            x: 0.7, y: y + 0.35, w: 8.6, h: 0.4,
            fontSize: 18, fontFace: "Microsoft YaHei", bold: true,
            color: "FFD54F"
        });
    });
}

// 结束页
function buildEndingSlide(slide, data) {
    slide.background = { color: COLORS.navy };

    slide.addText(data.title, {
        x: 0.5, y: 2, w: 9, h: 0.8,
        fontSize: 36, fontFace: "Microsoft YaHei", bold: true,
        color: COLORS.white, align: "center"
    });

    slide.addShape(pres.ShapeType.rect, {
        x: 3, y: 3, w: 4, h: 0.05,
        fill: { color: COLORS.white }
    });

    slide.addText(`项目仓库: ${data.repo}`, {
        x: 0.5, y: 3.5, w: 9, h: 0.4,
        fontSize: 14, fontFace: "Microsoft YaHei",
        color: COLORS.white, align: "center"
    });

    slide.addText("欢迎提问与交流", {
        x: 0.5, y: 4.2, w: 9, h: 0.4,
        fontSize: 16, fontFace: "Microsoft YaHei",
        color: "FFD54F", align: "center"
    });
}

// 构建并保存
buildSlides();

const outputPath = "/Users/bytedance/Desktop/DB/slides/midterm_academic_v2.pptx";
pres.writeFile({ fileName: outputPath })
    .then(fileName => {
        console.log(`PPT已成功生成: ${fileName}`);
    })
    .catch(err => {
        console.error("生成PPT时出错:", err);
    });
