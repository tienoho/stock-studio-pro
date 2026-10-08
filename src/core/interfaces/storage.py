"""
Interfaces for configuration and state persistence.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class IConfigRepository(ABC):
    """Abstract repository for application config and API keys."""

    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """Load configuration."""
        pass

    @abstractmethod
    def save(self, config: Dict[str, Any]) -> None:
        """Save configuration."""
        pass


class IStateRepository(ABC):
    """Abstract repository for application session state."""

    @abstractmethod
    def load(self) -> Optional[Dict[str, Any]]:
        """Load state if exists."""
        pass

    @abstractmethod
    def save(self, state: Dict[str, Any]) -> None:
        """Save state."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Clear state file."""
        pass
