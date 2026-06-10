from app.scraping import PublicEvidenceCrawler, _fill_financial_notice_dates


def test_public_evidence_crawler_extracts_structured_rows_from_html():
    html_by_url = {
        "eastmoney": """
        <html><body>
          <div>2026-06-08</div>
          <a href="/news/1">五一视界 获机构关注 订单增长明显</a>
          <p>新闻提到五一视界 06651.HK 的行业合作和需求变化。</p>
          <div>2026/06/07</div>
          <a href="/notice/2">五一视界 关于业绩预告的公告</a>
          <p>公告披露业绩预告和经营进展。</p>
        </body></html>
        """,
        "cninfo": """
        <html><body>
          <a href="/disclosure/3">五一视界 回购事项公告</a>
          <span>2026年06月06日</span>
        </body></html>
        """,
    }

    def fetch_html(url: str) -> str:
        if "eastmoney" in url:
            return html_by_url["eastmoney"]
        return html_by_url["cninfo"]

    crawler = PublicEvidenceCrawler(fetch_html=fetch_html)
    bundle = crawler.crawl(market="港股", symbol="06651", name="五一视界")

    assert "结构化补采" in bundle.source_note
    assert not bundle.news_rows.empty
    assert not bundle.announcement_rows.empty
    assert "新闻标题" in bundle.news_rows.columns
    assert "公告标题" in bundle.announcement_rows.columns
    assert bundle.news_rows.iloc[0]["url"].startswith("https://")
    assert bundle.announcement_rows.iloc[0]["采集时间"]


def test_financial_notice_date_is_calibrated_from_same_target_announcement():
    financial_rows = [
        {
            "报告期": "2025-12-31",
            "公告日期": "",
            "披露日期": "",
            "来源": "东方财富财务接口/RPT_HKF10_FN_MAININDICATOR",
        }
    ]
    announcement_rows = [
        {
            "title": "截至2025年12月31日止年度之年度业绩公告",
            "published_at": "2026-03-25 18:30:00",
        }
    ]

    _fill_financial_notice_dates(financial_rows, announcement_rows)

    assert financial_rows[0]["公告日期"] == "2026-03-25 18:30:00"
    assert financial_rows[0]["披露日期"] == "2026-03-25 18:30:00"
    assert "披露时点由同标的公告校准" in str(financial_rows[0]["来源"])
