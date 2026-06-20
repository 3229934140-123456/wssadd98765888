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
    total_posts: int
    time_range: str
    data_source: DataSource = DataSource.MOCK
    source_file: Optional[str] = None
