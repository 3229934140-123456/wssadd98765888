from datetime import datetime, timedelta
from typing import List

from colorama import Fore, Style, init

from models import Platform, TraceConfig

init(autoreset=True)


def _print_title(text: str):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 50}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  {text}")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 50}{Style.RESET_ALL}\n")


def _prompt(text: str, default: str = "") -> str:
    default_str = f" [{default}]" if default else ""
    result = input(f"{Fore.YELLOW}?{Style.RESET_ALL} {text}{default_str}: ").strip()
    return result if result else default


def _prompt_yes_no(text: str, default: bool = False) -> bool:
    default_str = "Y/n" if default else "y/N"
    result = input(f"{Fore.YELLOW}?{Style.RESET_ALL} {text} ({default_str}): ").strip().lower()
    if not result:
        return default
    return result in ("y", "yes", "是")


def collect_event_basic_info() -> dict:
    _print_title("步骤 1/4 · 事件基本信息")

    event_id = _prompt("事件编号", "EVT-" + datetime.now().strftime("%Y%m%d") + "-001")
    keywords_str = _prompt("关键词列表（逗号分隔）", "突发,热点")
    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]

    start_str = _prompt("开始时间 (YYYY-MM-DD HH:MM)",
                        (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d 00:00"))
    end_str = _prompt("结束时间 (YYYY-MM-DD HH:MM)",
                      datetime.now().strftime("%Y-%m-%d %H:%M"))

    start_time = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
    end_time = datetime.strptime(end_str, "%Y-%m-%d %H:%M")

    return {
        "event_id": event_id,
        "keywords": keywords,
        "start_time": start_time,
        "end_time": end_time,
    }


def collect_platforms() -> List[Platform]:
    _print_title("步骤 2/4 · 重点平台选择")

    print(f"{Fore.GREEN}可用平台：")
    all_platforms = list(Platform)
    for i, p in enumerate(all_platforms, 1):
        print(f"  {i}. {p.value}")

    selected_str = _prompt("\n请输入平台编号（逗号分隔，回车=全选）", "")

    if not selected_str:
        return all_platforms

    selected_indices = [int(s.strip()) - 1 for s in selected_str.split(",") if s.strip().isdigit()]
    selected = [all_platforms[i] for i in selected_indices if 0 <= i < len(all_platforms)]

    if not selected:
        print(f"{Fore.RED}未选择有效平台，默认全选{Style.RESET_ALL}")
        return all_platforms

    return selected


def collect_filters() -> dict:
    _print_title("步骤 3/4 · 过滤条件设置")

    use_exclude = _prompt_yes_no("是否加入排除词？", False)
    exclude_words = []
    if use_exclude:
        exclude_str = _prompt("排除词列表（逗号分隔）", "广告,推广")
        exclude_words = [k.strip() for k in exclude_str.split(",") if k.strip()]

    original_only = _prompt_yes_no("是否只看原创内容？", False)
    verified_only = _prompt_yes_no("是否仅关注认证账号？", False)

    return {
        "exclude_words": exclude_words,
        "original_only": original_only,
        "verified_only": verified_only,
    }


def confirm_config(basic: dict, platforms: List[Platform], filters: dict) -> bool:
    _print_title("步骤 4/4 · 配置确认")

    print(f"{Fore.WHITE}事件编号：{Fore.GREEN}{basic['event_id']}")
    print(f"{Fore.WHITE}关键词：{Fore.GREEN}{', '.join(basic['keywords'])}")
    print(f"{Fore.WHITE}时间范围：{Fore.GREEN}{basic['start_time']} ~ {basic['end_time']}")
    print(f"{Fore.WHITE}重点平台：{Fore.GREEN}{', '.join(p.value for p in platforms)}")
    print(f"{Fore.WHITE}排除词：{Fore.GREEN}{', '.join(filters['exclude_words']) if filters['exclude_words'] else '无'}")
    print(f"{Fore.WHITE}仅原创：{Fore.GREEN}{'是' if filters['original_only'] else '否'}")
    print(f"{Fore.WHITE}仅认证：{Fore.GREEN}{'是' if filters['verified_only'] else '否'}")

    return _prompt_yes_no("\n确认以上配置并开始分析？", True)


def collect_trace_config() -> TraceConfig:
    while True:
        basic = collect_event_basic_info()
        platforms = collect_platforms()
        filters = collect_filters()

        if confirm_config(basic, platforms, filters):
            return TraceConfig(
                event_id=basic["event_id"],
                keywords=basic["keywords"],
                exclude_words=filters["exclude_words"],
                start_time=basic["start_time"],
                end_time=basic["end_time"],
                platforms=platforms,
                original_only=filters["original_only"],
                verified_only=filters["verified_only"],
            )
        else:
            print(f"\n{Fore.MAGENTA}正在重新配置...{Style.RESET_ALL}")
