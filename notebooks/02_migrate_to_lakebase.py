# Databricks notebook source
# MAGIC %md
# MAGIC # Migrate Delta Tables → Lakebase (PostgreSQL)
# MAGIC
# MAGIC One-time migration of the 5 Xome tables from Delta to the Lakebase instance `xome-campaign`.
# MAGIC
# MAGIC Tables: `users`, `properties`, `browsing_activity`, `recommendations`, `campaign_tracking`

# COMMAND ----------

# MAGIC %pip install psycopg2-binary
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import uuid

import psycopg2
import psycopg2.extras
from databricks.sdk import WorkspaceClient
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()
ws = WorkspaceClient()

# Source Delta tables
CATALOG = "serverless_stable_14ey07_catalog"
SCHEMA = "xome"

# Lakebase target
LAKEBASE_INSTANCE = "xome-campaign"
LAKEBASE_DNS = "ep-blue-shape-d2evoduc.database.us-east-1.cloud.databricks.com"
LAKEBASE_DB = "xome-campaign"
LAKEBASE_SCHEMA = "xome"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Connect to Lakebase

# COMMAND ----------

def get_lakebase_conn():
    """Get a psycopg2 connection to Lakebase using a database credential."""
    # Generate a Lakebase-specific credential via REST API
    resp = ws.api_client.do(
        "POST",
        "/api/2.0/database/credentials",
        body={"instance_names": [LAKEBASE_INSTANCE], "request_id": str(uuid.uuid4())},
    )
    token = resp["token"]
    me = ws.current_user.me()
    conn = psycopg2.connect(
        host=LAKEBASE_DNS,
        port=5432,
        dbname=LAKEBASE_DB,
        user=me.user_name,
        password=token,
        sslmode="require",
        options=f"-c search_path={LAKEBASE_SCHEMA}",
    )
    conn.autocommit = True
    return conn

conn = get_lakebase_conn()
print(f"Connected to Lakebase: {LAKEBASE_DNS}/{LAKEBASE_DB}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create Tables

# COMMAND ----------

DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        email TEXT,
        phone TEXT,
        preferred_city TEXT,
        preferred_state TEXT,
        budget_min INTEGER,
        budget_max INTEGER,
        preferred_property_type TEXT,
        preferred_beds_min INTEGER,
        signup_date DATE,
        is_active BOOLEAN,
        user_segment TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS properties (
        property_id TEXT PRIMARY KEY,
        address TEXT,
        city TEXT,
        state TEXT,
        zip_code TEXT,
        price INTEGER,
        beds INTEGER,
        baths REAL,
        sqft INTEGER,
        property_type TEXT,
        year_built INTEGER,
        school_rating REAL,
        neighborhood TEXT,
        listing_status TEXT,
        days_on_market INTEGER,
        auction_date TEXT,
        auction_start_price INTEGER,
        hoa_fee INTEGER,
        description TEXT,
        image_url TEXT,
        latitude DOUBLE PRECISION,
        longitude DOUBLE PRECISION
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS browsing_activity (
        activity_id TEXT PRIMARY KEY,
        user_id TEXT,
        property_id TEXT,
        activity_type TEXT,
        activity_timestamp TIMESTAMP,
        session_duration_seconds INTEGER,
        search_query TEXT,
        device_type TEXT,
        referral_source TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS recommendations (
        recommendation_id TEXT PRIMARY KEY,
        user_id TEXT,
        property_id TEXT,
        recommendation_score REAL,
        recommendation_reason TEXT,
        model_version TEXT,
        generated_at TIMESTAMP,
        is_active BOOLEAN
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS campaign_tracking (
        user_id TEXT,
        property_id TEXT,
        recommendation_id TEXT,
        campaign_date DATE,
        campaign_status BOOLEAN
    )
    """,
]

cur = conn.cursor()
for ddl in DDL_STATEMENTS:
    table_name = ddl.split("IF NOT EXISTS")[1].split("(")[0].strip()
    cur.execute(ddl)
    print(f"Created table: {table_name}")
cur.close()
print("All tables created.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Migrate Data

# COMMAND ----------

def migrate_table(table_name: str, conn):
    """Read a Delta table via Spark, convert to Pandas, bulk-insert into Lakebase."""
    fqn = f"{CATALOG}.{SCHEMA}.{table_name}"

    # Check if Delta table exists
    try:
        df = spark.table(fqn)
    except Exception as e:
        print(f"  Skipping {table_name}: {e}")
        return 0

    pdf = df.toPandas()
    if pdf.empty:
        print(f"  {table_name}: 0 rows (empty)")
        return 0

    # Truncate target before loading
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {table_name}")

    columns = list(pdf.columns)
    col_str = ", ".join(columns)
    template = "(" + ", ".join(["%s"] * len(columns)) + ")"

    # Convert DataFrame rows to list of tuples
    values = [tuple(None if str(v) == "NaT" or str(v) == "nan" else v for v in row) for row in pdf.itertuples(index=False, name=None)]

    psycopg2.extras.execute_values(
        cur,
        f"INSERT INTO {table_name} ({col_str}) VALUES %s",
        values,
        template=template,
        page_size=500,
    )

    cur.close()
    print(f"  {table_name}: {len(values)} rows inserted")
    return len(values)


tables = ["users", "properties", "browsing_activity", "recommendations", "campaign_tracking"]
total = 0
for t in tables:
    print(f"Migrating {t}...")
    total += migrate_table(t, conn)

print(f"\nTotal rows migrated: {total}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create Indexes

# COMMAND ----------

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)",
    "CREATE INDEX IF NOT EXISTS idx_users_preferred_city ON users(preferred_city)",
    "CREATE INDEX IF NOT EXISTS idx_properties_city_state ON properties(city, state)",
    "CREATE INDEX IF NOT EXISTS idx_rec_user_active ON recommendations(user_id, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_rec_score ON recommendations(recommendation_score DESC)",
    "CREATE INDEX IF NOT EXISTS idx_browsing_user_ts ON browsing_activity(user_id, activity_timestamp DESC)",
    "CREATE INDEX IF NOT EXISTS idx_ct_user_prop ON campaign_tracking(user_id, property_id)",
]

cur = conn.cursor()
for idx_sql in INDEXES:
    idx_name = idx_sql.split("IF NOT EXISTS")[1].split("ON")[0].strip()
    cur.execute(idx_sql)
    print(f"Created index: {idx_name}")
cur.close()
print("All indexes created.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Row Counts

# COMMAND ----------

cur = conn.cursor()
print("Row count verification:")
print("-" * 40)
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    count = cur.fetchone()[0]
    delta_count = spark.table(f"{CATALOG}.{SCHEMA}.{t}").count() if t != "campaign_tracking" else "N/A"
    print(f"  {t:25s} Lakebase={count:>6}  Delta={delta_count}")
cur.close()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Quick Smoke Test

# COMMAND ----------

cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

cur.execute("SELECT user_id, first_name, last_name, preferred_city FROM users WHERE is_active = true LIMIT 3")
print("Sample active users:")
for row in cur.fetchall():
    print(f"  {row['user_id'][:8]}... {row['first_name']} {row['last_name']} ({row['preferred_city']})")

cur.execute("SELECT city, COUNT(*) as cnt FROM properties GROUP BY city ORDER BY cnt DESC LIMIT 5")
print("\nTop 5 cities by property count:")
for row in cur.fetchall():
    print(f"  {row['city']}: {row['cnt']}")

cur.close()
conn.close()
print("\nMigration complete! Lakebase is ready.")
