from app.services.feeds.base import BaseFeedGenerator


class JoobleFeedGenerator(BaseFeedGenerator):
    portal_name = "jooble"


class TalentFeedGenerator(BaseFeedGenerator):
    portal_name = "talent"


class JoraFeedGenerator(BaseFeedGenerator):
    portal_name = "jora"
