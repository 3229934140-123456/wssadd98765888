import json
import os
from typing import List, Tuple, Optional, Dict

from colorama import Fore, Style, init

from models import AnalysisResult, KeyNode, SentimentTurningPoint, TimelineNode
from formatter import _print_key_node, _print_sentiment_point, _build_daily_timeline, _format_num, _truncate_text

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

REVIEW_DIR = os.path.join(os.path.expanduser("~"), ".trace_workbench_reviews")


def _ensure_review_dir():
    try:
        if not os.path.exists(REVIEW_DIR):
            os.makedirs(REVIEW_DIR, exist_ok=True)
    except Exception:
        pass


def _safe_event_id(event_id: str) -> str:
    safe = "".join(c for c in event_id if c.isalnum() or c in ("-", "_"))
    return safe or "unnamed"


def _review_file_path(event_id: str) -> str:
    _ensure_review_dir()
    return os.path.join(REVIEW_DIR, f"review_{_safe_event_id(event_id)}.json")


def _build_node_key(node: KeyNode) -> str:
    p = node.post
    return f"node|{p.platform.value}|{p.username}|{p.publish_time.strftime('%Y%m%d%H%M')}|{hash(p.content[:50]) % 10000:04d}"


def _build_sentiment_key(point: SentimentTurningPoint) -> str:
    return f"sent|{point.time_point.strftime('%Y%m%d%H%M')}|{hash(point.description[:30]) % 10000:04d}"


def save_review_session(event_id: str, first_nodes: List[KeyNode],
                        amp_nodes: List[KeyNode],
                        sentiment_points: List[SentimentTurningPoint]) -> int:
    data: Dict = {"version": 1, "nodes": {}, "sentiments": {}}
    reviewed = 0

    for node in first_nodes:
        if node.review_status != "待复核":
            data["nodes"][_build_node_key(node)] = {"status": node.review_status, "reason": ""}
            reviewed += 1
    for node in amp_nodes:
        if node.review_status != "待复核":
            data["nodes"][_build_node_key(node)] = {"status": node.review_status, "reason": ""}
            reviewed += 1
    for point in sentiment_points:
        if point.review_status != "待复核":
            data["sentiments"][_build_sentiment_key(point)] = {
                "status": point.review_status,
                "reason": getattr(point, 'review_reason', ''),
            }
            reviewed += 1

    try:
        with open(_review_file_path(event_id), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  {Fore.YELLOW}警告：保存复核记录失败：{str(e)}{Style.RESET_ALL}")

    return reviewed


def load_review_session(event_id: str, first_nodes: List[KeyNode],
                        amp_nodes: List[KeyNode],
                        sentiment_points: List[SentimentTurningPoint]) -> int:
    path = _review_file_path(event_id)
    if not os.path.exists(path):
        return 0

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return 0

    applied = 0
    node_map: Dict[str, dict] = data.get("nodes", {})
    sent_map: Dict[str, dict] = data.get("sentiments", {})

    for node in first_nodes:
        key = _build_node_key(node)
        if key in node_map:
            node.review_status = node_map[key].get("status", "待复核")
            applied += 1
    for node in amp_nodes:
        key = _build_node_key(node)
        if key in node_map:
            node.review_status = node_map[key].get("status", "待复核")
            applied += 1
    for point in sentiment_points:
        key = _build_sentiment_key(point)
        if key in sent_map:
            point.review_status = sent_map[key].get("status", "待复核")
            point.review_reason = sent_map[key].get("reason", "")
            applied += 1

    return applied


def clear_review_session(event_id: str):
    path = _review_file_path(event_id)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def get_review_summary(result: AnalysisResult) -> Dict[str, int]:
    categories = ["可信", "存疑", "排除", "待复核"]
    summary = {cat: 0 for cat in categories}

    for nodes in (result.first_post_nodes, result.amplification_nodes):
        for n in nodes:
            summary[n.review_status] = summary.get(n.review_status, 0) + 1
    for p in result.sentiment_turning_points:
        summary[p.review_status] = summary.get(p.review_status, 0) + 1

    return summary


def _sync_timeline_from_nodes(timeline: List[TimelineNode],
                              first_nodes: List[KeyNode],
                              amp_nodes: List[KeyNode],
                              sentiment_points: List[SentimentTurningPoint]):
    for tnode in timeline:
        ref = tnode._source_ref
        if not ref:
            continue
        try:
            kind, idx_str = ref.split("|", 1)
            idx = int(idx_str)
        except Exception:
            continue

        if kind == "first" and idx < len(first_nodes):
            tnode.review_status = first_nodes[idx].review_status
        elif kind == "amp" and idx < len(amp_nodes):
            tnode.review_status = amp_nodes[idx].review_status
        elif kind == "sentiment" and idx < len(sentiment_points):
            tnode.review_status = sentiment_points[idx].review_status


def _review_one_node(node: KeyNode, index: int, total: int) -> str:
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}--- 复核进度：{index}/{total} ---{Style.RESET_ALL}")
    _print_key_node(node, index, show_status=True)

    print(f"{Fore.CYAN}操作选项：")
    print(f"  1/k/y → 可信    2/d → 存疑    3/n → 排除    Enter/s → 跳过")
    print(f"  w → 保存进度    q → 退出复核")

    while True:
        choice = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 请选择：").strip().lower()

        if choice == "q":
            return "quit"
        if choice == "w":
            return "save"
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
            print(f"      · {tp.platform.value} @{tp.username}: {_truncate_text(tp.content, 50)}")

    print(f"\n{Fore.CYAN}操作选项：")
    print(f"  1/k/y → 可信    2/d → 存疑    3/n → 排除    Enter/s → 跳过")
    print(f"  w → 保存进度    q → 退出复核")

    while True:
        choice = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 请选择：").strip().lower()

        if choice == "q":
            return "quit", ""
        if choice == "w":
            return "save", ""
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


def _filter_excluded_timeline(timeline: List[TimelineNode]) -> List[TimelineNode]:
    return [t for t in timeline if t.review_status != "排除"]


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

    applied = load_review_session(event_id, result.first_post_nodes,
                                  result.amplification_nodes,
                                  result.sentiment_turning_points)
    if applied > 0:
        remaining = total - sum(
            1 for _, _, item in all_items if item.review_status != "待复核"
        )
        print(f"{Fore.GREEN}发现历史复核记录，已恢复 {applied} 项标记，剩余 {remaining} 项待复核{Style.RESET_ALL}")
        print()
        action = input(f"{Fore.YELLOW}?{Style.RESET_ALL} [c]继续剩余  [r]重置从头开始  [a]放弃复核: ").strip().lower()
        if action == "r":
            for _, _, item in all_items:
                item.review_status = "待复核"
                if hasattr(item, 'review_reason'):
                    item.review_reason = ""
            clear_review_session(event_id)
            print(f"{Fore.YELLOW}已重置复核进度{Style.RESET_ALL}")
        elif action == "a":
            return result
    else:
        start = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 按回车开始复核，输入 q 跳过：").strip().lower()
        if start == "q":
            return result

    reviewed_count = 0
    quit_flag = False

    for i, (item_type, category, item) in enumerate(all_items, 1):
        if quit_flag:
            break

        if item.review_status != "待复核":
            continue

        save_now = False

        if item_type == "node":
            status = _review_one_node(item, i, total)
            if status == "quit":
                quit_flag = True
                continue
            if status == "save":
                save_now = True
                status = None
            if status == "跳过" or status is None:
                pass
            else:
                item.review_status = status
                reviewed_count += 1
        else:
            status, reason = _review_one_sentiment(item, i, total)
            if status == "quit":
                quit_flag = True
                continue
            if status == "save":
                save_now = True
                status = None
            if status == "跳过" or status is None:
                pass
            else:
                item.review_status = status
                item.review_reason = reason
                reviewed_count += 1

        if save_now:
            saved = save_review_session(event_id, result.first_post_nodes,
                                        result.amplification_nodes,
                                        result.sentiment_turning_points)
            print(f"  {Fore.GREEN}进度已保存（已标记 {saved} 条）{Style.RESET_ALL}")
            i -= 1
            continue

        if reviewed_count % 5 == 0 and reviewed_count > 0:
            save_review_session(event_id, result.first_post_nodes,
                                result.amplification_nodes,
                                result.sentiment_turning_points)

    final_saved = save_review_session(event_id, result.first_post_nodes,
                                      result.amplification_nodes,
                                      result.sentiment_turning_points)

    if quit_flag:
        print(f"\n{Fore.YELLOW}已退出复核模式，本会话新增标记 {reviewed_count} 条，"
              f"合计已标记 {final_saved} 条，进度已保存{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.GREEN}复核完成，共标记 {final_saved} 条，进度已保存{Style.RESET_ALL}")
        clear_review_session(event_id)

    first_nodes = [item for _, cat, item in all_items if cat == "first"]
    amp_nodes = [item for _, cat, item in all_items if cat == "amp"]
    sentiment_points = [item for _, cat, item in all_items if cat == "sentiment"]

    first_nodes_sorted = _sort_key_nodes(first_nodes)
    amp_nodes_sorted = _sort_key_nodes(amp_nodes)
    sentiment_sorted = _sort_sentiment_points(sentiment_points)

    timeline = getattr(result, 'timeline', [])
    if timeline:
        _sync_timeline_from_nodes(timeline, first_nodes_sorted, amp_nodes_sorted, sentiment_sorted)

    new_result = AnalysisResult(
        first_post_nodes=first_nodes_sorted,
        amplification_nodes=amp_nodes_sorted,
        sentiment_turning_points=sentiment_sorted,
        timeline=timeline,
        total_posts=result.total_posts,
        time_range=result.time_range,
        data_source=result.data_source,
        source_file=result.source_file,
        engagement_caliber=getattr(result, 'engagement_caliber', "分字段统计"),
        import_stats=getattr(result, 'import_stats', []),
    )

    _print_reviewed_report(new_result, event_id)

    return new_result


def get_trusted_result(result: AnalysisResult) -> AnalysisResult:
    timeline = getattr(result, 'timeline', [])
    filtered_timeline = _filter_excluded_timeline(timeline) if timeline else []

    return AnalysisResult(
        first_post_nodes=_filter_excluded(result.first_post_nodes),
        amplification_nodes=_filter_excluded(result.amplification_nodes),
        sentiment_turning_points=_filter_excluded_sentiment(result.sentiment_turning_points),
        timeline=filtered_timeline,
        total_posts=result.total_posts,
        time_range=result.time_range,
        data_source=result.data_source,
        source_file=result.source_file,
        engagement_caliber=getattr(result, 'engagement_caliber', "分字段统计"),
        import_stats=getattr(result, 'import_stats', []),
    )


def _print_reviewed_report(result: AnalysisResult, event_id: str):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  复核后简版结论")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.LIGHTBLACK_EX}  事件编号：{event_id}")
    print(f"{Fore.LIGHTBLACK_EX}  时间范围：{result.time_range}")
    print(f"{Fore.LIGHTBLACK_EX}  互动量口径：{getattr(result, 'engagement_caliber', '分字段统计')}")
    print(f"{Fore.CYAN}{'-' * 60}{Style.RESET_ALL}\n")

    summary = get_review_summary(result)

    print(f"{Fore.WHITE}{Style.BRIGHT}> 复核统计汇总{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}可信：{summary.get('可信', 0)}{Style.RESET_ALL}"
          f"  {Fore.YELLOW}存疑：{summary.get('存疑', 0)}{Style.RESET_ALL}"
          f"  {Fore.RED}排除：{summary.get('排除', 0)}{Style.RESET_ALL}"
          f"  {Fore.LIGHTBLACK_EX}待复核：{summary.get('待复核', 0)}{Style.RESET_ALL}")
    print()

    first_trusted = [n for n in result.first_post_nodes if n.review_status == "可信"]
    first_doubt = [n for n in result.first_post_nodes if n.review_status == "存疑"]
    first_excluded = [n for n in result.first_post_nodes if n.review_status == "排除"]

    amp_trusted = [n for n in result.amplification_nodes if n.review_status == "可信"]
    amp_doubt = [n for n in result.amplification_nodes if n.review_status == "存疑"]
    amp_excluded = [n for n in result.amplification_nodes if n.review_status == "排除"]

    sent_trusted = [p for p in result.sentiment_turning_points if p.review_status == "可信"]
    sent_doubt = [p for p in result.sentiment_turning_points if p.review_status == "存疑"]
    sent_excluded = [p for p in result.sentiment_turning_points if p.review_status == "排除"]

    if first_trusted:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}> 可信首发线索 Top{min(3, len(first_trusted))}{Style.RESET_ALL}")
        for i, node in enumerate(first_trusted[:3], 1):
            p = node.post
            print(f"  {i}. [{p.publish_time.strftime('%m-%d %H:%M')}] {p.platform.value} @{p.username}")
            print(f"     {_truncate_text(p.content, 45)}")

    if amp_trusted:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}> 可信传播节点 Top{min(3, len(amp_trusted))}{Style.RESET_ALL}")
        for i, node in enumerate(amp_trusted[:3], 1):
            p = node.post
            print(f"  {i}. [{p.publish_time.strftime('%m-%d %H:%M')}] {p.platform.value} @{p.username}")
            if p.total_engagement is not None and p.total_engagement > 0 \
                    and p.repost_count == 0 and p.comment_count == 0 \
                    and p.like_count == 0 and p.share_count == 0:
                print(f"     总互动量：{_format_num(p.total_engagement)}")
            else:
                print(f"     转{p.repost_count} 评{p.comment_count} 赞{p.like_count}")
            print(f"     {_truncate_text(p.content, 45)}")

    if sent_trusted:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}> 可信情绪拐点 Top{min(2, len(sent_trusted))}{Style.RESET_ALL}")
        for i, point in enumerate(sent_trusted[:2], 1):
            neg = point.sentiment_ratio["负面"] * 100
            print(f"  {i}. [{point.time_point.strftime('%m-%d %H:%M')}] 负面{neg:.0f}% - {point.description[:30]}")

    timeline = getattr(result, 'timeline', [])
    timeline_filtered = _filter_excluded_timeline(timeline)
    if timeline_filtered:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}> 传播时间线（过滤排除项，{len(timeline_filtered)}个节点）{Style.RESET_ALL}")
        daily_tl = _build_daily_timeline(timeline_filtered, filter_excluded=True)
        for line in daily_tl.split("\n"):
            print(f"  {line}")

    total_excluded = len(first_excluded) + len(amp_excluded) + len(sent_excluded)
    if total_excluded > 0:
        print(f"\n{Fore.LIGHTBLACK_EX}({total_excluded} 项已排除，不纳入最终简报){Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")
