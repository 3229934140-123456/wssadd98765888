from typing import List

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


def run_review_mode(result: AnalysisResult, event_id: str) -> AnalysisResult:
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}  复核模式")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.LIGHTBLACK_EX}  逐条标记关键节点为：可信 / 存疑 / 排除")
    print(f"{Fore.LIGHTBLACK_EX}  复核后系统将按可信度重新排序并输出简版结论")
    print(f"{Fore.MAGENTA}{'-' * 60}{Style.RESET_ALL}")

    all_nodes = []
    for node in result.first_post_nodes:
        node.node_type = f"[首发] {node.node_type}"
        all_nodes.append(("first", node))
    for node in result.amplification_nodes:
        node.node_type = f"[传播] {node.node_type}"
        all_nodes.append(("amp", node))

    total = len(all_nodes)
    if total == 0:
        print(f"{Fore.YELLOW}没有可复核的节点{Style.RESET_ALL}")
        return result

    print(f"\n共 {total} 条关键节点待复核\n")

    start = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 按回车开始复核，输入 q 跳过：").strip().lower()
    if start == "q":
        return result

    reviewed_count = 0
    for i, (category, node) in enumerate(all_nodes, 1):
        status = _review_one_node(node, i, total)

        if status == "quit":
            print(f"\n{Fore.YELLOW}已退出复核模式{Style.RESET_ALL}")
            break
        if status == "跳过":
            continue

        node.review_status = status
        reviewed_count += 1

    print(f"\n{Fore.GREEN}复核完成，共标记 {reviewed_count} 条节点{Style.RESET_ALL}")

    first_nodes = [n for c, n in all_nodes if c == "first"]
    amp_nodes = [n for c, n in all_nodes if c == "amp"]

    first_nodes_sorted = _sort_by_review(first_nodes)
    amp_nodes_sorted = _sort_by_review(amp_nodes)

    new_result = AnalysisResult(
        first_post_nodes=first_nodes_sorted,
        amplification_nodes=amp_nodes_sorted,
        sentiment_turning_points=result.sentiment_turning_points,
        total_posts=result.total_posts,
        time_range=result.time_range,
    )

    _print_reviewed_report(new_result, event_id)

    return new_result


def _sort_by_review(nodes: List[KeyNode]) -> List[KeyNode]:
    priority = {"可信": 0, "待复核": 1, "存疑": 2, "排除": 3}

    def sort_key(n):
        return (priority.get(n.review_status, 1), -n.score)

    return sorted(nodes, key=sort_key)


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

    print(f"{Fore.GREEN}可信首发线索：{len(first_trusted)} 条")
    print(f"{Fore.YELLOW}存疑首发线索：{len(first_doubt)} 条")
    print(f"{Fore.RED}排除首发线索：{len(first_excluded)} 条")
    print(f"{Fore.LIGHTBLACK_EX}待复核首发线索：{len(first_pending)} 条")
    print()

    print(f"{Fore.GREEN}可信传播节点：{len(amp_trusted)} 条")
    print(f"{Fore.YELLOW}存疑传播节点：{len(amp_doubt)} 条")
    print(f"{Fore.RED}排除传播节点：{len(amp_excluded)} 条")
    print(f"{Fore.LIGHTBLACK_EX}待复核传播节点：{len(amp_pending)} 条")
    print()

    if first_trusted:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}> 可信首发线索 Top{min(3, len(first_trusted))}{Style.RESET_ALL}")
        for i, node in enumerate(first_trusted[:3], 1):
            p = node.post
            print(f"  {i}. [{p.publish_time.strftime('%m-%d %H:%M')}] {p.platform.value} "
                  f"@{p.username}")
            print(f"     {p.content[:45]}..." if len(p.content) > 45 else f"     {p.content}")

    if amp_trusted:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}> 可信传播节点 Top{min(3, len(amp_trusted))}{Style.RESET_ALL}")
        for i, node in enumerate(amp_trusted[:3], 1):
            p = node.post
            print(f"  {i}. [{p.publish_time.strftime('%m-%d %H:%M')}] {p.platform.value} "
                  f"@{p.username}")
            print(f"     转{p.repost_count} 评{p.comment_count} 赞{p.like_count}")
            print(f"     {p.content[:45]}..." if len(p.content) > 45 else f"     {p.content}")

    if result.sentiment_turning_points:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}> 情绪拐点（共 {len(result.sentiment_turning_points)} 个）{Style.RESET_ALL}")
        for i, point in enumerate(result.sentiment_turning_points[:2], 1):
            neg = point.sentiment_ratio["负面"] * 100
            print(f"  {i}. [{point.time_point.strftime('%m-%d %H:%M')}] 负面{neg:.0f}% - {point.description[:30]}")

    print(f"\n{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")
