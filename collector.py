from datetime import datetime, timedelta
from typing import List, Optional

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
    while True:
        result = input(f"{Fore.YELLOW}?{Style.RESET_ALL} {text} ({default_str}): ").strip().lower()
        if not result:
            return default
        if result in ("y", "yes", "是", "n", "no", "否"):
            return result in ("y", "yes", "是")
        print(f"{Fore.RED}请输入 y 或 n{Style.RESET_ALL}")


def _validate_keywords(keywords: List[str]) -> Optional[str]:
    if not keywords:
        return "关键词列表不能为空，请输入至少一个关键词"
    if len(keywords) > 20:
        return f"关键词数量过多（{len(keywords)}个），建议不超过20个"
    for kw in keywords:
        if len(kw) > 30:
            return f"关键词过长：「{kw}」，单个关键词建议不超过30字"
    return None


def _validate_time_range(start_time: datetime, end_time: datetime) -> Optional[str]:
    if end_time <= start_time:
        return f"结束时间 {end_time.strftime('%Y-%m-%d %H:%M')} 必须晚于开始时间 {start_time.strftime('%Y-%m-%d %H:%M')}"
    delta = end_time - start_time
    if delta.total_seconds() < 3600:
        return "时间范围过短，建议至少1小时以上"
    if delta.days > 365:
        return "时间范围过长，建议不超过1年"
    return None


def _parse_datetime(date_str: str) -> Optional[datetime]:
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if "%H:%M" not in fmt and fmt != "%Y-%m-%d" and fmt != "%Y/%m/%d":
                pass
            if fmt in ("%Y-%m-%d", "%Y/%m/%d"):
                return dt.replace(hour=0, minute=0)
            return dt
        except ValueError:
            continue
    return None


def collect_event_basic_info() -> dict:
    _print_title("步骤 1/4 · 事件基本信息")

    while True:
        event_id = _prompt("事件编号", "EVT-" + datetime.now().strftime("%Y%m%d") + "-001")
        if not event_id:
            print(f"{Fore.RED}事件编号不能为空{Style.RESET_ALL}")
            continue
        break

    while True:
        keywords_str = _prompt("关键词列表（逗号分隔，至少1个）", "突发,热点")
        keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
        error = _validate_keywords(keywords)
        if error:
            print(f"{Fore.RED}{error}{Style.RESET_ALL}")
            continue
        break

    while True:
        start_str = _prompt("开始时间 (YYYY-MM-DD HH:MM)",
                            (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d 00:00"))
        start_time = _parse_datetime(start_str)
        if not start_time:
            print(f"{Fore.RED}时间格式错误，请使用 YYYY-MM-DD HH:MM 格式{Style.RESET_ALL}")
            continue
        break

    while True:
        end_str = _prompt("结束时间 (YYYY-MM-DD HH:MM)",
                          datetime.now().strftime("%Y-%m-%d %H:%M"))
        end_time = _parse_datetime(end_str)
        if not end_time:
            print(f"{Fore.RED}时间格式错误，请使用 YYYY-MM-DD HH:MM 格式{Style.RESET_ALL}")
            continue

        error = _validate_time_range(start_time, end_time)
        if error:
            print(f"{Fore.RED}{error}{Style.RESET_ALL}")
            continue
        break

    return {
        "event_id": event_id,
        "keywords": keywords,
        "start_time": start_time,
        "end_time": end_time,
    }


def collect_platforms() -> List[Platform]:
    _print_title("步骤 2/4 · 重点平台选择")

    all_platforms = list(Platform)
    while True:
        print(f"{Fore.GREEN}可用平台：")
        for i, p in enumerate(all_platforms, 1):
            print(f"  {i}. {p.value}")

        selected_str = _prompt("\n请输入平台编号（逗号分隔，回车=全选）", "")

        if not selected_str:
            print(f"{Fore.GREEN}已选择全部平台{Style.RESET_ALL}")
            return all_platforms

        parts = [s.strip() for s in selected_str.split(",") if s.strip()]
        selected_indices = []
        valid = True

        for part in parts:
            if not part.isdigit():
                print(f"{Fore.RED}无效编号「{part}」，请输入数字{Style.RESET_ALL}")
                valid = False
                break
            idx = int(part) - 1
            if idx < 0 or idx >= len(all_platforms):
                print(f"{Fore.RED}编号「{part}」超出范围（1-{len(all_platforms)}）{Style.RESET_ALL}")
                valid = False
                break
            if idx in selected_indices:
                print(f"{Fore.YELLOW}平台「{all_platforms[idx].value}」重复选择，已去重{Style.RESET_ALL}")
                continue
            selected_indices.append(idx)

        if not valid:
            continue

        if not selected_indices:
            print(f"{Fore.RED}未选择有效平台，请重新输入{Style.RESET_ALL}")
            continue

        selected = [all_platforms[i] for i in selected_indices]
        print(f"{Fore.GREEN}已选择：{', '.join(p.value for p in selected)}{Style.RESET_ALL}")
        return selected


def collect_filters() -> dict:
    _print_title("步骤 3/4 · 过滤条件设置")

    while True:
        use_exclude = _prompt_yes_no("是否加入排除词？", False)
        exclude_words = []
        if use_exclude:
            while True:
                exclude_str = _prompt("排除词列表（逗号分隔）", "广告,推广")
                exclude_words = [k.strip() for k in exclude_str.split(",") if k.strip()]
                if not exclude_words:
                    print(f"{Fore.RED}排除词列表不能为空，或者选择不使用排除词{Style.RESET_ALL}")
                    continue
                break

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
    print(f"{Fore.WHITE}时间范围：{Fore.GREEN}{basic['start_time'].strftime('%Y-%m-%d %H:%M')} ~ {basic['end_time'].strftime('%Y-%m-%d %H:%M')}")
    duration = basic['end_time'] - basic['start_time']
    days = duration.days
    hours = duration.seconds // 3600
    print(f"{Fore.LIGHTBLACK_EX}  时长：{days}天{hours}小时")
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
