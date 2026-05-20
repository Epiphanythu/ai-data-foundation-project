// 基于多源数据的个人贷款违约风险检测 - 中期学术汇报 PPT
// 使用 pptxgenjs 生成专业学术风格演示文稿

const PptxGenJS = require("pptxgenjs");
const path = require("path");
const fs = require("fs");

// 颜色方案
const COLORS = {
    navy: "1F4E79",      // 主色
    midBlue: "2E75B6",   // 强调色
    white: "FFFFFF",     // 背景
    lightGray: "F0F0F0", // 辅助
    coral: "E74C3C"      // 警示/重点
};

// 字体设置
const FONTS = {
    main: "Arial",
    title: { fontSize: 28, bold: true },
    section: { fontSize: 22, bold: true },
    body: { fontSize: 18, regular: true },
    small: { fontSize: 14, regular: true }
};

// 图表路径
const FIGURES_PATH = "/Users/bytedance/Desktop/DB/outputs/figures";

// 创建演示文稿
const pres = new PptxGenJS();

// 设置全局属性
pres.defineLayout({ name: "A4", width: 10, height: 5.625 });
pres.layout = "A4";
pres.author = "贷款违约风险检测项目组";
pres.company = "数据科学课程项目";
pres.title = "基于多源数据的个人贷款违约风险检测 - 中期汇报";

// ============================================================
// 幻灯片定义
// ============================================================

/**
 * 幻灯片列表 - 每页包含:
 * - type: 幻灯片类型
 * - title: 动作标题（完整句子）
 * - content: 内容
 */
const slides = [
    // ==================== 标题页 ====================
    {
        type: "title",
        title: "基于多源数据的个人贷款违约风险检测",
        subtitle: "中期汇报 | 多源数据融合与可解释风险分析",
        authors: ["汇报人A", "汇报人B"],
        date: "2026年5月21日",
        course: "数据科学课程项目"
    },

    // ==================== 研究动机 ====================
    {
        type: "section",
        title: "研究动机：为什么违约风险不只是个人问题？"
    },
    {
        type: "motivation",
        title: "核心问题：环境与周期如何影响个人违约风险？",
        points: [
            "同样收入和信用评分的人，在不同地区违约风险相同吗？",
            "不同经济周期（如2008金融危机vs2015年）下风险有何差异？",
            "传统模型只看个人特征，忽略了地区经济和宏观周期"
        ],
        hook: "如果两个人收入相同、信用评分相同，一个住在密西西比州，一个住在加州；一个在2008年贷款，一个在2015年贷款；他们的违约风险会一样吗？"
    },
    {
        type: "importance",
        title: "研究价值：兼顾科学意义与实际应用",
        leftCol: {
            heading: "科学意义",
            points: [
                "验证三层风险模型：违约风险 = 个人特征 + 地区经济 + 宏观周期",
                '回答"地区经济和宏观环境是否独立影响个人违约风险"的学术问题',
                "为多源数据融合提供方法论基础"
            ]
        },
        rightCol: {
            heading: "实际价值",
            points: [
                "帮助金融机构降低坏账损失",
                "改善风险定价公平性",
                "为借款人提供更合理的信用定价"
            ]
        }
    },
    {
        type: "challenges",
        title: "三大技术挑战：规模、标签与融合",
        challenges: [
            {
                title: "挑战一：数据规模大",
                desc: "Lending Club 2.8GB CSV文件，226万条记录，151个字段，一次性读取导致内存溢出"
            },
            {
                title: "挑战二：标签复杂",
                desc: "贷款状态有10多种（Fully Paid, Charged Off, Current, Late...），未完结状态无法判断最终违约"
            },
            {
                title: "挑战三：多源数据粒度不一致",
                desc: "个人级别贷款数据 + 50州级平均数据 + 国家宏观时间序列，如何有效融合？"
            }
        ]
    },

    // ==================== 相关工作 ====================
    {
        type: "section",
        title: "相关工作：现有方法的局限性"
    },
    {
        type: "comparison",
        title: "三类现有方法各有优势，但均存在明显局限",
        table: {
            headers: ["方法类型", "代表技术", "优点", "局限"],
            rows: [
                ["传统信用评分", "FICO、收入、负债率", "解释性强，易于理解", "只看个人，忽略环境和周期"],
                ["机器学习预测", "LR、RF、XGBoost、神经网络", "预测能力强，准确率高", "黑盒化，缺乏可解释性"],
                ["多源风险分析", "地区收入、失业率、利率", "视角全面，贴近实际", "数据对齐困难，缺乏控制变量分析"]
            ]
        }
    },
    {
        type: "positioning",
        title: "本研究定位：补充外部维度，强化可解释性",
        points: [
            "不是取代传统方法，而是补充地区经济和宏观周期维度",
            "先做好数据清洗、融合、可解释统计分析，再考虑预测模型",
            "强调多源数据的增量价值和可解释洞察，而非单纯追求预测准确率"
        ]
    },

    // ==================== 数据与方法 ====================
    {
        type: "section",
        title: "数据与方法：四源融合与可解释分析"
    },
    {
        type: "dataSources",
        title: "四源数据融合：覆盖个人、州级、宏观三个维度",
        sources: [
            { name: "Lending Club", scale: "226万条，151字段", desc: "个体贷款记录、违约标签", status: "✅" },
            { name: "FRED 宏观", scale: "47季度，3指标", desc: "联邦基金利率、CPI、失业率", status: "✅" },
            { name: "USDA ERS", scale: "50州，3指标", desc: "州级收入、贫困率、失业率", status: "✅" },
            { name: "Home Credit", scale: "30万条，122字段", desc: "补充信贷场景对照", status: "✅" }
        ]
    },
    {
        type: "fusion",
        title: "数据融合成果：136万样本×50州×47季度",
        metrics: [
            { label: "已完结样本", value: "1,367,578 条", desc: "排除Current等未完结状态" },
            { label: "州级覆盖", value: "50 个州", desc: "完整州级匹配" },
            { label: "时间跨度", value: "47 季度", desc: "2007-Q2 至 2018-Q4" },
            { label: "聚合维度", value: "州 + 季度", desc: "双重聚合分析" }
        ]
    },
    {
        type: "methodology",
        title: "方法一：流式处理解决大规模数据加载问题",
        content: {
            problem: "2.8GB CSV文件一次性读取导致内存溢出",
            solution: "使用 pandas.read_csv(chunksize=10000) 逐块处理",
            result: "每次只读1万条，处理完成后丢弃，内存占用始终保持在低水平"
        }
    },
    {
        type: "methodology",
        title: "方法二：严格违约标签构造确保结论可靠性",
        content: {
            problem: "贷款状态有10多种，Current（正在还款）将来是否违约未知",
            solution: "只保留已完结状态：Fully Paid（全额还款）、Charged Off（核销）、Default（违约）",
            result: "从226万条筛选出136万条已完结样本，标签质量显著提高"
        }
    },
    {
        type: "methodology",
        title: "方法三：时间对齐匹配贷款发放时的宏观环境",
        content: {
            problem: "贷款数据跨越2007-2018年，FRED数据为月度频率",
            solution: "FRED月度数据取季度最后一个月值，与贷款发放季度对齐",
            result: "匹配发放时的宏观环境，避免使用未来数据"
        }
    },
    {
        type: "methodology",
        title: "方法四：残差分析证明地区经济的独立解释力",
        content: {
            problem: "观察到贫困率高的州违约率高，但可能是因为这些州高风险贷款更多",
            solution: "残差分析法：①建立利率→违约率模型 ②计算预期违约率 ③残差=实际-预期 ④分析残差与贫困率相关性",
            result: "控制利率后相关性从0.398降至0.362，仍然显著，证明地区经济有独立解释力"
        }
    },

    // ==================== 核心发现 ====================
    {
        type: "section",
        title: "核心发现：五组实证结果"
    },
    {
        type: "chartSlide",
        title: "发现一：贷款等级强区分违约风险，A与G相差8倍",
        chart: "lc_default_rate_by_grade.png",
        findings: [
            "A等级违约率仅6.57%，G等级高达51.57%，相差近8倍",
            "违约率随等级上升呈明显单调递增趋势",
            "Lending Club的风险定价体系是有效的，等级是强分层工具"
        ]
    },
    {
        type: "chartSlide",
        title: "发现二：利率与违约高度相关，反映平台风险定价能力",
        chart: "lc_default_rate_by_interest_bin.png",
        findings: [
            "低利率（<8%）违约率6.38%，高利率（≥24%）违约率48.56%",
            "违约率随利率上升几乎呈线性增长",
            "利率定价已包含风险判断，但仍有额外维度可探索"
        ]
    },
    {
        type: "chartSlide",
        title: "发现三：宏观金融环境与违约率季度相关系数达0.844",
        chart: "lc_fred_quarterly_overlay.png",
        findings: [
            "联邦基金利率与违约率的季度相关系数为0.844，显示高度相关",
            "两条曲线趋势高度一致，反映宏观周期对个人违约的系统性影响",
            "【重要说明】此为相关性分析，不能简单解释为因果关系"
        ]
    },
    {
        type: "chartSlide",
        title: "发现四：地区经济具有独立于个人特征的解释力",
        chart: "lc_state_default_residual_interest_vs_poverty.png",
        findings: [
            "原始相关（贫困率vs违约率）：r = 0.398",
            "控制州级平均利率后：r = 0.362，仍然显著",
            "控制州级平均FICO后：r = 0.459，相关性反而更强",
            "结论：即使信用评分和利率相同，生活在高贫困率州的个人违约风险仍然更高"
        ]
    },
    {
        type: "chartSlide",
        title: "发现五：组合风险分层识别超高风险人群",
        chart: "lc_top_risk_grade_purpose_segments.png",
        findings: [
            "G等级 × debt_consolidation（债务整合）违约率高达52.99%",
            "每两笔此类贷款就有一笔违约，属于极高风险组合",
            "实际应用：风控部门可直接识别此类组合进行严格审核或差异化定价"
        ]
    },

    // ==================== 进度汇报 ====================
    {
        type: "section",
        title: "进度汇报：按计划完成中期目标"
    },
    {
        type: "gantt",
        title: "项目进展：各阶段均按计划完成",
        tasks: [
            { phase: "开题与问题定义", time: "4/20–4/30", status: "✅ 完成" },
            { phase: "项目仓库与数据说明", time: "5/15–5/18", status: "✅ 完成" },
            { phase: "Lending Club EDA", time: "5/18–5/19", status: "✅ 完成" },
            { phase: "FRED/ERS 数据融合", time: "5/19–5/20", status: "✅ 完成" },
            { phase: "风险分层分析", time: "5/20", status: "✅ 完成" },
            { phase: "Home Credit 数据下载", time: "5/20", status: "✅ 完成 当前节点" },
            { phase: "控制变量建模", time: "5/21–5/27", status: "🔄 进行中" },
            { phase: "最终可视化", time: "5/27–6/3", status: "⏳ 计划中" },
            { phase: "最终报告与答辩", time: "6/3–6/17", status: "⏳ 计划中" }
        ]
    },
    {
        type: "whatWorked",
        title: "奏效部分：四项关键技术成功落地",
        successes: [
            { title: "大型CSV流式处理", desc: "使用chunksize=10000逐块处理，避免内存溢出" },
            { title: "贷款状态过滤", desc: "排除Current等未完结状态，确保标签质量" },
            { title: "多源数据融合", desc: "州代码映射和时间对齐逻辑实现正确" },
            { title: "可视化成果", desc: "生成28张图表和45+张统计表" }
        ]
    },
    {
        type: "challenges",
        title: "受阻部分：两项限制均有明确应对方案",
        challenges: [
            {
                title: "限制一：Home Credit需要网页授权",
                desc: "问题：Kaggle API返回403 | 解决：手动接受规则后成功下载 | 影响：不影响主线，HC为可选补充"
            },
            {
                title: "限制二：当前为相关性分析，非因果推断",
                desc: "问题：无法从相关性推断因果关系 | 解决：下一阶段加入控制变量模型，谨慎表述结论"
            }
        ]
    },

    // ==================== 后续计划 ====================
    {
        type: "section",
        title: "后续计划：建模与可视化"
    },
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
            { risk: "Home Credit授权受限", impact: "数据可能无法获取", backup: "已有LC+FRED+ERS主线，HC为可选补充", status: "✅ 已解决" },
            { risk: "相关性≠因果", impact: "解释力度有限", backup: "加入控制变量模型，谨慎表述结论", status: "🔄 进行中" },
            { risk: "时间紧张", impact: "建模可能简化", backup: "保证多源分析完整性，模型可作为扩展", status: "📋 备用" },
            { risk: "多源变量提升不显著", impact: "结论不够强", backup: "强调方法论价值和可解释洞察", status: "📋 备用" }
        ]
    },

    // ==================== 结论 ====================
    {
        type: "conclusions",
        title: "结论：违约风险是个人、地区与宏观的复合结果",
        conclusions: [
            { title: "等级是强风险分层工具", stat: "A等级6.57% vs G等级51.57%，相差8倍" },
            { title: "宏观环境与违约高度相关", stat: "联邦基金利率季度相关系数0.844" },
            { title: "地区经济有独立解释力", stat: "控制贷款结构后，贫困率仍相关0.362" },
            { title: "多源融合能精确识别高风险", stat: "G×debt_consolidation违约率52.99%" }
        ]
    },

    // ==================== 结束页 ====================
    {
        type: "ending",
        title: "感谢聆听，欢迎提问",
        repo: "github.com/Epiphanythu/ai-data-foundation-project",
        email: "项目组邮箱"
    }
];

// ============================================================
// 幻灯片构建函数
// ============================================================

/**
 * 添加标题页
 */
function addTitleSlide(slide) {
    // 主标题
    slide.addText("基于多源数据的个人贷款违约风险检测", {
        x: 0.5, y: 1.5, w: 9, h: 1,
        fontSize: 36, fontFace: FONTS.main, bold: true,
        color: COLORS.navy, align: "center"
    });

    // 副标题
    slide.addText("中期汇报 | 多源数据融合与可解释风险分析", {
        x: 0.5, y: 2.5, w: 9, h: 0.5,
        fontSize: 20, fontFace: FONTS.main,
        color: COLORS.midBlue, align: "center"
    });

    // 分隔线
    slide.addShape(pres.ShapeType.line, {
        x: 3, y: 3.3, w: 4, h: 0,
        line: { color: COLORS.midBlue, width: 2 }
    });

    // 课程信息
    slide.addText("数据科学课程项目", {
        x: 0.5, y: 3.8, w: 9, h: 0.4,
        fontSize: 16, fontFace: FONTS.main,
        color: "666666", align: "center"
    });

    // 汇报人
    slide.addText("汇报人：汇报人A、汇报人B", {
        x: 0.5, y: 5, w: 9, h: 0.4,
        fontSize: 18, fontFace: FONTS.main,
        color: COLORS.navy, align: "center"
    });

    // 日期
    slide.addText("2026年5月21日", {
        x: 0.5, y: 5.5, w: 9, h: 0.4,
        fontSize: 18, fontFace: FONTS.main,
        color: COLORS.navy, align: "center"
    });
}

/**
 * 添加章节分隔页
 */
function addSectionSlide(slide, title) {
    slide.background = { color: COLORS.navy };

    slide.addText(title, {
        x: 0.5, y: 2, w: 9, h: 2,
        fontSize: 32, fontFace: FONTS.main, bold: true,
        color: COLORS.white, align: "center"
    });
}

/**
 * 添加要点页（用于研究动机相关工作）
 */
function addPointsSlide(slide, data) {
    // 标题
    slide.addText(data.title, {
        x: 0.5, y: 0.5, w: 9, h: 0.6,
        fontSize: 24, fontFace: FONTS.main, bold: true,
        color: COLORS.navy
    });

    // 要点列表
    if (data.points) {
        data.points.forEach((point, i) => {
            slide.addText(`• ${point}`, {
                x: 0.8, y: 1.5 + i * 0.7, w: 8.4, h: 0.6,
                fontSize: 20, fontFace: FONTS.main,
                color: "333333"
            });
        });
    }

    // 引子问题（如果有）
    if (data.hook) {
        slide.addShape(pres.ShapeType.rect, {
            x: 0.8, y: 4.2, w: 8.4, h: 1.5,
            fill: { color: "FFF4E6" },
            line: { color: COLORS.midBlue, width: 1 }
        });

        slide.addText(data.hook, {
            x: 1, y: 4.4, w: 8, h: 1.1,
            fontSize: 16, fontFace: FONTS.main, italic: true,
            color: COLORS.navy
        });
    }
}

/**
 * 添加双栏对比页（重要性）
 */
function addTwoColSlide(slide, data) {
    // 标题
    slide.addText(data.title, {
        x: 0.5, y: 0.5, w: 9, h: 0.6,
        fontSize: 24, fontFace: FONTS.main, bold: true,
        color: COLORS.navy
    });

    // 左栏
    slide.addShape(pres.ShapeType.rect, {
        x: 0.7, y: 1.3, w: 4.1, h: 4.5,
        fill: { color: "F0F8FF" },
        line: { color: COLORS.midBlue, width: 1 }
    });

    slide.addText(data.leftCol.heading, {
        x: 0.9, y: 1.5, w: 3.7, h: 0.5,
        fontSize: 20, fontFace: FONTS.main, bold: true,
        color: COLORS.navy
    });

    data.leftCol.points.forEach((point, i) => {
        slide.addText(`• ${point}`, {
            x: 0.9, y: 2.1 + i * 0.7, w: 3.7, h: 0.6,
            fontSize: 16, fontFace: FONTS.main,
            color: "333333"
        });
    });

    // 右栏
    slide.addShape(pres.ShapeType.rect, {
        x: 5.2, y: 1.3, w: 4.1, h: 4.5,
        fill: { color: "FFF8DC" },
        line: { color: COLORS.midBlue, width: 1 }
    });

    slide.addText(data.rightCol.heading, {
        x: 5.4, y: 1.5, w: 3.7, h: 0.5,
        fontSize: 20, fontFace: FONTS.main, bold: true,
        color: COLORS.navy
    });

    data.rightCol.points.forEach((point, i) => {
        slide.addText(`• ${point}`, {
            x: 5.4, y: 2.1 + i * 0.7, w: 3.7, h: 0.6,
            fontSize: 16, fontFace: FONTS.main,
            color: "333333"
        });
    });
}

/**
 * 添加挑战页
 */
function addChallengesSlide(slide, data) {
    // 标题
    slide.addText(data.title, {
        x: 0.5, y: 0.5, w: 9, h: 0.6,
        fontSize: 24, fontFace: FONTS.main, bold: true,
        color: COLORS.navy
    });

    data.challenges.forEach((challenge, i) => {
        const yPos = 1.4 + i * 1.6;

        // 挑战标题
        slide.addText(challenge.title, {
            x: 0.8, y: yPos, w: 8.4, h: 0.4,
            fontSize: 18, fontFace: FONTS.main, bold: true,
            color: COLORS.coral
        });

        // 挑战描述
        slide.addText(challenge.desc, {
            x: 0.8, y: yPos + 0.4, w: 8.4, h: 0.9,
            fontSize: 16, fontFace: FONTS.main,
            color: "333333"
        });
    });
}

/**
 * 添加对比表格页
 */
function addComparisonSlide(slide, data) {
    // 标题
    slide.addText(data.title, {
        x: 0.5, y: 0.5, w: 9, h: 0.6,
        fontSize: 24, fontFace: FONTS.main, bold: true,
        color: COLORS.navy
    });

    // 表格数据
    const tableData = [data.table.headers, ...data.table.rows];

    slide.addTable(tableData, {
        x: 0.8, y: 1.3, w: 8.4,
        border: { pt: 1, color: "CCCCCC" },
        colW: [2, 1.5, 2.2, 2.7],
        fontSize: 14, fontFace: FONTS.main,
        color: "333333",
        fill: { color: "F5F5F5" },
        margin: 6
    });
}

/**
 * 添加定位页
 */
function addPositioningSlide(slide, data) {
    // 标题
    slide.addText(data.title, {
        x: 0.5, y: 0.5, w: 9, h: 0.6,
        fontSize: 24, fontFace: FONTS.main, bold: true,
        color: COLORS.navy
    });

    // 研究定位框
    slide.addShape(pres.ShapeType.rect, {
        x: 0.8, y: 1.3, w: 8.4, h: 4.5,
        fill: { color: "F0F8FF" },
        line: { color: COLORS.midBlue, width: 2 }
    });

    data.points.forEach((point, i) => {
        slide.addText(`• ${point}`, {
            x: 1, y: 1.6 + i * 1.1, w: 8, h: 1,
            fontSize: 18, fontFace: FONTS.main,
            color: COLORS.navy
        });
    });
}

/**
 * 添加数据源页
 */
function addDataSourcesSlide(slide, data) {
    // 标题
    slide.addText(data.title, {
        x: 0.5, y: 0.5, w: 9, h: 0.6,
        fontSize: 24, fontFace: FONTS.main, bold: true,
        color: COLORS.navy
    });

    data.sources.forEach((source, i) => {
        const yPos = 1.4 + i * 1.3;
        const xPos = (i % 2) * 4.7 + 0.8;

        // 数据源框
        slide.addShape(pres.ShapeType.rect, {
            x: xPos, y: yPos, w: 4.1, h: 1.1,
            fill: { color: i % 2 === 0 ? "F0F8FF" : "FFF8DC" },
            line: { color: COLORS.midBlue, width: 1 }
        });

        slide.addText(`${source.status} ${source.name}`, {
            x: xPos + 0.2, y: yPos + 0.1, w: 3.7, h: 0.35,
            fontSize: 16, fontFace: FONTS.main, bold: true,
            color: COLORS.navy
        });

        slide.addText(`${source.scale} | ${source.desc}`, {
            x: xPos + 0.2, y: yPos + 0.5, w: 3.7, h: 0.5,
            fontSize: 13, fontFace: FONTS.main,
            color: "333333"
        });
    });
}

/**
 * 添加融合成果页
 */
function addFusionSlide(slide, data) {
    // 标题
    slide.addText(data.title, {
        x: 0.5, y: 0.5, w: 9, h: 0.6,
        fontSize: 24, fontFace: FONTS.main, bold: true,
        color: COLORS.navy
    });

    data.metrics.forEach((metric, i) => {
        const xPos = (i % 2) * 4.6 + 0.8;
        const yPos = 1.5 + Math.floor(i / 2) * 1.5;

        // 数值
        slide.addText(metric.value, {
            x: xPos, y: yPos, w: 4.4, h: 0.5,
            fontSize: 28, fontFace: FONTS.main, bold: true,
            color: COLORS.coral
        });

        // 标签
        slide.addText(metric.label, {
            x: xPos, y: yPos + 0.5, w: 4.4, h: 0.35,
            fontSize: 16, fontFace: FONTS.main, bold: true,
            color: COLORS.navy
        });

        // 描述
        slide.addText(metric.desc, {
            x: xPos, y: yPos + 0.85, w: 4.4, h: 0.35,
            fontSize: 13, fontFace: FONTS.main,
            color: "666666"
        });
    });
}

/**
 * 添加方法页
 */
function addMethodologySlide(slide, data) {
    // 标题
    slide.addText(data.title, {
        x: 0.5, y: 0.5, w: 9, h: 0.6,
        fontSize: 24, fontFace: FONTS.main, bold: true,
        color: COLORS.navy
    });

    // 问题
    slide.addShape(pres.ShapeType.rect, {
        x: 0.8, y: 1.3, w: 8.4, h: 0.8,
        fill: { color: "FFE6E6" },
        line: { color: COLORS.coral, width: 1 }
    });

    slide.addText("问题", {
        x: 1, y: 1.4, w: 1, h: 0.3,
        fontSize: 14, fontFace: FONTS.main, bold: true,
        color: COLORS.coral
    });

    slide.addText(data.content.problem, {
        x: 1, y: 1.7, w: 8, h: 0.4,
        fontSize: 15, fontFace: FONTS.main,
        color: "333333"
    });

    // 解决方案
    slide.addShape(pres.ShapeType.rect, {
        x: 0.8, y: 2.3, w: 8.4, h: 1.2,
        fill: { color: "E6F7FF" },
        line: { color: COLORS.midBlue, width: 1 }
    });

    slide.addText("解决方案", {
        x: 1, y: 2.4, w: 1.5, h: 0.3,
        fontSize: 14, fontFace: FONTS.main, bold: true,
        color: COLORS.midBlue
    });

    slide.addText(data.content.solution, {
        x: 1, y: 2.7, w: 8, h: 0.8,
        fontSize: 15, fontFace: FONTS.main,
        color: "333333"
    });

    // 结果
    slide.addShape(pres.ShapeType.rect, {
        x: 0.8, y: 3.7, w: 8.4, h: 1,
        fill: { color: "E8F5E9" },
        line: { color: "4CAF50", width: 1 }
    });

    slide.addText("结果", {
        x: 1, y: 3.8, w: 1, h: 0.3,
        fontSize: 14, fontFace: FONTS.main, bold: true,
        color: "4CAF50"
    });

    slide.addText(data.content.result, {
        x: 1, y: 4.1, w: 8, h: 0.6,
        fontSize: 15, fontFace: FONTS.main,
        color: "333333"
    });
}

/**
 * 添加图表页（核心发现）
 */
function addChartSlide(slide, data) {
    // 检查图片文件是否存在
    const imgPath = path.join(FIGURES_PATH, data.chart);
    const imgExists = fs.existsSync(imgPath);

    // 标题
    slide.addText(data.title, {
        x: 0.5, y: 0.5, w: 9, h: 0.6,
        fontSize: 22, fontFace: FONTS.main, bold: true,
        color: COLORS.navy
    });

    if (imgExists) {
        // 图片在左侧
        slide.addImage({
            path: imgPath,
            x: 0.5, y: 1.3, w: 5.5, h: 4.5,
            sizing: { type: "contain", w: 5.5, h: 4.5 }
        });

        // 发现要点在右侧
        slide.addShape(pres.ShapeType.rect, {
            x: 6.2, y: 1.3, w: 3.3, h: 4.5,
            fill: { color: "F8F9FA" },
            line: { color: COLORS.midBlue, width: 1 }
        });

        slide.addText("核心发现", {
            x: 6.4, y: 1.5, w: 2.9, h: 0.35,
            fontSize: 16, fontFace: FONTS.main, bold: true,
            color: COLORS.navy
        });

        data.findings.forEach((finding, i) => {
            slide.addText(`• ${finding}`, {
                x: 6.4, y: 1.95 + i * 1.1, w: 2.9, h: 1,
                fontSize: 13, fontFace: FONTS.main,
                color: "333333"
            });
        });
    } else {
        // 图片不存在时的后备方案
        slide.addShape(pres.ShapeType.rect, {
            x: 0.5, y: 1.3, w: 5.5, h: 4.5,
            fill: { color: "EEEEEE" },
            line: { color: "CCCCCC", width: 1, dashType: "dash" }
        });

        slide.addText(`图表: ${data.chart}`, {
            x: 0.5, y: 3, w: 5.5, h: 0.5,
            fontSize: 16, fontFace: FONTS.main,
            color: "666666", align: "center"
        });

        // 发现要点占满宽度
        data.findings.forEach((finding, i) => {
            slide.addText(`• ${finding}`, {
                x: 6.2, y: 1.5 + i * 1.1, w: 3.3, h: 1,
                fontSize: 14, fontFace: FONTS.main,
                color: "333333"
            });
        });
    }
}

/**
 * 添加甘特图页
 */
function addGanttSlide(slide, data) {
    // 标题
    slide.addText(data.title, {
        x: 0.5, y: 0.5, w: 9, h: 0.6,
        fontSize: 24, fontFace: FONTS.main, bold: true,
        color: COLORS.navy
    });

    // 任务列表
    const tableData = [
        [
            { text: "阶段", options: { fontSize: 14, fontFace: FONTS.main, bold: true, color: COLORS.white } },
            { text: "时间", options: { fontSize: 14, fontFace: FONTS.main, bold: true, color: COLORS.white } },
            { text: "状态", options: { fontSize: 14, fontFace: FONTS.main, bold: true, color: COLORS.white } }
        ],
        ...data.tasks.map(task => [
            task.phase,
            task.time,
            { text: task.status, options: { fontSize: 13, fontFace: FONTS.main, color: task.status.includes("✅") ? "4CAF50" : task.status.includes("🔄") ? "FF9800" : "999999" } }
        ])
    ];

    slide.addTable(tableData, {
        x: 0.8, y: 1.3, w: 8.4,
        border: { pt: 1, color: "CCCCCC" },
        colW: [3.5, 2.5, 2.4],
        fontSize: 14, fontFace: FONTS.main,
        color: "333333",
        fill: { color: COLORS.navy },
        margin: 8
    });
}

/**
 * 添加奏效部分页
 */
function addWhatWorkedSlide(slide, data) {
    // 标题
    slide.addText(data.title, {
        x: 0.5, y: 0.5, w: 9, h: 0.6,
        fontSize: 24, fontFace: FONTS.main, bold: true,
        color: COLORS.navy
    });

    data.successes.forEach((success, i) => {
        const xPos = (i % 2) * 4.6 + 0.8;
        const yPos = 1.5 + Math.floor(i / 2) * 1.4;

        // 成功框
        slide.addShape(pres.ShapeType.rect, {
            x: xPos, y: yPos, w: 4.1, h: 1.2,
            fill: { color: "E8F5E9" },
            line: { color: "4CAF50", width: 2 }
        });

        slide.addText(`✓ ${success.title}`, {
            x: xPos + 0.2, y: yPos + 0.15, w: 3.7, h: 0.4,
            fontSize: 16, fontFace: FONTS.main, bold: true,
            color: "2E7D32"
        });

        slide.addText(success.desc, {
            x: xPos + 0.2, y: yPos + 0.55, w: 3.7, h: 0.6,
            fontSize: 13, fontFace: FONTS.main,
            color: "333333"
        });
    });
}

/**
 * 添加时间线页
 */
function addTimelineSlide(slide, data) {
    // 标题
    slide.addText(data.title, {
        x: 0.5, y: 0.5, w: 9, h: 0.6,
        fontSize: 24, fontFace: FONTS.main, bold: true,
        color: COLORS.navy
    });

    data.phases.forEach((phase, i) => {
        const yPos = 1.4 + i * 1.5;

        // 时间标签
        slide.addShape(pres.ShapeType.rect, {
            x: 0.8, y: yPos, w: 1.5, h: 1.2,
            fill: { color: COLORS.midBlue },
            line: { color: COLORS.midBlue, width: 1 }
        });

        slide.addText(phase.time.replace(/\//g, "\n"), {
            x: 0.9, y: yPos + 0.2, w: 1.3, h: 0.8,
            fontSize: 12, fontFace: FONTS.main, bold: true,
            color: COLORS.white, align: "center"
        });

        // 任务详情
        slide.addText(phase.task, {
            x: 2.5, y: yPos + 0.1, w: 2.5, h: 0.4,
            fontSize: 16, fontFace: FONTS.main, bold: true,
            color: COLORS.navy
        });

        slide.addText(`负责人: ${phase.owner}`, {
            x: 2.5, y: yPos + 0.5, w: 2.5, h: 0.3,
            fontSize: 13, fontFace: FONTS.main,
            color: "666666"
        });

        slide.addText(`产出: ${phase.output}`, {
            x: 2.5, y: yPos + 0.8, w: 6, h: 0.5,
            fontSize: 13, fontFace: FONTS.main,
            color: "333333"
        });
    });
}

/**
 * 添加风险页
 */
function addRisksSlide(slide, data) {
    // 标题
    slide.addText(data.title, {
        x: 0.5, y: 0.5, w: 9, h: 0.6,
        fontSize: 24, fontFace: FONTS.main, bold: true,
        color: COLORS.navy
    });

    data.risks.forEach((risk, i) => {
        const yPos = 1.3 + i * 1.3;

        // 风险行
        slide.addShape(pres.ShapeType.rect, {
            x: 0.8, y: yPos, w: 8.4, h: 1.1,
            fill: { color: risk.status.includes("✅") ? "E8F5E9" : risk.status.includes("🔄") ? "FFF3E0" : "FFF9C4" },
            line: { color: risk.status.includes("✅") ? "4CAF50" : risk.status.includes("🔄") ? "FF9800" : "FBC02D", width: 1 }
        });

        slide.addText(`${risk.status} ${risk.risk}`, {
            x: 1, y: yPos + 0.1, w: 8, h: 0.35,
            fontSize: 14, fontFace: FONTS.main, bold: true,
            color: COLORS.navy
        });

        slide.addText(`影响: ${risk.impact}`, {
            x: 1, y: yPos + 0.45, w: 4, h: 0.25,
            fontSize: 12, fontFace: FONTS.main,
            color: "666666"
        });

        slide.addText(`备选: ${risk.backup}`, {
            x: 1, y: yPos + 0.7, w: 8, h: 0.3,
            fontSize: 12, fontFace: FONTS.main,
            color: "333333"
        });
    });
}

/**
 * 添加结论页
 */
function addConclusionsSlide(slide, data) {
    slide.background = { color: COLORS.navy };

    slide.addText(data.title, {
        x: 0.5, y: 0.5, w: 9, h: 0.6,
        fontSize: 28, fontFace: FONTS.main, bold: true,
        color: COLORS.white, align: "center"
    });

    data.conclusions.forEach((concl, i) => {
        const yPos = 1.5 + i * 1.3;

        slide.addText(`${concl.title}`, {
            x: 0.8, y: yPos, w: 8.4, h: 0.4,
            fontSize: 18, fontFace: FONTS.main, bold: true,
            color: COLORS.white
        });

        slide.addText(concl.stat, {
            x: 0.8, y: yPos + 0.4, w: 8.4, h: 0.5,
            fontSize: 20, fontFace: FONTS.main,
            color: "FFD54F"
        });
    });
}

/**
 * 添加结束页
 */
function addEndingSlide(slide, data) {
    slide.background = { color: COLORS.navy };

    slide.addText(data.title, {
        x: 0.5, y: 2.5, w: 9, h: 1,
        fontSize: 36, fontFace: FONTS.main, bold: true,
        color: COLORS.white, align: "center"
    });

    slide.addShape(pres.ShapeType.line, {
        x: 3, y: 3.8, w: 4, h: 0,
        line: { color: COLORS.white, width: 2 }
    });

    slide.addText(`项目仓库: ${data.repo}`, {
        x: 0.5, y: 4.2, w: 9, h: 0.5,
        fontSize: 18, fontFace: FONTS.main,
        color: COLORS.white, align: "center"
    });

    slide.addText("欢迎提问与交流", {
        x: 0.5, y: 5, w: 9, h: 0.5,
        fontSize: 16, fontFace: FONTS.main,
        color: "FFD54F", align: "center"
    });
}

// ============================================================
// 主构建逻辑
// ============================================================

// 遍历幻灯片列表并生成
slides.forEach((slideData, index) => {
    const slide = pres.addSlide();

    switch (slideData.type) {
        case "title":
            addTitleSlide(slide, slideData);
            break;
        case "section":
            addSectionSlide(slide, slideData.title);
            break;
        case "motivation":
            addPointsSlide(slide, slideData);
            break;
        case "importance":
            addTwoColSlide(slide, slideData);
            break;
        case "challenges":
            addChallengesSlide(slide, slideData);
            break;
        case "comparison":
            addComparisonSlide(slide, slideData);
            break;
        case "positioning":
            addPositioningSlide(slide, slideData);
            break;
        case "dataSources":
            addDataSourcesSlide(slide, slideData);
            break;
        case "fusion":
            addFusionSlide(slide, slideData);
            break;
        case "methodology":
            addMethodologySlide(slide, slideData);
            break;
        case "chartSlide":
            addChartSlide(slide, slideData);
            break;
        case "gantt":
            addGanttSlide(slide, slideData);
            break;
        case "whatWorked":
            addWhatWorkedSlide(slide, slideData);
            break;
        case "timeline":
            addTimelineSlide(slide, slideData);
            break;
        case "risks":
            addRisksSlide(slide, slideData);
            break;
        case "conclusions":
            addConclusionsSlide(slide, slideData);
            break;
        case "ending":
            addEndingSlide(slide, slideData);
            break;
        default:
            // 默认添加标题
            slide.addText(slideData.title || "", {
                x: 0.5, y: 0.5, w: 9, h: 0.6,
                fontSize: 24, fontFace: FONTS.main, bold: true,
                color: COLORS.navy
            });
    }
});

// 保存文件
const outputPath = "/Users/bytedance/Desktop/DB/slides/midterm_academic.pptx";
pres.writeFile({ fileName: outputPath })
    .then(fileName => {
        console.log(`PPT已成功生成: ${fileName}`);
    })
    .catch(err => {
        console.error("生成PPT时出错:", err);
    });
