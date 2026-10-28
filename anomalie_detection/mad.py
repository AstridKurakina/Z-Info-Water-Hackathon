import os
from pathlib import Path
import duckdb
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

# Standard MAD threshold (3 * 1.4826 corresponds to 3 standard deviations for normal distribution)
THRESHOLD_K = 3.0
CONSISTENCY_CONSTANT = 1.4826

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

# 3. Robust Median Absolute Deviation (MAD) Anomaly Detection per sensor
results = []
for pid, group in daily.groupby("point_id"):
    g = group.sort_values("observation_date").copy()
    
    med = g["numeric_value"].median()
    abs_deviation = (g["numeric_value"] - med).abs()
    mad = abs_deviation.median()

    # Guard against flatlines / zero-MAD edge cases
    scale = CONSISTENCY_CONSTANT * mad if mad > 1e-6 else 1e-6

    g["sensor_name"] = SENSORS[pid]
    g["median"] = med
    g["mad"] = mad
    g["modified_z"] = abs_deviation / scale
    g["lower_bound"] = (med - THRESHOLD_K * scale).round(2)
    g["upper_bound"] = (med + THRESHOLD_K * scale).round(2)
    g["is_anomaly"] = g["modified_z"] > THRESHOLD_K
    results.append(g)

data = pd.concat(results, ignore_index=True)

# 4. Generate Anomaly Table (grouped by day, showing value & normal range)
anomalies_df = data[data["is_anomaly"]].copy()
anomalies_df["observation_date"] = anomalies_df["observation_date"].dt.strftime("%Y-%m-%d")
anomalies_df["numeric_value"] = anomalies_df["numeric_value"].round(2)
anomalies_df["normal_range"] = (
    "[" + anomalies_df["lower_bound"].astype(str) + " to " + anomalies_df["upper_bound"].astype(str) + "]"
)

# Table 1: Flat list ordered by day
anomaly_table = anomalies_df[[
    "observation_date", 
    "sensor_name", 
    "numeric_value", 
    "normal_range"
]].sort_values(by=["observation_date", "sensor_name"]).rename(
    columns={
        "observation_date": "Date",
        "sensor_name": "Sensor",
        "numeric_value": "Abnormal Value",
        "normal_range": "Normal Range (Median ± 3·MAD)"
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
    anomalies_df.groupby("observation_date")["detail"]
    .apply(lambda x: " | ".join(x))
    .reset_index()
    .rename(columns={"observation_date": "Date", "detail": "Anomalies Detected"})
    .sort_values(by="Date")
)

# Print and save the tables
pd.set_option("display.max_rows", 50, "display.max_colwidth", None, "display.width", 1000)
print("\n--- Anomalies by Day (Aggregated per Date - MAD Method) ---")
print(daily_anomaly_table.head(20).to_string(index=False))

# Save both formats to CSV
anomaly_table.to_csv(OUT_DIR / "mad_anomaly_list.csv", index=False)
daily_anomaly_table.to_csv(OUT_DIR / "mad_anomaly_table_by_day.csv", index=False)
print(f"\nTables saved to:\n - {OUT_DIR / 'mad_anomaly_list.csv'}\n - {OUT_DIR / 'mad_anomaly_table_by_day.csv'}")

# 5. Plot anomalies over time for all sensors
fig, axes = plt.subplots(len(SENSORS), 1, figsize=(12, 3 * len(SENSORS)), sharex=True)
if len(SENSORS) == 1:
    axes = [axes]

for ax, (pid, label) in zip(axes, SENSORS.items()):
    sub = data[data["point_id"] == pid]
    med = sub["median"].iloc[0]
    lower = sub["lower_bound"].iloc[0]
    upper = sub["upper_bound"].iloc[0]

    ax.plot(sub["observation_date"], sub["numeric_value"], lw=0.8, label="Value")
    anomalies = sub[sub["is_anomaly"]]
    ax.scatter(
        anomalies["observation_date"],
        anomalies["numeric_value"],
        color="red",
        s=15,
        label=f"Anomaly ({len(anomalies)})",
    )

    ax.axhline(med, color="black", lw=0.8, linestyle="-", label="Median")
    ax.axhline(upper, color="gray", lw=0.8, linestyle="--", label="Median ± 3·MAD")
    ax.axhline(lower, color="gray", lw=0.8, linestyle="--")

    ax.set_title(f"{label} ({pid})")
    ax.set_ylabel("mg/l")
    ax.legend(loc="upper right")

axes[-1].set_xlabel("Date")
plt.tight_layout()

plot_path = OUT_DIR / "mad_simple_anomalies.png"
fig.savefig(plot_path, dpi=150)
print(f"Plot saved to: {plot_path}")

plt.close(fig)