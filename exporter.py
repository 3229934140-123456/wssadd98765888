import os
from datetime import datetime
from typing import Optional

from colorama import Fore, Style, init

from models import AnalysisResult
from formatter import _format_num, _truncate_text

init(autoreset=True)


def _generate_filename(event_id: str, suffix: str, ext: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_event_id = "".join(c for c in event_id if c.isalnum() or c in ("-", "_"))
    return f"TRACE_{safe_event_id}_{suffix}_{timestamp}.{ext}"


def _generate_full_report_text(result: AnalysisResult, event_id: str, filter_excluded: bool = False) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("  舆情热点溯源分析报告")
    lines.append("=" * 60)
    lines.append(f"  事件编号：{event_id}")
    lines.append(f"  时间范围：{result.time_range}")
    lines.append(f"  样本总量：{result.total_posts} 条")
    lines.append(f"  数据来源：{result.data_source.value}")
    if result.source_file:
        lines.append(f"  来源文件：{result.source_file}")
    lines.append(f"  生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("-" * 60)
    lines.append("")

    first_nodes = result.first_post_nodes
    amp_nodes = result.amplification_nodes
    sentiment_points = result.sentiment_turning_points

    if filter_excluded:
        first_nodes = [n for n in first_nodes if n.review_status != "排除"]
        amp_nodes = [n for n in amp_nodes if n.review_status != "排除"]
        sentiment_points = [p for p in sentiment_points if p.review_status != "排除"]

    lines.append("-" * 56)
    lines.append(f"  一、疑似首发线索  ({len(first_nodes)}条)")
    lines.append("-" * 56)
    lines.append("")

    for i, node in enumerate(first_nodes, 1):
        p = node.post
        status = f" [{node.review_status}]" if node.review_status != "待复核" else ""
        lines.append(f"  [{i}] {node.node_type}{status}")
        lines.append(f"    发布时间：{p.publish_time.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"    平台：{p.platform.value}  |  账号：{p.username}")
        lines.append(f"    认证：{p.verification.value}  |  粉丝：{_format_num(p.followers_count)}")
        lines.append(f"    互动：转{_format_num(p.repost_count)} 评{_format_num(p.comment_count)} "
                     f"赞{_format_num(p.like_count)} 分享{_format_num(p.share_count)}")
        orig_tag = "[原创] " if p.is_original else ""
        lines.append(f"    {orig_tag}[{p.sentiment.value}] {_truncate_text(p.content, 100)}")
        lines.append(f"    > 判断理由：{node.reason}")
        lines.append("")

    lines.append("-" * 56)
    lines.append(f"  二、传播放大节点  ({len(amp_nodes)}条)")
    lines.append("-" * 56)
    lines.append("")

    for i, node in enumerate(amp_nodes, 1):
        p = node.post
        status = f" [{node.review_status}]" if node.review_status != "待复核" else ""
        lines.append(f"  [{i}] {node.node_type}{status}")
        lines.append(f"    发布时间：{p.publish_time.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"    平台：{p.platform.value}  |  账号：{p.username}")
        lines.append(f"    认证：{p.verification.value}  |  粉丝：{_format_num(p.followers_count)}")
        lines.append(f"    互动：转{_format_num(p.repost_count)} 评{_format_num(p.comment_count)} "
                     f"赞{_format_num(p.like_count)} 分享{_format_num(p.share_count)}")
        orig_tag = "[原创] " if p.is_original else ""
        lines.append(f"    {orig_tag}[{p.sentiment.value}] {_truncate_text(p.content, 100)}")
        lines.append(f"    > 判断理由：{node.reason}")
        lines.append("")

    lines.append("-" * 56)
    lines.append(f"  三、情绪拐点提示  ({len(sentiment_points)}条)")
    lines.append("-" * 56)
    lines.append("")

    for i, point in enumerate(sentiment_points, 1):
        status = f" [{point.review_status}]" if point.review_status != "待复核" else ""
        pos = point.sentiment_ratio["正面"] * 100
        neu = point.sentiment_ratio["中性"] * 100
        neg = point.sentiment_ratio["负面"] * 100
        lines.append(f"  [{i}] 情绪拐点 · {point.time_point.strftime('%Y-%m-%d %H:%M')}{status}")
        lines.append(f"    {point.description}")
        lines.append(f"    正面 {pos:.0f}%  |  中性 {neu:.0f}%  |  负面 {neg:.0f}%")

        if point.trigger_posts:
            lines.append(f"    关联热帖：")
            for tp in point.trigger_posts:
                lines.append(f"      · {tp.platform.value} @{tp.username}: {_truncate_text(tp.content, 60)}")
        lines.append("")

    excluded_count = (
        len([n for n in result.first_post_nodes if n.review_status == "排除"]) +
        len([n for n in result.amplification_nodes if n.review_status == "排除"]) +
        len([p for p in result.sentiment_turning_points if p.review_status == "排除"])
    )
    if filter_excluded and excluded_count > 0:
        lines.append("-" * 60)
        lines.append(f"  注：共 {excluded_count} 项已标记为「排除」，未纳入本报告")
        lines.append("-" * 60)
        lines.append("")

    lines.append("=" * 60)
    lines.append(f"  报告生成完毕，共 {result.total_posts} 条样本")
    lines.append("=" * 60)
    lines.append("")

    return "\n".join(lines)


def _generate_full_report_markdown(result: AnalysisResult, event_id: str, filter_excluded: bool = False) -> str:
    lines = []
    lines.append("# 舆情热点溯源分析报告")
    lines.append("")
    lines.append("| 项目 | 内容 |")
    lines.append("|------|------|")
    lines.append(f"| 事件编号 | {event_id} |")
    lines.append(f"| 时间范围 | {result.time_range} |")
    lines.append(f"| 样本总量 | {result.total_posts} 条 |")
    lines.append(f"| 数据来源 | {result.data_source.value} |")
    if result.source_file:
        lines.append(f"| 来源文件 | {result.source_file} |")
    lines.append(f"| 生成时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |")
    lines.append("")

    first_nodes = result.first_post_nodes
    amp_nodes = result.amplification_nodes
    sentiment_points = result.sentiment_turning_points

    if filter_excluded:
        first_nodes = [n for n in first_nodes if n.review_status != "排除"]
        amp_nodes = [n for n in amp_nodes if n.review_status != "排除"]
        sentiment_points = [p for p in sentiment_points if p.review_status != "排除"]

    lines.append("## 一、疑似首发线索")
    lines.append(f"共 **{len(first_nodes)}** 条")
    lines.append("")

    for i, node in enumerate(first_nodes, 1):
        p = node.post
        status = f" <span style='color:red'>[{node.review_status}]</span>" if node.review_status == "排除" else \
                 f" <span style='color:orange'>[{node.review_status}]</span>" if node.review_status == "存疑" else \
                 f" <span style='color:green'>[{node.review_status}]</span>" if node.review_status == "可信" else ""
        lines.append(f"### [{i}] {node.node_type}{status}")
        lines.append("")
        lines.append(f"- **发布时间**：{p.publish_time.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"- **平台**：{p.platform.value}")
        lines.append(f"- **账号**：{p.username}")
        lines.append(f"- **认证**：{p.verification.value}")
        lines.append(f"- **粉丝**：{_format_num(p.followers_count)}")
        lines.append(f"- **互动数据**：转发 {_format_num(p.repost_count)} / 评论 {_format_num(p.comment_count)} / 点赞 {_format_num(p.like_count)} / 分享 {_format_num(p.share_count)}")
        orig_tag = "**[原创]** " if p.is_original else ""
        sent_emoji = "🟢" if p.sentiment.value == "正面" else "⚪" if p.sentiment.value == "中性" else "🔴"
        lines.append(f"- **内容**：{orig_tag}{sent_emoji}[{p.sentiment.value}] {_truncate_text(p.content, 150)}")
        lines.append(f"- **判断理由**：{node.reason}")
        lines.append("")

    lines.append("## 二、传播放大节点")
    lines.append(f"共 **{len(amp_nodes)}** 条")
    lines.append("")

    for i, node in enumerate(amp_nodes, 1):
        p = node.post
        status = f" <span style='color:red'>[{node.review_status}]</span>" if node.review_status == "排除" else \
                 f" <span style='color:orange'>[{node.review_status}]</span>" if node.review_status == "存疑" else \
                 f" <span style='color:green'>[{node.review_status}]</span>" if node.review_status == "可信" else ""
        lines.append(f"### [{i}] {node.node_type}{status}")
        lines.append("")
        lines.append(f"- **发布时间**：{p.publish_time.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"- **平台**：{p.platform.value}")
        lines.append(f"- **账号**：{p.username}")
        lines.append(f"- **认证**：{p.verification.value}")
        lines.append(f"- **粉丝**：{_format_num(p.followers_count)}")
        lines.append(f"- **互动数据**：转发 {_format_num(p.repost_count)} / 评论 {_format_num(p.comment_count)} / 点赞 {_format_num(p.like_count)} / 分享 {_format_num(p.share_count)}")
        orig_tag = "**[原创]** " if p.is_original else ""
        sent_emoji = "🟢" if p.sentiment.value == "正面" else "⚪" if p.sentiment.value == "中性" else "🔴"
        lines.append(f"- **内容**：{orig_tag}{sent_emoji}[{p.sentiment.value}] {_truncate_text(p.content, 150)}")
        lines.append(f"- **判断理由**：{node.reason}")
        lines.append("")

    lines.append("## 三、情绪拐点提示")
    lines.append(f"共 **{len(sentiment_points)}** 条")
    lines.append("")

    for i, point in enumerate(sentiment_points, 1):
        status = f" <span style='color:red'>[{point.review_status}]</span>" if point.review_status == "排除" else \
                 f" <span style='color:orange'>[{point.review_status}]</span>" if point.review_status == "存疑" else \
                 f" <span style='color:green'>[{point.review_status}]</span>" if point.review_status == "可信" else ""
        pos = point.sentiment_ratio["正面"] * 100
        neu = point.sentiment_ratio["中性"] * 100
        neg = point.sentiment_ratio["负面"] * 100
        lines.append(f"### [{i}] 情绪拐点 · {point.time_point.strftime('%Y-%m-%d %H:%M')}{status}")
        lines.append("")
        lines.append(f"- **描述**：{point.description}")
        lines.append(f"- **情绪分布**：")
        lines.append(f"  - 🟢 正面：{pos:.1f}%")
        lines.append(f"  - ⚪ 中性：{neu:.1f}%")
        lines.append(f"  - 🔴 负面：{neg:.1f}%")

        if point.trigger_posts:
            lines.append(f"- **关联热帖**：")
            for tp in point.trigger_posts:
                lines.append(f"  - {tp.platform.value} @{tp.username}: {_truncate_text(tp.content, 80)}")
        lines.append("")

    excluded_count = (
        len([n for n in result.first_post_nodes if n.review_status == "排除"]) +
        len([n for n in result.amplification_nodes if n.review_status == "排除"]) +
        len([p for p in result.sentiment_turning_points if p.review_status == "排除"])
    )
    if filter_excluded and excluded_count > 0:
        lines.append("---")
        lines.append(f"> **注**：共 {excluded_count} 项已标记为「排除」，未纳入本报告")
        lines.append("")

    lines.append("---")
    lines.append(f"*报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    lines.append("")

    return "\n".join(lines)


def _generate_daily_text(result: AnalysisResult, event_id: str, filter_excluded: bool = True) -> str:
    from formatter import print_report_for_daily
    return print_report_for_daily(result, event_id, filter_excluded=filter_excluded)


def export_report(result: AnalysisResult, event_id: str, output_dir: str = ".",
                  filter_excluded: bool = True, reviewed: bool = False) -> Optional[str]:
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  导出报告")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    print(f"{Fore.GREEN}可选格式：")
    print(f"  1. TXT 格式（纯文本，适合复制到日报）")
    print(f"  2. Markdown 格式（带格式，适合归档）")
    print(f"  3. 同时导出 TXT + Markdown")
    print()

    while True:
        choice = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 请选择格式 (1/2/3) [3]: ").strip()
        if choice == "":
            choice = "3"
        if choice in ("1", "2", "3"):
            break
        print(f"{Fore.RED}无效选择，请输入 1、2 或 3{Style.RESET_ALL}")

    suffix = "reviewed" if reviewed else "full"
    saved_files = []

    try:
        os.makedirs(output_dir, exist_ok=True)

        if choice in ("1", "3"):
            filename = _generate_filename(event_id, suffix, "txt")
            filepath = os.path.join(output_dir, filename)

            content = _generate_full_report_text(result, event_id, filter_excluded=filter_excluded)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            saved_files.append(filepath)
            print(f"{Fore.GREEN}✓ 已导出 TXT：{filepath}{Style.RESET_ALL}")

        if choice in ("2", "3"):
            filename = _generate_filename(event_id, suffix, "md")
            filepath = os.path.join(output_dir, filename)

            content = _generate_full_report_markdown(result, event_id, filter_excluded=filter_excluded)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            saved_files.append(filepath)
            print(f"{Fore.GREEN}✓ 已导出 Markdown：{filepath}{Style.RESET_ALL}")

        if choice in ("1", "3"):
            daily_filename = _generate_filename(event_id, f"{suffix}_daily", "txt")
            daily_filepath = os.path.join(output_dir, daily_filename)
            daily_content = _generate_daily_text(result, event_id, filter_excluded=filter_excluded)
            with open(daily_filepath, "w", encoding="utf-8") as f:
                f.write(daily_content)
            saved_files.append(daily_filepath)
            print(f"{Fore.GREEN}✓ 已导出日报简报：{daily_filepath}{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}导出失败：{str(e)}{Style.RESET_ALL}")
        return None

    print(f"\n{Fore.CYAN}共导出 {len(saved_files)} 个文件{Style.RESET_ALL}")
    return saved_files[0] if saved_files else None


def prompt_export(result: AnalysisResult, event_id: str, reviewed: bool = False) -> bool:
    print(f"\n{Fore.YELLOW}是否导出报告文件？{Style.RESET_ALL}")
    choice = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 输入 y 导出，其他键跳过：").strip().lower()

    if choice in ("y", "yes", "是"):
        export_report(result, event_id, filter_excluded=True, reviewed=reviewed)
        return True
    return False
