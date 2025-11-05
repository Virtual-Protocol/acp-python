from abc import ABC, abstractmethod
from decimal import Decimal, ROUND_DOWN
from typing import Union
from web3 import Web3
from web3.contract import Contract

from virtuals_acp.exceptions import ACPError

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from virtuals_acp.configs.configs import ACPContractConfig


class Fare:
    def __init__(self, contract_address: str, decimals: int):
        self.contract_address = Web3.to_checksum_address(contract_address)
        self.decimals = decimals

    def format_amount(self, amount: Union[int, float, Decimal]) -> int:
        """Convert to smallest unit (like parseUnits)."""
        amount_decimal = Decimal(str(amount)).scaleb(self.decimals)
        return int(amount_decimal.to_integral_value(rounding=ROUND_DOWN))

    @staticmethod
    def from_contract_address(
        contract_address: str, config: "ACPContractConfig"
    ) -> "Fare":
        if Web3.to_checksum_address(contract_address) == Web3.to_checksum_address(
            config.base_fare.contract_address
        ):
            return config.base_fare

        w3 = Web3(Web3.HTTPProvider(config.rpc_url))

        erc20_abi = [
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function",
            }
        ]

        contract: Contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address), abi=erc20_abi
        )
        decimals = contract.functions.decimals().call()
        return Fare(contract_address, decimals)


class FareAmountBase(ABC):
    def __init__(self, amount: int, fare: Fare):
        self.amount = amount
        self.fare = fare

    def __repr__(self) -> str:
        return (
            f"<FareAmount amount={self.amount} "
            f"token={self.fare.contract_address} "
            f"decimals={self.fare.decimals}>"
        )

    __str__ = __repr__

    @abstractmethod
    def add(self, other: "FareAmountBase") -> "FareAmountBase":
        pass

    @staticmethod
    def from_contract_address(
        amount: Union[int, float], contract_address: str, config: "ACPContractConfig"
    ) -> "FareAmountBase":
        fare = Fare.from_contract_address(contract_address, config)
        if isinstance(amount, float):
            return FareAmount(amount, fare)
        return FareBigInt(int(amount), fare)


class FareAmount(FareAmountBase):
    def __init__(self, fare_amount: Union[int, float], fare: Fare):
        def truncate_to_6_decimals(value: str) -> str:
            d = Decimal(value)
            return str(d.quantize(Decimal("0.000001"), rounding=ROUND_DOWN))

        truncated = truncate_to_6_decimals(str(fare_amount))
        super().__init__(fare.format_amount(Decimal(truncated)), fare)

    def add(self, other: FareAmountBase) -> "FareAmountBase":
        if self.fare.contract_address != other.fare.contract_address:
            raise ACPError("Token addresses do not match")
        return FareBigInt(self.amount + other.amount, self.fare)


class FareBigInt(FareAmountBase):
    def __init__(self, amount: int, fare: Fare):
        super().__init__(amount, fare)

    def add(self, other: FareAmountBase) -> "FareAmountBase":
        if self.fare.contract_address != other.fare.contract_address:
            raise ACPError("Token addresses do not match")
        return FareBigInt(self.amount + other.amount, self.fare)


# --- Declared Fare Instances ---
WETH_FARE = Fare("0x4200000000000000000000000000000000000006", 18)
ETH_FARE = Fare("0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", 18)
