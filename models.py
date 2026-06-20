from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class Platform(str, Enum):
    WEIBO = "微博"
    WECHAT = "微信公众号"
    DOUYIN = "抖音"
    XHS = "小红书"
    ZHIHU = "知乎"
    BILIBILI = "B站"


class Sentiment(str, Enum):
    POSITIVE = "正面"
    NEUTRAL = "中性"
    NEGATIVE = "负面"


class VerificationType(str, Enum):
    PERSONAL = "个人认证"
    ORGANIZATION = "机构认证"
    NONE = "未认证"
    MEDIA = "媒体认证"
    GOV = "政府认证"


class DataSource(str, Enum):
    MOCK = "模拟数据"
    CSV = "CSV导入"
    JSON = "JSON导入"


@dataclass
class Post:
    post_id: str
    platform: Platform
    username: str
    verification: VerificationType
    followers_count: int
    publish_time: datetime
    content: str
    is_original: bool
    sentiment: Sentiment
    repost_count: int
    comment_count: int
    like_count: int
    share_count: int = 0
    source_url: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    data_source: DataSource = DataSource.MOCK
    raw_id: Optional[str] = None
    total_engagement: Optional[int] = None

    @property
    def effective_engagement(self) -> int:
        if self.total_engagement is not None and self.total_engagement > 0 \
                and self.repost_count == 0 and self.comment_count == 0 \
                and self.like_count == 0 and self.share_count == 0:
            return self.total_engagement
        return self.repost_count + self.comment_count + self.like_count + self.share_count


@dataclass
class TimelineNode:
    time_point: datetime
    node_type: str
    title: str
    description: str
    related_post: Optional[Post] = None
    sentiment_change: Optional[str] = None
    review_status: str = "待复核"
    _source_ref: Optional[str] = None


@dataclass
class ImportStats:
    file_path: str
    total_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    filtered_count: int = 0
    duplicate_count: int = 0
    error_messages: List[str] = field(default_factory=list)


@dataclass
class TraceConfig:
    event_id: str
    keywords: List[str]
    exclude_words: List[str]
    start_time: datetime
    end_time: datetime
    platforms: List[Platform]
    original_only: bool
    verified_only: bool


@dataclass
class KeyNode:
    post: Post
    node_type: str
    reason: str
    score: float
    review_status: str = "待复核"


@dataclass
class SentimentTurningPoint:
    time_point: datetime
    sentiment_ratio: dict
    trigger_posts: List[Post]
    description: str
    review_status: str = "待复核"
    review_reason: str = ""


@dataclass
class AnalysisResult:
    first_post_nodes: List[KeyNode]
    amplification_nodes: List[KeyNode]
    sentiment_turning_points: List[SentimentTurningPoint]
    timeline: List[TimelineNode] = field(default_factory=list)
    total_posts: int = 0
    time_range: str = ""
    data_source: DataSource = DataSource.MOCK
    source_file: Optional[str] = None
    engagement_caliber: str = "分字段统计"
    import_stats: List = field(default_factory=list)
