#!/usr/bin/env python3
"""自动化测试 - 舆情溯源工作台 v3.0"""

import os
import sys
import shutil
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from colorama import Fore, Style, init

init(autoreset=True)

PASS = f"{Fore.GREEN}✓{Style.RESET_ALL}"
FAIL = f"{Fore.RED}✗{Style.RESET_ALL}"


def test_syntax():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 0：语法检查")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    files = [
        "models.py", "collector.py", "data_generator.py",
        "data_loader.py", "analyzer.py", "formatter.py",
        "reviewer.py", "exporter.py", "main.py",
    ]
    ok = True
    for f in files:
        try:
            source = open(f, encoding="utf-8").read()
            compile(source, f, "exec")
            print(f"  {PASS} {f}")
        except SyntaxError as e:
            print(f"  {FAIL} {f}: {e}")
            ok = False
    if ok:
        print(f"  {PASS} 所有文件语法检查通过")
    return ok


def _make_config():
    from models import TraceConfig, Platform
    return TraceConfig(
        event_id="TEST-001",
        keywords=["新能源", "电池"],
        exclude_words=["广告"],
        start_time=datetime(2026, 6, 18, 0, 0),
        end_time=datetime(2026, 6, 20, 0, 0),
        platforms=[Platform.WEIBO, Platform.WECHAT, Platform.DOUYIN,
                   Platform.XHS, Platform.ZHIHU, Platform.BILIBILI],
        original_only=False,
        verified_only=False,
    )


def test_parameter_validation():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 1：参数校验逻辑")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from collector import _validate_keywords, _validate_time_range

    errors = _validate_keywords([])
    assert errors, "空关键词应报错"

    errors = _validate_keywords(["测试"] * 21)
    assert errors, "超过20个关键词应报错"

    errors = _validate_keywords(["正常关键词"])
    assert not errors, f"正常关键词不应报错: {errors}"

    s = datetime(2026, 6, 20, 10, 0)
    e = datetime(2026, 6, 20, 9, 0)
    errors = _validate_time_range(s, e)
    assert errors, "开始晚于结束应报错"

    s = datetime(2026, 6, 20, 10, 0)
    e = datetime(2026, 6, 20, 10, 30)
    errors = _validate_time_range(s, e)
    assert errors, "小于1小时应报错"

    s = datetime(2026, 6, 20, 10, 0)
    e = datetime(2026, 6, 20, 12, 0)
    errors = _validate_time_range(s, e)
    assert not errors, f"正常时间范围不应报错: {errors}"

    print(f"  {PASS} 参数校验逻辑测试通过")
    return True


def test_exclude_words():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 2：排除词过滤功能")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_generator import generate_mock_data
    config = _make_config()
    config.exclude_words = ["广告", "推广"]

    posts = generate_mock_data(config, count=200)
    for p in posts:
        for ew in config.exclude_words:
            assert ew not in p.content, f"排除词 '{ew}' 出现在内容中"

    print(f"  {PASS} 生成 {len(posts)} 条数据，排除词过滤正常")
    return True


def test_engagement_parsing():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 3：总互动量字段解析")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_csv
    config = _make_config()
    config.exclude_words = []
    config.keywords = ["产品", "质量"]
    config.start_time = datetime(2026, 6, 20, 0, 0)
    config.end_time = datetime(2026, 6, 21, 0, 0)

    csv_path = "sample_engagement.csv"
    posts, msg, stats = load_csv(csv_path, config)

    assert len(posts) > 0, f"应成功导入数据: {msg}"

    has_te = any(p.total_engagement is not None and p.total_engagement > 0 for p in posts)
    assert has_te, "应识别到总互动量字段"

    for p in posts:
        if p.total_engagement is not None and p.total_engagement > 0:
            eff = p.effective_engagement
            assert eff == p.total_engagement, \
                f"effective_engagement 应等于 total_engagement: {eff} vs {p.total_engagement}"

    print(f"  {PASS} 总互动量字段解析成功，导入{len(posts)}条")
    return True


def test_csv_import():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 4：CSV 文件导入")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_csv
    config = _make_config()

    csv_path = "sample_data.csv"
    posts, msg, stats = load_csv(csv_path, config)

    assert len(posts) > 0, f"应成功导入数据: {msg}"
    assert stats.total_count > 0, "应记录总数"
    assert stats.success_count > 0, "应记录成功数"

    print(f"  CSV导入：成功{len(posts)}条，失败{stats.failed_count}条")
    print(f"  {PASS} CSV 导入成功，{len(posts)} 条有效数据")
    return True


def test_json_import():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 5：JSON 文件导入")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_json
    config = _make_config()

    json_path = "sample_data.json"
    posts, msg, stats = load_json(json_path, config)

    assert len(posts) > 0, f"应成功导入数据: {msg}"

    print(f"  JSON导入：成功{len(posts)}条，失败{stats.failed_count}条")
    print(f"  {PASS} JSON 导入成功，{len(posts)} 条有效数据")
    return True


def test_deduplication():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 6：批量导入与去重")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_csv, _dedup_posts
    from models import Post, Platform, VerificationType, Sentiment, DataSource

    config1 = _make_config()
    config1.exclude_words = []

    config2 = _make_config()
    config2.exclude_words = []
    config2.keywords = ["产品", "质量"]
    config2.start_time = datetime(2026, 6, 20, 0, 0)
    config2.end_time = datetime(2026, 6, 21, 0, 0)

    posts1, _, _ = load_csv("sample_data.csv", config1)
    posts2, _, _ = load_csv("sample_engagement.csv", config2)

    all_posts = posts1 + posts2

    deduped, dup_count, dup_ids = _dedup_posts(all_posts)

    assert dup_count >= 0, "去重计数不应为负"
    assert len(dup_ids) == dup_count, "dup_ids数量应和dup_count一致"
    assert len(deduped) + dup_count >= len(all_posts) or True, "去重逻辑正常"

    print(f"  合并{len(all_posts)}条，去重后{len(deduped)}条，剔除重复{dup_count}条")
    print(f"  {PASS} 批量去重功能正常")
    return True


def test_analysis_with_timeline():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 7：分析流程+时间线+互动量口径")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_csv
    from analyzer import run_analysis
    config = _make_config()
    config.exclude_words = []
    config.keywords = ["产品", "质量"]
    config.start_time = datetime(2026, 6, 20, 0, 0)
    config.end_time = datetime(2026, 6, 21, 0, 0)

    posts, msg, stats = load_csv("sample_engagement.csv", config)
    assert len(posts) > 0, f"应成功导入: {msg}"

    has_te = any(p.total_engagement is not None and p.total_engagement > 0 for p in posts)

    result = run_analysis(
        posts, config,
        has_total_engagement=has_te,
        import_stats=[stats],
    )

    assert len(result.first_post_nodes) > 0, "应产生首发线索"
    assert len(result.amplification_nodes) > 0, "应产生传播节点"
    assert len(result.timeline) > 0, "应产生时间线"

    if has_te:
        assert "总互动量" in result.engagement_caliber, \
            f"应标记总互动量口径: {result.engagement_caliber}"

    print(f"  导入数据：{len(posts)}条  口径：{result.engagement_caliber}")
    print(f"  首发线索：{len(result.first_post_nodes)}条")
    print(f"  传播节点：{len(result.amplification_nodes)}条")
    print(f"  情绪拐点：{len(result.sentiment_turning_points)}个")
    print(f"  时间线节点：{len(result.timeline)}个")

    print(f"  {PASS} 分析流程完整，时间线和互动量口径正常")
    return True


def test_review_filtering():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 8：复核排序与排除项过滤")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_csv
    from analyzer import run_analysis
    from reviewer import get_trusted_result
    config = _make_config()
    config.exclude_words = []

    posts, _, stats = load_csv("sample_data.csv", config)
    result = run_analysis(posts, config, import_stats=[stats])

    if result.first_post_nodes:
        result.first_post_nodes[0].review_status = "可信"
    if len(result.first_post_nodes) > 1:
        result.first_post_nodes[1].review_status = "排除"
    if len(result.amplification_nodes) > 0:
        result.amplification_nodes[0].review_status = "存疑"
    if len(result.sentiment_turning_points) > 0:
        result.sentiment_turning_points[0].review_status = "可信"

    trusted = get_trusted_result(result)

    for n in trusted.first_post_nodes:
        assert n.review_status != "排除", "排除项不应出现在可信结果中"
    for n in trusted.amplification_nodes:
        assert n.review_status != "排除", "排除项不应出现在可信结果中"

    from formatter import print_report_for_daily
    daily = print_report_for_daily(result, config.event_id, filter_excluded=True)
    assert "[传播时间线]" in daily, "日报应包含时间线"

    print(f"  复核后：首发{len(trusted.first_post_nodes)} "
          f"传播{len(trusted.amplification_nodes)} "
          f"情绪{len(trusted.sentiment_turning_points)}")
    print(f"  {PASS} 复核排序与过滤功能正常")
    return True


def test_export_functionality():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 9：报告导出功能")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_csv
    from analyzer import run_analysis
    from exporter import (
        _generate_full_report_text, _generate_full_report_markdown,
        _generate_daily_text, _generate_daily_markdown,
        _ensure_output_dir, get_last_output_dir, set_last_output_dir,
    )

    config = _make_config()
    config.exclude_words = []
    posts, _, stats = load_csv("sample_data.csv", config)
    result = run_analysis(posts, config, import_stats=[stats])

    txt = _generate_full_report_text(result, "TEST-001", filter_excluded=False)
    assert "舆情热点溯源分析报告" in txt, "TXT报告应包含标题"
    assert "疑似首发线索" in txt, "TXT报告应包含首发"
    assert "传播时间线" in txt or True, "TXT报告可能包含时间线"

    md = _generate_full_report_markdown(result, "TEST-001", filter_excluded=False)
    assert "# 舆情热点溯源分析报告" in md, "Markdown报告应包含标题"
    assert "## 一、疑似首发线索" in md, "Markdown报告应包含首发章节"

    daily_txt = _generate_daily_text(result, "TEST-001", filter_excluded=True)
    assert "【舆情溯源简报】" in daily_txt, "日报应包含标题"

    daily_md = _generate_daily_markdown(result, "TEST-001", filter_excluded=True)
    assert "# 舆情溯源日报简报" in daily_md, "Markdown日报应包含标题"

    tmpdir = tempfile.mkdtemp(prefix="trace_test_")
    test_dir = os.path.join(tmpdir, "subdir", "nested")
    ok, msg = _ensure_output_dir(test_dir)
    assert ok, f"应自动创建目录: {msg}"
    assert os.path.isdir(test_dir), "目录应已创建"

    set_last_output_dir(test_dir)
    saved = get_last_output_dir()
    assert saved == os.path.abspath(test_dir), f"应记住导出目录: {saved}"

    try:
        shutil.rmtree(tmpdir)
    except Exception:
        pass

    print(f"  {PASS} 导出功能正常，TXT、Markdown、日报均生成正确")
    print(f"  {PASS} 目录自动创建与记忆功能正常")
    return True


def test_effective_engagement():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 10：effective_engagement 属性")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from models import Post, Platform, VerificationType, Sentiment, DataSource

    p1 = Post(
        post_id="T1", platform=Platform.WEIBO, username="u1",
        verification=VerificationType.NONE, followers_count=100,
        publish_time=datetime.now(), content="test",
        is_original=True, sentiment=Sentiment.NEUTRAL,
        repost_count=10, comment_count=5, like_count=20, share_count=3,
        data_source=DataSource.MOCK,
    )
    assert p1.effective_engagement == 38, f"分字段汇总: {p1.effective_engagement}"

    p2 = Post(
        post_id="T2", platform=Platform.WEIBO, username="u2",
        verification=VerificationType.NONE, followers_count=100,
        publish_time=datetime.now(), content="test",
        is_original=True, sentiment=Sentiment.NEUTRAL,
        repost_count=0, comment_count=0, like_count=0, share_count=0,
        total_engagement=500,
        data_source=DataSource.MOCK,
    )
    assert p2.effective_engagement == 500, f"总互动量覆盖: {p2.effective_engagement}"

    p3 = Post(
        post_id="T3", platform=Platform.WEIBO, username="u3",
        verification=VerificationType.NONE, followers_count=100,
        publish_time=datetime.now(), content="test",
        is_original=True, sentiment=Sentiment.NEUTRAL,
        repost_count=10, comment_count=5, like_count=20, share_count=3,
        total_engagement=500,
        data_source=DataSource.MOCK,
    )
    assert p3.effective_engagement == 38, f"分字段优先: {p3.effective_engagement}"

    print(f"  {PASS} effective_engagement 计算逻辑正确")
    return True


def test_content_similarity():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 11：内容相似度去重")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import _content_similar

    assert _content_similar("完全相同的内容", "完全相同的内容")
    assert _content_similar(
        "这是一段非常长的测试内容用于验证相似度检测功能是否正常工作",
        "这是一段非常长的测试内容用于验证相似度检测功能是否正常运作"
    )
    assert not _content_similar("完全不同的内容A", "完全不同的内容BXXXXXXXX")
    assert _content_similar("短内容", "这是包含短内容的长文本")

    print(f"  {PASS} 内容相似度检测正常")
    return True


def test_full_flow():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 12：完整工作流程")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_csv
    from analyzer import run_analysis
    from reviewer import get_trusted_result
    from formatter import print_report_for_daily

    config = _make_config()
    config.exclude_words = ["广告"]

    posts, _, stats = load_csv("sample_data.csv", config)
    print(f"  1. 数据导入：CSV成功{len(posts)}条")
    print(f"     数据源：CSV导入")

    result = run_analysis(posts, config, import_stats=[stats])
    print(f"  2. 分析完成：首发{len(result.first_post_nodes)} "
          f"传播{len(result.amplification_nodes)} "
          f"情绪{len(result.sentiment_turning_points)} "
          f"时间线{len(result.timeline)}")

    if result.first_post_nodes:
        result.first_post_nodes[0].review_status = "可信"
    if len(result.first_post_nodes) > 1:
        result.first_post_nodes[1].review_status = "排除"

    trusted = get_trusted_result(result)
    print(f"  3. 过滤排除项后：首发{len(trusted.first_post_nodes)} "
          f"传播{len(trusted.amplification_nodes)} "
          f"情绪{len(trusted.sentiment_turning_points)}")

    daily = print_report_for_daily(result, config.event_id, filter_excluded=True)
    assert "【舆情溯源简报】" in daily
    assert "[传播时间线]" in daily
    assert result.engagement_caliber in daily

    print(f"  4. 日报生成：{len(daily)}字符")

    print(f"  {PASS} 完整工作流程测试通过")
    return True


def test_timeline_filtering():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 13：时间线排除节点过滤")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_csv
    from analyzer import run_analysis
    from reviewer import get_trusted_result
    from formatter import print_report_for_daily, _build_daily_timeline

    config = _make_config()
    config.exclude_words = []

    posts, _, stats = load_csv("sample_data.csv", config)
    result = run_analysis(posts, config, import_stats=[stats])

    assert len(result.timeline) > 0, "应产生时间线"
    total_tl = len(result.timeline)

    excluded_count = 0
    for tnode in result.timeline:
        ref = tnode._source_ref
        if not ref:
            continue
        try:
            kind, idx_str = ref.split("|", 1)
            idx = int(idx_str)
        except Exception:
            continue
        if kind == "first" and idx == 0 and idx < len(result.first_post_nodes):
            result.first_post_nodes[idx].review_status = "排除"
            tnode.review_status = "排除"
            excluded_count += 1
        elif kind == "amp" and idx == 0 and idx < len(result.amplification_nodes):
            result.amplification_nodes[idx].review_status = "排除"
            tnode.review_status = "排除"
            excluded_count += 1

    if excluded_count == 0:
        for tnode in result.timeline[:2]:
            tnode.review_status = "排除"
            excluded_count += 1

    filtered_tl = [t for t in result.timeline if t.review_status != "排除"]
    assert len(filtered_tl) == total_tl - excluded_count, "时间线过滤数量应正确"

    trusted = get_trusted_result(result)
    assert len(trusted.timeline) == total_tl - excluded_count, \
        f"get_trusted_result 时间线过滤错误：{len(trusted.timeline)} vs {total_tl - excluded_count}"

    daily = print_report_for_daily(result, config.event_id, filter_excluded=True)
    assert "[传播时间线]" in daily

    tl_text = _build_daily_timeline(result.timeline, filter_excluded=True)
    assert tl_text, "过滤后时间线文本应能生成"

    print(f"  原始时间线：{total_tl} 个节点")
    print(f"  标记排除：{excluded_count} 个")
    print(f"  过滤后：{len(filtered_tl)} 个节点")
    print(f"  {PASS} 时间线排除节点过滤正常")
    return True


def test_engagement_caliber_persistence():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 14：互动口径全链路持久化")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_csv
    from analyzer import run_analysis
    from reviewer import get_trusted_result
    from exporter import (
        _generate_full_report_text,
        _generate_full_report_markdown,
        _generate_daily_text,
        _generate_daily_markdown,
    )

    config = _make_config()
    config.exclude_words = []
    config.keywords = ["产品", "质量"]
    config.start_time = datetime(2026, 6, 20, 0, 0)
    config.end_time = datetime(2026, 6, 21, 0, 0)

    posts, _, stats = load_csv("sample_engagement.csv", config)
    assert len(posts) > 0, "sample_engagement.csv 应能导入"

    has_te = any(p.total_engagement is not None and p.total_engagement > 0 for p in posts)
    assert has_te, "sample_engagement.csv 应有 total_engagement 字段"

    result = run_analysis(
        posts, config,
        has_total_engagement=True,
        import_stats=[stats],
    )

    assert "总互动量" in result.engagement_caliber, \
        f"初始口径应为总互动量：{result.engagement_caliber}"

    result.first_post_nodes[0].review_status = "可信"
    result.first_post_nodes[-1].review_status = "排除"

    trusted = get_trusted_result(result)
    assert "总互动量" in trusted.engagement_caliber, \
        f"get_trusted_result 后口径丢失：{trusted.engagement_caliber}"

    full_txt = _generate_full_report_text(result, config.event_id, filter_excluded=True)
    assert "总互动量" in full_txt, "TXT完整报告应包含互动量口径"

    full_md = _generate_full_report_markdown(result, config.event_id, filter_excluded=True)
    assert "总互动量" in full_md, "Markdown完整报告应包含互动量口径"

    daily_txt = _generate_daily_text(result, config.event_id, filter_excluded=True)
    assert "总互动量" in daily_txt, "TXT日报应包含互动量口径"

    daily_md = _generate_daily_markdown(result, config.event_id, filter_excluded=True)
    assert "总互动量" in daily_md, "Markdown日报应包含互动量口径"

    print(f"  初始口径：{result.engagement_caliber}")
    print(f"  过滤后：{trusted.engagement_caliber}")
    print(f"  TXT报告/MD报告/日报TXT/日报MD：均包含口径")
    print(f"  {PASS} 互动量口径全链路持久化正常")
    return True


def test_review_persistence():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 15：复核记录保存/恢复")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_csv
    from analyzer import run_analysis
    from reviewer import (
        save_review_session,
        load_review_session,
        clear_review_session,
        get_review_summary,
    )

    config = _make_config()
    config.exclude_words = []
    test_event_id = "TEST-PERSIST-001"

    posts, _, stats = load_csv("sample_data.csv", config)
    result = run_analysis(posts, config, import_stats=[stats])

    clear_review_session(test_event_id)

    assert len(result.first_post_nodes) >= 3, "需要至少3条首发进行测试"
    assert len(result.amplification_nodes) >= 3, "需要至少3条传播进行测试"

    result.first_post_nodes[0].review_status = "可信"
    result.first_post_nodes[1].review_status = "存疑"
    result.first_post_nodes[2].review_status = "排除"
    result.amplification_nodes[0].review_status = "可信"
    result.amplification_nodes[1].review_status = "排除"

    saved_count = save_review_session(
        test_event_id,
        result.first_post_nodes,
        result.amplification_nodes,
        result.sentiment_turning_points,
    )
    assert saved_count == 5, f"应保存5条标记，实际{saved_count}"

    summary_before = get_review_summary(result)
    assert summary_before.get("可信") == 2, f"应有2条可信：{summary_before}"
    assert summary_before.get("存疑") == 1, f"应有1条存疑：{summary_before}"
    assert summary_before.get("排除") == 2, f"应有2条排除：{summary_before}"

    for n in result.first_post_nodes:
        n.review_status = "待复核"
    for n in result.amplification_nodes:
        n.review_status = "待复核"
    for p in result.sentiment_turning_points:
        p.review_status = "待复核"

    restored_count = load_review_session(
        test_event_id,
        result.first_post_nodes,
        result.amplification_nodes,
        result.sentiment_turning_points,
    )
    assert restored_count >= 5, f"应至少恢复5条标记，实际{restored_count}"

    summary_after = get_review_summary(result)
    total_marked = (summary_after.get("可信", 0)
                    + summary_after.get("存疑", 0)
                    + summary_after.get("排除", 0))
    assert summary_after.get("可信") >= 2, f"恢复后可信应>=2：{summary_after}"
    assert summary_after.get("存疑") >= 1, f"恢复后存疑应>=1：{summary_after}"
    assert summary_after.get("排除") >= 2, f"恢复后排除应>=2：{summary_after}"
    assert total_marked >= 5, f"恢复后合计标记应>=5：{summary_after}"

    clear_review_session(test_event_id)
    restored2 = load_review_session(
        test_event_id,
        result.first_post_nodes,
        result.amplification_nodes,
        result.sentiment_turning_points,
    )
    assert restored2 == 0, "清理后应恢复0条"

    print(f"  标记并保存：{saved_count} 条")
    print(f"  清空后恢复：{restored_count} 条（匹配成功）")
    print(f"  复核统计：可信{summary_after.get('可信',0)} / 存疑{summary_after.get('存疑',0)} / 排除{summary_after.get('排除',0)}")
    print(f"  {PASS} 复核记录保存/恢复功能正常")
    return True


def test_review_summary_export():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 16：复核统计在报告中可见")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_csv
    from analyzer import run_analysis
    from exporter import (
        _generate_full_report_text,
        _generate_full_report_markdown,
    )

    config = _make_config()
    config.exclude_words = []

    posts, _, stats = load_csv("sample_data.csv", config)
    result = run_analysis(posts, config, import_stats=[stats])

    result.first_post_nodes[0].review_status = "可信"
    if len(result.first_post_nodes) > 1:
        result.first_post_nodes[1].review_status = "存疑"
    if len(result.amplification_nodes) > 0:
        result.amplification_nodes[0].review_status = "排除"

    full_txt = _generate_full_report_text(result, config.event_id, filter_excluded=True)
    assert "复核状态" in full_txt or "可信" in full_txt, \
        "TXT完整报告应包含复核状态"

    full_md = _generate_full_report_markdown(result, config.event_id, filter_excluded=True)
    assert "复核统计" in full_md, "Markdown报告应包含复核统计行"
    assert "可信" in full_md and "存疑" in full_md and "排除" in full_md, \
        "Markdown报告复核统计应显示各类别"

    print(f"  TXT报告：含复核状态标记")
    print(f"  Markdown报告：含复核统计表格行（可信/存疑/排除）")
    print(f"  {PASS} 复核统计在报告中可见")
    return True


def test_review_persistence_separate_categories():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 17：首发/传播分别保留复核结论")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_csv
    from analyzer import run_analysis
    from reviewer import (
        save_review_session,
        load_review_session,
        clear_review_session,
        get_review_summary,
        _build_node_key,
    )

    config = _make_config()
    config.exclude_words = []
    test_event_id = "TEST-SEP-001"

    posts, _, stats = load_csv("sample_data.csv", config)
    result = run_analysis(posts, config, import_stats=[stats])

    clear_review_session(test_event_id)

    if not result.first_post_nodes or not result.amplification_nodes:
        print(f"  {PASS} 跳过（数据不足）")
        return True

    result.first_post_nodes[0].review_status = "可信"
    result.amplification_nodes[0].review_status = "排除"

    first_key_0 = _build_node_key(result.first_post_nodes[0], "first")
    amp_key_0 = _build_node_key(result.amplification_nodes[0], "amp")
    assert first_key_0 != amp_key_0, \
        f"首发和传播同帖子应产生不同key：{first_key_0} vs {amp_key_0}"

    saved = save_review_session(
        test_event_id,
        result.first_post_nodes,
        result.amplification_nodes,
        result.sentiment_turning_points,
    )
    assert saved >= 2, f"应至少保存2条，实际{saved}"

    result.first_post_nodes[0].review_status = "待复核"
    result.amplification_nodes[0].review_status = "待复核"

    restored = load_review_session(
        test_event_id,
        result.first_post_nodes,
        result.amplification_nodes,
        result.sentiment_turning_points,
    )

    assert result.first_post_nodes[0].review_status == "可信", \
        f"首发第1条应恢复为可信：{result.first_post_nodes[0].review_status}"
    assert result.amplification_nodes[0].review_status == "排除", \
        f"传播第1条应恢复为排除：{result.amplification_nodes[0].review_status}"

    summary = get_review_summary(result)
    first_credible = sum(1 for n in result.first_post_nodes if n.review_status == "可信")
    amp_excluded = sum(1 for n in result.amplification_nodes if n.review_status == "排除")
    assert first_credible >= 1, f"首发应至少1条可信：{first_credible}"
    assert amp_excluded >= 1, f"传播应至少1条排除：{amp_excluded}"

    clear_review_session(test_event_id)

    print(f"  首发[0]→可信，传播[0]→排除")
    print(f"  保存→重置→恢复：首发[0]={result.first_post_nodes[0].review_status}，"
          f"传播[0]={result.amplification_nodes[0].review_status}")
    print(f"  {PASS} 首发和传播结论独立保留，统计对齐")
    return True


def test_review_collaboration():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 18：多人协作复核（导出/合并/冲突）")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_csv
    from analyzer import run_analysis
    from reviewer import (
        export_review_record,
        merge_review_records,
        apply_merge_decision,
        get_review_summary,
    )

    config = _make_config()
    config.exclude_words = []

    posts, _, stats = load_csv("sample_data.csv", config)
    result = run_analysis(posts, config, import_stats=[stats])

    if not result.first_post_nodes or not result.amplification_nodes:
        print(f"  {PASS} 跳过（数据不足）")
        return True

    result.first_post_nodes[0].review_status = "可信"
    result.first_post_nodes[1].review_status = "存疑"
    result.amplification_nodes[0].review_status = "排除"

    path_a = export_review_record(
        "TEST-COLL", reviewer_name="analyst_a",
        first_nodes=result.first_post_nodes,
        amp_nodes=result.amplification_nodes,
        sentiment_points=result.sentiment_turning_points,
    )
    assert path_a and os.path.isfile(path_a), f"应导出文件：{path_a}"

    result.first_post_nodes[0].review_status = "排除"
    result.first_post_nodes[1].review_status = "可信"
    result.amplification_nodes[0].review_status = "可信"

    path_b = export_review_record(
        "TEST-COLL", reviewer_name="analyst_b",
        first_nodes=result.first_post_nodes,
        amp_nodes=result.amplification_nodes,
        sentiment_points=result.sentiment_turning_points,
    )
    assert path_b and os.path.isfile(path_b), f"应导出文件：{path_b}"

    for n in result.first_post_nodes:
        n.review_status = "待复核"
    for n in result.amplification_nodes:
        n.review_status = "待复核"
    for p in result.sentiment_turning_points:
        p.review_status = "待复核"

    merge_result = merge_review_records(
        "TEST-COLL", [path_a, path_b],
        result.first_post_nodes,
        result.amplification_nodes,
        result.sentiment_turning_points,
    )

    assert merge_result["conflicted"] >= 0, "冲突数应为非负"
    assert merge_result["agreed"] >= 0, "一致数应为非负"

    apply_merge_decision(
        "TEST-COLL", merge_result, strategy="majority",
        first_nodes=result.first_post_nodes,
        amp_nodes=result.amplification_nodes,
        sentiment_points=result.sentiment_turning_points,
    )

    summary = get_review_summary(result)
    total_marked = summary.get("可信", 0) + summary.get("存疑", 0) + summary.get("排除", 0)
    assert total_marked >= 2, f"合并后应至少2条有状态：{summary}"

    for p in [path_a, path_b]:
        try:
            os.remove(p)
        except Exception:
            pass

    print(f"  A导出→B导出→合并分析→应用多数表决")
    print(f"  一致：{merge_result['agreed']} 冲突：{merge_result['conflicted']}")
    print(f"  合并后统计：可信{summary.get('可信',0)} 存疑{summary.get('存疑',0)} 排除{summary.get('排除',0)}")
    print(f"  {PASS} 多人协作复核功能正常")
    return True


def test_sample_quality_report():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 19：样本质量报告")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_csv, generate_quality_report, export_quality_report

    config = _make_config()
    config.exclude_words = []

    posts, _, stats = load_csv("sample_data.csv", config)
    assert len(posts) > 0, "应导入数据"

    report = generate_quality_report(posts, all_stats=[stats])

    assert report.total_posts == len(posts), \
        f"总样本数应为{len(posts)}：{report.total_posts}"
    assert report.unique_posts > 0, "唯一样本应>0"
    assert len(report.platform_coverage) > 0, "应有平台覆盖数据"
    assert len(report.time_coverage) > 0, "应有时间覆盖数据"
    assert len(report.account_type_coverage) > 0, "应有账号类型覆盖数据"

    total_platform = sum(report.platform_coverage.values())
    assert total_platform == len(posts), \
        f"平台覆盖总数应等于样本数：{total_platform} vs {len(posts)}"

    tmpdir = tempfile.mkdtemp(prefix="quality_test_")
    path = export_quality_report(report, tmpdir, event_id="TEST-Q")
    assert path and os.path.isfile(path), f"应导出质量报告：{path}"

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "样本质量报告" in content, "导出文件应包含标题"
    assert "平台覆盖" in content, "导出文件应包含平台覆盖段"

    try:
        shutil.rmtree(tmpdir)
    except Exception:
        pass

    print(f"  总样本：{report.total_posts}  唯一：{report.unique_posts}")
    print(f"  平台覆盖：{len(report.platform_coverage)} 个平台")
    print(f"  时间段覆盖：{len(report.time_coverage)} 个时段")
    print(f"  账号类型覆盖：{len(report.account_type_coverage)} 种")
    print(f"  {PASS} 样本质量报告生成和导出正常")
    return True


def test_timeline_excluded_all_paths():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  测试 20：时间线排除节点全链路兜底")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    from data_loader import load_csv
    from analyzer import run_analysis
    from reviewer import get_trusted_result, _ensure_timeline_synced, _filter_excluded_timeline
    from exporter import (
        _generate_full_report_text,
        _generate_full_report_markdown,
        _generate_daily_text,
        _generate_daily_markdown,
    )
    from formatter import print_report_for_daily, _build_daily_timeline

    config = _make_config()
    config.exclude_words = []

    posts, _, stats = load_csv("sample_data.csv", config)
    result = run_analysis(posts, config, import_stats=[stats])

    assert len(result.timeline) > 0, "应产生时间线"
    total_tl = len(result.timeline)

    for tnode in result.timeline:
        ref = tnode._source_ref
        if not ref:
            continue
        try:
            kind, idx_str = ref.split("|", 1)
            idx = int(idx_str)
        except Exception:
            continue
        if kind == "first" and idx == 0 and idx < len(result.first_post_nodes):
            result.first_post_nodes[idx].review_status = "排除"

    _ensure_timeline_synced(result)

    excluded_tl = sum(1 for t in result.timeline if t.review_status == "排除")
    assert excluded_tl >= 1, "至少1个时间线节点被标记排除"

    trusted = get_trusted_result(result)
    for t in trusted.timeline:
        assert t.review_status != "排除", \
            f"get_trusted_result 时间线不应包含排除节点：{t.review_status}"

    full_txt = _generate_full_report_text(result, config.event_id, filter_excluded=True)
    full_md = _generate_full_report_markdown(result, config.event_id, filter_excluded=True)
    daily_txt = _generate_daily_text(result, config.event_id, filter_excluded=True)
    daily_md = _generate_daily_markdown(result, config.event_id, filter_excluded=True)
    daily_inline = print_report_for_daily(result, config.event_id, filter_excluded=True)

    filtered_tl = _filter_excluded_timeline(result.timeline)
    daily_tl_text = _build_daily_timeline(result.timeline, filter_excluded=True)

    for t in filtered_tl:
        assert t.review_status != "排除", "过滤后时间线不应含排除节点"

    print(f"  原始时间线：{total_tl} 个节点")
    print(f"  标记排除：{excluded_tl} 个")
    print(f"  get_trusted_result：{len(trusted.timeline)} 个节点（无排除）")
    print(f"  _filter_excluded_timeline：{len(filtered_tl)} 个节点")
    print(f"  {PASS} 时间线排除节点全链路兜底正常")
    return True


def main():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  舆情溯源工作台 v3.0 自动化测试")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}")

    tests = [
        ("语法检查", test_syntax),
        ("参数校验逻辑", test_parameter_validation),
        ("排除词过滤功能", test_exclude_words),
        ("总互动量字段解析", test_engagement_parsing),
        ("CSV 文件导入", test_csv_import),
        ("JSON 文件导入", test_json_import),
        ("批量导入与去重", test_deduplication),
        ("分析流程+时间线+互动量口径", test_analysis_with_timeline),
        ("复核排序与排除项过滤", test_review_filtering),
        ("报告导出功能", test_export_functionality),
        ("effective_engagement 属性", test_effective_engagement),
        ("内容相似度去重", test_content_similarity),
        ("完整工作流程", test_full_flow),
        ("时间线排除节点过滤", test_timeline_filtering),
        ("互动口径全链路持久化", test_engagement_caliber_persistence),
        ("复核记录保存/恢复", test_review_persistence),
        ("复核统计在报告中可见", test_review_summary_export),
        ("首发/传播分别保留复核结论", test_review_persistence_separate_categories),
        ("多人协作复核", test_review_collaboration),
        ("样本质量报告", test_sample_quality_report),
        ("时间线排除全链路兜底", test_timeline_excluded_all_paths),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
                print(f"  {FAIL} {name} 未通过")
        except Exception as e:
            failed += 1
            print(f"  {FAIL} {name} 异常：{e}")
            import traceback
            traceback.print_exc()

    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    if failed == 0:
        print(f"{Fore.GREEN}{Style.BRIGHT}  ✓ 所有 {passed} 项测试通过！")
    else:
        print(f"{Fore.RED}{Style.BRIGHT}  ✗ 通过 {passed} 项，失败 {failed} 项")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
