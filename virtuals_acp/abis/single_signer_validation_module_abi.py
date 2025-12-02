SINGLE_SIGNER_VALIDATION_MODULE_ABI = [
    { "inputs": [], "name": "InvalidSignatureType", "type": "error" },
    {
        "inputs": [],
        "name": "NotAuthorized",
        "type": "error",
    },
    { "inputs": [], "name": "NotImplemented", "type": "error" },
    {
        "inputs": [],
        "name": "UnexpectedDataPassed",
        "type": "error",
    },
    {
        "anonymous": True,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "account",
                "type": "address",
            },
            {
                "indexed": True,
                "internalType": "uint32",
                "name": "entityId",
                "type": "uint32",
            },
            {
                "indexed": True,
                "internalType": "address",
                "name": "newSigner",
                "type": "address",
            },
            {
                "indexed": False,
                "internalType": "address",
                "name": "previousSigner",
                "type": "address",
            },
        ],
        "name": "SignerTransferred",
        "type": "event",
    },
    {
        "inputs": [],
        "name": "moduleId",
        "outputs": [{ "internalType": "string", "name": "", "type": "string" }],
        "stateMutability": "pure",
        "type": "function",
    },
    {
        "inputs": [{ "internalType": "bytes", "name": "data", "type": "bytes" }],
        "name": "onInstall",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{ "internalType": "bytes", "name": "data", "type": "bytes" }],
        "name": "onUninstall",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            { "internalType": "address", "name": "account", "type": "address" },
            {
                "internalType": "bytes32",
                "name": "hash",
                "type": "bytes32",
            },
        ],
        "name": "replaySafeHash",
        "outputs": [{ "internalType": "bytes32", "name": "", "type": "bytes32" }],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            { "internalType": "uint32", "name": "entityId", "type": "uint32" },
            {
                "internalType": "address",
                "name": "account",
                "type": "address",
            },
        ],
        "name": "signers",
        "outputs": [{ "internalType": "address", "name": "", "type": "address" }],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{ "internalType": "bytes4", "name": "interfaceId", "type": "bytes4" }],
        "name": "supportsInterface",
        "outputs": [{ "internalType": "bool", "name": "", "type": "bool" }],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            { "internalType": "uint32", "name": "entityId", "type": "uint32" },
            {
                "internalType": "address",
                "name": "newSigner",
                "type": "address",
            },
        ],
        "name": "transferSigner",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            { "internalType": "address", "name": "account", "type": "address" },
            {
                "internalType": "uint32",
                "name": "entityId",
                "type": "uint32",
            },
            { "internalType": "address", "name": "sender", "type": "address" },
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256",
            },
            { "internalType": "bytes", "name": "", "type": "bytes" },
            {
                "internalType": "bytes",
                "name": "",
                "type": "bytes",
            },
        ],
        "name": "validateRuntime",
        "outputs": [],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            { "internalType": "address", "name": "account", "type": "address" },
            {
                "internalType": "uint32",
                "name": "entityId",
                "type": "uint32",
            },
            { "internalType": "address", "name": "", "type": "address" },
            {
                "internalType": "bytes32",
                "name": "digest",
                "type": "bytes32",
            },
            { "internalType": "bytes", "name": "signature", "type": "bytes" },
        ],
        "name": "validateSignature",
        "outputs": [{ "internalType": "bytes4", "name": "", "type": "bytes4" }],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {
                "internalType": "uint32",
                "name": "entityId",
                "type": "uint32",
            },
            {
                "components": [
                    { "internalType": "address", "name": "sender", "type": "address" },
                    {
                        "internalType": "uint256",
                        "name": "nonce",
                        "type": "uint256",
                    },
                    { "internalType": "bytes", "name": "initCode", "type": "bytes" },
                    {
                        "internalType": "bytes",
                        "name": "callData",
                        "type": "bytes",
                    },
                    {
                        "internalType": "bytes32",
                        "name": "accountGasLimits",
                        "type": "bytes32",
                    },
                    {
                        "internalType": "uint256",
                        "name": "preVerificationGas",
                        "type": "uint256",
                    },
                    { "internalType": "bytes32", "name": "gasFees", "type": "bytes32" },
                    {
                        "internalType": "bytes",
                        "name": "paymasterAndData",
                        "type": "bytes",
                    },
                    { "internalType": "bytes", "name": "signature", "type": "bytes" },
                ],
                "internalType": "struct PackedUserOperation",
                "name": "userOp",
                "type": "tuple",
            },
            { "internalType": "bytes32", "name": "userOpHash", "type": "bytes32" },
        ],
        "name": "validateUserOp",
        "outputs": [{ "internalType": "uint256", "name": "", "type": "uint256" }],
        "stateMutability": "view",
        "type": "function",
    },
]
