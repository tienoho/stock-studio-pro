"""
Custom domain and infrastructure exceptions.
"""

class AutoStockError(Exception):
    """Base exception for all errors in AutoStock Studio."""
    pass

StockStudioError = AutoStockError


class PartMergeError(AutoStockError):
    """Raised when merging Claude script parts fails validation."""
    pass


class ProviderError(AutoStockError):
    """Raised when an external API provider encounters an error."""
    pass


class RateLimitExceededError(ProviderError):
    """Raised when provider rate limit is exceeded."""
    pass


class InvalidApiKeyError(ProviderError):
    """Raised when an API key is rejected or expired."""
    pass


class DownloadError(AutoStockError):
    """Raised when downloading a media file fails."""
    pass


class VideoProcessingError(AutoStockError):
    """Raised when FFmpeg or ffprobe fails to process video."""
    pass
