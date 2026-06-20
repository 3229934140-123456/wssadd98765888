import csv
import json
import os
from datetime import datetime
from typing import List, Optional, Tuple

from colorama import Fore, Style, init

from models import (
    DataSource,
    Post,
    Platform,
    Sentiment,
    TraceConfig,
    VerificationType,
)

init(autoreset=True)

PLATFORM_ALIASES = {
    "微博": Platform.WEIBO,
    "weibo": Platform.WEIBO,
    "weibo.com": Platform.WEIBO,
    "微信": Platform.WECHAT,
    "微信公众号": Platform.WECHAT,
    "wechat": Platform.WECHAT,
    "公众号": Platform.WECHAT,
    "抖音": Platform.DOUYIN,
    "douyin": Platform.DOUYIN,
    "小红书": Platform.XHS,
    "xhs": Platform.XHS,
    "xiaohongshu": Platform.XHS,
    "知乎": Platform.ZHIHU,
    "zhihu": Platform.ZHIHU,
    "B站": Platform.BILIBILI,
    "bilibili": Platform.BILIBILI,
    "b站": Platform.BILIBILI,
}

VERIFICATION_ALIASES = {
    "未认证": VerificationType.NONE,
    "无": VerificationType.NONE,
    "none": VerificationType.NONE,
    "个人认证": VerificationType.PERSONAL,
    "个人": VerificationType.PERSONAL,
    "黄V": VerificationType.PERSONAL,
    "personal": VerificationType.PERSONAL,
    "机构认证": VerificationType.ORGANIZATION,
    "机构": VerificationType.ORGANIZATION,
    "蓝V": VerificationType.ORGANIZATION,
    "organization": VerificationType.ORGANIZATION,
    "媒体认证": VerificationType.MEDIA,
    "媒体": VerificationType.MEDIA,
    "media": VerificationType.MEDIA,
    "政府认证": VerificationType.GOV,
    "政府": VerificationType.GOV,
    "政务": VerificationType.GOV,
    "government": VerificationType.GOV,
}

SENTIMENT_ALIASES = {
    "正面": Sentiment.POSITIVE,
    "积极": Sentiment.POSITIVE,
    "positive": Sentiment.POSITIVE,
    "pos": Sentiment.POSITIVE,
    "+1": Sentiment.POSITIVE,
    "1": Sentiment.POSITIVE,
    "中性": Sentiment.NEUTRAL,
    "中立": Sentiment.NEUTRAL,
    "neutral": Sentiment.NEUTRAL,
    "neu": Sentiment.NEUTRAL,
    "0": Sentiment.NEUTRAL,
    "负面": Sentiment.NEGATIVE,
    "消极": Sentiment.NEGATIVE,
    "negative": Sentiment.NEGATIVE,
    "neg": Sentiment.NEGATIVE,
    "-1": Sentiment.NEGATIVE,
    "-1": Sentiment.NEGATIVE,
}

REQUIRED_FIELDS = ["platform", "publish_time", "username", "content"]
OPTIONAL_FIELDS = {
    "verification": ("未认证", VERIFICATION_ALIASES),
    "followers": (0, None),
    "followers_count": (0, None),
    "is_original": (True, None),
    "original": (True, None),
    "sentiment": ("中性", SENTIMENT_ALIASES),
    "repost_count": (0, None),
    "repost": (0, None),
    "share": (0, None),
    "share_count": (0, None),
    "comment_count": (0, None),
    "comment": (0, None),
    "like_count": (0, None),
    "like": (0, None),
    "likes": (0, None),
    "id": (None, None),
    "post_id": (None, None),
    "raw_id": (None, None),
}


def _parse_platform(value: str) -> Optional[Platform]:
    if not value:
        return None
    key = str(value).strip().lower()
    for alias, platform in PLATFORM_ALIASES.items():
        if alias.lower() == key or key in alias.lower():
            return platform
    return None


def _parse_verification(value: str) -> VerificationType:
    if not value:
        return VerificationType.NONE
    key = str(value).strip().lower()
    for alias, vtype in VERIFICATION_ALIASES.items():
        if alias.lower() == key or key in alias.lower():
            return vtype
    return VerificationType.NONE


def _parse_sentiment(value: str) -> Sentiment:
    if value is None:
        return Sentiment.NEUTRAL
    key = str(value).strip().lower()
    for alias, stype in SENTIMENT_ALIASES.items():
        if alias.lower() == key or key in alias.lower():
            return stype
    return Sentiment.NEUTRAL


def _parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    value = str(value).strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y年%m月%d日 %H:%M:%S",
        "%Y年%m月%d日 %H:%M",
        "%Y年%m月%d日",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            if fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
                dt = dt.replace(hour=0, minute=0, second=0)
            return dt
        except ValueError:
            continue
    return None


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    key = str(value).strip().lower()
    return key in ("true", "1", "yes", "是", "y", "t")


def _parse_int(value, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        s = str(value).strip().replace(",", "").replace("万", "0000").replace("w", "0000")
        return int(float(s))
    except (ValueError, TypeError):
        return default


def _map_row_to_post(row: dict, idx: int, data_source: DataSource) -> Tuple[Optional[Post], Optional[str]]:
    try:
        platform = _parse_platform(row.get("platform", row.get("平台", "")))
        if not platform:
            return None, f"无法识别平台：{row.get('platform')}"

        publish_time = _parse_datetime(row.get("publish_time", row.get("发布时间", row.get("时间", ""))))
        if not publish_time:
            return None, f"无法识别发布时间：{row.get('publish_time')}"

        username = str(row.get("username", row.get("账号", row.get("作者", "")))).strip()
        if not username:
            return None, "账号名为空"

        content = str(row.get("content", row.get("正文", row.get("内容", "")))).strip()
        if not content:
            return None, "内容为空"

        verification = _parse_verification(row.get("verification", row.get("认证", "未认证")))
        followers = _parse_int(row.get("followers_count", row.get("粉丝", row.get("粉丝数", 0))))
        is_original = _parse_bool(row.get("is_original", row.get("原创", row.get("是否原创", True))))
        sentiment = _parse_sentiment(row.get("sentiment", row.get("情绪", "中性")))
        repost = _parse_int(row.get("repost_count", row.get("转发", row.get("转发数", 0))))
        comment = _parse_int(row.get("comment_count", row.get("评论", row.get("评论数", 0))))
        like = _parse_int(row.get("like_count", row.get("点赞", row.get("点赞数", 0))))
        share = _parse_int(row.get("share_count", row.get("分享", row.get("分享数", 0))))
        raw_id = str(row.get("id", row.get("post_id", row.get("raw_id", "")))) or None

        post = Post(
            post_id=f"IMP-{idx:06d}",
            platform=platform,
            username=username,
            verification=verification,
            followers_count=followers,
            publish_time=publish_time,
            content=content,
            is_original=is_original,
            sentiment=sentiment,
            repost_count=repost,
            comment_count=comment,
            like_count=like,
            share_count=share,
            raw_id=raw_id,
            data_source=data_source,
        )
        return post, None
    except Exception as e:
        return None, f"解析异常：{str(e)}"


def _filter_posts(posts: List[Post], config: TraceConfig) -> List[Post]:
    filtered = []
    excluded_count = 0
    for post in posts:
        if config.exclude_words:
            has_exclude = any(ew in post.content for ew in config.exclude_words)
            if has_exclude:
                excluded_count += 1
                continue

        if post.publish_time < config.start_time or post.publish_time > config.end_time:
            continue

        if post.platform not in config.platforms:
            continue

        if config.original_only and not post.is_original:
            continue

        if config.verified_only and post.verification == VerificationType.NONE:
            continue

        has_keyword = any(kw in post.content for kw in config.keywords)
        if not has_keyword:
            continue

        filtered.append(post)

    if excluded_count > 0:
        print(f"{Fore.YELLOW}已排除 {excluded_count} 条包含排除词的内容{Style.RESET_ALL}")

    return filtered


def load_csv(file_path: str, config: TraceConfig) -> Tuple[List[Post], str]:
    if not os.path.exists(file_path):
        return [], f"文件不存在：{file_path}"

    data_source = DataSource.CSV
    posts = []
    errors = []

    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            field_lower = [fn.lower() for fn in fieldnames]

            has_platform = any("platform" in f or "平台" in f for f in field_lower)
            has_time = any("time" in f or "时间" in f or "publish" in f for f in field_lower)
            has_user = any("username" in f or "账号" in f or "作者" in f or "user" in f for f in field_lower)
            has_content = any("content" in f or "正文" in f or "内容" in f for f in field_lower)

            if not (has_platform and has_time and has_user and has_content):
                return [], f"CSV缺少必要字段。需要：平台(platform)、发布时间(publish_time)、账号(username)、正文(content)"

            print(f"{Fore.GREEN}检测到字段：{', '.join(fieldnames)}{Style.RESET_ALL}")

            for idx, row in enumerate(reader, 1):
                post, err = _map_row_to_post(row, idx, data_source)
                if post:
                    posts.append(post)
                else:
                    errors.append(f"第{idx}行：{err}")

    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding="gbk") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader, 1):
                    post, err = _map_row_to_post(row, idx, data_source)
                    if post:
                        posts.append(post)
                    else:
                        errors.append(f"第{idx}行：{err}")
        except Exception as e:
            return [], f"文件编码错误，尝试UTF-8和GBK均失败：{str(e)}"
    except Exception as e:
        return [], f"读取CSV失败：{str(e)}"

    filtered = _filter_posts(posts, config)

    if errors:
        print(f"{Fore.YELLOW}共 {len(errors)} 条数据解析失败，前5条错误：{Style.RESET_ALL}")
        for err in errors[:5]:
            print(f"  {Fore.LIGHTBLACK_EX}- {err}{Style.RESET_ALL}")

    return filtered, f"CSV导入：成功{len(filtered)}条，失败{len(errors)}条"


def load_json(file_path: str, config: TraceConfig) -> Tuple[List[Post], str]:
    if not os.path.exists(file_path):
        return [], f"文件不存在：{file_path}"

    data_source = DataSource.JSON
    posts = []
    errors = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list):
                data = data["data"]
            elif "posts" in data and isinstance(data["posts"], list):
                data = data["posts"]
            elif "list" in data and isinstance(data["list"], list):
                data = data["list"]
            else:
                data = [data]

        if not isinstance(data, list):
            return [], "JSON格式错误，需要数组或包含数组的对象"

        print(f"{Fore.GREEN}检测到 {len(data)} 条记录{Style.RESET_ALL}")

        for idx, item in enumerate(data, 1):
            if not isinstance(item, dict):
                errors.append(f"第{idx}条：不是对象")
                continue
            post, err = _map_row_to_post(item, idx, data_source)
            if post:
                posts.append(post)
            else:
                errors.append(f"第{idx}条：{err}")

    except json.JSONDecodeError as e:
        return [], f"JSON解析错误：{str(e)}"
    except Exception as e:
        return [], f"读取JSON失败：{str(e)}"

    filtered = _filter_posts(posts, config)

    if errors:
        print(f"{Fore.YELLOW}共 {len(errors)} 条数据解析失败，前5条错误：{Style.RESET_ALL}")
        for err in errors[:5]:
            print(f"  {Fore.LIGHTBLACK_EX}- {err}{Style.RESET_ALL}")

    return filtered, f"JSON导入：成功{len(filtered)}条，失败{len(errors)}条"


def prompt_data_source(config: TraceConfig) -> Tuple[List[Post], DataSource, Optional[str]]:
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 50}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  数据来源选择")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 50}{Style.RESET_ALL}\n")

    print(f"{Fore.GREEN}  1. 从 CSV 文件导入")
    print(f"{Fore.GREEN}  2. 从 JSON 文件导入")
    print(f"{Fore.GREEN}  3. 使用模拟数据（默认）")
    print()

    while True:
        choice = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 请选择数据来源 (1/2/3) [3]: ").strip()

        if choice == "" or choice == "3":
            print(f"{Fore.CYAN}使用模拟数据{Style.RESET_ALL}")
            from data_generator import generate_mock_data
            posts = generate_mock_data(config, count=300)
            return posts, DataSource.MOCK, None

        if choice == "1":
            while True:
                file_path = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 请输入CSV文件路径：").strip().strip('"').strip("'")
                if not file_path:
                    print(f"{Fore.RED}路径不能为空{Style.RESET_ALL}")
                    continue
                if not file_path.lower().endswith(".csv"):
                    print(f"{Fore.YELLOW}文件扩展名不是.csv，仍尝试读取？(y/n) y{Style.RESET_ALL}")
                    confirm = input().strip().lower()
                    if confirm not in ("", "y", "yes", "是"):
                        continue
                break

            print(f"{Fore.CYAN}正在读取 CSV：{file_path}{Style.RESET_ALL}")
            posts, msg = load_csv(file_path, config)
            print(f"{Fore.GREEN}{msg}{Style.RESET_ALL}")

            if not posts:
                print(f"{Fore.RED}没有有效数据，是否改用模拟数据？(y/n) y{Style.RESET_ALL}")
                confirm = input().strip().lower()
                if confirm in ("", "y", "yes", "是"):
                    from data_generator import generate_mock_data
                    posts = generate_mock_data(config, count=300)
                    return posts, DataSource.MOCK, None
                return [], DataSource.CSV, file_path

            return posts, DataSource.CSV, file_path

        if choice == "2":
            while True:
                file_path = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 请输入JSON文件路径：").strip().strip('"').strip("'")
                if not file_path:
                    print(f"{Fore.RED}路径不能为空{Style.RESET_ALL}")
                    continue
                if not file_path.lower().endswith(".json"):
                    print(f"{Fore.YELLOW}文件扩展名不是.json，仍尝试读取？(y/n) y{Style.RESET_ALL}")
                    confirm = input().strip().lower()
                    if confirm not in ("", "y", "yes", "是"):
                        continue
                break

            print(f"{Fore.CYAN}正在读取 JSON：{file_path}{Style.RESET_ALL}")
            posts, msg = load_json(file_path, config)
            print(f"{Fore.GREEN}{msg}{Style.RESET_ALL}")

            if not posts:
                print(f"{Fore.RED}没有有效数据，是否改用模拟数据？(y/n) y{Style.RESET_ALL}")
                confirm = input().strip().lower()
                if confirm in ("", "y", "yes", "是"):
                    from data_generator import generate_mock_data
                    posts = generate_mock_data(config, count=300)
                    return posts, DataSource.MOCK, None
                return [], DataSource.JSON, file_path

            return posts, DataSource.JSON, file_path

        print(f"{Fore.RED}无效选择，请输入 1、2 或 3{Style.RESET_ALL}")
