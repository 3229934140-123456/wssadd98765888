#!/usr/bin/env python3

import sys

from colorama import Fore, Style, init

from collector import collect_trace_config
from data_loader import prompt_data_source
from analyzer import run_analysis
from formatter import print_full_report, print_report_for_daily
from reviewer import (
    run_review_mode,
    get_trusted_result,
    _filter_excluded_timeline,
    _ensure_timeline_synced,
    _build_node_key,
    _build_sentiment_key,
)
from exporter import prompt_export

init(autoreset=True)


def print_banner():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}")
    print(f"  ======  舆情热点溯源分析工作台  ======")
    print(f"{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  Public Opinion Trace Workbench v3.0")
    print(f"{Fore.LIGHTBLACK_EX}  快速产出突发热点初步溯源结果 · 面向专业分析师{Style.RESET_ALL}")
    print()
    print(f"{Fore.LIGHTBLACK_EX}  支持：批量导入 · 智能去重 · 时间线视图 · 总互动量兼容"
          f" · 复核协作 · 样本治理 · 一键导出{Style.RESET_ALL}")
    print()


def _prompt_review_export(result, event_id):
    from reviewer import export_review_record
    print(f"\n{Fore.CYAN}{Style.BRIGHT}  复核记录导出{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}  可将本次复核结果导出为独立文件，供其他分析师合并{Style.RESET_ALL}")
    name = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 请输入复核人名称：").strip()
    if not name:
        name = "analyst"

    path = export_review_record(
        event_id, reviewer_name=name,
        first_nodes=result.first_post_nodes,
        amp_nodes=result.amplification_nodes,
        sentiment_points=result.sentiment_turning_points,
    )
    if path:
        print(f"{Fore.GREEN}✓ 复核记录已导出：{path}{Style.RESET_ALL}")
    return path


def _prompt_review_merge(event_id, result):
    from reviewer import merge_review_records, apply_merge_decision, _sort_key_nodes, _sort_sentiment_points
    from models import AnalysisResult
    print(f"\n{Fore.CYAN}{Style.BRIGHT}  合并复核记录{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}  输入之前导出的复核记录文件路径，多个用逗号分隔{Style.RESET_ALL}")
    raw = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 复核记录路径：").strip()
    if not raw:
        print(f"{Fore.YELLOW}已取消合并{Style.RESET_ALL}")
        return result

    import os
    paths = [p.strip().strip('"').strip("'") for p in raw.replace(";", ",").split(",") if p.strip()]
    paths = [p for p in paths if os.path.isfile(p)]

    if not paths:
        print(f"{Fore.RED}未找到有效文件{Style.RESET_ALL}")
        return result

    merge_result = merge_review_records(
        event_id, paths,
        result.first_post_nodes,
        result.amplification_nodes,
        result.sentiment_turning_points,
    )

    if merge_result.get("conflicted", 0) > 0 or merge_result.get("agreed", 0) > 0:
        print(f"\n{Fore.CYAN}选择冲突解决策略：")
        print(f"  1. 多数表决（majority）")
        print(f"  2. 从宽原则（取最优状态）")
        print(f"  3. 从严原则（取最严状态）")
        strategy_choice = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 请选择 (1/2/3) [1]: ").strip()
        strategy_map = {"1": "majority", "2": "optimistic", "3": "conservative", "": "majority"}
        strategy = strategy_map.get(strategy_choice, "majority")

        apply_merge_decision(
            event_id, merge_result, strategy=strategy,
            first_nodes=result.first_post_nodes,
            amp_nodes=result.amplification_nodes,
            sentiment_points=result.sentiment_turning_points,
        )

        timeline = getattr(result, 'timeline', [])
        if timeline:
            _ensure_timeline_synced(result)

        first_sorted = _sort_key_nodes(result.first_post_nodes)
        amp_sorted = _sort_key_nodes(result.amplification_nodes)
        sent_sorted = _sort_sentiment_points(result.sentiment_turning_points)

        merged_result = AnalysisResult(
            first_post_nodes=first_sorted,
            amplification_nodes=amp_sorted,
            sentiment_turning_points=sent_sorted,
            timeline=timeline,
            total_posts=result.total_posts,
            time_range=result.time_range,
            data_source=result.data_source,
            source_file=result.source_file,
            engagement_caliber=getattr(result, 'engagement_caliber', "分字段统计"),
            import_stats=getattr(result, 'import_stats', []),
        )
        print(f"{Fore.GREEN}✓ 合并完成，已应用终版口径{Style.RESET_ALL}")
        return merged_result

    return result


def _prompt_quality_report(posts, import_stats, dup_ids, event_id, output_dir=None):
    from data_loader import generate_quality_report, print_quality_report, export_quality_report

    report = generate_quality_report(posts, all_stats=import_stats or [], dup_ids=dup_ids)
    print_quality_report(report)

    choice = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 是否导出质量报告？(y/n) n：").strip().lower()
    if choice in ("y", "yes", "是"):
        if output_dir is None:
            from exporter import _prompt_output_dir
            output_dir = _prompt_output_dir()
        if output_dir:
            path = export_quality_report(report, output_dir, event_id=event_id)
            if path:
                print(f"{Fore.GREEN}✓ 质量报告已导出：{path}{Style.RESET_ALL}")
    return report


def main():
    print_banner()

    try:
        config = collect_trace_config()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}已取消操作{Style.RESET_ALL}")
        return

    posts, data_source, source_file, import_stats, has_total_engagement, dup_ids = prompt_data_source(config)

    if not posts:
        print(f"{Fore.RED}没有有效数据，程序退出{Style.RESET_ALL}")
        return

    excluded_count = 0
    if config.exclude_words:
        from data_loader import _filter_posts
        all_count = len(posts)
        posts, _excluded = _filter_posts(posts, config)
        excluded_count = all_count - len(posts)
        if excluded_count > 0:
            print(f"{Fore.YELLOW}已排除 {excluded_count} 条不符合过滤条件的内容{Style.RESET_ALL}")

    if len(posts) == 0:
        print(f"{Fore.RED}经过过滤后样本量为0，请检查过滤条件{Style.RESET_ALL}")
        return

    if import_stats and dup_ids:
        _prompt_quality_report(posts, import_stats, dup_ids, config.event_id)

    print(f"\n{Fore.GREEN}{Style.BRIGHT}> 正在分析 {len(posts)} 条样本...{Style.RESET_ALL}\n")

    result = run_analysis(
        posts, config,
        data_source=data_source,
        source_file=source_file,
        has_total_engagement=has_total_engagement,
        import_stats=import_stats,
    )

    print_full_report(result, config.event_id)

    daily_text = print_report_for_daily(result, config.event_id, filter_excluded=False)

    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}【日报文本（可直接复制）{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}{'-' * 56}{Style.RESET_ALL}")
    print(daily_text)
    print(f"{Fore.LIGHTBLACK_EX}{'-' * 56}{Style.RESET_ALL}")

    export_dir = prompt_export(result, config.event_id, reviewed=False)

    print(f"\n{Fore.YELLOW}是否进入复核模式？{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}（复核后可重新排序并过滤排除项，生成最终简报）{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}  1 → 单人复核   2 → 导出复核记录   3 → 合并他人记录   其他 → 跳过{Style.RESET_ALL}")
    choice = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 请选择：").strip().lower()

    if choice == "1":
        reviewed_result = run_review_mode(result, config.event_id)
        trusted_result = get_trusted_result(reviewed_result)

        final_daily = print_report_for_daily(reviewed_result, config.event_id, filter_excluded=True)
        print(f"\n{Fore.GREEN}{Style.BRIGHT}【复核后简报（已过滤排除项，可直接复制到日报）{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}{'-' * 56}{Style.RESET_ALL}")
        print(final_daily)
        print(f"{Fore.LIGHTBLACK_EX}{'-' * 56}{Style.RESET_ALL}")

        prompt_export(reviewed_result, config.event_id, reviewed=True)

    elif choice == "2":
        _prompt_review_export(result, config.event_id)

    elif choice == "3":
        result = _prompt_review_merge(config.event_id, result)
        trusted_result = get_trusted_result(result)

        final_daily = print_report_for_daily(result, config.event_id, filter_excluded=True)
        print(f"\n{Fore.GREEN}{Style.BRIGHT}【合并后简报（已过滤排除项）{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}{'-' * 56}{Style.RESET_ALL}")
        print(final_daily)
        print(f"{Fore.LIGHTBLACK_EX}{'-' * 56}{Style.RESET_ALL}")

        prompt_export(result, config.event_id, reviewed=True)

    print(f"\n{Fore.CYAN}分析完成，感谢使用！{Style.RESET_ALL}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}程序已中断{Style.RESET_ALL}")
        sys.exit(0)
