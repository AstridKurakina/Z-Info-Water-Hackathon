from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parent.parent   # repo root
DB_PATH = ROOT / "tai.duckdb"

if not DB_PATH.exists():
    raise FileNotFoundError(f"Database not found at {DB_PATH}")

con = duckdb.connect(str(DB_PATH), read_only=True)

tables = con.execute("SHOW TABLES").df()
print(tables)

# Describe every table and show a few rows, so you don't need to guess names
for name in tables["name"]:
    print(f"\n=== {name} ===")
    print(con.execute(f"DESCRIBE {name}").df())
    print(con.execute(f"SELECT * FROM {name} LIMIT 5").df())




from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parent.parent
con = duckdb.connect(str(ROOT / "tai.duckdb"), read_only=True)

# Overall size and missing values
print(con.execute("""
    SELECT COUNT(*) AS rows,
           COUNT(DISTINCT point_id) AS points,
           MIN(observation_date) AS first_day,
           MAX(observation_date) AS last_day,
           SUM((numeric_value IS NULL)::INT) AS null_values
    FROM sensor_data
""").df())

# Duplicate readings (same point and day appearing more than once)
print(con.execute("""
    SELECT COUNT(*) AS duplicated_point_days FROM (
        SELECT point_id, observation_date
        FROM sensor_data
        GROUP BY 1, 2 HAVING COUNT(*) > 1)
""").df())

# How long are the series?
print(con.execute("""
    SELECT COUNT(*) AS n_obs FROM sensor_data
    WHERE numeric_value IS NOT NULL
    GROUP BY point_id
""").df().describe())