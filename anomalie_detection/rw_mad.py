import os
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")  # Prevents display popups and renders directly to file
import matplotlib.pyplot as plt

# 1. Configuration: Add or change sensors here
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "tai.duckdb"
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(exist_ok=True)

SENSORS = {
    # "15.HNPD11_AIR_0020.NO3": "NO3 nitrate",
    # "15.HNPE50_AIR_0001.NH4": "NH4 ammonium",
    # "15.HNPD23_AIR_O2.O2": "O2 oxygen",
    "11.AMwlBI.mi-100.O2": "Dissolved oxygen Online O2 nitrificatietank AT1",
    "11.AMwlBI.mi-104.NH4": "Ammonium Online NH4 nitrificatietank AT1",
    "11.AMwlBI.mi-106.NO3": "Nitrate Online NO3 nitrificatie AT1",
    "11.AMwlBI.mi-110.PO4": "Phosphate Online PO4 nitrificatietank AT1",
    "11.AMwlBI.mi-102.OB": "Suspended solids Online OB nitrificatietank AT1",
}

# Rolling MAD Configuration
ROLL_WINDOW = "90D"    # Rolling lookback window
MIN_PERIODS = 5       # Minimum valid days in window to compute baseline
THRESHOLD_K = 3.0      # Number of robust deviations
CONSISTENCY_CONSTANT = 1.4826  # Normal consistency factor for MAD

# 2. Load and aggregate daily data
con = duckdb.connect(str(DB_PATH), read_only=True)
placeholders = ",".join("?" for _ in SENSORS)
query = f"""
    SELECT point_id, observation_date, numeric_value
    FROM sensor_data
    WHERE point_id IN ({placeholders}) AND numeric_value IS NOT NULL
"""
df = con.execute(query, list(SENSORS.keys())).df()
con.close()

df["observation_date"] = pd.to_datetime(df["observation_date"])
daily = (
    df.groupby(["point_id", "observation_date"], as_index=False)["numeric_value"]
    .mean()
)

# 3. Rolling Window MAD Calculation per sensor (Past Data Only via closed="left")
def calc_rolling_mad(group: pd.DataFrame) -> pd.DataFrame:
    g = group.sort_values("observation_date").copy()
    s = g.set_index("observation_date")["numeric_value"]

    # Rolling median of past window
    roll_median = s.rolling(ROLL_WINDOW, min_periods=MIN_PERIODS, closed="left").median()

    # Function to compute MAD over past window
    def get_window_mad(window_vals):
        med = np.median(window_vals)
        return np.median(np.abs(window_vals - med))

    roll_mad = s.rolling(ROLL_WINDOW, min_periods=MIN_PERIODS, closed="left").apply(
        get_window_mad, raw=True
    )

    g["sensor_name"] = SENSORS[g["point_id"].iloc[0]]
    g["roll_median"] = roll_median.values
    g["roll_mad"] = roll_mad.values

    # Scale MAD to approximate standard deviation
    scale = (CONSISTENCY_CONSTANT * g["roll_mad"]).clip(lower=1e-6)

    # Dynamic bounds and anomaly condition
    g["lower_bound"] = (g["roll_median"] - THRESHOLD_K * scale).round(2)
    g["upper_bound"] = (g["roll_median"] + THRESHOLD_K * scale).round(2)
    g["modified_z"] = (g["numeric_value"] - g["roll_median"]).abs() / scale
    
    # Flag anomaly if beyond threshold (ignoring early warm-up period where baseline is NaN)
    g["is_anomaly"] = (g["modified_z"] > THRESHOLD_K) & g["roll_median"].notna()
    return g

data = pd.concat([calc_rolling_mad(g) for _, g in daily.groupby("point_id")], ignore_index=True)

# 4. Generate Anomaly Table (grouped by day, showing value & normal range)
anomalies_df = data[data["is_anomaly"]].copy()
anomalies_df["observation_date_str"] = anomalies_df["observation_date"].dt.strftime("%Y-%m-%d")
anomalies_df["numeric_value"] = anomalies_df["numeric_value"].round(2)
anomalies_df["normal_range"] = (
    "[" + anomalies_df["lower_bound"].astype(str) + " to " + anomalies_df["upper_bound"].astype(str) + "]"
)

# Table 1: Flat list ordered by day
anomaly_table = anomalies_df[[
    "observation_date_str", 
    "sensor_name", 
    "numeric_value", 
    "normal_range"
]].sort_values(by=["observation_date_str", "sensor_name"]).rename(
    columns={
        "observation_date_str": "Date",
        "sensor_name": "Sensor",
        "numeric_value": "Abnormal Value",
        "normal_range": "Rolling Range (Median ± 3·MAD)"
    }
)

# Table 2: One row per day (aggregating multiple sensor anomalies onto the same day)
anomalies_df["detail"] = (
    anomalies_df["sensor_name"] 
    + ": " 
    + anomalies_df["numeric_value"].astype(str) 
    + " (Normal: " 
    + anomalies_df["normal_range"] 
    + ")"
)

daily_anomaly_table = (
    anomalies_df.groupby("observation_date_str")["detail"]
    .apply(lambda x: " | ".join(x))
    .reset_index()
    .rename(columns={"observation_date_str": "Date", "detail": "Anomalies Detected"})
    .sort_values(by="Date")
)

# Print and save the tables
pd.set_option("display.max_rows", 50, "display.max_colwidth", None, "display.width", 1000)
print("\n--- Anomalies by Day (Aggregated per Date - Rolling MAD Method) ---")
print(daily_anomaly_table.head(20).to_string(index=False))

# Save both formats to CSV
anomaly_table.to_csv(OUT_DIR / "rolling_mad_anomaly_list.csv", index=False)
daily_anomaly_table.to_csv(OUT_DIR / "rolling_mad_anomaly_table_by_day.csv", index=False)
print(f"\nTables saved to:\n - {OUT_DIR / 'rolling_mad_anomaly_list.csv'}\n - {OUT_DIR / 'rolling_mad_anomaly_table_by_day.csv'}")

# 5. Plot dynamic rolling envelopes and anomalies over time for all sensors
fig, axes = plt.subplots(len(SENSORS), 1, figsize=(12, 3.2 * len(SENSORS)), sharex=True)
if len(SENSORS) == 1:
    axes = [axes]

for ax, (pid, label) in zip(axes, SENSORS.items()):
    sub = data[data["point_id"] == pid].sort_values("observation_date")

    # Plot base measurements
    ax.plot(sub["observation_date"], sub["numeric_value"], lw=0.7, color="tab:blue", label="Value")

    # Dynamic rolling median line
    ax.plot(sub["observation_date"], sub["roll_median"], lw=0.9, color="black", label=f"Rolling Median ({ROLL_WINDOW})")

    # Dynamic rolling envelope (shaded band)
    ax.fill_between(
        sub["observation_date"],
        sub["lower_bound"],
        sub["upper_bound"],
        color="orange",
        alpha=0.25,
        label=f"Rolling Median ± {THRESHOLD_K}·MAD"
    )

    # Plot flagged anomalies
    anomalies = sub[sub["is_anomaly"]]
    ax.scatter(
        anomalies["observation_date"],
        anomalies["numeric_value"],
        color="red",
        s=16,
        zorder=4,
        label=f"Anomaly ({len(anomalies)})",
    )

    ax.set_title(f"{label} ({pid})", fontsize=10)
    ax.set_ylabel("mg/l")
    ax.legend(loc="upper right", fontsize=8)

axes[-1].set_xlabel("Date")
plt.tight_layout()

plot_path = OUT_DIR / "rolling_mad_anomalies.png"
fig.savefig(plot_path, dpi=150)
print(f"Plot saved to: {plot_path}")

plt.close(fig)