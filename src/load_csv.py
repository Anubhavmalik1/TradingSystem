import pandas as pd
import os
# -------------------------
# Load Contracts CSV
# -------------------------
contracts = pd.read_csv("./data/contracts.csv", low_memory=False)
desc_to_id = dict(zip(contracts["Description"], contracts["exchangeInstrumentID"]))

# -------------------------
# get_exchange_instrument_id() function : return id respective of NAME/DESCRIPTION
# -------------------------
def get_exchange_instrument_id(description: str) -> str:
    """
    Return the exchangeInstrumentID for a given Description.
    If not found, returns 'NOT FOUND'.
    """
    return desc_to_id.get(description, "NOT FOUND")