class ACPError(Exception):
    """Base exception for ACP client errors."""
    pass

class ACPApiError(ACPError):
    """Raised for errors from the ACP API."""
    pass

class ACPContractError(ACPError):
    """Raised for errors interacting with the ACP smart contract."""
    pass

class TransactionFailedError(ACPContractError):
    """Raised when a blockchain transaction fails."""
    pass
