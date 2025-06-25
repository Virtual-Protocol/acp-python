class ACPError(Exception):
    """Base exception for all ACP client errors."""
    pass


# Connection-related exceptions
class ACPConnectionError(ACPError):
    """Raised when connection to external services fails."""
    pass


class ACPRPCConnectionError(ACPConnectionError):
    """Raised when RPC connection to blockchain fails."""
    pass


class ACPSocketConnectionError(ACPConnectionError):
    """Raised when WebSocket connection fails."""
    pass


# Authentication and authorization exceptions
class ACPAuthenticationError(ACPError):
    """Raised for authentication and authorization issues."""
    pass


class ACPInvalidPrivateKeyError(ACPAuthenticationError):
    """Raised when private key format is invalid or cannot be parsed."""
    pass


class ACPInvalidAddressError(ACPAuthenticationError):
    """Raised when wallet address format is invalid."""
    pass


# API-related exceptions
class ACPApiError(ACPError):
    """Base class for API-related errors."""
    pass


class ACPApiRequestError(ACPApiError):
    """Raised when HTTP API requests fail."""
    pass


class ACPAgentNotFoundError(ACPApiError):
    """Raised when requested agent cannot be found."""
    pass


class ACPJobNotFoundError(ACPApiError):
    """Raised when requested job cannot be found."""
    pass


class ACPMemoNotFoundError(ACPApiError):
    """Raised when requested memo cannot be found."""
    pass


# Smart contract interaction exceptions
class ACPContractError(ACPError):
    """Base class for smart contract interaction errors."""
    pass


class ACPTransactionError(ACPContractError):
    """Base class for blockchain transaction errors."""
    pass


class ACPTransactionFailedError(ACPTransactionError):
    """Raised when blockchain transaction fails or is rejected."""
    pass


class ACPInsufficientFundsError(ACPTransactionError):
    """Raised when account has insufficient funds for transaction."""
    pass


class ACPGasEstimationError(ACPTransactionError):
    """Raised when gas estimation for transaction fails."""
    pass


class ACPContractLogParsingError(ACPContractError):
    """Raised when contract logs cannot be parsed or are missing."""
    pass


class ACPTransactionSigningError(ACPContractError):
    """Raised when transaction signing fails."""
    pass


# Job lifecycle exceptions
class ACPJobError(ACPError):
    """Base class for job lifecycle errors."""
    pass


class ACPJobCreationError(ACPJobError):
    """Raised when job creation fails."""
    pass


class ACPJobStateError(ACPJobError):
    """Raised for invalid job state transitions."""
    pass


class ACPPaymentError(ACPJobError):
    """Raised when payment processing fails."""
    pass


class ACPJobBudgetError(ACPJobError):
    """Raised when job budget operations fail."""
    pass


# Data validation exceptions
class ACPValidationError(ACPError):
    """Base class for data validation errors."""
    pass


class ACPMemoValidationError(ACPValidationError):
    """Raised when memo data validation fails."""
    pass


class ACPSchemaValidationError(ACPValidationError):
    """Raised when requirement schema validation fails."""
    pass


class ACPParameterValidationError(ACPValidationError):
    """Raised when function parameters are invalid."""
    pass


# Legacy exception for backward compatibility
TransactionFailedError = ACPTransactionFailedError