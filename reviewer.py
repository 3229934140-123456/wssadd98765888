from typing import List, Tuple

from colorama import Fore, Style, init

from models import AnalysisResult, KeyNode, SentimentTurningPoint
from formatter import _print_key_node, _print_sentiment_point, print_summary_header

init(autoreset=True)

REVIEW_OPTIONS = {
    "1": "可信",
    "2": "存疑",
    "3": "排除",
    "k": "可信",
    "y": "可信",
    "d": "存疑",
    "n": "排除",
    "s": "跳过",
    "": "跳过",
}

REVIEW_PRIORITY = {"可信": 0, "待复核": 1, "存疑": 2, "排除": 3}


def _review_one_node(node: KeyNode, index: int, total: int) -> str:
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}--- 复核进度：{index}/{total} ---{Style.RESET_ALL}")
    _print_key_node(node, index, show_status=True)

    print(f"{Fore.CYAN}操作选项：")
    print(f"  1/k/y → 可信    2/d → 存疑    3/n → 排除    Enter/s → 跳过")
    print(f"  q → 退出复核")

    while True:
        choice = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 请选择：").strip().lower()

        if choice == "q":
            return "quit"
        if choice in REVIEW_OPTIONS:
            return REVIEW_OPTIONS[choice]

        print(f"{Fore.RED}无效输入，请重新选择{Style.RESET_ALL}")


def _review_one_sentiment(point: SentimentTurningPoint, index: int, total: int) -> Tuple[str, str]:
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}--- 复核进度：{index}/{total} ---{Style.RESET_ALL}")

    status_color = {
        "可信": Fore.GREEN,
        "存疑": Fore.YELLOW,
        "排除": Fore.RED,
        "待复核": Fore.WHITE,
    }.get(point.review_status, Fore.WHITE)

    print(f"{Fore.WHITE}{Style.BRIGHT}  [{index}] 情绪拐点 · {point.time_point.strftime('%Y-%m-%d %H:%M')} "
          f"[{status_color}{point.review_status}{Style.RESET_ALL}]")
    print(f"    {Fore.LIGHTBLACK_EX}{point.description}")

    pos = point.sentiment_ratio["正面"] * 100
    neu = point.sentiment_ratio["中性"] * 100
    neg = point.sentiment_ratio["负面"] * 100
    print(f"    {Fore.GREEN}正面 {pos:.0f}%{Style.RESET_ALL}  "
          f"{Fore.LIGHTBLACK_EX}中性 {neu:.0f}%{Style.RESET_ALL}  "
          f"{Fore.RED}负面 {neg:.0f}%{Style.RESET_ALL}")

    if point.trigger_posts:
        print(f"    {Fore.LIGHTBLACK_EX}关联热帖：")
        for tp in point.trigger_posts[:2]:
            from formatter import _truncate_text
            print(f"      · {tp.platform.value} @{tp.username}: {_truncate_text(tp.content, 50)}")

    print(f"\n{Fore.CYAN}操作选项：")
    print(f"  1/k/y → 可信    2/d → 存疑    3/n → 排除    Enter/s → 跳过")
    print(f"  q → 退出复核")

    while True:
        choice = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 请选择：").strip().lower()

        if choice == "q":
            return "quit", ""
        if choice in REVIEW_OPTIONS:
            status = REVIEW_OPTIONS[choice]
            reason = ""
            if status == "存疑" or status == "排除":
                reason = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 备注原因（可选）：").strip()
            return status, reason

        print(f"{Fore.RED}无效输入，请重新选择{Style.RESET_ALL}")


def _sort_key_nodes(nodes: List[KeyNode]) -> List[KeyNode]:
    def sort_key(n):
        return (REVIEW_PRIORITY.get(n.review_status, 1), -n.score)
    return sorted(nodes, key=sort_key)


def _sort_sentiment_points(points: List[SentimentTurningPoint]) -> List[SentimentTurningPoint]:
    def sort_key(p):
        return (REVIEW_PRIORITY.get(p.review_status, 1), -p.sentiment_ratio.get("负面", 0))
    return sorted(points, key=sort_key)


def _filter_excluded(nodes: List[KeyNode]) -> List[KeyNode]:
    return [n for n in nodes if n.review_status != "排除"]


def _filter_excluded_sentiment(points: List[SentimentTurningPoint]) -> List[SentimentTurningPoint]:
    return [p for p in points if p.review_status != "排除"]


def run_review_mode(result: AnalysisResult, event_id: str) -> AnalysisResult:
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}  复核模式")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.LIGHTBLACK_EX}  逐条标记关键节点和情绪拐点为：可信 / 存疑 / 排除")
    print(f"{Fore.LIGHTBLACK_EX}  复核后系统将按可信度重新排序，排除项不纳入最终简报")
    print(f"{Fore.MAGENTA}{'-' * 60}{Style.RESET_ALL}")

    all_items = []
    for node in result.first_post_nodes:
        node.node_type = f"[首发] {node.node_type}"
        all_items.append(("node", "first", node))
    for node in result.amplification_nodes:
        node.node_type = f"[传播] {node.node_type}"
        all_items.append(("node", "amp", node))
    for point in result.sentiment_turning_points:
        all_items.append(("sentiment", "sentiment", point))

    total = len(all_items)
    if total == 0:
        print(f"{Fore.YELLOW}没有可复核的内容{Style.RESET_ALL}")
        return result

    first_count = len(result.first_post_nodes)
    amp_count = len(result.amplification_nodes)
    sent_count = len(result.sentiment_turning_points)

    print(f"\n待复核内容统计：")
    print(f"  {Fore.CYAN}首发线索：{first_count} 条")
    print(f"  {Fore.CYAN}传播节点：{amp_count} 条")
    print(f"  {Fore.CYAN}情绪拐点：{sent_count} 个")
    print(f"  {Fore.WHITE}合计：{total} 项{Style.RESET_ALL}\n")

    start = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 按回车开始复核，输入 q 跳过：").strip().lower()
    if start == "q":
        return result

    reviewed_count = 0
    quit_flag = False

    for i, (item_type, category, item) in enumerate(all_items, 1):
        if quit_flag:
            break

        if item_type == "node":
            status = _review_one_node(item, i, total)
            if status == "quit":
                quit_flag = True
                continue
            if status == "跳过":
                continue
            item.review_status = status
        else:
            status, reason = _review_one_sentiment(item, i, total)
            if status == "quit":
                quit_flag = True
                continue
            if status == "跳过":
                continue
            item.review_status = status
            item.review_reason = reason

        reviewed_count += 1

    if quit_flag:
        print(f"\n{Fore.YELLOW}已退出复核模式，已标记 {reviewed_count} 条{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.GREEN}复核完成，共标记 {reviewed_count} 条{Style.RESET_ALL}")

    first_nodes = [item for _, cat, item in all_items if cat == "first"]
    amp_nodes = [item for _, cat, item in all_items if cat == "amp"]
    sentiment_points = [item for _, cat, item in all_items if cat == "sentiment"]

    first_nodes_sorted = _sort_key_nodes(first_nodes)
    amp_nodes_sorted = _sort_key_nodes(amp_nodes)
    sentiment_sorted = _sort_sentiment_points(sentiment_points)

    new_result = AnalysisResult(
        first_post_nodes=first_nodes_sorted,
        amplification_nodes=amp_nodes_sorted,
        sentiment_turning_points=sentiment_sorted,
        total_posts=result.total_posts,
        time_range=result.time_range,
        data_source=result.data_source,
        source_file=result.source_file,
    )

    _print_reviewed_report(new_result, event_id)

    return new_result


def get_trusted_result(result: AnalysisResult) -> AnalysisResult:
    return AnalysisResult(
        first_post_nodes=_filter_excluded(result.first_post_nodes),
        amplification_nodes=_filter_excluded(result.amplification_nodes),
        sentiment_turning_points=_filter_excluded_sentiment(result.sentiment_turning_points),
        total_posts=result.total_posts,
        time_range=result.time_range,
        data_source=result.data_source,
        source_file=result.source_file,
    )


def _print_reviewed_report(result: AnalysisResult, event_id: str):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  复核后简版结论")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.LIGHTBLACK_EX}  事件编号：{event_id}")
    print(f"{Fore.LIGHTBLACK_EX}  时间范围：{result.time_range}")
    print(f"{Fore.CYAN}{'-' * 60}{Style.RESET_ALL}\n")

    first_trusted = [n for n in result.first_post_nodes if n.review_status == "可信"]
    first_doubt = [n for n in result.first_post_nodes if n.review_status == "存疑"]
    first_excluded = [n for n in result.first_post_nodes if n.review_status == "排除"]
    first_pending = [n for n in result.first_post_nodes if n.review_status == "待复核"]

    amp_trusted = [n for n in result.amplification_nodes if n.review_status == "可信"]
    amp_doubt = [n for n in result.amplification_nodes if n.review_status == "存疑"]
    amp_excluded = [n for n in result.amplification_nodes if n.review_status == "排除"]
    amp_pending = [n for n in result.amplification_nodes if n.review_status == "待复核"]

    sent_trusted = [p for p in result.sentiment_turning_points if p.review_status == "可信"]
    sent_doubt = [p for p in result.sentiment_turning_points if p.review_status == "存疑"]
    sent_excluded = [p for p in result.sentiment_turning_points if p.review_status == "排除"]
    sent_pending = [p for p in result.sentiment_turning_points if p.review_status == "待复核"]

    print(f"{Fore.WHITE}首发线索：{Style.RESET_ALL}", end="")
    print(f"  {Fore.GREEN}可信 {len(first_trusted)}{Style.RESET_ALL}"
          f"  {Fore.YELLOW}存疑 {len(first_doubt)}{Style.RESET_ALL}"
          f"  {Fore.RED}排除 {len(first_excluded)}{Style.RESET_ALL}"
          f"  {Fore.LIGHTBLACK_EX}待复核 {len(first_pending)}{Style.RESET_ALL}")

    print(f"{Fore.WHITE}传播节点：{Style.RESET_ALL}", end="")
    print(f"  {Fore.GREEN}可信 {len(amp_trusted)}{Style.RESET_ALL}"
          f"  {Fore.YELLOW}存疑 {len(amp_doubt)}{Style.RESET_ALL}"
          f"  {Fore.RED}排除 {len(amp_excluded)}{Style.RESET_ALL}"
          f"  {Fore.LIGHTBLACK_EX}待复核 {len(amp_pending)}{Style.RESET_ALL}")

    print(f"{Fore.WHITE}情绪拐点：{Style.RESET_ALL}", end="")
    print(f"  {Fore.GREEN}可信 {len(sent_trusted)}{Style.RESET_ALL}"
          f"  {Fore.YELLOW}存疑 {len(sent_doubt)}{Style.RESET_ALL}"
          f"  {Fore.RED}排除 {len(sent_excluded)}{Style.RESET_ALL}"
          f"  {Fore.LIGHTBLACK_EX}待复核 {len(sent_pending)}{Style.RESET_ALL}")

    print()

    if first_trusted:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}> 可信首发线索 Top{min(3, len(first_trusted))}{Style.RESET_ALL}")
        for i, node in enumerate(first_trusted[:3], 1):
            p = node.post
            from formatter import _truncate_text
            print(f"  {i}. [{p.publish_time.strftime('%m-%d %H:%M')}] {p.platform.value} @{p.username}")
            print(f"     {_truncate_text(p.content, 45)}")

    if amp_trusted:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}> 可信传播节点 Top{min(3, len(amp_trusted))}{Style.RESET_ALL}")
        for i, node in enumerate(amp_trusted[:3], 1):
            p = node.post
            from formatter import _truncate_text
            print(f"  {i}. [{p.publish_time.strftime('%m-%d %H:%M')}] {p.platform.value} @{p.username}")
            print(f"     转{p.repost_count} 评{p.comment_count} 赞{p.like_count}")
            print(f"     {_truncate_text(p.content, 45)}")

    if sent_trusted:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}> 可信情绪拐点 Top{min(2, len(sent_trusted))}{Style.RESET_ALL}")
        for i, point in enumerate(sent_trusted[:2], 1):
            neg = point.sentiment_ratio["负面"] * 100
            print(f"  {i}. [{point.time_point.strftime('%m-%d %H:%M')}] 负面{neg:.0f}% - {point.description[:30]}")

    if first_excluded or amp_excluded or sent_excluded:
        total_excluded = len(first_excluded) + len(amp_excluded) + len(sent_excluded)
        print(f"\n{Fore.LIGHTBLACK_EX}({total_excluded} 项已排除，不纳入最终简报){Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")
