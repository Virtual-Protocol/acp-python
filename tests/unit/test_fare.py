"""
Unit tests for virtuals_acp.fare module
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from virtuals_acp.fare import Fare, FareAmount, FareBigInt, FareAmountBase, WETH_FARE, ETH_FARE
from virtuals_acp.exceptions import ACPError


class TestFare:
    """Test suite for Fare class"""

    class TestInitialization:
        """Test Fare initialization"""

        def test_should_initialize_with_contract_address_and_decimals(self):
            """Should initialize with contract address and decimals"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)

            assert fare.contract_address == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
            assert fare.decimals == 6

        def test_should_convert_address_to_checksum(self):
            """Should convert contract address to checksum format"""
            # Lowercase address
            fare = Fare("0x833589fcd6edb6e08f4c7c32d4f71b54bda02913", 6)

            # Should be checksummed
            assert fare.contract_address == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

        def test_should_handle_18_decimals(self):
            """Should handle 18 decimals for ETH-like tokens"""
            fare = Fare("0x4200000000000000000000000000000000000006", 18)

            assert fare.decimals == 18

    class TestFormatAmount:
        """Test format_amount method"""

        def test_should_format_integer_amount(self):
            """Should format integer amount to smallest unit"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)

            result = fare.format_amount(100)

            assert result == 100000000  # 100 * 10^6

        def test_should_format_float_amount(self):
            """Should format float amount to smallest unit"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)

            result = fare.format_amount(1.5)

            assert result == 1500000  # 1.5 * 10^6

        def test_should_format_decimal_amount(self):
            """Should format Decimal amount to smallest unit"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)

            result = fare.format_amount(Decimal("2.5"))

            assert result == 2500000  # 2.5 * 10^6

        def test_should_round_down_fractional_smallest_unit(self):
            """Should round down when converting to smallest unit"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)

            # 1.5555555 -> rounds down to 1.555555 (6 decimals) -> 1555555
            result = fare.format_amount(1.5555559)

            assert result == 1555555

        def test_should_handle_18_decimals_for_eth(self):
            """Should format amount with 18 decimals for ETH"""
            fare = Fare("0x4200000000000000000000000000000000000006", 18)

            result = fare.format_amount(1.0)

            assert result == 1000000000000000000  # 1 * 10^18

        def test_should_handle_very_small_amounts(self):
            """Should handle very small amounts"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)

            result = fare.format_amount(0.000001)

            assert result == 1  # 0.000001 * 10^6

        def test_should_handle_zero(self):
            """Should handle zero amount"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)

            result = fare.format_amount(0)

            assert result == 0

    class TestFromContractAddress:
        """Test from_contract_address static method"""

        def test_should_return_base_fare_when_address_matches(self):
            """Should return base_fare from config when address matches"""
            mock_config = MagicMock()
            base_fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)
            mock_config.base_fare = base_fare

            result = Fare.from_contract_address(
                "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                mock_config
            )

            assert result is base_fare

        def test_should_return_base_fare_with_lowercase_address(self):
            """Should match address case-insensitively"""
            mock_config = MagicMock()
            base_fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)
            mock_config.base_fare = base_fare

            # Use lowercase address
            result = Fare.from_contract_address(
                "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
                mock_config
            )

            assert result is base_fare

        def test_should_query_blockchain_for_unknown_token(self):
            """Should query blockchain to get decimals for unknown token"""
            mock_config = MagicMock()
            mock_config.base_fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)
            mock_config.rpc_url = "https://rpc.example.com"

            # Mock Web3 and contract
            with patch('virtuals_acp.fare.Web3') as mock_web3_class:
                mock_w3 = MagicMock()
                mock_web3_class.return_value = mock_w3
                mock_web3_class.HTTPProvider = MagicMock()
                mock_web3_class.to_checksum_address = lambda x: x.replace("0x", "0x").upper() if "0x" in x else x

                mock_contract = MagicMock()
                mock_contract.functions.decimals().call.return_value = 18
                mock_w3.eth.contract.return_value = mock_contract

                result = Fare.from_contract_address(
                    "0x4200000000000000000000000000000000000006",  # Different address
                    mock_config
                )

                assert result.decimals == 18
                assert mock_contract.functions.decimals().call.called


class TestFareAmountBase:
    """Test suite for FareAmountBase abstract class"""

    class TestInitialization:
        """Test FareAmountBase initialization"""

        def test_should_initialize_with_amount_and_fare(self):
            """Should initialize with amount and fare"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)
            fare_amount = FareBigInt(1000000, fare)

            assert fare_amount.amount == 1000000
            assert fare_amount.fare is fare

    class TestStringRepresentation:
        """Test __repr__ and __str__ methods"""

        def test_should_return_formatted_repr(self):
            """Should return formatted representation"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)
            fare_amount = FareBigInt(1500000, fare)

            result = repr(fare_amount)

            assert "FareAmount" in result
            assert "1500000" in result
            assert "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913" in result
            assert "decimals=6" in result

        def test_should_return_same_string_as_repr(self):
            """Should return same string representation as repr"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)
            fare_amount = FareBigInt(1500000, fare)

            assert str(fare_amount) == repr(fare_amount)

    class TestFromContractAddress:
        """Test from_contract_address static method"""

        def test_should_return_fare_amount_for_float(self):
            """Should return FareAmount when amount is float"""
            mock_config = MagicMock()
            base_fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)
            mock_config.base_fare = base_fare

            result = FareAmountBase.from_contract_address(
                1.5,
                "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                mock_config
            )

            assert isinstance(result, FareAmount)
            assert result.amount == 1500000

        def test_should_return_fare_big_int_for_int(self):
            """Should return FareBigInt when amount is int"""
            mock_config = MagicMock()
            base_fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)
            mock_config.base_fare = base_fare

            result = FareAmountBase.from_contract_address(
                1000000,
                "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                mock_config
            )

            assert isinstance(result, FareBigInt)
            assert result.amount == 1000000


class TestFareAmount:
    """Test suite for FareAmount class"""

    class TestInitialization:
        """Test FareAmount initialization"""

        def test_should_initialize_with_float_amount(self):
            """Should initialize with float amount"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)

            fare_amount = FareAmount(1.5, fare)

            assert fare_amount.amount == 1500000  # 1.5 * 10^6
            assert fare_amount.fare is fare

        def test_should_initialize_with_integer_amount(self):
            """Should initialize with integer amount"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)

            fare_amount = FareAmount(100, fare)

            assert fare_amount.amount == 100000000  # 100 * 10^6

        def test_should_truncate_to_6_decimals(self):
            """Should truncate amount to 6 decimal places"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)

            # 1.5555559 should be truncated to 1.555555
            fare_amount = FareAmount(1.5555559, fare)

            assert fare_amount.amount == 1555555  # 1.555555 * 10^6

        def test_should_handle_very_small_amounts(self):
            """Should handle very small amounts"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)

            fare_amount = FareAmount(0.000001, fare)

            assert fare_amount.amount == 1

        def test_should_handle_large_amounts_with_18_decimals(self):
            """Should handle large amounts with 18 decimals"""
            fare = Fare("0x4200000000000000000000000000000000000006", 18)

            fare_amount = FareAmount(1.0, fare)

            assert fare_amount.amount == 1000000000000000000

    class TestAdd:
        """Test add method"""

        def test_should_add_two_fare_amounts(self):
            """Should add two fare amounts with same token"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)
            fare_amount1 = FareAmount(1.5, fare)
            fare_amount2 = FareAmount(2.5, fare)

            result = fare_amount1.add(fare_amount2)

            assert isinstance(result, FareBigInt)
            assert result.amount == 4000000  # (1.5 + 2.5) * 10^6

        def test_should_add_fare_amount_and_fare_big_int(self):
            """Should add FareAmount and FareBigInt"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)
            fare_amount = FareAmount(1.5, fare)
            fare_big_int = FareBigInt(1000000, fare)

            result = fare_amount.add(fare_big_int)

            assert isinstance(result, FareBigInt)
            assert result.amount == 2500000  # 1.5 * 10^6 + 1000000

        def test_should_raise_error_when_tokens_do_not_match(self):
            """Should raise ACPError when token addresses do not match"""
            fare1 = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)
            fare2 = Fare("0x4200000000000000000000000000000000000006", 18)
            fare_amount1 = FareAmount(1.5, fare1)
            fare_amount2 = FareAmount(2.5, fare2)

            with pytest.raises(ACPError, match="Token addresses do not match"):
                fare_amount1.add(fare_amount2)


class TestFareBigInt:
    """Test suite for FareBigInt class"""

    class TestInitialization:
        """Test FareBigInt initialization"""

        def test_should_initialize_with_integer_amount(self):
            """Should initialize with integer amount"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)

            fare_big_int = FareBigInt(1000000, fare)

            assert fare_big_int.amount == 1000000
            assert fare_big_int.fare is fare

        def test_should_store_amount_as_is(self):
            """Should store amount without formatting"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)

            fare_big_int = FareBigInt(123456789, fare)

            assert fare_big_int.amount == 123456789

    class TestAdd:
        """Test add method"""

        def test_should_add_two_fare_big_ints(self):
            """Should add two FareBigInt amounts"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)
            fare_big_int1 = FareBigInt(1000000, fare)
            fare_big_int2 = FareBigInt(2000000, fare)

            result = fare_big_int1.add(fare_big_int2)

            assert isinstance(result, FareBigInt)
            assert result.amount == 3000000

        def test_should_add_fare_big_int_and_fare_amount(self):
            """Should add FareBigInt and FareAmount"""
            fare = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)
            fare_big_int = FareBigInt(1000000, fare)
            fare_amount = FareAmount(1.5, fare)

            result = fare_big_int.add(fare_amount)

            assert isinstance(result, FareBigInt)
            assert result.amount == 2500000  # 1000000 + 1.5 * 10^6

        def test_should_raise_error_when_tokens_do_not_match(self):
            """Should raise ACPError when token addresses do not match"""
            fare1 = Fare("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)
            fare2 = Fare("0x4200000000000000000000000000000000000006", 18)
            fare_big_int1 = FareBigInt(1000000, fare1)
            fare_big_int2 = FareBigInt(2000000, fare2)

            with pytest.raises(ACPError, match="Token addresses do not match"):
                fare_big_int1.add(fare_big_int2)


class TestPredeclaredFares:
    """Test predeclared fare instances"""

    def test_weth_fare_should_be_defined(self):
        """Should have WETH_FARE predeclared"""
        assert WETH_FARE.contract_address == "0x4200000000000000000000000000000000000006"
        assert WETH_FARE.decimals == 18

    def test_eth_fare_should_be_defined(self):
        """Should have ETH_FARE predeclared"""
        assert ETH_FARE.contract_address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
        assert ETH_FARE.decimals == 18
