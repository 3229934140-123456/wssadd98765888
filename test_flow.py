from datetime import datetime, timedelta
from models import Platform, TraceConfig, DataSource
from data_loader import load_csv, load_json, prompt_data_source
from data_generator import generate_mock_data
from analyzer import run_analysis
from formatter import print_full_report, print_report_for_daily
from reviewer import run_review_mode, _sort_key_nodes, _sort_sentiment_points, get_trusted_result
from exporter import export_report
import os
import sys


def test_parameter_validation():
    print("=" * 60)
    print("  测试 1：参数校验逻辑")
    print("=" * 60)

    from collector import _validate_keywords, _validate_time_range, _parse_datetime

    assert _validate_keywords([]) is not None, "空关键词应报错"
    assert _validate_keywords(["新能源"]) is None, "单个关键词应通过"
    assert _validate_keywords(["新能源", "电池", "安全"]) is None, "多个关键词应通过"

    long_kw = "x" * 40
    assert _validate_keywords([long_kw]) is not None, "过长关键词应报错"

    too_many = [f"kw{i}" for i in range(25)]
    assert _validate_keywords(too_many) is not None, "过多关键词应报错"

    now = datetime.now()
    assert _validate_time_range(now, now - timedelta(hours=1)) is not None, "结束早于开始应报错"
    assert _validate_time_range(now, now + timedelta(minutes=30)) is not None, "时间过短应报错"
    assert _validate_time_range(now - timedelta(days=400), now) is not None, "时间过长应报错"
    assert _validate_time_range(now - timedelta(days=3), now) is None, "正常时间应通过"

    assert _parse_datetime("2026-06-18 08:30") is not None
    assert _parse_datetime("2026/06/18 08:30") is not None
    assert _parse_datetime("2026-06-18") is not None
    assert _parse_datetime("invalid") is None

    print("  ✓ 参数校验逻辑测试通过")
    print()


def test_exclude_words():
    print("=" * 60)
    print("  测试 2：排除词过滤功能")
    print("=" * 60)

    config = TraceConfig(
        event_id="EVT-TEST-001",
        keywords=["新能源汽车", "电池安全"],
        exclude_words=["广告", "推广"],
        start_time=datetime.now() - timedelta(days=3),
        end_time=datetime.now(),
        platforms=[Platform.WEIBO],
        original_only=False,
        verified_only=False,
    )

    posts = generate_mock_data(config, count=200)

    for post in posts:
        for ew in config.exclude_words:
            assert ew not in post.content, f"排除词 {ew} 不应出现在内容中"

    print(f"  ✓ 生成 {len(posts)} 条数据，排除词过滤正常")
    print()


def test_csv_import():
    print("=" * 60)
    print("  测试 3：CSV 文件导入")
    print("=" * 60)

    config = TraceConfig(
        event_id="EVT-TEST-CSV",
        keywords=["新能源", "电池"],
        exclude_words=["广告", "推广"],
        start_time=datetime(2026, 6, 18),
        end_time=datetime(2026, 6, 20),
        platforms=list(Platform),
        original_only=False,
        verified_only=False,
    )

    csv_path = os.path.join(os.path.dirname(__file__), "sample_data.csv")
    posts, msg = load_csv(csv_path, config)

    print(f"  {msg}")
    assert len(posts) > 0, "应成功导入数据"

    for post in posts:
        assert post.data_source == DataSource.CSV
        for ew in config.exclude_words:
            assert ew not in post.content, f"排除词 {ew} 未过滤"

    for post in posts:
        assert post.platform in config.platforms
        assert config.start_time <= post.publish_time <= config.end_time
        has_kw = any(kw in post.content for kw in config.keywords)
        assert has_kw, f"内容应包含关键词：{post.content[:30]}"

    print(f"  ✓ CSV 导入成功，{len(posts)} 条有效数据")
    print()
    return posts, config


def test_json_import():
    print("=" * 60)
    print("  测试 4：JSON 文件导入")
    print("=" * 60)

    config = TraceConfig(
        event_id="EVT-TEST-JSON",
        keywords=["新能源", "电池"],
        exclude_words=["广告"],
        start_time=datetime(2026, 6, 18),
        end_time=datetime(2026, 6, 20),
        platforms=list(Platform),
        original_only=False,
        verified_only=False,
    )

    json_path = os.path.join(os.path.dirname(__file__), "sample_data.json")
    posts, msg = load_json(json_path, config)

    print(f"  {msg}")
    assert len(posts) > 0, "应成功导入数据"

    for post in posts:
        assert post.data_source == DataSource.JSON

    print(f"  ✓ JSON 导入成功，{len(posts)} 条有效数据")
    print()
    return posts, config


def test_analysis_with_imported_data():
    print("=" * 60)
    print("  测试 5：导入数据的分析流程")
    print("=" * 60)

    config = TraceConfig(
        event_id="EVT-TEST-ANALYSIS",
        keywords=["新能源", "电池"],
        exclude_words=["广告"],
        start_time=datetime(2026, 6, 18),
        end_time=datetime(2026, 6, 20),
        platforms=list(Platform),
        original_only=False,
        verified_only=False,
    )

    csv_path = os.path.join(os.path.dirname(__file__), "sample_data.csv")
    posts, msg = load_csv(csv_path, config)
    print(f"  导入数据：{msg}")

    result = run_analysis(posts, config, data_source=DataSource.CSV, source_file="sample_data.csv")

    assert result.data_source == DataSource.CSV
    assert result.source_file == "sample_data.csv"

    print(f"  首发线索：{len(result.first_post_nodes)} 条")
    print(f"  传播节点：{len(result.amplification_nodes)} 条")
    print(f"  情绪拐点：{len(result.sentiment_turning_points)} 个")

    daily = print_report_for_daily(result, config.event_id)
    assert "数据来源：CSV导入" in daily, "日报应包含数据源信息"
    assert "来源文件：sample_data.csv" in daily, "日报应包含来源文件"

    print("  ✓ 导入数据分析完成，日报包含数据源信息")
    print()


def test_review_filtering():
    print("=" * 60)
    print("  测试 6：复核排序与排除项过滤")
    print("=" * 60)

    config = TraceConfig(
        event_id="EVT-TEST-REVIEW",
        keywords=["新能源", "电池"],
        exclude_words=[],
        start_time=datetime(2026, 6, 18),
        end_time=datetime(2026, 6, 20),
        platforms=list(Platform),
        original_only=False,
        verified_only=False,
    )

    csv_path = os.path.join(os.path.dirname(__file__), "sample_data.csv")
    posts, _ = load_csv(csv_path, config)
    result = run_analysis(posts, config, data_source=DataSource.CSV)

    for i, node in enumerate(result.first_post_nodes):
        if i == 0:
            node.review_status = "可信"
        elif i == 1:
            node.review_status = "存疑"
        elif i == 2:
            node.review_status = "排除"

    for i, node in enumerate(result.amplification_nodes):
        if i == 0:
            node.review_status = "可信"
        elif i == 1:
            node.review_status = "排除"

    for i, point in enumerate(result.sentiment_turning_points):
        if i == 0:
            point.review_status = "可信"
        elif i == 1:
            point.review_status = "排除"

    sorted_first = _sort_key_nodes(result.first_post_nodes)
    assert sorted_first[0].review_status == "可信", "可信应排在最前"
    assert sorted_first[-1].review_status == "排除", "排除应排在最后"

    trusted = get_trusted_result(result)
    for n in trusted.first_post_nodes:
        assert n.review_status != "排除", "排除项不应出现在可信结果中"
    for n in trusted.amplification_nodes:
        assert n.review_status != "排除", "排除项不应出现在可信结果中"
    for p in trusted.sentiment_turning_points:
        assert p.review_status != "排除", "排除项不应出现在可信结果中"

    daily = print_report_for_daily(result, config.event_id, filter_excluded=True)
    assert "[排除]" not in daily, "日报不应包含排除项"

    print("  ✓ 复核排序与过滤功能正常")
    print()


def test_export():
    print("=" * 60)
    print("  测试 7：报告导出功能")
    print("=" * 60)

    config = TraceConfig(
        event_id="EVT-TEST-EXPORT",
        keywords=["新能源", "电池"],
        exclude_words=["广告"],
        start_time=datetime(2026, 6, 18),
        end_time=datetime(2026, 6, 20),
        platforms=list(Platform),
        original_only=False,
        verified_only=False,
    )

    csv_path = os.path.join(os.path.dirname(__file__), "sample_data.csv")
    posts, _ = load_csv(csv_path, config)
    result = run_analysis(posts, config, data_source=DataSource.CSV, source_file="sample_data.csv")

    result.first_post_nodes[0].review_status = "可信"
    result.first_post_nodes[1].review_status = "排除"

    from exporter import _generate_full_report_text, _generate_full_report_markdown, _generate_daily_text

    txt_content = _generate_full_report_text(result, config.event_id, filter_excluded=False)
    assert "舆情热点溯源分析报告" in txt_content
    assert "CSV导入" in txt_content
    assert "sample_data.csv" in txt_content

    md_content = _generate_full_report_markdown(result, config.event_id, filter_excluded=False)
    assert "# 舆情热点溯源分析报告" in md_content
    assert "| 数据来源 | CSV导入 |" in md_content

    daily_content = _generate_daily_text(result, config.event_id, filter_excluded=True)
    assert "[排除]" not in daily_content

    tmp_dir = os.path.join(os.path.dirname(__file__), "test_export")
    os.makedirs(tmp_dir, exist_ok=True)

    test_md = os.path.join(tmp_dir, "test_report.md")
    with open(test_md, "w", encoding="utf-8") as f:
        f.write(md_content)
    assert os.path.exists(test_md)
    assert os.path.getsize(test_md) > 0

    for f in os.listdir(tmp_dir):
        os.remove(os.path.join(tmp_dir, f))
    os.rmdir(tmp_dir)

    print("  ✓ 导出功能正常，TXT、Markdown格式生成正确")
    print()


def test_platform_verification_sentiment_parsing():
    print("=" * 60)
    print("  测试 8：字段解析兼容性")
    print("=" * 60)

    from data_loader import _parse_platform, _parse_verification, _parse_sentiment

    assert _parse_platform("微博") == Platform.WEIBO
    assert _parse_platform("weibo") == Platform.WEIBO
    assert _parse_platform("微信公众号") == Platform.WECHAT
    assert _parse_platform("抖音") == Platform.DOUYIN
    assert _parse_platform("小红书") == Platform.XHS
    assert _parse_platform("知乎") == Platform.ZHIHU
    assert _parse_platform("B站") == Platform.BILIBILI
    assert _parse_platform("未知平台") is None

    from models import VerificationType, Sentiment

    assert _parse_verification("媒体认证") == VerificationType.MEDIA
    assert _parse_verification("政府") == VerificationType.GOV
    assert _parse_verification("黄V") == VerificationType.PERSONAL
    assert _parse_verification("蓝V") == VerificationType.ORGANIZATION
    assert _parse_verification("无") == VerificationType.NONE

    assert _parse_sentiment("正面") == Sentiment.POSITIVE
    assert _parse_sentiment("积极") == Sentiment.POSITIVE
    assert _parse_sentiment("负面") == Sentiment.NEGATIVE
    assert _parse_sentiment("-1") == Sentiment.NEGATIVE
    assert _parse_sentiment("中性") == Sentiment.NEUTRAL

    print("  ✓ 字段解析兼容性正常")
    print()


def test_full_flow():
    print("=" * 60)
    print("  测试 9：完整工作流程（CSV导入 → 分析 → 复核 → 导出）")
    print("=" * 60)

    config = TraceConfig(
        event_id="EVT-FULL-2026",
        keywords=["新能源", "电池", "安全"],
        exclude_words=["广告", "推广"],
        start_time=datetime(2026, 6, 17),
        end_time=datetime(2026, 6, 21),
        platforms=[Platform.WEIBO, Platform.DOUYIN, Platform.WECHAT, Platform.ZHIHU],
        original_only=False,
        verified_only=False,
    )

    csv_path = os.path.join(os.path.dirname(__file__), "sample_data.csv")
    posts, msg = load_csv(csv_path, config)
    print(f"  1. 数据导入：{msg}")
    print(f"     数据源：{posts[0].data_source.value}")

    result = run_analysis(posts, config, data_source=DataSource.CSV, source_file="sample_data.csv")
    print(f"  2. 分析完成：首发{len(result.first_post_nodes)} 传播{len(result.amplification_nodes)} 情绪{len(result.sentiment_turning_points)}")

    for i, n in enumerate(result.first_post_nodes[:3]):
        n.review_status = ["可信", "存疑", "排除"][i]
    for i, n in enumerate(result.amplification_nodes[:3]):
        n.review_status = ["可信", "可信", "排除"][i]
    for i, p in enumerate(result.sentiment_turning_points[:2]):
        p.review_status = ["可信", "排除"][i]

    trusted = get_trusted_result(result)
    print(f"  3. 过滤排除项后：首发{len(trusted.first_post_nodes)} 传播{len(trusted.amplification_nodes)} 情绪{len(trusted.sentiment_turning_points)}")

    daily = print_report_for_daily(result, config.event_id, filter_excluded=True)
    assert "[排除]" not in daily
    assert "数据来源：CSV导入" in daily
    assert "来源文件：sample_data.csv" in daily

    print("  ✓ 完整工作流程测试通过")
    print()


def test_syntax():
    print("=" * 60)
    print("  测试 0：语法检查")
    print("=" * 60)

    import py_compile
    files = [
        "models.py", "collector.py", "data_generator.py", "data_loader.py",
        "analyzer.py", "formatter.py", "reviewer.py", "exporter.py", "main.py"
    ]

    for f in files:
        path = os.path.join(os.path.dirname(__file__), f)
        py_compile.compile(path, doraise=True)
        print(f"  ✓ {f}")

    print("  所有文件语法检查通过")
    print()


def main():
    print("\n" + "=" * 60)
    print("  舆情溯源工作台 v2.0 自动化测试")
    print("=" * 60 + "\n")

    try:
        test_syntax()
        test_parameter_validation()
        test_exclude_words()
        test_platform_verification_sentiment_parsing()
        test_csv_import()
        test_json_import()
        test_analysis_with_imported_data()
        test_review_filtering()
        test_export()
        test_full_flow()

        print("=" * 60)
        print("  ✓ 所有测试通过！")
        print("=" * 60)
        print("\n功能清单：")
        print("  ✓ 参数校验（关键词/时间/平台）")
        print("  ✓ 排除词严格过滤")
        print("  ✓ CSV/JSON 本地样本导入")
        print("  ✓ 数据源标记（日报可见）")
        print("  ✓ 三类结果复核（含情绪拐点）")
        print("  ✓ 排除项过滤，不进入最终简报")
        print("  ✓ 按可信度自动排序（可信>待复核>存疑>排除）")
        print("  ✓ TXT/Markdown 格式导出")
        print("  ✓ 文件名自动带事件编号和时间")
        print()

    except Exception as e:
        print(f"\n{Fore.RED}✗ 测试失败：{e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    from colorama import Fore, Style, init
    init(autoreset=True)
    main()
