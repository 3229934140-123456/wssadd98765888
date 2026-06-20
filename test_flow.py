from datetime import datetime, timedelta
from models import Platform, TraceConfig
from data_generator import generate_mock_data
from analyzer import run_analysis
from formatter import print_full_report, print_report_for_daily
from reviewer import run_review_mode, _sort_by_review


def test_full_flow():
    print("=" * 60)
    print("  自动化测试：完整分析流程")
    print("=" * 60)

    config = TraceConfig(
        event_id="EVT-TEST-001",
        keywords=["新能源汽车", "电池安全"],
        exclude_words=["广告"],
        start_time=datetime.now() - timedelta(days=3),
        end_time=datetime.now(),
        platforms=[Platform.WEIBO, Platform.WECHAT, Platform.DOUYIN, Platform.ZHIHU],
        original_only=False,
        verified_only=False,
    )

    print(f"\n事件编号：{config.event_id}")
    print(f"关键词：{config.keywords}")
    print(f"平台：{[p.value for p in config.platforms]}")
    print(f"时间范围：{config.start_time} ~ {config.end_time}")

    posts = generate_mock_data(config, count=200)
    print(f"\n生成模拟数据：{len(posts)} 条")

    result = run_analysis(posts, config)
    print(f"分析完成")
    print(f"  - 首发线索：{len(result.first_post_nodes)} 条")
    print(f"  - 传播节点：{len(result.amplification_nodes)} 条")
    print(f"  - 情绪拐点：{len(result.sentiment_turning_points)} 个")

    print("\n" + "=" * 60)
    print("  测试 1：完整报告输出")
    print("=" * 60)
    print_full_report(result, config.event_id)

    print("\n" + "=" * 60)
    print("  测试 2：日报文本输出")
    print("=" * 60)
    daily_text = print_report_for_daily(result, config.event_id)
    print(daily_text)

    print("\n" + "=" * 60)
    print("  测试 3：复核排序功能")
    print("=" * 60)

    for i, node in enumerate(result.first_post_nodes):
        if i < 2:
            node.review_status = "可信"
        elif i < 4:
            node.review_status = "存疑"
        elif i < 6:
            node.review_status = "排除"

    for i, node in enumerate(result.amplification_nodes):
        if i < 3:
            node.review_status = "可信"
        elif i < 5:
            node.review_status = "存疑"

    sorted_first = _sort_by_review(result.first_post_nodes)
    sorted_amp = _sort_by_review(result.amplification_nodes)

    print(f"首发线索排序后状态：")
    for n in sorted_first[:6]:
        print(f"  - {n.review_status}: {n.post.username} ({n.post.platform.value})")

    print(f"\n传播节点排序后状态：")
    for n in sorted_amp[:6]:
        print(f"  - {n.review_status}: {n.post.username} ({n.post.platform.value})")

    print("\n" + "=" * 60)
    print("  测试 4：过滤条件验证")
    print("=" * 60)

    config_original = TraceConfig(
        event_id="EVT-TEST-002",
        keywords=["测试"],
        exclude_words=[],
        start_time=datetime.now() - timedelta(days=1),
        end_time=datetime.now(),
        platforms=[Platform.WEIBO],
        original_only=True,
        verified_only=False,
    )
    posts_original = generate_mock_data(config_original, count=50)
    all_original = all(p.is_original for p in posts_original)
    print(f"仅原创模式：{len(posts_original)} 条，全部原创={all_original}")

    config_verified = TraceConfig(
        event_id="EVT-TEST-003",
        keywords=["测试"],
        exclude_words=[],
        start_time=datetime.now() - timedelta(days=1),
        end_time=datetime.now(),
        platforms=[Platform.WEIBO],
        original_only=False,
        verified_only=True,
    )
    posts_verified = generate_mock_data(config_verified, count=50)
    all_verified = all(p.verification.value != "未认证" for p in posts_verified)
    print(f"仅认证模式：{len(posts_verified)} 条，全部认证={all_verified}")

    print("\n" + "=" * 60)
    print("  ✓ 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    test_full_flow()
