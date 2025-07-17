def get_tx_hash_from_alchemy_response(response: dict) -> str:
    return response.get('receipts', [])[0].get('transactionHash')

def get_logs_from_alchemy_response(response: dict) -> list:
    return response.get("receipts", [])[0].get("logs", [])
