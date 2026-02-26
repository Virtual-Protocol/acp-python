MEMO_MANAGER_ABI = [
  { "inputs": [], "stateMutability": "nonpayable", "type": "constructor" },
  { "inputs": [], "name": "AccessControlBadConfirmation", "type": "error" },
  {
    "inputs": [
      { "internalType": "address", "name": "account", "type": "address" },
      { "internalType": "bytes32", "name": "neededRole", "type": "bytes32" }
    ],
    "name": "AccessControlUnauthorizedAccount",
    "type": "error"
  },
  {
    "inputs": [{ "internalType": "address", "name": "target", "type": "address" }],
    "name": "AddressEmptyCode",
    "type": "error"
  },
  { "inputs": [], "name": "AlreadyVoted", "type": "error" },
  { "inputs": [], "name": "CannotApproveMemo", "type": "error" },
  { "inputs": [], "name": "CannotUpdateApprovedMemo", "type": "error" },
  { "inputs": [], "name": "CannotUpdateMemo", "type": "error" },
  { "inputs": [], "name": "CannotWithdrawYet", "type": "error" },
  { "inputs": [], "name": "DestinationChainNotConfigured", "type": "error" },
  {
    "inputs": [
      { "internalType": "address", "name": "implementation", "type": "address" }
    ],
    "name": "ERC1967InvalidImplementation",
    "type": "error"
  },
  { "inputs": [], "name": "ERC1967NonPayable", "type": "error" },
  { "inputs": [], "name": "EmptyContent", "type": "error" },
  { "inputs": [], "name": "FailedInnerCall", "type": "error" },
  { "inputs": [], "name": "InvalidInitialization", "type": "error" },
  { "inputs": [], "name": "InvalidMemoState", "type": "error" },
  { "inputs": [], "name": "InvalidMemoStateTransition", "type": "error" },
  { "inputs": [], "name": "InvalidMemoType", "type": "error" },
  { "inputs": [], "name": "JobAlreadyCompleted", "type": "error" },
  { "inputs": [], "name": "JobDoesNotExist", "type": "error" },
  { "inputs": [], "name": "MemoAlreadyApproved", "type": "error" },
  { "inputs": [], "name": "MemoAlreadyExecuted", "type": "error" },
  { "inputs": [], "name": "MemoAlreadySigned", "type": "error" },
  { "inputs": [], "name": "MemoCannotBeSigned", "type": "error" },
  { "inputs": [], "name": "MemoDoesNotExist", "type": "error" },
  { "inputs": [], "name": "MemoDoesNotRequireApproval", "type": "error" },
  { "inputs": [], "name": "MemoExpired", "type": "error" },
  { "inputs": [], "name": "MemoNotApproved", "type": "error" },
  { "inputs": [], "name": "MemoNotReadyToBeSigned", "type": "error" },
  { "inputs": [], "name": "MemoStateUnchanged", "type": "error" },
  { "inputs": [], "name": "NoAmountToTransfer", "type": "error" },
  { "inputs": [], "name": "NoPaymentAmount", "type": "error" },
  { "inputs": [], "name": "NotEscrowTransferMemoType", "type": "error" },
  { "inputs": [], "name": "NotInitializing", "type": "error" },
  { "inputs": [], "name": "NotPayableMemoType", "type": "error" },
  { "inputs": [], "name": "OnlyACPContract", "type": "error" },
  { "inputs": [], "name": "OnlyAssetManager", "type": "error" },
  { "inputs": [], "name": "OnlyClientOrProvider", "type": "error" },
  { "inputs": [], "name": "OnlyCounterParty", "type": "error" },
  { "inputs": [], "name": "OnlyEvaluator", "type": "error" },
  { "inputs": [], "name": "OnlyMemoSender", "type": "error" },
  { "inputs": [], "name": "ReentrancyGuardReentrantCall", "type": "error" },
  { "inputs": [], "name": "UUPSUnauthorizedCallContext", "type": "error" },
  {
    "inputs": [{ "internalType": "bytes32", "name": "slot", "type": "bytes32" }],
    "name": "UUPSUnsupportedProxiableUUID",
    "type": "error"
  },
  { "inputs": [], "name": "ZeroAcpContractAddress", "type": "error" },
  { "inputs": [], "name": "ZeroAddressRecipient", "type": "error" },
  { "inputs": [], "name": "ZeroAddressToken", "type": "error" },
  { "inputs": [], "name": "ZeroAssetManagerAddress", "type": "error" },
  { "inputs": [], "name": "ZeroJobManagerAddress", "type": "error" },
  {
    "anonymous": False,
    "inputs": [
      {
        "indexed": False,
        "internalType": "uint64",
        "name": "version",
        "type": "uint64"
      }
    ],
    "name": "Initialized",
    "type": "event"
  },
  {
    "anonymous": False,
    "inputs": [
      {
        "indexed": True,
        "internalType": "uint256",
        "name": "memoId",
        "type": "uint256"
      },
      {
        "indexed": True,
        "internalType": "address",
        "name": "approver",
        "type": "address"
      },
      { "indexed": False, "internalType": "bool", "name": "approved", "type": "bool" },
      {
        "indexed": False,
        "internalType": "string",
        "name": "reason",
        "type": "string"
      }
    ],
    "name": "MemoSigned",
    "type": "event"
  },
  {
    "anonymous": False,
    "inputs": [
      {
        "indexed": True,
        "internalType": "uint256",
        "name": "memoId",
        "type": "uint256"
      },
      {
        "indexed": False,
        "internalType": "enum ACPTypes.MemoState",
        "name": "oldState",
        "type": "uint8"
      },
      {
        "indexed": False,
        "internalType": "enum ACPTypes.MemoState",
        "name": "newState",
        "type": "uint8"
      }
    ],
    "name": "MemoStateUpdated",
    "type": "event"
  },
  {
    "anonymous": False,
    "inputs": [
      {
        "indexed": True,
        "internalType": "uint256",
        "name": "memoId",
        "type": "uint256"
      },
      {
        "indexed": True,
        "internalType": "uint256",
        "name": "jobId",
        "type": "uint256"
      },
      {
        "indexed": True,
        "internalType": "address",
        "name": "sender",
        "type": "address"
      },
      {
        "indexed": False,
        "internalType": "enum ACPTypes.MemoType",
        "name": "memoType",
        "type": "uint8"
      },
      {
        "indexed": False,
        "internalType": "enum ACPTypes.JobPhase",
        "name": "nextPhase",
        "type": "uint8"
      },
      {
        "indexed": False,
        "internalType": "string",
        "name": "content",
        "type": "string"
      }
    ],
    "name": "NewMemo",
    "type": "event"
  },
  {
    "anonymous": False,
    "inputs": [
      {
        "indexed": True,
        "internalType": "uint256",
        "name": "jobId",
        "type": "uint256"
      },
      {
        "indexed": True,
        "internalType": "uint256",
        "name": "memoId",
        "type": "uint256"
      },
      {
        "indexed": True,
        "internalType": "address",
        "name": "sender",
        "type": "address"
      },
      {
        "indexed": False,
        "internalType": "address",
        "name": "token",
        "type": "address"
      },
      {
        "indexed": False,
        "internalType": "uint256",
        "name": "amount",
        "type": "uint256"
      }
    ],
    "name": "PayableFeeRefunded",
    "type": "event"
  },
  {
    "anonymous": False,
    "inputs": [
      {
        "indexed": True,
        "internalType": "uint256",
        "name": "jobId",
        "type": "uint256"
      },
      {
        "indexed": True,
        "internalType": "uint256",
        "name": "memoId",
        "type": "uint256"
      },
      {
        "indexed": True,
        "internalType": "address",
        "name": "sender",
        "type": "address"
      },
      {
        "indexed": False,
        "internalType": "address",
        "name": "token",
        "type": "address"
      },
      {
        "indexed": False,
        "internalType": "uint256",
        "name": "amount",
        "type": "uint256"
      }
    ],
    "name": "PayableFundsRefunded",
    "type": "event"
  },
  {
    "anonymous": False,
    "inputs": [
      {
        "indexed": True,
        "internalType": "uint256",
        "name": "memoId",
        "type": "uint256"
      },
      {
        "indexed": True,
        "internalType": "uint256",
        "name": "jobId",
        "type": "uint256"
      },
      {
        "indexed": True,
        "internalType": "address",
        "name": "executor",
        "type": "address"
      },
      {
        "indexed": False,
        "internalType": "uint256",
        "name": "amount",
        "type": "uint256"
      }
    ],
    "name": "PayableMemoExecuted",
    "type": "event"
  },
  {
    "anonymous": False,
    "inputs": [
      { "indexed": True, "internalType": "bytes32", "name": "role", "type": "bytes32" },
      {
        "indexed": True,
        "internalType": "bytes32",
        "name": "previousAdminRole",
        "type": "bytes32"
      },
      {
        "indexed": True,
        "internalType": "bytes32",
        "name": "newAdminRole",
        "type": "bytes32"
      }
    ],
    "name": "RoleAdminChanged",
    "type": "event"
  },
  {
    "anonymous": False,
    "inputs": [
      { "indexed": True, "internalType": "bytes32", "name": "role", "type": "bytes32" },
      {
        "indexed": True,
        "internalType": "address",
        "name": "account",
        "type": "address"
      },
      {
        "indexed": True,
        "internalType": "address",
        "name": "sender",
        "type": "address"
      }
    ],
    "name": "RoleGranted",
    "type": "event"
  },
  {
    "anonymous": False,
    "inputs": [
      { "indexed": True, "internalType": "bytes32", "name": "role", "type": "bytes32" },
      {
        "indexed": True,
        "internalType": "address",
        "name": "account",
        "type": "address"
      },
      {
        "indexed": True,
        "internalType": "address",
        "name": "sender",
        "type": "address"
      }
    ],
    "name": "RoleRevoked",
    "type": "event"
  },
  {
    "anonymous": False,
    "inputs": [
      {
        "indexed": True,
        "internalType": "address",
        "name": "implementation",
        "type": "address"
      }
    ],
    "name": "Upgraded",
    "type": "event"
  },
  {
    "inputs": [],
    "name": "ACP_CONTRACT_ROLE",
    "outputs": [{ "internalType": "bytes32", "name": "", "type": "bytes32" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "ADMIN_ROLE",
    "outputs": [{ "internalType": "bytes32", "name": "", "type": "bytes32" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "DEFAULT_ADMIN_ROLE",
    "outputs": [{ "internalType": "bytes32", "name": "", "type": "bytes32" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "UPGRADE_INTERFACE_VERSION",
    "outputs": [{ "internalType": "string", "name": "", "type": "string" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "acpContract",
    "outputs": [{ "internalType": "address", "name": "", "type": "address" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "memoId", "type": "uint256" },
      { "internalType": "address", "name": "sender", "type": "address" },
      { "internalType": "bool", "name": "approved", "type": "bool" },
      { "internalType": "string", "name": "reason", "type": "string" }
    ],
    "name": "approveMemo",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "assetManager",
    "outputs": [{ "internalType": "address", "name": "", "type": "address" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256[]", "name": "memoIds", "type": "uint256[]" },
      { "internalType": "bool", "name": "approved", "type": "bool" },
      { "internalType": "string", "name": "reason", "type": "string" }
    ],
    "name": "bulkApproveMemos",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "memoId", "type": "uint256" },
      { "internalType": "address", "name": "user", "type": "address" }
    ],
    "name": "canApproveMemo",
    "outputs": [{ "internalType": "bool", "name": "", "type": "bool" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "jobId", "type": "uint256" },
      { "internalType": "address", "name": "sender", "type": "address" },
      { "internalType": "string", "name": "content", "type": "string" },
      {
        "internalType": "enum ACPTypes.MemoType",
        "name": "memoType",
        "type": "uint8"
      },
      { "internalType": "bool", "name": "isSecured", "type": "bool" },
      {
        "internalType": "enum ACPTypes.JobPhase",
        "name": "nextPhase",
        "type": "uint8"
      },
      { "internalType": "string", "name": "metadata", "type": "string" }
    ],
    "name": "createMemo",
    "outputs": [{ "internalType": "uint256", "name": "memoId", "type": "uint256" }],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "jobId", "type": "uint256" },
      { "internalType": "address", "name": "sender", "type": "address" },
      { "internalType": "string", "name": "content", "type": "string" },
      {
        "internalType": "enum ACPTypes.MemoType",
        "name": "memoType",
        "type": "uint8"
      },
      { "internalType": "bool", "name": "isSecured", "type": "bool" },
      {
        "internalType": "enum ACPTypes.JobPhase",
        "name": "nextPhase",
        "type": "uint8"
      },
      {
        "components": [
          { "internalType": "address", "name": "token", "type": "address" },
          { "internalType": "uint256", "name": "amount", "type": "uint256" },
          { "internalType": "address", "name": "recipient", "type": "address" },
          { "internalType": "uint256", "name": "feeAmount", "type": "uint256" },
          {
            "internalType": "enum ACPTypes.FeeType",
            "name": "feeType",
            "type": "uint8"
          },
          { "internalType": "bool", "name": "isExecuted", "type": "bool" },
          { "internalType": "uint256", "name": "expiredAt", "type": "uint256" },
          { "internalType": "uint32", "name": "lzSrcEid", "type": "uint32" },
          { "internalType": "uint32", "name": "lzDstEid", "type": "uint32" }
        ],
        "internalType": "struct ACPTypes.PayableDetails",
        "name": "payableDetails_",
        "type": "tuple"
      },
      { "internalType": "uint256", "name": "expiredAt", "type": "uint256" }
    ],
    "name": "createPayableMemo",
    "outputs": [{ "internalType": "uint256", "name": "memoId", "type": "uint256" }],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [{ "internalType": "uint256", "name": "memoId", "type": "uint256" }],
    "name": "emergencyApproveMemo",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [{ "internalType": "uint256", "name": "memoId", "type": "uint256" }],
    "name": "executePayableMemo",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "getAssetManager",
    "outputs": [{ "internalType": "address", "name": "", "type": "address" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "jobId", "type": "uint256" },
      { "internalType": "uint256", "name": "offset", "type": "uint256" },
      { "internalType": "uint256", "name": "limit", "type": "uint256" }
    ],
    "name": "getJobMemos",
    "outputs": [
      {
        "components": [
          { "internalType": "uint256", "name": "id", "type": "uint256" },
          { "internalType": "uint256", "name": "jobId", "type": "uint256" },
          { "internalType": "address", "name": "sender", "type": "address" },
          { "internalType": "string", "name": "content", "type": "string" },
          {
            "internalType": "enum ACPTypes.MemoType",
            "name": "memoType",
            "type": "uint8"
          },
          { "internalType": "uint256", "name": "createdAt", "type": "uint256" },
          { "internalType": "bool", "name": "isApproved", "type": "bool" },
          { "internalType": "address", "name": "approvedBy", "type": "address" },
          { "internalType": "uint256", "name": "approvedAt", "type": "uint256" },
          { "internalType": "bool", "name": "requiresApproval", "type": "bool" },
          { "internalType": "string", "name": "metadata", "type": "string" },
          { "internalType": "bool", "name": "isSecured", "type": "bool" },
          {
            "internalType": "enum ACPTypes.JobPhase",
            "name": "nextPhase",
            "type": "uint8"
          },
          { "internalType": "uint256", "name": "expiredAt", "type": "uint256" },
          {
            "internalType": "enum ACPTypes.MemoState",
            "name": "state",
            "type": "uint8"
          }
        ],
        "internalType": "struct ACPTypes.Memo[]",
        "name": "memoArray",
        "type": "tuple[]"
      },
      { "internalType": "uint256", "name": "total", "type": "uint256" }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "jobId", "type": "uint256" },
      { "internalType": "enum ACPTypes.JobPhase", "name": "phase", "type": "uint8" },
      { "internalType": "uint256", "name": "offset", "type": "uint256" },
      { "internalType": "uint256", "name": "limit", "type": "uint256" }
    ],
    "name": "getJobMemosByPhase",
    "outputs": [
      {
        "components": [
          { "internalType": "uint256", "name": "id", "type": "uint256" },
          { "internalType": "uint256", "name": "jobId", "type": "uint256" },
          { "internalType": "address", "name": "sender", "type": "address" },
          { "internalType": "string", "name": "content", "type": "string" },
          {
            "internalType": "enum ACPTypes.MemoType",
            "name": "memoType",
            "type": "uint8"
          },
          { "internalType": "uint256", "name": "createdAt", "type": "uint256" },
          { "internalType": "bool", "name": "isApproved", "type": "bool" },
          { "internalType": "address", "name": "approvedBy", "type": "address" },
          { "internalType": "uint256", "name": "approvedAt", "type": "uint256" },
          { "internalType": "bool", "name": "requiresApproval", "type": "bool" },
          { "internalType": "string", "name": "metadata", "type": "string" },
          { "internalType": "bool", "name": "isSecured", "type": "bool" },
          {
            "internalType": "enum ACPTypes.JobPhase",
            "name": "nextPhase",
            "type": "uint8"
          },
          { "internalType": "uint256", "name": "expiredAt", "type": "uint256" },
          {
            "internalType": "enum ACPTypes.MemoState",
            "name": "state",
            "type": "uint8"
          }
        ],
        "internalType": "struct ACPTypes.Memo[]",
        "name": "memoArray",
        "type": "tuple[]"
      },
      { "internalType": "uint256", "name": "total", "type": "uint256" }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "jobId", "type": "uint256" },
      {
        "internalType": "enum ACPTypes.MemoType",
        "name": "memoType",
        "type": "uint8"
      },
      { "internalType": "uint256", "name": "offset", "type": "uint256" },
      { "internalType": "uint256", "name": "limit", "type": "uint256" }
    ],
    "name": "getJobMemosByType",
    "outputs": [
      {
        "components": [
          { "internalType": "uint256", "name": "id", "type": "uint256" },
          { "internalType": "uint256", "name": "jobId", "type": "uint256" },
          { "internalType": "address", "name": "sender", "type": "address" },
          { "internalType": "string", "name": "content", "type": "string" },
          {
            "internalType": "enum ACPTypes.MemoType",
            "name": "memoType",
            "type": "uint8"
          },
          { "internalType": "uint256", "name": "createdAt", "type": "uint256" },
          { "internalType": "bool", "name": "isApproved", "type": "bool" },
          { "internalType": "address", "name": "approvedBy", "type": "address" },
          { "internalType": "uint256", "name": "approvedAt", "type": "uint256" },
          { "internalType": "bool", "name": "requiresApproval", "type": "bool" },
          { "internalType": "string", "name": "metadata", "type": "string" },
          { "internalType": "bool", "name": "isSecured", "type": "bool" },
          {
            "internalType": "enum ACPTypes.JobPhase",
            "name": "nextPhase",
            "type": "uint8"
          },
          { "internalType": "uint256", "name": "expiredAt", "type": "uint256" },
          {
            "internalType": "enum ACPTypes.MemoState",
            "name": "state",
            "type": "uint8"
          }
        ],
        "internalType": "struct ACPTypes.Memo[]",
        "name": "memoArray",
        "type": "tuple[]"
      },
      { "internalType": "uint256", "name": "total", "type": "uint256" }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "getLocalEid",
    "outputs": [{ "internalType": "uint32", "name": "", "type": "uint32" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [{ "internalType": "uint256", "name": "memoId", "type": "uint256" }],
    "name": "getMemo",
    "outputs": [
      {
        "components": [
          { "internalType": "uint256", "name": "id", "type": "uint256" },
          { "internalType": "uint256", "name": "jobId", "type": "uint256" },
          { "internalType": "address", "name": "sender", "type": "address" },
          { "internalType": "string", "name": "content", "type": "string" },
          {
            "internalType": "enum ACPTypes.MemoType",
            "name": "memoType",
            "type": "uint8"
          },
          { "internalType": "uint256", "name": "createdAt", "type": "uint256" },
          { "internalType": "bool", "name": "isApproved", "type": "bool" },
          { "internalType": "address", "name": "approvedBy", "type": "address" },
          { "internalType": "uint256", "name": "approvedAt", "type": "uint256" },
          { "internalType": "bool", "name": "requiresApproval", "type": "bool" },
          { "internalType": "string", "name": "metadata", "type": "string" },
          { "internalType": "bool", "name": "isSecured", "type": "bool" },
          {
            "internalType": "enum ACPTypes.JobPhase",
            "name": "nextPhase",
            "type": "uint8"
          },
          { "internalType": "uint256", "name": "expiredAt", "type": "uint256" },
          {
            "internalType": "enum ACPTypes.MemoState",
            "name": "state",
            "type": "uint8"
          }
        ],
        "internalType": "struct ACPTypes.Memo",
        "name": "",
        "type": "tuple"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [{ "internalType": "uint256", "name": "memoId", "type": "uint256" }],
    "name": "getMemoApprovalStatus",
    "outputs": [
      { "internalType": "bool", "name": "isApproved", "type": "bool" },
      { "internalType": "address", "name": "approvedBy", "type": "address" },
      { "internalType": "uint256", "name": "approvedAt", "type": "uint256" }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [{ "internalType": "uint256", "name": "memoId", "type": "uint256" }],
    "name": "getMemoWithPayableDetails",
    "outputs": [
      {
        "components": [
          { "internalType": "uint256", "name": "id", "type": "uint256" },
          { "internalType": "uint256", "name": "jobId", "type": "uint256" },
          { "internalType": "address", "name": "sender", "type": "address" },
          { "internalType": "string", "name": "content", "type": "string" },
          {
            "internalType": "enum ACPTypes.MemoType",
            "name": "memoType",
            "type": "uint8"
          },
          { "internalType": "uint256", "name": "createdAt", "type": "uint256" },
          { "internalType": "bool", "name": "isApproved", "type": "bool" },
          { "internalType": "address", "name": "approvedBy", "type": "address" },
          { "internalType": "uint256", "name": "approvedAt", "type": "uint256" },
          { "internalType": "bool", "name": "requiresApproval", "type": "bool" },
          { "internalType": "string", "name": "metadata", "type": "string" },
          { "internalType": "bool", "name": "isSecured", "type": "bool" },
          {
            "internalType": "enum ACPTypes.JobPhase",
            "name": "nextPhase",
            "type": "uint8"
          },
          { "internalType": "uint256", "name": "expiredAt", "type": "uint256" },
          {
            "internalType": "enum ACPTypes.MemoState",
            "name": "state",
            "type": "uint8"
          }
        ],
        "internalType": "struct ACPTypes.Memo",
        "name": "memo",
        "type": "tuple"
      },
      {
        "components": [
          { "internalType": "address", "name": "token", "type": "address" },
          { "internalType": "uint256", "name": "amount", "type": "uint256" },
          { "internalType": "address", "name": "recipient", "type": "address" },
          { "internalType": "uint256", "name": "feeAmount", "type": "uint256" },
          {
            "internalType": "enum ACPTypes.FeeType",
            "name": "feeType",
            "type": "uint8"
          },
          { "internalType": "bool", "name": "isExecuted", "type": "bool" },
          { "internalType": "uint256", "name": "expiredAt", "type": "uint256" },
          { "internalType": "uint32", "name": "lzSrcEid", "type": "uint32" },
          { "internalType": "uint32", "name": "lzDstEid", "type": "uint32" }
        ],
        "internalType": "struct ACPTypes.PayableDetails",
        "name": "details",
        "type": "tuple"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [{ "internalType": "uint256", "name": "memoId", "type": "uint256" }],
    "name": "getPayableDetails",
    "outputs": [
      {
        "components": [
          { "internalType": "address", "name": "token", "type": "address" },
          { "internalType": "uint256", "name": "amount", "type": "uint256" },
          { "internalType": "address", "name": "recipient", "type": "address" },
          { "internalType": "uint256", "name": "feeAmount", "type": "uint256" },
          {
            "internalType": "enum ACPTypes.FeeType",
            "name": "feeType",
            "type": "uint8"
          },
          { "internalType": "bool", "name": "isExecuted", "type": "bool" },
          { "internalType": "uint256", "name": "expiredAt", "type": "uint256" },
          { "internalType": "uint32", "name": "lzSrcEid", "type": "uint32" },
          { "internalType": "uint32", "name": "lzDstEid", "type": "uint32" }
        ],
        "internalType": "struct ACPTypes.PayableDetails",
        "name": "",
        "type": "tuple"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [{ "internalType": "bytes32", "name": "role", "type": "bytes32" }],
    "name": "getRoleAdmin",
    "outputs": [{ "internalType": "bytes32", "name": "", "type": "bytes32" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "bytes32", "name": "role", "type": "bytes32" },
      { "internalType": "address", "name": "account", "type": "address" }
    ],
    "name": "grantRole",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "bytes32", "name": "role", "type": "bytes32" },
      { "internalType": "address", "name": "account", "type": "address" }
    ],
    "name": "hasRole",
    "outputs": [{ "internalType": "bool", "name": "", "type": "bool" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "address", "name": "acpContract_", "type": "address" },
      { "internalType": "address", "name": "jobManager_", "type": "address" },
      { "internalType": "address", "name": "paymentManager_", "type": "address" }
    ],
    "name": "initialize",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "jobId", "type": "uint256" },
      { "internalType": "address", "name": "user", "type": "address" }
    ],
    "name": "isJobEvaluator",
    "outputs": [{ "internalType": "bool", "name": "", "type": "bool" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "memoId", "type": "uint256" },
      { "internalType": "address", "name": "user", "type": "address" }
    ],
    "name": "isMemoSigner",
    "outputs": [{ "internalType": "bool", "name": "", "type": "bool" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [{ "internalType": "uint256", "name": "memoId", "type": "uint256" }],
    "name": "isPayable",
    "outputs": [{ "internalType": "bool", "name": "", "type": "bool" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "jobManager",
    "outputs": [{ "internalType": "address", "name": "", "type": "address" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "", "type": "uint256" },
      { "internalType": "uint256", "name": "", "type": "uint256" }
    ],
    "name": "jobMemos",
    "outputs": [{ "internalType": "uint256", "name": "", "type": "uint256" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "", "type": "uint256" },
      { "internalType": "enum ACPTypes.JobPhase", "name": "", "type": "uint8" },
      { "internalType": "uint256", "name": "", "type": "uint256" }
    ],
    "name": "jobMemosByPhase",
    "outputs": [{ "internalType": "uint256", "name": "", "type": "uint256" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "", "type": "uint256" },
      { "internalType": "enum ACPTypes.MemoType", "name": "", "type": "uint8" },
      { "internalType": "uint256", "name": "", "type": "uint256" }
    ],
    "name": "jobMemosByType",
    "outputs": [{ "internalType": "uint256", "name": "", "type": "uint256" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "", "type": "uint256" },
      { "internalType": "address", "name": "", "type": "address" }
    ],
    "name": "memoApprovals",
    "outputs": [{ "internalType": "bool", "name": "", "type": "bool" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "memoCounter",
    "outputs": [{ "internalType": "uint256", "name": "", "type": "uint256" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [{ "internalType": "uint256", "name": "", "type": "uint256" }],
    "name": "memos",
    "outputs": [
      { "internalType": "uint256", "name": "id", "type": "uint256" },
      { "internalType": "uint256", "name": "jobId", "type": "uint256" },
      { "internalType": "address", "name": "sender", "type": "address" },
      { "internalType": "string", "name": "content", "type": "string" },
      {
        "internalType": "enum ACPTypes.MemoType",
        "name": "memoType",
        "type": "uint8"
      },
      { "internalType": "uint256", "name": "createdAt", "type": "uint256" },
      { "internalType": "bool", "name": "isApproved", "type": "bool" },
      { "internalType": "address", "name": "approvedBy", "type": "address" },
      { "internalType": "uint256", "name": "approvedAt", "type": "uint256" },
      { "internalType": "bool", "name": "requiresApproval", "type": "bool" },
      { "internalType": "string", "name": "metadata", "type": "string" },
      { "internalType": "bool", "name": "isSecured", "type": "bool" },
      {
        "internalType": "enum ACPTypes.JobPhase",
        "name": "nextPhase",
        "type": "uint8"
      },
      { "internalType": "uint256", "name": "expiredAt", "type": "uint256" },
      { "internalType": "enum ACPTypes.MemoState", "name": "state", "type": "uint8" }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [{ "internalType": "uint256", "name": "", "type": "uint256" }],
    "name": "payableDetails",
    "outputs": [
      { "internalType": "address", "name": "token", "type": "address" },
      { "internalType": "uint256", "name": "amount", "type": "uint256" },
      { "internalType": "address", "name": "recipient", "type": "address" },
      { "internalType": "uint256", "name": "feeAmount", "type": "uint256" },
      { "internalType": "enum ACPTypes.FeeType", "name": "feeType", "type": "uint8" },
      { "internalType": "bool", "name": "isExecuted", "type": "bool" },
      { "internalType": "uint256", "name": "expiredAt", "type": "uint256" },
      { "internalType": "uint32", "name": "lzSrcEid", "type": "uint32" },
      { "internalType": "uint32", "name": "lzDstEid", "type": "uint32" }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "paymentManager",
    "outputs": [{ "internalType": "address", "name": "", "type": "address" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "proxiableUUID",
    "outputs": [{ "internalType": "bytes32", "name": "", "type": "bytes32" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "bytes32", "name": "role", "type": "bytes32" },
      { "internalType": "address", "name": "callerConfirmation", "type": "address" }
    ],
    "name": "renounceRole",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [{ "internalType": "uint256", "name": "", "type": "uint256" }],
    "name": "requiredApprovals",
    "outputs": [{ "internalType": "uint256", "name": "", "type": "uint256" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [{ "internalType": "uint256", "name": "memoId", "type": "uint256" }],
    "name": "requiresApproval",
    "outputs": [{ "internalType": "bool", "name": "", "type": "bool" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "bytes32", "name": "role", "type": "bytes32" },
      { "internalType": "address", "name": "account", "type": "address" }
    ],
    "name": "revokeRole",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "enum ACPTypes.MemoType",
        "name": "memoType",
        "type": "uint8"
      },
      { "internalType": "uint256", "name": "requiredApprovals_", "type": "uint256" }
    ],
    "name": "setApprovalRequirements",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "address", "name": "assetManager_", "type": "address" }
    ],
    "name": "setAssetManager",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "memoId", "type": "uint256" },
      { "internalType": "address", "name": "sender", "type": "address" },
      { "internalType": "bool", "name": "isApproved", "type": "bool" },
      { "internalType": "string", "name": "reason", "type": "string" }
    ],
    "name": "signMemo",
    "outputs": [{ "internalType": "uint256", "name": "jobId", "type": "uint256" }],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [{ "internalType": "bytes4", "name": "interfaceId", "type": "bytes4" }],
    "name": "supportsInterface",
    "outputs": [{ "internalType": "bool", "name": "", "type": "bool" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "address", "name": "acpContract_", "type": "address" },
      { "internalType": "address", "name": "jobManager_", "type": "address" },
      { "internalType": "address", "name": "paymentManager_", "type": "address" },
      { "internalType": "address", "name": "assetManager_", "type": "address" }
    ],
    "name": "updateContracts",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "memoId", "type": "uint256" },
      { "internalType": "string", "name": "newContent", "type": "string" }
    ],
    "name": "updateMemoContent",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "memoId", "type": "uint256" },
      {
        "internalType": "enum ACPTypes.MemoState",
        "name": "newMemoState",
        "type": "uint8"
      }
    ],
    "name": "updateMemoState",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "address", "name": "newImplementation", "type": "address" },
      { "internalType": "bytes", "name": "data", "type": "bytes" }
    ],
    "name": "upgradeToAndCall",
    "outputs": [],
    "stateMutability": "payable",
    "type": "function"
  },
  {
    "inputs": [{ "internalType": "uint256", "name": "memoId", "type": "uint256" }],
    "name": "withdrawEscrowedFunds",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  }
];