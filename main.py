#!/usr/bin/env python3
"""舆情热点溯源分析工具 - 面向分析师的命令行小工具"""

import sys

from colorama import Fore, Style, init

from collector import collect_trace_config
from data_generator import generate_mock_data
from analyzer import run_analysis
from formatter import print_full_report, print_report_for_daily
from reviewer import run_review_mode

init(autoreset=True)


def print_banner():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}")
    print(f"  ======  舆情热点溯源分析工具  ======")
    print(f"{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  Public Opinion Trace Tool v1.0")
    print(f"{Fore.LIGHTBLACK_EX}  快速产出突发热点初步溯源结果 · 面向专业分析师{Style.RESET_ALL}")
    print()


def main():
    print_banner()

    try:
        config = collect_trace_config()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}已取消操作{Style.RESET_ALL}")
        return

    print(f"\n{Fore.GREEN}{Style.BRIGHT}> 正在生成模拟数据并分析...{Style.RESET_ALL}\n")

    posts = generate_mock_data(config, count=300)
    result = run_analysis(posts, config)

    print_full_report(result, config.event_id)

    daily_text = print_report_for_daily(result, config.event_id)

    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}【日报文本（可直接复制）】{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}{'-' * 56}{Style.RESET_ALL}")
    print(daily_text)
    print(f"{Fore.LIGHTBLACK_EX}{'-' * 56}{Style.RESET_ALL}")

    print(f"\n{Fore.YELLOW}是否进入复核模式？{Style.RESET_ALL}")
    choice = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 输入 y 进入复核，其他键退出：").strip().lower()

    if choice in ("y", "yes", "是"):
        reviewed_result = run_review_mode(result, config.event_id)

        final_daily = print_report_for_daily(reviewed_result, config.event_id)
        print(f"\n{Fore.GREEN}{Style.BRIGHT}【复核后简报（可直接复制到日报）】{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}{'-' * 56}{Style.RESET_ALL}")
        print(final_daily)
        print(f"{Fore.LIGHTBLACK_EX}{'-' * 56}{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}分析完成，感谢使用！{Style.RESET_ALL}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}程序已中断{Style.RESET_ALL}")
        sys.exit(0)
