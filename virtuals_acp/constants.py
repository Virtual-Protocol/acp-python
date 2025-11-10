USDC_TOKEN_ADDRESS = {
    84532: "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    8453: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
}

# EIP-712 "Authorization" type data specification for X402.
X402_AUTHORIZATION_TYPES = [
    {"name": "from", "type": "address"},
    {"name": "to", "type": "address"},
    {"name": "value", "type": "uint256"},
    {"name": "validAfter", "type": "uint256"},
    {"name": "validBefore", "type": "uint256"},
    {"name": "nonce", "type": "bytes32"},
]

VERIFYING_CONTRACT_ADDRESS = "0x00000000000099DE0BF6fA90dEB851E2A2df7d83"

HTTP_STATUS_CODES_X402 = {"Payment Required": 402, "OK": 200}
