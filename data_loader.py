import csv
import difflib
import glob
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from colorama import Fore, Style, init

from models import (
    DataSource,
    DuplicateCluster,
    DirtyDataEntry,
    ImportStats,
    Post,
    Platform,
    SampleQualityReport,
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
}

ENGAGEMENT_ALIASES = [
    "engagement", "total_engagement", "total_interaction",
    "互动量", "总互动量", "互动数", "总互动数",
    "热度", "声量", "pv", "uv",
]


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


def _find_engagement_field(row: dict) -> Tuple[Optional[int], Optional[str]]:
    for key in row.keys():
        if key is None:
            continue
        key_lower = str(key).strip().lower()
        for alias in ENGAGEMENT_ALIASES:
            if alias.lower() in key_lower:
                val = _parse_int(row[key], 0)
                if val > 0:
                    return val, key
    return None, None


def _map_row_to_post(row: dict, idx: int, data_source: DataSource,
                     file_prefix: str = "IMP") -> Tuple[Optional[Post], Optional[str]]:
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

        total_eng, eng_field = _find_engagement_field(row)

        post = Post(
            post_id=f"{file_prefix}-{idx:06d}",
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
            total_engagement=total_eng,
        )
        return post, None
    except Exception as e:
        return None, f"解析异常：{str(e)}"


def _content_similar(a: str, b: str, threshold: float = 0.85) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    short = a if len(a) < len(b) else b
    long_str = b if len(a) < len(b) else a
    if len(short) < 10:
        return short in long_str
    ratio = difflib.SequenceMatcher(None, a[:200], b[:200]).ratio()
    return ratio >= threshold


def _dedup_posts(posts: List[Post]) -> Tuple[List[Post], int, set]:
    if not posts:
        return [], 0, set()

    seen: Dict[str, Post] = {}
    duplicate_count = 0
    dup_ids: set = set()

    sorted_posts = sorted(posts, key=lambda p: (
        p.platform.value,
        p.username,
        p.publish_time.strftime("%Y%m%d%H%M"),
    ))

    for post in sorted_posts:
        time_key = post.publish_time.strftime("%Y%m%d%H%M")
        exact_key = f"{post.platform.value}|{post.username}|{time_key}|{post.content[:30]}"

        if exact_key in seen:
            duplicate_count += 1
            dup_ids.add(post.post_id)
            continue

        is_dup = False
        for key, existing in seen.items():
            if existing.platform != post.platform:
                continue
            if existing.username != post.username:
                continue
            time_diff = abs((existing.publish_time - post.publish_time).total_seconds())
            if time_diff > 300:
                continue
            if _content_similar(existing.content, post.content):
                is_dup = True
                duplicate_count += 1
                dup_ids.add(post.post_id)
                break

        if not is_dup:
            seen[exact_key] = post

    result = sorted(seen.values(), key=lambda p: p.publish_time)
    return result, duplicate_count, dup_ids


def _filter_posts(posts: List[Post], config: TraceConfig) -> Tuple[List[Post], int]:
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

    return filtered, excluded_count


def load_csv(file_path: str, config: TraceConfig,
             file_prefix: str = "CSV") -> Tuple[List[Post], str, ImportStats]:
    stats = ImportStats(file_path=file_path)
    if not os.path.exists(file_path):
        return [], f"文件不存在：{file_path}", stats

    data_source = DataSource.CSV
    posts = []
    errors = []
    has_engagement_field = False

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
                return [], f"CSV缺少必要字段。需要：平台(platform)、发布时间(publish_time)、账号(username)、正文(content)", stats

            has_engagement_field = any(
                any(alias in f for alias in [a.lower() for a in ENGAGEMENT_ALIASES])
                for f in field_lower
            )

            print(f"{Fore.GREEN}检测到字段：{', '.join(fieldnames)}{Style.RESET_ALL}")
            if has_engagement_field:
                print(f"{Fore.CYAN}  识别到总互动量字段，将使用总互动量口径{Style.RESET_ALL}")

            all_rows = list(reader)
            stats.total_count = len(all_rows)

            for idx, row in enumerate(all_rows, 1):
                post, err = _map_row_to_post(row, idx, data_source, file_prefix=file_prefix)
                if post:
                    posts.append(post)
                    stats.success_count += 1
                else:
                    errors.append(f"第{idx}行：{err}")
                    stats.failed_count += 1

    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding="gbk") as f:
                reader = csv.DictReader(f)
                all_rows = list(reader)
                stats.total_count = len(all_rows)
                for idx, row in enumerate(all_rows, 1):
                    post, err = _map_row_to_post(row, idx, data_source, file_prefix=file_prefix)
                    if post:
                        posts.append(post)
                        stats.success_count += 1
                    else:
                        errors.append(f"第{idx}行：{err}")
                        stats.failed_count += 1
        except Exception as e:
            return [], f"文件编码错误，尝试UTF-8和GBK均失败：{str(e)}", stats
    except Exception as e:
        return [], f"读取CSV失败：{str(e)}", stats

    filtered_posts, filtered_count = _filter_posts(posts, config)
    stats.filtered_count = stats.success_count - len(filtered_posts)
    stats.error_messages = errors[:5]

    if errors:
        print(f"{Fore.YELLOW}共 {len(errors)} 条数据解析失败，前5条错误：{Style.RESET_ALL}")
        for err in errors[:5]:
            print(f"  {Fore.LIGHTBLACK_EX}- {err}{Style.RESET_ALL}")

    msg = f"CSV导入：总{stats.total_count}条，成功{len(filtered_posts)}条，失败{stats.failed_count}条，过滤{stats.filtered_count}条"
    if has_engagement_field:
        msg += "（总互动量口径）"
    return filtered_posts, msg, stats


def load_json(file_path: str, config: TraceConfig,
              file_prefix: str = "JSON") -> Tuple[List[Post], str, ImportStats]:
    stats = ImportStats(file_path=file_path)
    if not os.path.exists(file_path):
        return [], f"文件不存在：{file_path}", stats

    data_source = DataSource.JSON
    posts = []
    errors = []
    has_engagement_field = False

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
            return [], "JSON格式错误，需要数组或包含数组的对象", stats

        if data and isinstance(data[0], dict):
            field_lower = [str(k).lower() for k in data[0].keys()]
            has_engagement_field = any(
                any(alias in f for alias in [a.lower() for a in ENGAGEMENT_ALIASES])
                for f in field_lower
            )

        print(f"{Fore.GREEN}检测到 {len(data)} 条记录{Style.RESET_ALL}")
        if has_engagement_field:
            print(f"{Fore.CYAN}  识别到总互动量字段，将使用总互动量口径{Style.RESET_ALL}")

        stats.total_count = len(data)

        for idx, item in enumerate(data, 1):
            if not isinstance(item, dict):
                errors.append(f"第{idx}条：不是对象")
                stats.failed_count += 1
                continue
            post, err = _map_row_to_post(item, idx, data_source, file_prefix=file_prefix)
            if post:
                posts.append(post)
                stats.success_count += 1
            else:
                errors.append(f"第{idx}条：{err}")
                stats.failed_count += 1

    except json.JSONDecodeError as e:
        return [], f"JSON解析错误：{str(e)}", stats
    except Exception as e:
        return [], f"读取JSON失败：{str(e)}", stats

    filtered_posts, filtered_count = _filter_posts(posts, config)
    stats.filtered_count = stats.success_count - len(filtered_posts)
    stats.error_messages = errors[:5]

    if errors:
        print(f"{Fore.YELLOW}共 {len(errors)} 条数据解析失败，前5条错误：{Style.RESET_ALL}")
        for err in errors[:5]:
            print(f"  {Fore.LIGHTBLACK_EX}- {err}{Style.RESET_ALL}")

    msg = f"JSON导入：总{stats.total_count}条，成功{len(filtered_posts)}条，失败{stats.failed_count}条，过滤{stats.filtered_count}条"
    if has_engagement_field:
        msg += "（总互动量口径）"
    return filtered_posts, msg, stats


def _expand_file_pattern(pattern: str) -> List[str]:
    pattern = pattern.strip().strip('"').strip("'")
    if not pattern:
        return []

    if os.path.isdir(pattern):
        files = []
        for ext in ("*.csv", "*.json"):
            files.extend(glob.glob(os.path.join(pattern, ext)))
        return sorted(files)

    if any(c in pattern for c in "*?[]"):
        return sorted(glob.glob(pattern))

    if os.path.isfile(pattern):
        return [pattern]

    return [pattern]


def _print_import_summary(all_stats: List[ImportStats], total_duplicates: int,
                          final_count: int, has_total_engagement: bool,
                          dup_source_ranking: Optional[List[Tuple[str, int]]] = None):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  批量导入统计汇总")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    grand_total = sum(s.total_count for s in all_stats)
    grand_success = sum(s.success_count for s in all_stats)
    grand_failed = sum(s.failed_count for s in all_stats)
    grand_filtered = sum(s.filtered_count for s in all_stats)
    grand_dup = sum(s.duplicate_count for s in all_stats)

    print(f"  {'文件':<28} {'总数':>5} {'成功':>5} {'失败':>5} {'过滤':>5} {'重复':>5}")
    print(f"  {'-' * 58}")
    for s in all_stats:
        fname = os.path.basename(s.file_path)
        if len(fname) > 26:
            fname = fname[:23] + "..."
        dup_color = Fore.YELLOW if s.duplicate_count > 0 else ""
        dup_reset = Style.RESET_ALL if s.duplicate_count > 0 else ""
        print(f"  {fname:<28} {s.total_count:>5} {s.success_count:>5} "
              f"{s.failed_count:>5} {s.filtered_count:>5} "
              f"{dup_color}{s.duplicate_count:>5}{dup_reset}")
    print(f"  {'-' * 58}")
    print(f"  {'合计':<28} {grand_total:>5} {grand_success:>5} "
          f"{grand_failed:>5} {grand_filtered:>5} {grand_dup:>5}")
    print(f"  {'去重后最终样本数':<28} {'':>5} {final_count:>5}")
    print()

    if dup_source_ranking and grand_dup > 0:
        print(f"{Fore.YELLOW}{Style.BRIGHT}  重复来源 Top 文件：{Style.RESET_ALL}")
        for fname, cnt in dup_source_ranking[:3]:
            pct = (cnt / grand_dup * 100) if grand_dup > 0 else 0
            print(f"    {Fore.LIGHTBLACK_EX}· {fname}: {cnt} 条重复（占 {pct:.0f}%）{Style.RESET_ALL}")
        print()
        print(f"  {Fore.LIGHTBLACK_EX}提示：可优先清理重复来源较多的样本文件{Style.RESET_ALL}")
        print()

    if has_total_engagement:
        print(f"  {Fore.YELLOW}互动量口径：总互动量（单列合并统计）{Style.RESET_ALL}")
    else:
        print(f"  {Fore.GREEN}互动量口径：分字段统计（转/评/赞/分享）{Style.RESET_ALL}")
    print()


def load_batch_files(file_paths: List[str], config: TraceConfig) -> Tuple[
    List[Post], str, List[ImportStats], bool, int, set
]:
    all_posts: List[Post] = []
    all_stats: List[ImportStats] = []
    has_total_engagement = False

    prefix_to_stat: Dict[str, ImportStats] = {}

    for i, fp in enumerate(file_paths, 1):
        ext = os.path.splitext(fp)[1].lower()
        prefix = f"F{i:02d}"

        print(f"\n{Fore.CYAN}[{i}/{len(file_paths)}] 处理：{fp}{Style.RESET_ALL}")

        if ext == ".csv":
            posts, msg, stats = load_csv(fp, config, file_prefix=prefix)
        elif ext == ".json":
            posts, msg, stats = load_json(fp, config, file_prefix=prefix)
        else:
            print(f"{Fore.YELLOW}  跳过不支持的文件类型：{ext}{Style.RESET_ALL}")
            continue

        prefix_to_stat[prefix] = stats

        print(f"  {Fore.GREEN}{msg}{Style.RESET_ALL}")
        all_posts.extend(posts)
        all_stats.append(stats)

        if posts:
            if any(p.total_engagement is not None and p.total_engagement > 0 for p in posts):
                has_total_engagement = True

    deduped_posts, dup_count, dup_ids = _dedup_posts(all_posts)

    for pid in dup_ids:
        try:
            prefix = pid.split("-", 1)[0]
            if prefix in prefix_to_stat:
                prefix_to_stat[prefix].duplicate_count += 1
        except Exception:
            pass

    dup_ranking = []
    if dup_count > 0:
        dup_ranking = sorted(
            ((os.path.basename(s.file_path), s.duplicate_count) for s in all_stats),
            key=lambda x: -x[1],
        )
        dup_ranking = [(f, c) for f, c in dup_ranking if c > 0]

    _print_import_summary(all_stats, dup_count, len(deduped_posts),
                          has_total_engagement, dup_source_ranking=dup_ranking)

    source_files = ", ".join(os.path.basename(fp) for fp in file_paths[:3])
    if len(file_paths) > 3:
        source_files += f" 等{len(file_paths)}个文件"
    summary = f"批量导入{len(file_paths)}个文件：最终{len(deduped_posts)}条有效样本"
    if has_total_engagement:
        summary += "（总互动量口径）"

    return deduped_posts, summary, all_stats, has_total_engagement, dup_count, dup_ids


def generate_quality_report(posts: List[Post], all_stats: Optional[List[ImportStats]] = None,
                            dup_ids: Optional[set] = None) -> SampleQualityReport:
    report = SampleQualityReport()
    report.total_posts = len(posts)

    platform_cov: Dict[str, int] = {}
    time_cov: Dict[str, int] = {}
    account_cov: Dict[str, int] = {}

    for post in posts:
        pname = post.platform.value
        platform_cov[pname] = platform_cov.get(pname, 0) + 1

        hour_key = post.publish_time.strftime("%Y-%m-%d %H:00")
        time_cov[hour_key] = time_cov.get(hour_key, 0) + 1

        vname = post.verification.value
        account_cov[vname] = account_cov.get(vname, 0) + 1

    report.platform_coverage = platform_cov
    report.time_coverage = time_cov
    report.account_type_coverage = account_cov

    if dup_ids:
        report.duplicate_count = len(dup_ids)
        report.unique_posts = len(posts) - len(dup_ids)
    else:
        report.unique_posts = len(posts)

    if dup_ids and posts:
        dup_posts = [p for p in posts if p.post_id in dup_ids]
        clusters: Dict[str, List[Post]] = {}
        for dp in dup_posts:
            ck = f"{dp.platform.value}|{dp.username}|{dp.publish_time.strftime('%Y%m%d%H%M')}"
            if ck not in clusters:
                clusters[ck] = []
            clusters[ck].append(dp)

        for ck, members in clusters.items():
            if len(members) < 2:
                continue
            rep = members[0]
            member_ids = [m.post_id for m in members]
            report.duplicate_clusters.append(DuplicateCluster(
                representative_id=rep.post_id,
                member_ids=member_ids,
                platform=rep.platform.value,
                username=rep.username,
                content_preview=rep.content[:50],
            ))

    if all_stats:
        for stats in all_stats:
            for err_msg in stats.error_messages:
                try:
                    line_num = err_msg.split("第")[1].split("行")[0]
                    prefix = ""
                    for pid_candidate in [p.post_id for p in posts]:
                        pass
                    report.dirty_data.append(DirtyDataEntry(
                        post_id=f"{os.path.basename(stats.file_path)}:{line_num}",
                        file_path=stats.file_path,
                        reason=err_msg,
                    ))
                except Exception:
                    report.dirty_data.append(DirtyDataEntry(
                        post_id="unknown",
                        file_path=stats.file_path,
                        reason=err_msg,
                    ))

        files_with_issues = set()
        for stats in all_stats:
            has_issues = (stats.duplicate_count > stats.total_count * 0.3
                          or stats.failed_count > stats.total_count * 0.2
                          or len(stats.error_messages) > 3)
            if has_issues:
                files_with_issues.add(stats.file_path)
        report.cleanup_files = sorted(files_with_issues)

    return report


def print_quality_report(report: SampleQualityReport):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  样本质量报告")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}\n")

    print(f"  总样本数：{report.total_posts}")
    print(f"  去重后样本数：{report.unique_posts}")
    if report.duplicate_count > 0:
        print(f"  {Fore.YELLOW}重复数：{report.duplicate_count}{Style.RESET_ALL}")
    print()

    if report.platform_coverage:
        print(f"  {Fore.WHITE}{Style.BRIGHT}> 平台覆盖{Style.RESET_ALL}")
        sorted_plat = sorted(report.platform_coverage.items(), key=lambda x: -x[1])
        for name, count in sorted_plat:
            pct = count / report.total_posts * 100 if report.total_posts > 0 else 0
            bar = "#" * int(pct / 5)
            print(f"    {name:<8} {count:>4} 条 ({pct:>5.1f}%) {Fore.CYAN}{bar}{Style.RESET_ALL}")
        print()

    if report.time_coverage:
        print(f"  {Fore.WHITE}{Style.BRIGHT}> 时间段覆盖（Top 10）{Style.RESET_ALL}")
        sorted_time = sorted(report.time_coverage.items(), key=lambda x: -x[1])[:10]
        for hour, count in sorted_time:
            bar = "#" * min(count, 30)
            print(f"    {hour}  {count:>3} 条 {Fore.LIGHTBLACK_EX}{bar}{Style.RESET_ALL}")
        print()

    if report.account_type_coverage:
        print(f"  {Fore.WHITE}{Style.BRIGHT}> 账号类型覆盖{Style.RESET_ALL}")
        sorted_acct = sorted(report.account_type_coverage.items(), key=lambda x: -x[1])
        for name, count in sorted_acct:
            pct = count / report.total_posts * 100 if report.total_posts > 0 else 0
            print(f"    {name:<8} {count:>4} 条 ({pct:>5.1f}%)")
        print()

    if report.duplicate_clusters:
        print(f"  {Fore.YELLOW}{Style.BRIGHT}> 重复簇（{len(report.duplicate_clusters)}个）{Style.RESET_ALL}")
        for i, cluster in enumerate(report.duplicate_clusters[:8], 1):
            print(f"    {i}. [{cluster.platform}] @{cluster.username} "
                  f"({len(cluster.member_ids)}条重复)")
            print(f"       {Fore.LIGHTBLACK_EX}{cluster.content_preview[:40]}...{Style.RESET_ALL}")
        if len(report.duplicate_clusters) > 8:
            print(f"    ... 还有 {len(report.duplicate_clusters) - 8} 个重复簇")
        print()

    if report.dirty_data:
        print(f"  {Fore.RED}{Style.BRIGHT}> 脏数据（{len(report.dirty_data)}条）{Style.RESET_ALL}")
        for dd in report.dirty_data[:5]:
            print(f"    {Fore.RED}· {dd.file_path}: {dd.reason[:50]}{Style.RESET_ALL}")
        if len(report.dirty_data) > 5:
            print(f"    ... 还有 {len(report.dirty_data) - 5} 条")
        print()

    if report.cleanup_files:
        print(f"  {Fore.YELLOW}{Style.BRIGHT}> 建议清理的文件{Style.RESET_ALL}")
        for fp in report.cleanup_files:
            print(f"    {Fore.YELLOW}· {fp}{Style.RESET_ALL}")
        print()

    print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")


def export_quality_report(report: SampleQualityReport, output_dir: str,
                          event_id: str = "") -> Optional[str]:
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception:
        return None

    safe_id = "".join(c for c in event_id if c.isalnum() or c in ("-", "_")) or "report"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"QUALITY_{safe_id}_{timestamp}.txt"
    filepath = os.path.join(output_dir, filename)

    lines = []
    lines.append("=" * 60)
    lines.append("  样本质量报告")
    lines.append("=" * 60)
    lines.append(f"  事件编号：{event_id}")
    lines.append(f"  生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  总样本数：{report.total_posts}")
    lines.append(f"  去重后样本数：{report.unique_posts}")
    lines.append(f"  重复数：{report.duplicate_count}")
    lines.append("")

    if report.platform_coverage:
        lines.append("-" * 40)
        lines.append("  平台覆盖")
        lines.append("-" * 40)
        for name, count in sorted(report.platform_coverage.items(), key=lambda x: -x[1]):
            pct = count / report.total_posts * 100 if report.total_posts > 0 else 0
            lines.append(f"  {name:<8} {count:>4} 条 ({pct:>5.1f}%)")
        lines.append("")

    if report.time_coverage:
        lines.append("-" * 40)
        lines.append("  时间段覆盖")
        lines.append("-" * 40)
        for hour, count in sorted(report.time_coverage.items(), key=lambda x: -x[1])[:20]:
            lines.append(f"  {hour}  {count:>3} 条")
        lines.append("")

    if report.account_type_coverage:
        lines.append("-" * 40)
        lines.append("  账号类型覆盖")
        lines.append("-" * 40)
        for name, count in sorted(report.account_type_coverage.items(), key=lambda x: -x[1]):
            pct = count / report.total_posts * 100 if report.total_posts > 0 else 0
            lines.append(f"  {name:<8} {count:>4} 条 ({pct:>5.1f}%)")
        lines.append("")

    if report.duplicate_clusters:
        lines.append("-" * 40)
        lines.append(f"  重复簇（{len(report.duplicate_clusters)}个）")
        lines.append("-" * 40)
        for i, cluster in enumerate(report.duplicate_clusters, 1):
            lines.append(f"  {i}. [{cluster.platform}] @{cluster.username} "
                         f"({len(cluster.member_ids)}条重复)")
            lines.append(f"     代表ID：{cluster.representative_id}")
            lines.append(f"     成员ID：{', '.join(cluster.member_ids[:5])}")
            lines.append(f"     内容预览：{cluster.content_preview[:50]}")
        lines.append("")

    if report.dirty_data:
        lines.append("-" * 40)
        lines.append(f"  脏数据（{len(report.dirty_data)}条）")
        lines.append("-" * 40)
        for dd in report.dirty_data:
            lines.append(f"  · [{dd.post_id}] {dd.reason}")
        lines.append("")

    if report.cleanup_files:
        lines.append("-" * 40)
        lines.append("  建议清理的文件清单")
        lines.append("-" * 40)
        for fp in report.cleanup_files:
            lines.append(f"  · {fp}")
        lines.append("")

    lines.append("=" * 60)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return filepath
    except Exception:
        return None


def prompt_data_source(config: TraceConfig) -> Tuple[List[Post], DataSource, Optional[str], List, bool, set]:
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 50}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  数据来源选择")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 50}{Style.RESET_ALL}\n")

    print(f"{Fore.GREEN}  1. 从单个 CSV 文件导入")
    print(f"{Fore.GREEN}  2. 从单个 JSON 文件导入")
    print(f"{Fore.GREEN}  3. 批量导入多个 CSV/JSON 文件（支持通配符/目录）")
    print(f"{Fore.GREEN}  4. 使用模拟数据（默认）")
    print()

    while True:
        choice = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 请选择数据来源 (1/2/3/4) [4]: ").strip()

        if choice == "" or choice == "4":
            print(f"{Fore.CYAN}使用模拟数据{Style.RESET_ALL}")
            from data_generator import generate_mock_data
            posts = generate_mock_data(config, count=300)
            return posts, DataSource.MOCK, None, [], False, set()

        if choice in ("1", "2"):
            ext_hint = "CSV" if choice == "1" else "JSON"
            while True:
                file_path = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 请输入{ext_hint}文件路径：").strip().strip('"').strip("'")
                if not file_path:
                    print(f"{Fore.RED}路径不能为空{Style.RESET_ALL}")
                    continue
                if choice == "1" and not file_path.lower().endswith(".csv"):
                    print(f"{Fore.YELLOW}文件扩展名不是.csv，仍尝试读取？(y/n) y{Style.RESET_ALL}")
                    confirm = input().strip().lower()
                    if confirm not in ("", "y", "yes", "是"):
                        continue
                if choice == "2" and not file_path.lower().endswith(".json"):
                    print(f"{Fore.YELLOW}文件扩展名不是.json，仍尝试读取？(y/n) y{Style.RESET_ALL}")
                    confirm = input().strip().lower()
                    if confirm not in ("", "y", "yes", "是"):
                        continue
                break

            print(f"{Fore.CYAN}正在读取 {ext_hint}：{file_path}{Style.RESET_ALL}")
            if choice == "1":
                posts, msg, stats = load_csv(file_path, config)
            else:
                posts, msg, stats = load_json(file_path, config)
            print(f"{Fore.GREEN}{msg}{Style.RESET_ALL}")

            has_te = any(p.total_engagement is not None and p.total_engagement > 0 for p in posts) if posts else False

            if not posts:
                print(f"{Fore.RED}没有有效数据，是否改用模拟数据？(y/n) y{Style.RESET_ALL}")
                confirm = input().strip().lower()
                if confirm in ("", "y", "yes", "是"):
                    from data_generator import generate_mock_data
                    posts = generate_mock_data(config, count=300)
                    return posts, DataSource.MOCK, None, [], False, set()
                return [], (DataSource.CSV if choice == "1" else DataSource.JSON), file_path, [stats], has_te, set()

            ds = DataSource.CSV if choice == "1" else DataSource.JSON
            return posts, ds, file_path, [stats], has_te, set()

        if choice == "3":
            print(f"\n{Fore.CYAN}批量导入模式{Style.RESET_ALL}")
            print(f"{Fore.LIGHTBLACK_EX}  支持输入：")
            print(f"{Fore.LIGHTBLACK_EX}    · 多个文件路径，用逗号分隔")
            print(f"{Fore.LIGHTBLACK_EX}    · 通配符：如 data/*.csv")
            print(f"{Fore.LIGHTBLACK_EX}    · 目录路径：自动读取目录下所有 CSV/JSON")
            print()

            while True:
                raw_input = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 请输入文件路径/通配符/目录：").strip()
                if not raw_input:
                    print(f"{Fore.RED}输入不能为空{Style.RESET_ALL}")
                    continue

                parts = [p.strip() for p in raw_input.replace(";", ",").split(",") if p.strip()]
                all_files: List[str] = []
                for p in parts:
                    expanded = _expand_file_pattern(p)
                    all_files.extend(expanded)

                all_files = [f for f in all_files if os.path.isfile(f)]
                all_files = list(dict.fromkeys(all_files))

                if not all_files:
                    print(f"{Fore.RED}未找到任何有效文件，请重新输入{Style.RESET_ALL}")
                    continue

                print(f"{Fore.GREEN}找到 {len(all_files)} 个文件：{Style.RESET_ALL}")
                for f in all_files[:10]:
                    print(f"  {Fore.LIGHTBLACK_EX}- {f}{Style.RESET_ALL}")
                if len(all_files) > 10:
                    print(f"  {Fore.LIGHTBLACK_EX}  ... 还有 {len(all_files) - 10} 个{Style.RESET_ALL}")

                confirm = input(f"{Fore.YELLOW}?{Style.RESET_ALL} 确认导入这些文件？(y/n) y：").strip().lower()
                if confirm in ("", "y", "yes", "是"):
                    break

            posts, summary, stats_list, has_te, dup_count, dup_ids_batch = load_batch_files(all_files, config)

            if not posts:
                print(f"{Fore.RED}没有有效数据，是否改用模拟数据？(y/n) y{Style.RESET_ALL}")
                confirm = input().strip().lower()
                if confirm in ("", "y", "yes", "是"):
                    from data_generator import generate_mock_data
                    posts = generate_mock_data(config, count=300)
                    return posts, DataSource.MOCK, None, [], False, set()
                return posts, DataSource.CSV, f"批量({len(all_files)}文件)", stats_list, has_te, dup_ids_batch

            source_file = f"批量导入 {len(all_files)} 个文件"
            return posts, DataSource.CSV, source_file, stats_list, has_te, dup_ids_batch

        print(f"{Fore.RED}无效选择，请输入 1、2、3 或 4{Style.RESET_ALL}")
