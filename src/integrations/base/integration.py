from abc import ABC, abstractmethod

from omegaconf import DictConfig


class Integration(ABC):
    def __init__(self, config: DictConfig):
        self.config = config

    @abstractmethod
    def refresh(self):
        pass
