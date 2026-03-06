"""Base generator abstract class."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import ScaleConfig
from ..data_store import DataStore


class BaseGenerator(ABC):
    """Abstract base for all data generators."""

    def __init__(self, store: DataStore, config: ScaleConfig, seeds: dict) -> None:
        self.store = store
        self.config = config
        self.seeds = seeds

    @abstractmethod
    def generate(self) -> None:
        """Generate entities and add them to the data store."""
        ...
