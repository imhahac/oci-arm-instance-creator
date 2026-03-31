class OracleArmManagerError(Exception):
    """Base exception for all oracle_arm_manager errors."""
    pass

class ConfigurationError(OracleArmManagerError):
    """Raised when there is an issue with the configuration (e.g., missing env vars, invalid values)."""
    pass

class NotificationError(OracleArmManagerError):
    """Raised when sending a notification fails after retries."""
    pass

class OciApiError(OracleArmManagerError):
    """Raised when an OCI SDK call fails with a general service error."""
    pass

class OciCapacityError(OciApiError):
    """Raised when instance creation fails due to OutOfCapacity or similar limits."""
    pass

class OciRateLimitError(OciApiError):
    """Raised when an OCI API call fails due to too many requests (Rate Limit)."""
    pass

class BudgetExceededError(OracleArmManagerError):
    """Raised when the configured budget threshold is exceeded."""
    pass
