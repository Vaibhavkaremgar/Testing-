from app.services.feeds.base import BaseFeedGenerator
from app.services.feeds.portal_generators import (
    CareerJetFeedGenerator,
    JoobleFeedGenerator,
    TalentFeedGenerator,
)


class FeedGeneratorRegistry:
    def __init__(self) -> None:
        self._generators = {
            "default": BaseFeedGenerator(),
            "jooble": JoobleFeedGenerator(),
            "careerjet": CareerJetFeedGenerator(),
            "talent": TalentFeedGenerator(),
        }

    def get(self, portal_name: str) -> BaseFeedGenerator:
        return self._generators[portal_name]


feed_registry = FeedGeneratorRegistry()
