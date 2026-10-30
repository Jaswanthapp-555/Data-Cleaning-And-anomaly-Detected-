"""Change history tracker for cleaning operations."""
from datetime import datetime


class ChangeHistory:
    def __init__(self):
        self._entries = []

    def record(self, action: str, description: str, column: str = None,
               row_index=None, original_value=None, new_value=None,
               method: str = None, extra: dict = None):
        entry = {
            "sequence": len(self._entries) + 1,
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "description": description,
            "column": column,
            "row_index": row_index,
            "original_value": _safe_val(original_value),
            "new_value": _safe_val(new_value),
            "method": method,
        }
        if extra:
            entry.update(extra)
        self._entries.append(entry)

    def to_list(self) -> list:
        return list(self._entries)

    def __len__(self):
        return len(self._entries)


def _safe_val(val):
    import pandas as pd
    import numpy as np
    if val is None:
        return None
    if isinstance(val, float) and np.isnan(val):
        return "NaN"
    if pd.isna(val):
        return "Missing"
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    return str(val)
