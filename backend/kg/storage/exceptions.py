"""Storage-specific exceptions for the knowledge graph system."""


class StorageError(Exception):
    """Base exception for all storage operations.

    This is the parent class for all storage-related errors,
    allowing callers to catch all storage issues with a single except clause.
    """

    def __init__(self, message: str, cause: Exception | None = None):
        """Initialize storage error.

        Args:
            message: Human-readable error description
            cause: Optional underlying exception that caused this error
        """
        super().__init__(message)
        self.cause = cause


class StorageConnectionError(StorageError):
    """Error connecting to or communicating with the storage backend.

    Raised when:
    - Cannot establish connection to storage backend
    - Connection is lost during operation
    - Authentication/authorization failures
    - Network timeouts
    """

    pass


class StorageOperationError(StorageError):
    """Error performing a storage operation.

    Raised when:
    - Storage operation fails due to backend issues
    - Transaction rollback required
    - Constraint violations
    - Insufficient storage space
    """

    pass


class StorageQueryError(StorageError):
    """Error executing a storage query.

    Raised when:
    - Query syntax is invalid
    - Query execution times out
    - Query results cannot be parsed
    - Query contains invalid references
    """

    pass


class StorageValidationError(StorageError):
    """Error validating data before storage.

    Raised when:
    - Entity data doesn't match schema requirements
    - Reference integrity violations
    - Business rule violations at storage level
    - Invalid entity identifiers
    """

    pass


class StorageConfigurationError(StorageError):
    """Error in storage configuration.

    Raised when:
    - Storage configuration is invalid or incomplete
    - Unsupported backend type specified
    - Required configuration parameters are missing
    - Configuration values are out of valid range
    """

    pass
