"""
Media Provider Registry service adhering to Open/Closed and Dependency Inversion principles.
Allows dynamic registration of media providers and decoupled provider resolution.
"""

from typing import Dict, List, Optional, Callable, Any
from ...core.interfaces.media_provider import IMediaProvider
from ...infrastructure.providers.pexels_provider import PexelsProvider
from ...infrastructure.providers.pixabay_provider import PixabayProvider
from ...infrastructure.providers.vecteezy_provider import VecteezyProvider


class MediaProviderRegistry:
    """Registry managing media providers (Pexels, Pixabay, Vecteezy, etc.)."""

    def __init__(self, key_manager=None):
        self._km = key_manager
        self._providers: Dict[str, IMediaProvider] = {}
        self._factories: Dict[str, Callable[[Any], IMediaProvider]] = {}
        self._register_default_providers()

    def _register_default_providers(self) -> None:
        """Register built-in providers."""
        self.register_factory("pexels", lambda km: PexelsProvider(km))
        self.register_factory("pixabay", lambda km: PixabayProvider(km))
        self.register_factory("vecteezy", lambda km: VecteezyProvider(km))

    def register_provider(self, name: str, provider: IMediaProvider) -> None:
        """Register a concrete provider instance."""
        self._providers[name.lower()] = provider

    def register_factory(self, name: str, factory: Callable[[Any], IMediaProvider]) -> None:
        """Register a provider factory callable that receives key_manager."""
        self._factories[name.lower()] = factory

    def get_provider(self, name: str, key_manager=None) -> Optional[IMediaProvider]:
        """Retrieve provider instance by name, instantiating via factory if needed."""
        name_lower = name.lower()
        if name_lower in self._providers:
            return self._providers[name_lower]

        km = key_manager or self._km
        if name_lower in self._factories:
            provider = self._factories[name_lower](km)
            self._providers[name_lower] = provider
            return provider
        return None

    def get_all_providers(self, key_manager=None) -> Dict[str, IMediaProvider]:
        """Instantiate and return all registered providers."""
        km = key_manager or self._km
        result = dict(self._providers)
        for name in self._factories:
            if name not in result:
                result[name] = self._factories[name](km)
        return result

    def resolve_providers_for_mode(self, mode: str, key_manager=None) -> Dict[str, IMediaProvider]:
        """
        Resolves active providers based on a search mode string (e.g., 'Pexels + Pixabay', 'Vecteezy', 'All').
        Filters to only providers that have valid configured API keys in key_manager.
        """
        km = key_manager or self._km
        mode_lower = (mode or "").lower()
        active: Dict[str, IMediaProvider] = {}

        is_all = any(term in mode_lower for term in ("cả", "all", "+"))

        for name, factory in self._factories.items():
            should_include = is_all or (name in mode_lower)
            if not should_include:
                continue

            # Verify key presence if key manager is provided
            has_keys = True
            if km:
                key_attr = f"{name}_keys"
                if hasattr(km, key_attr):
                    keys_list = getattr(km, key_attr, [])
                    has_keys = bool(keys_list)

            if has_keys:
                provider = self.get_provider(name, km)
                if provider:
                    active[name] = provider

        return active
