#!/usr/bin/env python3
"""舆情热点溯源分析工具 - 面向分析师的命令行小工具"""

import sys

from colorama import Fore, Style, init

from collector import collect_trace_config
from data_loader import prompt_data_source
from analyzer import run_analysis
from formatter import print_full_report, print_report_for_daily
from reviewer import run_review_mode, get_trusted_result
from exporter import prompt_export

init(autoreset=True)


def print_banner():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}")
    print(f"  ======  舆情热点溯源分析工作台  ======")
    print(f"{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  Public Opinion Trace Workbench v2.0")
    print(f"{Fore.LIGHTBLACK_EX}  快速产出突发热点初步溯源结果 · 面向专业分析师{Style.RESET_ALL}")
    print()
    print(f"{Fore.LIGHTBLACK_EX}  支持：CSV/JSON导入 · 智能过滤 · 三类分析 · 专家复核 · 一键导出{Style.RESET_ALL}")
    print()


def main():
    print_banner()

    try:
        config = collect_trace_config()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}已取消操作{Style.RESET_ALL}")
        return

    posts, data_source, source_file = prompt_data_source(config)

    if not posts:
        print(f"{Fore.RED}没有有效数据，程序退出{Style.RESET_ALL}")
        return

    excluded_count = 0
    if config.exclude_words:
        from data_loader import _filter_posts
        all_count = len(posts)
        posts = _filter_posts(posts, config)
        excluded_count = all_count - len(posts)
        if excluded_count > 0:
            print(f"{Fore.YELLOW}已排除 {excluded_count} 条不符合过滤条件的内容{Style.RESET_ALL}")

    if len(posts) == 0:
        print(f"{Fore.RED}经过过滤后样本量为0，请检查过滤条件{Style.RESET_ALL}")
        return

    print(f"\n{Fore.GREEN}{Style.BRIGHT}> 正在分析 {len(posts)} 条样本...{Style.RESET_ALL}\n")

    result = run_analysis(posts, config, data_source=data_source, source_file=source_file)

    print_full_report(result, config.event_id)

    daily_text = print_report_for_daily(result, config.event_id, filter_excluded=False)

    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}【日报文本（可直接复制）{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}{'-' * 56}{Style.RESET_ALL}")
    print(daily_text)
    print(f"{Fore.LIGHTBLACK_EX}{'-' * 56}{Style.RESET_ALL}")

    prompt_export(result, config.event_id, reviewed=False)

    print(f"\n{Fore.YELLOW}是否进入复核模式？{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}（复核后可重新排序并过滤排除项，生成最终简报）{Style.RESET_ALL}")
    choice = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 输入 y 进入复核，其他键退出：").strip().lower()

    if choice in ("y", "yes", "是"):
        reviewed_result = run_review_mode(result, config.event_id)

        trusted_result = get_trusted_result(reviewed_result)

        final_daily = print_report_for_daily(reviewed_result, config.event_id, filter_excluded=True)
        print(f"\n{Fore.GREEN}{Style.BRIGHT}【复核后简报（已过滤排除项，可直接复制到日报）{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}{'-' * 56}{Style.RESET_ALL}")
        print(final_daily)
        print(f"{Fore.LIGHTBLACK_EX}{'-' * 56}{Style.RESET_ALL}")

        prompt_export(reviewed_result, config.event_id, reviewed=True)

    print(f"\n{Fore.CYAN}分析完成，感谢使用！{Style.RESET_ALL}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}程序已中断{Style.RESET_ALL}")
        sys.exit(0)
