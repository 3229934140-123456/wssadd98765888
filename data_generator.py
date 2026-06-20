import random
from datetime import datetime, timedelta
from typing import List

from models import (
    DataSource,
    Post,
    Platform,
    Sentiment,
    TraceConfig,
    VerificationType,
)

USERNAME_POOLS = {
    Platform.WEIBO: [
        "财经观察家", "社会时评", "科技前沿君", "娱乐八卦社",
        "本地生活通", "新闻晨报", "深度调查记者", "草根爆料王",
        "职场导师Amy", "美食探店达人", "旅行摄影日记", "数码测评君",
        "健康养生堂", "教育观察", "法律科普君", "历史图鉴",
    ],
    Platform.WECHAT: [
        "虎嗅网", "36氪", "饭统戴老板", "人物",
        "财经十一人", "每日人物", "谷雨实验室", "棱镜",
        "晚点LatePost", "远鉴智库", "市值榜", "未来汽车日报",
    ],
    Platform.DOUYIN: [
        "新闻主播小李", "街头采访实录", "热点追踪官", "实时现场",
        "社会百态", "民生观察", "都市快报", "第一现场",
        "普法小剧场", "职场那些事", "生活记录者", "知识分享官",
    ],
    Platform.XHS: [
        "生活家小A", "成长记录册", "城市漫步指南", "好物分享馆",
        "职场干货铺", "学习打卡日记", "护肤心得录", "健身打卡站",
    ],
    Platform.ZHIHU: [
        "法务老张", "产品经理阿杰", "码农老王", "医生Dr李",
        "咨询师Amy", "大学教授陈", "投资分析师", "HR老司机",
        "心理咨询师", "建筑师老刘", "数据分析师", "运营喵",
    ],
    Platform.BILIBILI: [
        "老师好我叫何同学", "影视飓风", "回形针PaperClip",
        "巫师财经", "罗翔说刑法", "半佛仙人", "观视频工作室",
        "张召忠说", "科技袁人", "沈逸",
    ],
}

VERIFICATION_DISTRIBUTION = [
    (VerificationType.NONE, 0.45),
    (VerificationType.PERSONAL, 0.25),
    (VerificationType.ORGANIZATION, 0.15),
    (VerificationType.MEDIA, 0.10),
    (VerificationType.GOV, 0.05),
]

CONTENT_TEMPLATES = [
    "突发：{keyword}事件最新进展，引发广泛关注",
    "深度解读：{keyword}背后的三大原因分析",
    "现场直击：{keyword}发生时的真实情况",
    "独家爆料：{keyword}不为人知的内幕",
    "【评论】{keyword}事件折射出的社会问题",
    "{keyword}持续发酵，多方回应汇总",
    "网友热议：{keyword}你怎么看？",
    "官方通报：{keyword}事件最新情况说明",
    "专家观点：{keyword}将带来哪些影响",
    "盘点：{keyword}事件时间线梳理",
    "实拍{keyword}现场，画面令人震惊",
    "{keyword}上热搜了，来龙去脉一文看懂",
    "关于{keyword}，这些信息你需要知道",
    "{keyword}事件后续：当事人首度发声",
    "数据说话：{keyword}传播量已突破百万",
]


def _weighted_choice(choices_with_weights):
    total = sum(w for _, w in choices_with_weights)
    r = random.uniform(0, total)
    for item, weight in choices_with_weights:
        r -= weight
        if r <= 0:
            return item
    return choices_with_weights[0][0]


def _generate_followers(platform: Platform, verification: VerificationType) -> int:
    base_ranges = {
        VerificationType.NONE: (100, 50000),
        VerificationType.PERSONAL: (10000, 5000000),
        VerificationType.ORGANIZATION: (50000, 10000000),
        VerificationType.MEDIA: (100000, 50000000),
        VerificationType.GOV: (50000, 20000000),
    }
    low, high = base_ranges.get(verification, (100, 10000))
    platform_mult = {
        Platform.WEIBO: 1.5,
        Platform.DOUYIN: 2.0,
        Platform.WECHAT: 0.8,
        Platform.XHS: 0.6,
        Platform.ZHIHU: 0.5,
        Platform.BILIBILI: 0.7,
    }
    return int(random.randint(low, high) * platform_mult.get(platform, 1.0))


def _generate_engagement(followers: int, is_original: bool, platform: Platform) -> tuple:
    base_rate = random.uniform(0.001, 0.05) if is_original else random.uniform(0.0001, 0.005)
    total_eng = int(followers * base_rate * random.uniform(0.5, 2.0))

    repost_ratio = {
        Platform.WEIBO: 0.3,
        Platform.WECHAT: 0.15,
        Platform.DOUYIN: 0.1,
        Platform.XHS: 0.08,
        Platform.ZHIHU: 0.05,
        Platform.BILIBILI: 0.06,
    }.get(platform, 0.1)

    comment_ratio = 0.2
    like_ratio = 0.5
    share_ratio = 0.1

    repost = int(total_eng * repost_ratio * random.uniform(0.5, 1.5))
    comment = int(total_eng * comment_ratio * random.uniform(0.5, 1.5))
    like = int(total_eng * like_ratio * random.uniform(0.5, 1.5))
    share = int(total_eng * share_ratio * random.uniform(0.5, 1.5))

    return max(0, repost), max(0, comment), max(0, like), max(0, share)


def _generate_content(keywords: List[str], platform: Platform) -> str:
    keyword = random.choice(keywords)
    template = random.choice(CONTENT_TEMPLATES)
    base = template.format(keyword=keyword)

    extra_phrases = [
        "目前相关话题阅读量已破亿",
        "多个大V相继转发评论",
        "当地已成立调查组",
        "涉事方暂未回应",
        "网友纷纷表示担忧",
        "专家提醒理性看待",
        "事件仍在持续发展中",
        "更多细节有待披露",
        "这已经是本月第三起类似事件",
        "业内人士分析或与政策调整有关",
    ]

    if platform == Platform.WEIBO:
        base += " #" + keyword + "# " + random.choice(extra_phrases)
    elif platform == Platform.WECHAT:
        base += "\n\n" + random.choice(extra_phrases) + "点击关注，获取更多深度分析。"
    elif platform == Platform.ZHIHU:
        base += "\n\n以上是个人观点，欢迎在评论区讨论。"
    elif platform == Platform.DOUYIN:
        base += " 记得点赞关注，持续更新最新进展。"
    else:
        base += " " + random.choice(extra_phrases)

    return base


def generate_mock_data(config: TraceConfig, count: int = 200) -> List[Post]:
    posts = []
    time_span = (config.end_time - config.start_time).total_seconds()

    for i in range(count):
        platform = random.choice(config.platforms)
        verification = _weighted_choice(VERIFICATION_DISTRIBUTION)
        username = random.choice(USERNAME_POOLS[platform]) + str(random.randint(1, 999))
        followers = _generate_followers(platform, verification)

        offset = int(time_span * random.betavariate(2, 3))
        publish_time = config.start_time + timedelta(seconds=offset)

        is_original = random.random() > 0.35

        repost, comment, like, share = _generate_engagement(followers, is_original, platform)

        sentiment_weights = [
            (Sentiment.POSITIVE, 0.2),
            (Sentiment.NEUTRAL, 0.35),
            (Sentiment.NEGATIVE, 0.45),
        ]
        sentiment = _weighted_choice(sentiment_weights)

        content = _generate_content(config.keywords, platform)

        excluded = False
        for ew in config.exclude_words:
            if ew in content:
                excluded = True
                break
        if excluded:
            continue

        post = Post(
            post_id=f"{platform.value[:2]}-{i:06d}",
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
            tags=[random.choice(config.keywords)],
            data_source=DataSource.MOCK,
        )
        posts.append(post)

    if config.original_only:
        posts = [p for p in posts if p.is_original]

    if config.verified_only:
        posts = [p for p in posts if p.verification != VerificationType.NONE]

    posts.sort(key=lambda p: p.publish_time)

    for idx, post in enumerate(posts):
        post.post_id = f"{post.platform.value[:2]}-{idx:06d}"

    return posts
