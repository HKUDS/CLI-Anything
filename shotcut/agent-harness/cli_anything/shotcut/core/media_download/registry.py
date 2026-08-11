"""Media resolver registry."""

from .models import ResolvedMedia
from .ports import MediaResolver


class MediaResolverRegistry:
    def __init__(self, resolvers: list[MediaResolver]) -> None:
        self._resolvers = resolvers

    def resolve(self, source_url: str) -> ResolvedMedia:
        for resolver in self._resolvers:
            if resolver.can_resolve(source_url):
                return resolver.resolve(source_url)
        raise ValueError(f"No media resolver supports URL: {source_url}")
