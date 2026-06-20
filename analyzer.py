from datetime import datetime, timedelta
from typing import List

from models import (
    AnalysisResult,
    KeyNode,
    Post,
    Sentiment,
    SentimentTurningPoint,
    TraceConfig,
    VerificationType,
)


def _calculate_influence_score(post: Post) -> float:
    base_eng = post.repost_count + post.comment_count * 2 + post.like_count + post.share_count * 3
    follower_factor = min(post.followers_count / 100000, 10)
    original_bonus = 1.5 if post.is_original else 0.6

    verif_bonus = {
        VerificationType.GOV: 2.0,
        VerificationType.MEDIA: 1.8,
        VerificationType.ORGANIZATION: 1.3,
        VerificationType.PERSONAL: 1.1,
        VerificationType.NONE: 1.0,
    }.get(post.verification, 1.0)

    return base_eng * follower_factor * original_bonus * verif_bonus


def find_first_post_nodes(posts: List[Post], config: TraceConfig, top_n: int = 8) -> List[KeyNode]:
    if not posts:
        return []

    sorted_by_time = sorted(posts, key=lambda p: p.publish_time)
    first_time = sorted_by_time[0].publish_time
    first_window_end = first_time + timedelta(hours=2)

    early_posts = [p for p in sorted_by_time if p.publish_time <= first_window_end]

    candidates = []
    for post in early_posts:
        score = _calculate_influence_score(post)

        reasons = []
        time_diff = (post.publish_time - first_time).total_seconds() / 60
        if time_diff < 5:
            reasons.append("极早期发布，疑似源头帖")
        elif time_diff < 30:
            reasons.append("首批传播参与者")
        else:
            reasons.append("事件早期参与")

        if post.is_original:
            reasons.append("原创内容")

        if post.verification != VerificationType.NONE:
            reasons.append(f"{post.verification.value}账号")

        if post.followers_count > 1000000:
            reasons.append("高影响力账号")

        node = KeyNode(
            post=post,
            node_type="疑似首发/早期线索",
            reason="；".join(reasons),
            score=score + (10000 - time_diff * 10),
        )
        candidates.append(node)

    candidates.sort(key=lambda n: n.score, reverse=True)
    return candidates[:top_n]


def find_amplification_nodes(posts: List[Post], config: TraceConfig, top_n: int = 10) -> List[KeyNode]:
    if not posts:
        return []

    sorted_by_eng = sorted(posts, key=lambda p: _calculate_influence_score(p), reverse=True)

    candidates = []
    for post in sorted_by_eng:
        score = _calculate_influence_score(post)

        reasons = []

        total_eng = post.repost_count + post.comment_count + post.like_count + post.share_count
        if total_eng > 100000:
            reasons.append("超高互动量")
        elif total_eng > 10000:
            reasons.append("高互动量")
        elif total_eng > 1000:
            reasons.append("较高互动量")

        if post.repost_count > 5000:
            reasons.append("转发量大，扩散力强")

        if post.verification == VerificationType.MEDIA:
            reasons.append("媒体账号报道，权威加持")
        elif post.verification == VerificationType.GOV:
            reasons.append("政府账号发声，定调作用")
        elif post.verification == VerificationType.ORGANIZATION:
            reasons.append("机构账号参与")
        elif post.verification == VerificationType.PERSONAL:
            reasons.append("个人认证大V")

        if post.followers_count > 10000000:
            reasons.append("千万级粉丝")
        elif post.followers_count > 1000000:
            reasons.append("百万级粉丝")

        if post.is_original:
            reasons.append("原创观点")

        node = KeyNode(
            post=post,
            node_type="传播放大节点",
            reason="；".join(reasons) if reasons else "有一定传播力",
            score=score,
        )
        candidates.append(node)

    return candidates[:top_n]


def find_sentiment_turning_points(
    posts: List[Post], config: TraceConfig, top_n: int = 5
) -> List[SentimentTurningPoint]:
    if not posts:
        return []

    time_span = (config.end_time - config.start_time).total_seconds()
    if time_span <= 0:
        return []

    bucket_hours = max(1, int(time_span / 3600 / 12))
    bucket = timedelta(hours=bucket_hours)

    buckets = {}
    for post in posts:
        bucket_key = post.publish_time.replace(
            minute=0, second=0, microsecond=0
        )
        bucket_key = bucket_key + timedelta(
            hours=(post.publish_time.minute // (bucket_hours * 60)) * bucket_hours
        )
        if bucket_key not in buckets:
            buckets[bucket_key] = {"pos": 0, "neu": 0, "neg": 0, "posts": []}
        if post.sentiment == Sentiment.POSITIVE:
            buckets[bucket_key]["pos"] += 1
        elif post.sentiment == Sentiment.NEUTRAL:
            buckets[bucket_key]["neu"] += 1
        else:
            buckets[bucket_key]["neg"] += 1
        buckets[bucket_key]["posts"].append(post)

    sorted_times = sorted(buckets.keys())
    if len(sorted_times) < 3:
        return []

    turning_points = []
    prev_neg_ratio = None

    for i, t in enumerate(sorted_times):
        data = buckets[t]
        total = data["pos"] + data["neu"] + data["neg"]
        if total < 3:
            continue

        neg_ratio = data["neg"] / total
        pos_ratio = data["pos"] / total
        neu_ratio = data["neu"] / total

        if prev_neg_ratio is not None:
            ratio_change = neg_ratio - prev_neg_ratio

            is_turning = False
            description = ""
            trigger_posts = sorted(data["posts"], key=lambda p: p.repost_count + p.comment_count, reverse=True)[:3]

            if ratio_change > 0.15 and neg_ratio > 0.4:
                is_turning = True
                description = f"负面情绪显著上升，负面占比达{neg_ratio:.0%}，较前一时段上升{ratio_change:.0%}"
            elif ratio_change < -0.15 and prev_neg_ratio > 0.4:
                is_turning = True
                description = f"负面情绪明显回落，负面占比降至{neg_ratio:.0%}，较前一时段下降{abs(ratio_change):.0%}"
            elif i > 0 and i < len(sorted_times) - 1:
                prev_data = buckets[sorted_times[i - 1]]
                next_data = buckets[sorted_times[i + 1]]
                prev_total = prev_data["pos"] + prev_data["neu"] + prev_data["neg"]
                next_total = next_data["pos"] + next_data["neu"] + next_data["neg"]
                if prev_total > 0 and next_total > 0:
                    prev_neg = prev_data["neg"] / prev_total
                    next_neg = next_data["neg"] / next_total
                    if neg_ratio > prev_neg + 0.1 and neg_ratio > next_neg + 0.1:
                        is_turning = True
                        description = f"负面情绪峰值点，负面占比{neg_ratio:.0%}"
                    elif neg_ratio < prev_neg - 0.1 and neg_ratio < next_neg - 0.1:
                        is_turning = True
                        description = f"正面/中性情绪高峰，负面占比仅{neg_ratio:.0%}"

            if is_turning:
                turning_points.append(
                    SentimentTurningPoint(
                        time_point=t,
                        sentiment_ratio={
                            "正面": round(pos_ratio, 3),
                            "中性": round(neu_ratio, 3),
                            "负面": round(neg_ratio, 3),
                        },
                        trigger_posts=trigger_posts,
                        description=description,
                    )
                )

        prev_neg_ratio = neg_ratio if total >= 3 else prev_neg_ratio

    turning_points.sort(key=lambda tp: abs(tp.sentiment_ratio["负面"] - 0.5), reverse=True)
    return turning_points[:top_n]


def run_analysis(posts: List[Post], config: TraceConfig) -> AnalysisResult:
    first_nodes = find_first_post_nodes(posts, config)
    amp_nodes = find_amplification_nodes(posts, config)
    sentiment_points = find_sentiment_turning_points(posts, config)

    time_range = f"{config.start_time.strftime('%Y-%m-%d %H:%M')} ~ {config.end_time.strftime('%Y-%m-%d %H:%M')}"

    return AnalysisResult(
        first_post_nodes=first_nodes,
        amplification_nodes=amp_nodes,
        sentiment_turning_points=sentiment_points,
        total_posts=len(posts),
        time_range=time_range,
    )
