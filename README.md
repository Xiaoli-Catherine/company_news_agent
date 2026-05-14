# Company Stock News Agent

一个用于搜索指定公司股票相关新闻、用 LLM 汇总新闻要点、并生成 HTML 和 PDF 报告的 Agent 框架。

默认关注：

| Company | Ticker |
| --- | --- |
| Google / Alphabet | GOOG |
| Amazon | AMZN |
| Apple | AAPL |
| Robinhood | HOOD |

## 功能

- 从 Google News RSS 搜索公司事件导向关键词
- 默认保留昨天、今天、明天三天发布的新闻，按 `America/Los_Angeles` 时区判断日期
- 在投喂 LLM 前过滤掉标题/摘要明确显示事件发生在日期窗口外的新闻
- 在投喂 LLM 前过滤掉明显的股价波动、分析师评级、技术面、股票推荐、公司文化和职场排名类噪音
- LLM 翻译阶段会再判断一次事件是否属于日期窗口，不属于则不进入后续整合
- LLM 翻译阶段会再判断是否是具体公司事件；非事件型股价/文化/评论新闻不进入后续整合
- 对新闻去重、排序、保留标题、来源、时间和链接
- 在每个整合新闻事件内部按媒体来源去重，同一媒体只保留最新一条
- 使用 LLM 将每条新闻标题和摘要翻译成中文
- 使用 LLM 将多个媒体报道的同一新闻事件整合成一条新闻
- 每条整合新闻的新闻总结限制在 10 句话以内
- 使用 LLM 生成每家公司的中文新闻概况、股票相关影响和来源索引
- 生成包含 emoji 图标、中文摘要、整合新闻、原文标题和所有报道媒体链接的 HTML
- 使用 ReportLab 直接生成 PDF，并将 emoji 作为 PNG 图片嵌入，避免 PDF 字体不显示 emoji
- PDF 中每条整合新闻最多展开 5 个来源，更多来源以“另有 N 个来源”概括；HTML 保留完整来源
- 没有 LLM API key 时自动使用基础规则摘要，便于本地调试，但不会翻译新闻

## 项目结构

```text
.
├── README.md
├── requirements.txt
├── .env.example
└── src
    └── company_news_agent
        ├── __init__.py
        ├── agent.py
        ├── config.py
        ├── html_report.py
        ├── llm.py
        ├── news.py
        ├── pdf_report.py
        └── types.py
```

## 安装

建议使用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

复制环境变量模板：

```bash
cp .env.example .env
```

如果要启用 LLM 汇总，在 `.env` 中填入：

```bash
OPENAI_API_KEY=your_api_key_here
```

## 运行

生成默认三家公司报告：

```bash
python -m src.company_news_agent.agent
```

指定输出路径：

```bash
python -m src.company_news_agent.agent \
  --html-output reports/mag7-news.html \
  --output reports/mag7-news.pdf
```

如需临时限制每家公司新闻数量：

```bash
python -m src.company_news_agent.agent --max-items 8
```

查看最近多天新闻，而不是使用默认日期窗口：

```bash
python -m src.company_news_agent.agent --all-recent --days 14
```

指定日期窗口的中心日期或时区：

```bash
python -m src.company_news_agent.agent --today-date 2026-05-10 --timezone America/Los_Angeles
```

只看中心日期当天：

```bash
python -m src.company_news_agent.agent --date-window-days 0
```

只跑部分股票：

```bash
python -m src.company_news_agent.agent --tickers GOOG AAPL
```

## 配置

主要配置在 [src/company_news_agent/config.py](src/company_news_agent/config.py)：

- `COMPANIES`: 公司名称和股票代码
- `COMPANIES.icon`: HTML/PDF 中区分不同公司的 emoji 图标
- `STOCK_KEYWORDS`: 公司事件导向搜索关键词
- `DEFAULT_MAX_ITEMS_PER_COMPANY`: 每家公司保留新闻数量，默认 `None` 表示不限制
- `DEFAULT_LOOKBACK_DAYS`: 使用 `--all-recent` 时的默认新闻时间窗口
- `DEFAULT_DATE_WINDOW_DAYS`: 默认日期窗口，`1` 表示昨天、今天、明天
- `DEFAULT_TIMEZONE`: 判断新闻日期的默认时区
- `DEFAULT_HTML_OUTPUT_PATH`: 默认 HTML 报告路径

## Agent 工作流

1. 为每家公司组合事件导向搜索词，例如 `Apple AAPL earnings acquisition lawsuit product launch partnership`
2. 从 Google News RSS 拉取候选新闻
3. 默认只保留昨天、今天、明天发布的新闻
4. 如果标题/摘要明确提到旧事件日期，例如 `last week`、`last month`、`May 7` 或 `2026-05-08` 且不在日期窗口内，则在投喂 LLM 前过滤掉
5. 如果标题/摘要明显只是股价波动、分析师评级、技术面、股票推荐、公司文化或职场排名，则在投喂 LLM 前过滤掉
6. 按链接和标题做基础去重，并按发布时间排序
7. 将每条新闻标题和摘要交给 LLM 翻译成中文，并让 LLM 再判断事件是否属于日期窗口、是否是具体公司事件
8. 过滤掉 LLM 判断为窗口外事件或非公司具体事件的新闻
9. 将同一事件的多个媒体报道整合成一个新闻主题
10. 在每个整合新闻事件内部按媒体来源去重，同一媒体只保留最新一条
11. 将整合后的新闻主题、来源和链接交给 LLM 生成公司层面的摘要
12. 把每家公司中文摘要、整合新闻、原文标题和所有报道媒体列表写入 HTML
13. 用 ReportLab 直接生成 PDF，emoji 图标会作为图片嵌入

## 中文翻译说明

完整中文报告需要安装依赖并配置 `OPENAI_API_KEY`。Agent 会保留原文标题和原始链接，方便回看来源；HTML/PDF 中优先展示整合后的中文新闻主题、中文总结，以及报道该主题的媒体列表。

## HTML 和 PDF

Agent 默认会生成：

```text
reports/company-stock-news.html
reports/company-stock-news.pdf
```

HTML 由 [src/company_news_agent/html_report.py](src/company_news_agent/html_report.py) 生成，保留 emoji 字符，方便浏览器查看。

PDF 由 [src/company_news_agent/pdf_report.py](src/company_news_agent/pdf_report.py) 直接生成，不调用 Chrome，也不依赖 HTML 转换。PDF 中的 emoji 会下载并缓存为 PNG 图片，默认缓存目录是：

```text
assets/emoji/
```

如果没有配置 `OPENAI_API_KEY`，Agent 仍可运行并生成报告，但新闻标题会保持原文，报告中会提示 LLM 翻译和整合未启用。

## 后续可扩展方向

- 接入 NewsAPI、SerpAPI、Tavily 或付费财经新闻源
- 增加股价数据源，把新闻和股价波动放在同一份报告
- 加入定时任务，每天开盘前自动生成报告
- 增加邮件、Slack 或 Notion 投递
- 添加更严格的来源可信度评分和重复报道合并逻辑
