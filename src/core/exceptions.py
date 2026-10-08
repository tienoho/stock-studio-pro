"""
Custom domain and infrastructure exceptions.
"""

class AutoStockError(Exception):
    """Base exception for all errors in AutoStock Studio."""
    pass

StockStudioError = AutoStockError


class PartMergeError(StockStudioError):
    """Raised when merging Claude script parts fails validation."""
    pass


class ProviderError(StockStudioError):
    """Raised when an external API provider encounters an error."""
    pass


class RateLimitExceededError(ProviderError):
    """Raised when provider rate limit is exceeded."""
    pass


class InvalidApiKeyError(ProviderError):
    """Raised when an API key is rejected or expired."""
    pass


class DownloadError(StockStudioError):
    """Raised when downloading a media file fails."""
    pass


class VideoProcessingError(StockStudioError):
    """Raised when FFmpeg or ffprobe fails to process video."""
    pass
