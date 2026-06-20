import json
import os
from datetime import datetime
from typing import Optional, Tuple

from colorama import Fore, Style, init

from models import AnalysisResult
from formatter import _format_num, _truncate_text

init(autoreset=True)

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".trace_workbench_config.json")


def load_config() -> dict:
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"{Fore.YELLOW}警告：无法保存配置：{str(e)}{Style.RESET_ALL}")


def get_last_output_dir() -> Optional[str]:
    cfg = load_config()
    return cfg.get("last_output_dir")


def set_last_output_dir(path: str):
    cfg = load_config()
    cfg["last_output_dir"] = os.path.abspath(path)
    save_config(cfg)


def _ensure_output_dir(path: str) -> Tuple[bool, str]:
    try:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            os.makedirs(abs_path, exist_ok=True)
            return True, f"已创建目录：{abs_path}"
        if os.path.isdir(abs_path):
            return True, f"使用现有目录：{abs_path}"
        return False, f"路径已存在但不是目录：{abs_path}"
    except PermissionError:
        return False, f"权限不足，无法创建目录：{path}"
    except OSError as e:
        return False, f"创建目录失败：{str(e)}"


def _generate_filename(event_id: str, suffix: str, ext: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_event_id = "".join(c for c in event_id if c.isalnum() or c in ("-", "_"))
    return f"TRACE_{safe_event_id}_{suffix}_{timestamp}.{ext}"


def _generate_timeline_text(timeline: list, indent: str = "    ",
                            filter_excluded: bool = False) -> list:
    lines = []
    if not timeline:
        return lines

    nodes = [t for t in timeline if not (filter_excluded and t.review_status == "排除")]
    if not nodes:
        lines.append(f"{indent}（暂无有效节点）")
        return lines

    type_icons = {"首发线索": "[起]", "放大节点": "[扩]", "情绪拐点": "[情]"}
    for i, node in enumerate(nodes, 1):
        icon = type_icons.get(node.node_type, "[·]")
        time_str = node.time_point.strftime("%m-%d %H:%M")
        status = f" [{node.review_status}]" if node.review_status != "待复核" else ""
        lines.append(f"{indent}{i}. [{time_str}]{icon} {node.title}{status}")
        lines.append(f"{indent}   {node.description}")
    return lines


def _calc_review_summary(result: AnalysisResult) -> dict:
    from reviewer import get_review_summary
    try:
        return get_review_summary(result)
    except Exception:
        return {}


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

    engagement_caliber = getattr(result, 'engagement_caliber', "分字段统计")
    lines.append(f"  互动量口径：{engagement_caliber}")

    rev_summary = _calc_review_summary(result)
    if rev_summary and sum(rev_summary.values()) > 0:
        stats_parts = []
        for k, v in rev_summary.items():
            if v > 0:
                stats_parts.append(f"{k} {v}")
        if stats_parts:
            lines.append(f"  复核状态：{' / '.join(stats_parts)}")

    lines.append(f"  生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("-" * 60)
    lines.append("")

    first_nodes = result.first_post_nodes
    amp_nodes = result.amplification_nodes
    sentiment_points = result.sentiment_turning_points
    timeline = getattr(result, 'timeline', [])

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
        if p.total_engagement is not None and p.total_engagement > 0 \
                and p.repost_count == 0 and p.comment_count == 0 \
                and p.like_count == 0 and p.share_count == 0:
            lines.append(f"    总互动量：{_format_num(p.total_engagement)}")
        else:
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
        if p.total_engagement is not None and p.total_engagement > 0 \
                and p.repost_count == 0 and p.comment_count == 0 \
                and p.like_count == 0 and p.share_count == 0:
            lines.append(f"    总互动量：{_format_num(p.total_engagement)}")
        else:
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

    timeline_count = len([t for t in timeline if not (filter_excluded and t.review_status == "排除")])
    if timeline:
        lines.append("-" * 56)
        lines.append(f"  四、传播时间线  ({timeline_count}个节点)")
        lines.append("-" * 56)
        lines.append("")
        lines.extend(_generate_timeline_text(timeline, filter_excluded=filter_excluded))
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

    engagement_caliber = getattr(result, 'engagement_caliber', "分字段统计")
    lines.append(f"| 互动量口径 | {engagement_caliber} |")

    rev_summary = _calc_review_summary(result)
    if rev_summary and sum(rev_summary.values()) > 0:
        stats_str = " / ".join(f"{k} {v}" for k, v in rev_summary.items() if v > 0)
        lines.append(f"| 复核统计 | {stats_str} |")

    lines.append(f"| 生成时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |")
    lines.append("")

    first_nodes = result.first_post_nodes
    amp_nodes = result.amplification_nodes
    sentiment_points = result.sentiment_turning_points
    timeline = getattr(result, 'timeline', [])

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
        if p.total_engagement is not None and p.total_engagement > 0 \
                and p.repost_count == 0 and p.comment_count == 0 \
                and p.like_count == 0 and p.share_count == 0:
            lines.append(f"- **总互动量**：{_format_num(p.total_engagement)}")
        else:
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
        if p.total_engagement is not None and p.total_engagement > 0 \
                and p.repost_count == 0 and p.comment_count == 0 \
                and p.like_count == 0 and p.share_count == 0:
            lines.append(f"- **总互动量**：{_format_num(p.total_engagement)}")
        else:
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

    timeline_filtered = [t for t in timeline if not (filter_excluded and t.review_status == "排除")]
    if timeline:
        lines.append("## 四、传播时间线")
        lines.append(f"共 **{len(timeline_filtered)}** 个节点")
        lines.append("")
        type_icons = {"首发线索": "🌱", "放大节点": "📣", "情绪拐点": "📊"}
        for i, node in enumerate(timeline_filtered, 1):
            icon = type_icons.get(node.node_type, "•")
            time_str = node.time_point.strftime("%m-%d %H:%M")
            status = f" `[{node.review_status}]`" if node.review_status != "待复核" else ""
            lines.append(f"**{i}. {icon} [{time_str}] {node.node_type}：{node.title}**{status}")
            lines.append("")
            lines.append(f"> {node.description}")
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


def _generate_daily_markdown(result: AnalysisResult, event_id: str, filter_excluded: bool = True) -> str:
    from formatter import print_report_for_daily
    daily_text = print_report_for_daily(result, event_id, filter_excluded=filter_excluded)
    engagement_caliber = getattr(result, 'engagement_caliber', "分字段统计")

    rev_summary = _calc_review_summary(result)

    lines = ["# 舆情溯源日报简报", ""]
    lines.append(f"**事件编号**：{event_id}")
    lines.append(f"**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**互动量口径**：{engagement_caliber}")

    if rev_summary and sum(rev_summary.values()) > 0:
        stats_str = " / ".join(f"**{k}** {v}" for k, v in rev_summary.items() if v > 0)
        lines.append(f"**复核统计**：{stats_str}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("```text")
    lines.append(daily_text)
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _prompt_output_dir(default_dir: Optional[str] = None) -> Optional[str]:
    last_dir = get_last_output_dir()
    hint_dir = default_dir or last_dir or "."

    while True:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}  导出目录")
        print(f"{Fore.CYAN}{Style.BRIGHT}{'-' * 40}{Style.RESET_ALL}")
        if last_dir:
            print(f"  {Fore.LIGHTBLACK_EX}上次使用：{last_dir}{Style.RESET_ALL}")
        print()

        prompt = f"{Fore.YELLOW}?{Style.RESET_ALL} 请输入导出目录 [{hint_dir}]: "
        choice = input(prompt).strip().strip('"').strip("'")

        target_dir = choice or hint_dir

        ok, msg = _ensure_output_dir(target_dir)
        if ok:
            print(f"  {Fore.GREEN}{msg}{Style.RESET_ALL}")
            set_last_output_dir(target_dir)
            return os.path.abspath(target_dir)
        else:
            print(f"  {Fore.RED}{msg}{Style.RESET_ALL}")
            retry = input(f"  {Fore.YELLOW}是否重试？(y/n) y{Style.RESET_ALL}").strip().lower()
            if retry not in ("", "y", "yes", "是"):
                return None


def export_report(result: AnalysisResult, event_id: str, output_dir: Optional[str] = None,
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

    target_dir = output_dir
    if target_dir is None:
        target_dir = _prompt_output_dir()
        if target_dir is None:
            print(f"{Fore.RED}已取消导出{Style.RESET_ALL}")
            return None

    ok, msg = _ensure_output_dir(target_dir)
    if not ok:
        print(f"{Fore.RED}{msg}{Style.RESET_ALL}")
        return None

    suffix_base = "reviewed" if reviewed else "full"
    saved_files = []

    try:
        if choice in ("1", "3"):
            filename = _generate_filename(event_id, suffix_base, "txt")
            filepath = os.path.join(target_dir, filename)

            content = _generate_full_report_text(result, event_id, filter_excluded=filter_excluded)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            saved_files.append(filepath)
            print(f"{Fore.GREEN}✓ 已导出完整报告(TXT)：{os.path.basename(filepath)}{Style.RESET_ALL}")

        if choice in ("2", "3"):
            filename = _generate_filename(event_id, suffix_base, "md")
            filepath = os.path.join(target_dir, filename)

            content = _generate_full_report_markdown(result, event_id, filter_excluded=filter_excluded)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            saved_files.append(filepath)
            print(f"{Fore.GREEN}✓ 已导出完整报告(Markdown)：{os.path.basename(filepath)}{Style.RESET_ALL}")

        if choice in ("1", "3"):
            daily_filename = _generate_filename(event_id, f"{suffix_base}_daily", "txt")
            daily_filepath = os.path.join(target_dir, daily_filename)
            daily_content = _generate_daily_text(result, event_id, filter_excluded=filter_excluded)
            with open(daily_filepath, "w", encoding="utf-8") as f:
                f.write(daily_content)
            saved_files.append(daily_filepath)
            print(f"{Fore.GREEN}✓ 已导出日报简报(TXT)：{os.path.basename(daily_filepath)}{Style.RESET_ALL}")

        if choice in ("2", "3"):
            daily_md_filename = _generate_filename(event_id, f"{suffix_base}_daily", "md")
            daily_md_filepath = os.path.join(target_dir, daily_md_filename)
            daily_md_content = _generate_daily_markdown(result, event_id, filter_excluded=filter_excluded)
            with open(daily_md_filepath, "w", encoding="utf-8") as f:
                f.write(daily_md_content)
            saved_files.append(daily_md_filepath)
            print(f"{Fore.GREEN}✓ 已导出日报简报(Markdown)：{os.path.basename(daily_md_filepath)}{Style.RESET_ALL}")

    except PermissionError:
        print(f"{Fore.RED}导出失败：权限不足，无法写入 {target_dir}{Style.RESET_ALL}")
        return None
    except Exception as e:
        print(f"{Fore.RED}导出失败：{str(e)}{Style.RESET_ALL}")
        return None

    print(f"\n{Fore.CYAN}共导出 {len(saved_files)} 个文件到：{target_dir}{Style.RESET_ALL}")
    return saved_files[0] if saved_files else None


def prompt_export(result: AnalysisResult, event_id: str, reviewed: bool = False) -> bool:
    print(f"\n{Fore.YELLOW}是否导出报告文件？{Style.RESET_ALL}")
    choice = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 输入 y 导出，其他键跳过：").strip().lower()

    if choice in ("y", "yes", "是"):
        export_report(result, event_id, filter_excluded=True, reviewed=reviewed)
        return True
    return False
