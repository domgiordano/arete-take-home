# Client-specific data adapters
# Each client module contains hardcoded logic specific to that client's data formats

from .retail_client import RetailClientLoader

__all__ = ["RetailClientLoader"]
