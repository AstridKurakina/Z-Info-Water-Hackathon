


# from pathlib import Path
# import duckdb
# import pandas as pd
# import matplotlib.pyplot as plt

# # ---------- Settings ----------
# ROOT = Path(__file__).resolve().parent.parent
# DB_PATH = ROOT / "tai.duckdb"
# OUT_DIR = ROOT / "outputs"            # keep this folder in .gitignore (derived from private data)
# OUT_DIR.mkdir(exist_ok=True)

# SENSORS = {
#     "15.HNPD11_AIR_0020.NO3": "NO3 nitrate",
#     "15.HNPE50_AIR_0001.NH4": "NH4 ammonium (verdeelwerk E50)",
#     "15.HNPD23_AIR_O2.O2":    "O2 oxygen (AT7)",
# }
# K = 3              # number of standard deviations
# ROLL_WINDOW = "90D"  # window for the rolling comparison
# MIN_PERIODS = 30

# if not DB_PATH.exists():
#     raise FileNotFoundError(f"Database not found at {DB_PATH}")

# # ---------- 1. Get the data ----------
# con = duckdb.connect(str(DB_PATH), read_only=True)
# placeholders = ",".join("?" for _ in SENSORS)

# raw = con.execute(f"""
#     SELECT point_id, observation_date, numeric_value
#     FROM sensor_data
#     WHERE point_id IN ({placeholders})
#       AND numeric_value IS NOT NULL
# """, list(SENSORS)).df()
# con.close()

# raw["observation_date"] = pd.to_datetime(raw["observation_date"])
# print("Raw rows per sensor:")
# print(raw.groupby("point_id").size(), "\n")

# # One value per sensor per day (average any duplicates)
# daily = (raw.groupby(["point_id", "observation_date"], as_index=False)
#             ["numeric_value"].mean())

# # ---------- 2. Detect anomalies ----------
# def detect(group: pd.DataFrame) -> pd.DataFrame:
#     g = group.sort_values("observation_date").copy()
#     v = g["numeric_value"]

#     # Method A: global mean and std over the whole history
#     g["mean_global"] = v.mean()
#     g["std_global"] = v.std()
#     g["z_global"] = (v - g["mean_global"]) / g["std_global"]
#     g["anom_global"] = g["z_global"].abs() > K

#     # Method B: rolling window using only PAST data (adapts to trends/seasonality)
#     s = g.set_index("observation_date")["numeric_value"]
#     roll = s.rolling(ROLL_WINDOW, min_periods=MIN_PERIODS, closed="left")
#     g["mean_roll"] = roll.mean().values
#     g["std_roll"] = roll.std().values
#     g["z_roll"] = (v.values - g["mean_roll"]) / g["std_roll"]
#     g["anom_roll"] = g["z_roll"].abs() > K
#     return g

# results = pd.concat([detect(g) for _, g in daily.groupby("point_id")],
#                     ignore_index=True)
# results["sensor"] = results["point_id"].map(SENSORS)

# # ---------- 3. Summary ----------
# summary = (results.groupby("sensor")
#            .agg(days=("numeric_value", "size"),
#                 first_day=("observation_date", "min"),
#                 last_day=("observation_date", "max"),
#                 mean=("numeric_value", "mean"),
#                 std=("numeric_value", "std"),
#                 min=("numeric_value", "min"),
#                 max=("numeric_value", "max"),
#                 anomalies_global=("anom_global", "sum"),
#                 anomalies_rolling=("anom_roll", "sum"))
#            .round(2))
# summary["pct_global"] = (100 * summary["anomalies_global"] / summary["days"]).round(2)
# print(summary.T, "\n")

# # Most extreme readings per sensor
# for name, g in results.groupby("sensor"):
#     top = (g[g["anom_global"]]
#            .assign(abs_z=lambda x: x["z_global"].abs())
#            .sort_values("abs_z", ascending=False)
#            .head(5)[["observation_date", "numeric_value", "z_global"]])
#     print(f"Top anomalies: {name}")
#     print(top.to_string(index=False), "\n")

# # Check for gaps in the data (missing days)
# for name, g in results.groupby("sensor"):
#     full = pd.date_range(g["observation_date"].min(), g["observation_date"].max())
#     print(f"{name}: {len(full) - len(g)} missing days")

# # ---------- 4. Save results ----------
# results.to_csv(OUT_DIR / "anomalies_3sensors.csv", index=False)

# # ---------- 5. Plots ----------
# fig, axes = plt.subplots(len(SENSORS), 1, figsize=(13, 3.6 * len(SENSORS)), sharex=True)
# for ax, (pid, name) in zip(axes, SENSORS.items()):
#     g = results[results["point_id"] == pid]
#     m, sd = g["mean_global"].iloc[0], g["std_global"].iloc[0]
#     ax.plot(g["observation_date"], g["numeric_value"], lw=0.7, label="value")
#     a = g[g["anom_global"]]
#     ax.scatter(a["observation_date"], a["numeric_value"], c="red", s=14, zorder=3,
#                label=f"anomaly (global, {len(a)})")
#     ax.axhline(m, c="gray", lw=0.8)
#     ax.axhline(m + K * sd, c="gray", ls="--", lw=0.8)
#     ax.axhline(m - K * sd, c="gray", ls="--", lw=0.8)
#     ax.set_title(f"{name}  [{pid}]  (mg/l)", fontsize=10)




# import os
# from pathlib import Path
# import pandas as pd
# import matplotlib
# matplotlib.use("Agg")  # Render headless to file (no display popup issues)
# import matplotlib.pyplot as plt

# # ---------- Settings & Paths ----------
# ROOT = Path(__file__).resolve().parent.parent
# OUT_DIR = ROOT / "outputs"
# CSV_PATH = OUT_DIR / "anomalies_3sensors.csv"
# K = 3

# if not CSV_PATH.exists():
#     raise FileNotFoundError(f"{CSV_PATH} not found. Run basic.py first.")

# df = pd.read_csv(CSV_PATH, parse_dates=["observation_date"])
# sensors = list(df["sensor"].dropna().unique())
# saved = []

# # ---------- 1. Overview: All sensors stacked, shared time axis ----------
# fig, axes = plt.subplots(len(sensors), 1, figsize=(14, 3.8 * len(sensors)), sharex=True)
# if len(sensors) == 1:
#     axes = [axes]

# for ax, name in zip(axes, sensors):
#     g = df[df["sensor"] == name].sort_values("observation_date")
#     m = g["mean_global"].iloc[0]
#     sd = g["std_global"].iloc[0]

#     ax.plot(g["observation_date"], g["numeric_value"], lw=0.7, color="tab:blue", label="Measured (mg/l)")
#     a = g[g["anom_global"]]
#     ax.scatter(a["observation_date"], a["numeric_value"], c="red", s=18, zorder=3, label=f"Anomaly ({len(a)})")
    
#     ax.axhline(m, c="gray", lw=0.8)
#     ax.axhline(m + K * sd, c="gray", ls="--", lw=0.8, label=f"Mean ± {K}σ")
#     ax.axhline(max(0, m - K * sd), c="gray", ls="--", lw=0.8)

#     ax.set_title(name, fontsize=11)
#     ax.set_ylabel("mg/l")
#     ax.legend(loc="upper right", fontsize=8)

# axes[-1].set_xlabel("Date")
# fig.suptitle("Global 3-Sigma Anomalies Across Sensors", fontsize=13)
# fig.tight_layout()

# p_overview = OUT_DIR / "plot_overview.png"
# fig.savefig(p_overview, dpi=150)
# plt.close(fig)
# saved.append(p_overview)

# # ---------- 2. Global vs Rolling Method (1 plot per sensor) ----------
# for name in sensors:
#     g = df[df["sensor"] == name].sort_values("observation_date")
#     fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True, sharey=True)
#     m = g["mean_global"].iloc[0]
#     sd = g["std_global"].iloc[0]

#     # Global
#     ax1.plot(g["observation_date"], g["numeric_value"], lw=0.7)
#     ax1.axhspan(max(0, m - K * sd), m + K * sd, color="gray", alpha=0.15)
#     a = g[g["anom_global"]]
#     ax1.scatter(a["observation_date"], a["numeric_value"], c="red", s=18, zorder=3)
#     ax1.set_title(f"{name}: Global Method ({len(a)} anomalies)")
#     ax1.set_ylabel("mg/l")

#     # Rolling
#     ax2.plot(g["observation_date"], g["numeric_value"], lw=0.7)
#     lower_roll = (g["mean_roll"] - K * g["std_roll"]).clip(lower=0)
#     upper_roll = g["mean_roll"] + K * g["std_roll"]
#     ax2.fill_between(g["observation_date"], lower_roll, upper_roll, color="orange", alpha=0.2, label=f"Rolling Mean ± {K}σ")
#     b = g[g["anom_roll"]]
#     ax2.scatter(b["observation_date"], b["numeric_value"], c="darkorange", s=18, zorder=3)
#     ax2.set_title(f"Rolling 90-Day Method ({len(b)} anomalies)")
#     ax2.set_ylabel("mg/l")
#     ax2.legend(loc="upper right", fontsize=8)
#     ax2.set_xlabel("Date")

#     fig.tight_layout()
#     safe_name = "".join(c if c.isalnum() else "_" for c in name)[:40]
#     p_sensor = OUT_DIR / f"plot_{safe_name}.png"
#     fig.savefig(p_sensor, dpi=150)
#     plt.close(fig)
#     saved.append(p_sensor)

# # ---------- 3. Timeline Strip Plot (Look for cross-sensor correlation) ----------
# fig, ax = plt.subplots(figsize=(14, 1.2 + 0.9 * len(sensors)))
# for i, name in enumerate(sensors):
#     a = df[(df["sensor"] == name) & (df["anom_global"])]
#     ax.scatter(a["observation_date"], [i] * len(a), marker="|", s=250, c="red")

# ax.set_yticks(range(len(sensors)))
# ax.set_yticklabels(sensors, fontsize=9)
# ax.set_ylim(-0.7, len(sensors) - 0.3)
# ax.grid(axis="x", alpha=0.3)
# ax.set_title("Days Flagged as Anomalous (Global 3-Sigma) — Vertical Alignment = Correlated Event")
# fig.tight_layout()

# p_timeline = OUT_DIR / "plot_timeline.png"
# fig.savefig(p_timeline, dpi=150)
# plt.close(fig)
# saved.append(p_timeline)

# # ---------- 4. Zoom-in: December 2022 Event ----------
# dec22 = df[(df["observation_date"] >= "2022-12-01") & (df["observation_date"] <= "2022-12-31")].copy()
# if not dec22.empty:
#     fig, axes = plt.subplots(len(sensors), 1, figsize=(14, 3 * len(sensors)), sharex=True)
#     if len(sensors) == 1:
#         axes = [axes]
#     for ax, name in zip(axes, sensors):
#         g = dec22[dec22["sensor"] == name].sort_values("observation_date")
#         ax.plot(g["observation_date"], g["numeric_value"], marker="o", markersize=4, lw=1)
#         a = g[g["anom_global"]]
#         ax.scatter(a["observation_date"], a["numeric_value"], c="red", s=30, zorder=3)
#         ax.set_title(f"{name} — December 2022", fontsize=10)
#         ax.set_ylabel("mg/l")
#         ax.grid(True, alpha=0.3)
#     axes[-1].set_xlabel("Date")
#     fig.suptitle("Zoomed Event Analysis: December 2022 Upset", fontsize=12)
#     fig.tight_layout()
#     p_dec = OUT_DIR / "plot_december_2022_zoom.png"
#     fig.savefig(p_dec, dpi=150)
#     plt.close(fig)
#     saved.append(p_dec)

# print("Saved plots:")
# for p in saved:
#     print(f" - {p}")

# if os.name == "nt":
#     os.startfile(saved[0])


# import sys
# from pathlib import Path
# import duckdb
# import pandas as pd

# # ==========================================
# # 1. CONFIGURE YOUR SENSORS HERE
# # ==========================================
# # You can provide either:
# #   - A dict: {"point_id": "Friendly Name"}
# #   - A list: ["point_id_1", "point_id_2"]  (names will be fetched from DB automatically)
# SENSORS_INPUT = {
#     "15.HNPD11_AIR_0020.NO3": "NO3 nitrate",
#     "15.HNPE50_AIR_0001.NH4": "NH4 ammonium (verdeelwerk E50)",
#     "15.HNPD23_AIR_O2.O2": "O2 oxygen (AT7)",
#     # Add new sensors here:
#     # "YOUR_NEW_POINT_ID": "Optional Display Name",
# }

# # Detection thresholds
# K = 3
# ROLL_WINDOW = "90D"
# MIN_PERIODS = 30

# # ==========================================
# # Paths & Setup
# # ==========================================
# ROOT = Path(__file__).resolve().parent.parent
# DB_PATH = ROOT / "tai.duckdb"
# OUT_DIR = ROOT / "outputs"
# OUT_DIR.mkdir(exist_ok=True)

# if not DB_PATH.exists():
#     raise FileNotFoundError(f"Database not found at {DB_PATH}")

# # Normalize input into a dictionary: {point_id: display_label}
# if isinstance(SENSORS_INPUT, list):
#     sensor_map = {pid: None for pid in SENSORS_INPUT}
# else:
#     sensor_map = dict(SENSORS_INPUT)

# # ==========================================
# # 2. Extract Data & Auto-resolve Names
# # ==========================================
# con = duckdb.connect(str(DB_PATH), read_only=True)
# point_ids = list(sensor_map.keys())
# placeholders = ",".join("?" for _ in point_ids)

# # Pull sensor data joining measurement points for fallback names
# raw = con.execute(
#     f"""
#     SELECT 
#         s.point_id, 
#         s.observation_date, 
#         s.numeric_value,
#         COALESCE(p.ParameterDescription, s.point_description, s.point_id) AS auto_name
#     FROM sensor_data s
#     LEFT JOIN measurement_points p ON p.MeasurementPointID = s.point_id
#     WHERE s.point_id IN ({placeholders})
#       AND s.numeric_value IS NOT NULL
#     """,
#     point_ids,
# ).df()
# con.close()

# if raw.empty:
#     print(f"Error: No data found for any of: {point_ids}")
#     sys.exit(1)

# # Fill in missing custom names using the database metadata
# db_names = raw.groupby("point_id")["auto_name"].first().to_dict()
# SENSORS = {pid: sensor_map[pid] if sensor_map[pid] else f"{pid} ({db_names.get(pid, pid)})" for pid in point_ids}

# raw["observation_date"] = pd.to_datetime(raw["observation_date"])

# print(f"Loaded {len(raw)} rows across {raw['point_id'].nunique()} sensor(s):")
# print(raw.groupby("point_id").size(), "\n")

# # Daily average to remove intra-day fluctuations
# daily = (
#     raw.groupby(["point_id", "observation_date"], as_index=False)["numeric_value"]
#     .mean()
# )

# # ==========================================
# # 3. Detect Anomalies
# # ==========================================
# def detect(group: pd.DataFrame) -> pd.DataFrame:
#     g = group.sort_values("observation_date").copy()
#     v = g["numeric_value"]

#     # Method A: Global Mean & Std
#     g["mean_global"] = v.mean()
#     g["std_global"] = v.std()
#     g["z_global"] = (v - g["mean_global"]) / g["std_global"]
#     g["anom_global"] = g["z_global"].abs() > K

#     # Method B: Rolling Window (Past data only)
#     s = g.set_index("observation_date")["numeric_value"]
#     roll = s.rolling(ROLL_WINDOW, min_periods=MIN_PERIODS, closed="left")
#     g["mean_roll"] = roll.mean().values
#     g["std_roll"] = roll.std().values
#     g["z_roll"] = (v.values - g["mean_roll"]) / g["std_roll"]
#     g["anom_roll"] = g["z_roll"].abs() > K

#     return g

# results = pd.concat([detect(g) for _, g in daily.groupby("point_id")], ignore_index=True)
# results["sensor"] = results["point_id"].map(SENSORS)

# # ==========================================
# # 4. Summary & Top Outliers
# # ==========================================
# summary = (
#     results.groupby("sensor")
#     .agg(
#         days=("numeric_value", "size"),
#         first_day=("observation_date", "min"),
#         last_day=("observation_date", "max"),
#         mean=("numeric_value", "mean"),
#         std=("numeric_value", "std"),
#         min=("numeric_value", "min"),
#         max=("numeric_value", "max"),
#         anomalies_global=("anom_global", "sum"),
#         anomalies_rolling=("anom_roll", "sum"),
#     )
# )
# summary["pct_global"] = (100 * summary["anomalies_global"] / summary["days"]).round(2)
# summary = summary.round({"mean": 2, "std": 2, "min": 2, "max": 2})

# print("--- SUMMARY ---")
# print(summary.T, "\n")

# # Save outputs (plots.py will automatically pick up any number of sensors)
# results.to_csv(OUT_DIR / "anomalies_3sensors.csv", index=False)
# print(f"Results saved to {OUT_DIR / 'anomalies_3sensors.csv'}")





# import os
# from pathlib import Path
# import duckdb
# import matplotlib.pyplot as plt
# import pandas as pd

# # 1. Configuration: Add or change sensors here
# ROOT = Path(__file__).resolve().parent.parent
# DB_PATH = ROOT / "tai.duckdb"
# OUT_DIR = ROOT / "outputs"
# OUT_DIR.mkdir(exist_ok=True)

# SENSORS = {
#     "15.HNPD11_AIR_0020.NO3": "NO3 nitrate",
#     "15.HNPE50_AIR_0001.NH4": "NH4 ammonium",
#     "15.HNPD23_AIR_O2.O2": "O2 oxygen",
# }

# # 2. Load and aggregate daily data
# con = duckdb.connect(str(DB_PATH), read_only=True)
# placeholders = ",".join("?" for _ in SENSORS)
# query = f"""
#     SELECT point_id, observation_date, numeric_value
#     FROM sensor_data
#     WHERE point_id IN ({placeholders}) AND numeric_value IS NOT NULL
# """
# df = con.execute(query, list(SENSORS.keys())).df()
# con.close()

# df["observation_date"] = pd.to_datetime(df["observation_date"])
# daily = (
#     df.groupby(["point_id", "observation_date"], as_index=False)["numeric_value"]
#     .mean()
# )

# # 3. Simple 3-Sigma Anomaly Detection per sensor
# results = []
# for pid, group in daily.groupby("point_id"):
#     g = group.sort_values("observation_date").copy()
#     mean = g["numeric_value"].mean()
#     std = g["numeric_value"].std()

#     g["mean"] = mean
#     g["std"] = std
#     g["is_anomaly"] = (g["numeric_value"] - mean).abs() > (3 * std)
#     results.append(g)

# data = pd.concat(results, ignore_index=True)

# # 4. Plot anomalies over time for all sensors
# fig, axes = plt.subplots(len(SENSORS), 1, figsize=(12, 3 * len(SENSORS)), sharex=True)
# if len(SENSORS) == 1:
#     axes = [axes]

# for ax, (pid, label) in zip(axes, SENSORS.items()):
#     sub = data[data["point_id"] == pid]
#     mean = sub["mean"].iloc[0]
#     std = sub["std"].iloc[0]

#     # Plot base measurements
#     ax.plot(sub["observation_date"], sub["numeric_value"], lw=0.8, label="Value")

#     # Plot anomalies
#     anomalies = sub[sub["is_anomaly"]]
#     ax.scatter(
#         anomalies["observation_date"],
#         anomalies["numeric_value"],
#         color="red",
#         s=15,
#         label=f"Anomaly ({len(anomalies)})",
#     )

#     # Plot mean and 3-sigma thresholds
#     ax.axhline(mean, color="black", lw=0.8, linestyle="-", label="Mean")
#     ax.axhline(mean + 3 * std, color="gray", lw=0.8, linestyle="--", label="Mean ± 3σ")
#     ax.axhline(mean - 3 * std, color="gray", lw=0.8, linestyle="--")

#     ax.set_title(f"{label} ({pid})")
#     ax.set_ylabel("mg/l")
#     ax.legend(loc="upper right")

# axes[-1].set_xlabel("Date")
# plt.tight_layout()

# # Save and display plot
# plot_path = OUT_DIR / "simple_anomalies.png"
# plt.savefig(plot_path, dpi=150)
# print(f"Plot saved to: {plot_path}")
# plt.show()

import os
from pathlib import Path
import duckdb
import matplotlib.pyplot as plt
import pandas as pd

# 1. Configuration: Add or change sensors here
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "tai.duckdb"
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(exist_ok=True)

SENSORS = {
    # "15.HNPD11_AIR_0020.NO3": "NO3 nitrate",
    # "15.HNPE50_AIR_0001.NH4": "NH4 ammonium",
    # "15.HNPD23_AIR_O2.O2": "O2 oxygen",
    "11.AMwlBI.mi-100.O2":"Dissolved oxygen	Online O2 nitrificatietank AT1",
    "11.AMwlBI.mi-104.NH4":"Ammonium Online NH4 nitrificatietank AT1",
    "11.AMwlBI.mi-106.NO3":"Nitrate	Online NO3 nitrificatie AT1",
    "11.AMwlBI.mi-110.PO4":"Phosphate Online PO4 nitrificatietank AT1",
    "11.AMwlBI.mi-102.OB":"Suspended solids	Online OB nitrificatietank AT1"

}

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

# 3. Simple 3-Sigma Anomaly Detection per sensor
results = []
for pid, group in daily.groupby("point_id"):
    g = group.sort_values("observation_date").copy()
    mean = g["numeric_value"].mean()
    std = g["numeric_value"].std()

    g["sensor_name"] = SENSORS[pid]
    g["mean"] = mean
    g["std"] = std
    g["lower_bound"] = (mean - 3 * std).round(2)
    g["upper_bound"] = (mean + 3 * std).round(2)
    g["is_anomaly"] = (g["numeric_value"] - mean).abs() > (3 * std)
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
        "normal_range": "Normal Range (Mean ± 3σ)"
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
print("\n--- Anomalies by Day (Aggregated per Date) ---")
print(daily_anomaly_table.head(20).to_string(index=False))

# Save both formats to CSV
anomaly_table.to_csv(OUT_DIR / "basic_anomaly_list.csv", index=False)
daily_anomaly_table.to_csv(OUT_DIR / "basic_anomaly_table_by_day.csv", index=False)
print(f"\nTables saved to:\n - {OUT_DIR / 'basic_anomaly_list.csv'}\n - {OUT_DIR / 'basic_anomaly_table_by_day.csv'}")

# 5. Plot anomalies over time for all sensors
fig, axes = plt.subplots(len(SENSORS), 1, figsize=(12, 3 * len(SENSORS)), sharex=True)
if len(SENSORS) == 1:
    axes = [axes]

for ax, (pid, label) in zip(axes, SENSORS.items()):
    sub = data[data["point_id"] == pid]
    mean = sub["mean"].iloc[0]
    std = sub["std"].iloc[0]

    ax.plot(sub["observation_date"], sub["numeric_value"], lw=0.8, label="Value")
    anomalies = sub[sub["is_anomaly"]]
    ax.scatter(
        anomalies["observation_date"],
        anomalies["numeric_value"],
        color="red",
        s=15,
        label=f"Anomaly ({len(anomalies)})",
    )

    ax.axhline(mean, color="black", lw=0.8, linestyle="-", label="Mean")
    ax.axhline(mean + 3 * std, color="gray", lw=0.8, linestyle="--", label="Mean ± 3σ")
    ax.axhline(mean - 3 * std, color="gray", lw=0.8, linestyle="--")

    ax.set_title(f"{label} ({pid})")
    ax.set_ylabel("mg/l")
    ax.legend(loc="upper right")

axes[-1].set_xlabel("Date")
plt.tight_layout()

plot_path = OUT_DIR / "basic_simple_anomalies.png"
plt.savefig(plot_path, dpi=150)
print(f"Plot saved to: {plot_path}")
#plt.show()

plot_path = OUT_DIR / "basic_simple_anomalies.png"
plt.savefig(plot_path, dpi=150)
print(f"Plot saved to: {plot_path}")

# Close the figure and do NOT call plt.show()
plt.close(fig)