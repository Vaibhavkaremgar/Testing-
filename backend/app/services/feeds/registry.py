from app.services.feeds.base import BaseFeedGenerator
from app.services.feeds.postjobfree_generator import PostJobFreeFeedGenerator
from app.services.feeds.portal_generators import (
    JoraFeedGenerator,
    JoobleFeedGenerator,
    TalentFeedGenerator,
)


class FeedGeneratorRegistry:
    def __init__(self) -> None:
        self._generators = {
            "default": BaseFeedGenerator(),
            "jooble": JoobleFeedGenerator(),
            "talent": TalentFeedGenerator(),
            "jora": JoraFeedGenerator(),
            "postjobfree": PostJobFreeFeedGenerator(),
        }

    def get(self, portal_name: str) -> BaseFeedGenerator:
        return self._generators[portal_name]


feed_registry = FeedGeneratorRegistry()
