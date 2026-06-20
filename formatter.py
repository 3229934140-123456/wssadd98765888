from colorama import Fore, Style, init

from models import AnalysisResult, KeyNode, SentimentTurningPoint

init(autoreset=True)


def _format_num(n: int) -> str:
    if n >= 100000000:
        return f"{n/100000000:.1f}亿"
    elif n >= 10000:
        return f"{n/10000:.1f}万"
    return str(n)


def _truncate_text(text: str, max_len: int = 60) -> str:
    clean_text = text.replace("\n", " ").replace("\r", " ")
    while "  " in clean_text:
        clean_text = clean_text.replace("  ", " ")
    if len(clean_text) <= max_len:
        return clean_text
    return clean_text[:max_len] + "..."


def _print_section_title(title: str, count: int):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'-' * 56}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  {title}  ({count}条)")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'-' * 56}{Style.RESET_ALL}\n")


def _print_key_node(node: KeyNode, index: int, show_status: bool = False):
    post = node.post
    status_color = {
        "可信": Fore.GREEN,
        "存疑": Fore.YELLOW,
        "排除": Fore.RED,
        "待复核": Fore.WHITE,
    }.get(node.review_status, Fore.WHITE)

    status_str = f" [{status_color}{node.review_status}{Style.RESET_ALL}]" if show_status else ""

    print(f"{Fore.WHITE}{Style.BRIGHT}  [{index}] {node.node_type}{status_str}")
    print(f"    {Fore.LIGHTBLACK_EX}发布时间：{post.publish_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"    {Fore.LIGHTBLACK_EX}平台：{post.platform.value}  |  账号：{post.username}")

    verif_str = post.verification.value
    if post.verification.value == "未认证":
        verif_color = Fore.LIGHTBLACK_EX
    elif post.verification.value in ["政府认证", "媒体认证"]:
        verif_color = Fore.RED
    else:
        verif_color = Fore.BLUE
    print(f"    {Fore.LIGHTBLACK_EX}认证：{verif_color}{verif_str}"
          f"{Fore.LIGHTBLACK_EX}  |  粉丝：{_format_num(post.followers_count)}")

    print(f"    {Fore.LIGHTBLACK_EX}互动：转{_format_num(post.repost_count)} "
          f"评{_format_num(post.comment_count)} 赞{_format_num(post.like_count)} "
          f"分享{_format_num(post.share_count)}")

    orig_tag = f"{Fore.GREEN}[原创]{Style.RESET_ALL} " if post.is_original else ""
    sent_color = {
        "正面": Fore.GREEN,
        "中性": Fore.LIGHTBLACK_EX,
        "负面": Fore.RED,
    }.get(post.sentiment.value, Fore.WHITE)
    print(f"    {orig_tag}{sent_color}[{post.sentiment.value}]{Style.RESET_ALL} "
          f"{Fore.WHITE}{_truncate_text(post.content, 80)}")

    print(f"    {Fore.MAGENTA}> 判断理由：{node.reason}")
    print()


def _print_sentiment_point(point: SentimentTurningPoint, index: int):
    print(f"{Fore.WHITE}{Style.BRIGHT}  [{index}] 情绪拐点 · {point.time_point.strftime('%Y-%m-%d %H:%M')}")
    print(f"    {Fore.LIGHTBLACK_EX}{point.description}")

    pos_pct = point.sentiment_ratio["正面"] * 100
    neu_pct = point.sentiment_ratio["中性"] * 100
    neg_pct = point.sentiment_ratio["负面"] * 100

    bar_len = 40
    pos_bar = int(bar_len * point.sentiment_ratio["正面"]) * "#"
    neu_bar = int(bar_len * point.sentiment_ratio["中性"]) * "-"
    neg_bar = int(bar_len * point.sentiment_ratio["负面"]) * "="

    print(f"    {Fore.GREEN}正面 {pos_pct:.0f}%{Style.RESET_ALL}  "
          f"{Fore.LIGHTBLACK_EX}中性 {neu_pct:.0f}%{Style.RESET_ALL}  "
          f"{Fore.RED}负面 {neg_pct:.0f}%{Style.RESET_ALL}")
    print(f"    {Fore.GREEN}{pos_bar}{Fore.LIGHTBLACK_EX}{neu_bar}{Fore.RED}{neg_bar}{Style.RESET_ALL}")

    if point.trigger_posts:
        print(f"    {Fore.LIGHTBLACK_EX}关联热帖：")
        for tp in point.trigger_posts:
            print(f"      · {tp.platform.value} @{tp.username}: "
                  f"{_truncate_text(tp.content, 50)}")
    print()


def print_summary_header(result: AnalysisResult, event_id: str):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  舆情热点溯源分析报告")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.LIGHTBLACK_EX}  事件编号：{event_id}")
    print(f"{Fore.LIGHTBLACK_EX}  时间范围：{result.time_range}")
    print(f"{Fore.LIGHTBLACK_EX}  样本总量：{result.total_posts} 条")
    print(f"{Fore.CYAN}{'-' * 60}{Style.RESET_ALL}")


def print_full_report(result: AnalysisResult, event_id: str):
    print_summary_header(result, event_id)

    _print_section_title("一、疑似首发线索", len(result.first_post_nodes))
    for i, node in enumerate(result.first_post_nodes, 1):
        _print_key_node(node, i)

    _print_section_title("二、传播放大节点", len(result.amplification_nodes))
    for i, node in enumerate(result.amplification_nodes, 1):
        _print_key_node(node, i)

    _print_section_title("三、情绪拐点提示", len(result.sentiment_turning_points))
    for i, point in enumerate(result.sentiment_turning_points, 1):
        _print_sentiment_point(point, i)

    print(f"\n{Fore.CYAN}{'=' * 60}")
    print(f"{Fore.CYAN}  报告生成完毕，共 {result.total_posts} 条样本")
    print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")


def print_report_for_daily(result: AnalysisResult, event_id: str) -> str:
    lines = []
    lines.append(f"【舆情溯源简报】事件编号：{event_id}")
    lines.append(f"时间范围：{result.time_range}  样本量：{result.total_posts}")
    lines.append("")

    lines.append("[疑似首发线索]")
    for i, node in enumerate(result.first_post_nodes[:5], 1):
        p = node.post
        lines.append(
            f"  {i}. [{p.publish_time.strftime('%m-%d %H:%M')}] {p.platform.value} "
            f"@{p.username}({p.verification.value}/{_format_num(p.followers_count)}粉)"
        )
        lines.append(f"     摘要：{_truncate_text(p.content, 50)}")
        lines.append(f"     判定：{node.reason}")
    lines.append("")

    lines.append("[传播放大节点]")
    for i, node in enumerate(result.amplification_nodes[:5], 1):
        p = node.post
        lines.append(
            f"  {i}. [{p.publish_time.strftime('%m-%d %H:%M')}] {p.platform.value} "
            f"@{p.username}({p.verification.value})"
        )
        lines.append(
            f"     互动：转{_format_num(p.repost_count)} 评{_format_num(p.comment_count)} "
            f"赞{_format_num(p.like_count)}"
        )
        lines.append(f"     摘要：{_truncate_text(p.content, 50)}")
        lines.append(f"     判定：{node.reason}")
    lines.append("")

    lines.append("[情绪拐点提示]")
    for i, point in enumerate(result.sentiment_turning_points[:3], 1):
        pos = point.sentiment_ratio["正面"] * 100
        neu = point.sentiment_ratio["中性"] * 100
        neg = point.sentiment_ratio["负面"] * 100
        lines.append(
            f"  {i}. [{point.time_point.strftime('%m-%d %H:%M')}] 正{pos:.0f}%/中{neu:.0f}%/负{neg:.0f}%"
        )
        lines.append(f"     {point.description}")
    lines.append("")

    return "\n".join(lines)
