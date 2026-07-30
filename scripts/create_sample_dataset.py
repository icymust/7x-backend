from pathlib import Path

import pandas as pd

rows = [
    ["DXB-001", "2026-08-01 09:00", 1020, 8, 4, 10],
    ["DXB-001", "2026-08-02 18:00", 980, 7, 5, 12],
    ["DXB-002", "2026-09-01 09:00", 1100, 9, 6, 15],
    ["DXB-002", "2026-09-02 18:00", 1050, 8, 5, 11],
]

columns = [
    "store_id",
    "time_bucket",
    "forecast_shipments",
    "available_permanent",
    "available_outsourced",
    "productivity_per_courier",
]

dataframe = pd.DataFrame(rows, columns=columns)
dataframe["time_bucket"] = pd.to_datetime(dataframe["time_bucket"])

Path("sample_data").mkdir(exist_ok=True)
dataframe.to_excel(
    "sample_data/sample_dataset.xlsx",
    index=False,
    sheet_name="capacity",
)
