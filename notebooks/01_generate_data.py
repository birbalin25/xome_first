# Databricks notebook source
# MAGIC %md
# MAGIC # Xome Synthetic Data Generation
# MAGIC
# MAGIC Generates 4 Delta tables in `serverless_stable_14ey07_catalog.xome`:
# MAGIC - `users` (500 rows)
# MAGIC - `properties` (1,000 rows)
# MAGIC - `browsing_activity` (10,000 rows)
# MAGIC - `recommendations` (5,000 rows)

# COMMAND ----------

# MAGIC %pip install faker
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import random
import uuid
from datetime import datetime, timedelta

from faker import Faker
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    BooleanType,
    DateType,
    DoubleType,
    FloatType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

fake = Faker()
Faker.seed(42)
random.seed(42)

spark = SparkSession.builder.getOrCreate()

CATALOG = "serverless_stable_14ey07_catalog"
SCHEMA = "xome"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

# Catalog already exists on this workspace; only create the schema
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")

METROS = {
    "Austin": {"state": "TX", "base_price": 450000, "zip_prefix": "787"},
    "Boston": {"state": "MA", "base_price": 650000, "zip_prefix": "021"},
    "Chicago": {"state": "IL", "base_price": 350000, "zip_prefix": "606"},
    "Denver": {"state": "CO", "base_price": 550000, "zip_prefix": "802"},
    "Miami": {"state": "FL", "base_price": 500000, "zip_prefix": "331"},
    "Nashville": {"state": "TN", "base_price": 400000, "zip_prefix": "372"},
    "New York": {"state": "NY", "base_price": 850000, "zip_prefix": "100"},
    "Portland": {"state": "OR", "base_price": 500000, "zip_prefix": "972"},
    "San Francisco": {"state": "CA", "base_price": 1100000, "zip_prefix": "941"},
    "Seattle": {"state": "WA", "base_price": 700000, "zip_prefix": "981"},
}

NEIGHBORHOODS = {
    "Austin": ["Downtown Austin", "South Lamar", "East Austin", "Mueller", "Zilker"],
    "Boston": ["Back Bay", "South End", "Cambridge", "Beacon Hill", "Jamaica Plain"],
    "Chicago": ["Lincoln Park", "Wicker Park", "Lakeview", "Logan Square", "Hyde Park"],
    "Denver": ["LoDo", "Capitol Hill", "Cherry Creek", "RiNo", "Highlands"],
    "Miami": ["Brickell", "Wynwood", "Coral Gables", "Coconut Grove", "Miami Beach"],
    "Nashville": ["The Gulch", "East Nashville", "12 South", "Germantown", "Hillsboro Village"],
    "New York": ["Upper West Side", "Brooklyn Heights", "SoHo", "Astoria", "Park Slope"],
    "Portland": ["Pearl District", "Alberta Arts", "Hawthorne", "Division", "Sellwood"],
    "San Francisco": ["Pacific Heights", "Mission District", "SOMA", "Noe Valley", "Marina"],
    "Seattle": ["Capitol Hill", "Ballard", "Fremont", "Queen Anne", "West Seattle"],
}

PROPERTY_TYPES = ["Single Family", "Condo", "Townhouse", "Multi-Family"]
TYPE_MULTIPLIERS = {"Single Family": 1.0, "Condo": 0.65, "Townhouse": 0.8, "Multi-Family": 1.3}
USER_SEGMENTS = ["first_time_buyer", "investor", "upgrader", "downsizer"]

# Approximate city center coordinates
CITY_COORDS = {
    "Austin": (30.2672, -97.7431),
    "Boston": (42.3601, -71.0589),
    "Chicago": (41.8781, -87.6298),
    "Denver": (39.7392, -104.9903),
    "Miami": (25.7617, -80.1918),
    "Nashville": (36.1627, -86.7816),
    "New York": (40.7128, -74.0060),
    "Portland": (45.5152, -122.6784),
    "San Francisco": (37.7749, -122.4194),
    "Seattle": (47.6062, -122.3321),
}

# COMMAND ----------

# MAGIC %md
# MAGIC ## Generate Users (500 rows)

# COMMAND ----------

def generate_users(n=500):
    users = []
    cities = list(METROS.keys())

    for _ in range(n):
        city = random.choice(cities)
        metro = METROS[city]
        base_price = metro["base_price"]

        # Budget calibrated to city
        budget_min = int(base_price * random.uniform(0.6, 0.9))
        budget_max = int(base_price * random.uniform(1.1, 1.6))

        signup_date = fake.date_between(start_date="-2y", end_date="today")

        users.append({
            "user_id": str(uuid.uuid4()),
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": fake.email(),
            "phone": fake.phone_number(),
            "preferred_city": city,
            "preferred_state": metro["state"],
            "budget_min": budget_min,
            "budget_max": budget_max,
            "preferred_property_type": random.choice(PROPERTY_TYPES),
            "preferred_beds_min": random.randint(1, 4),
            "signup_date": signup_date,
            "is_active": random.random() < 0.9,
            "user_segment": random.choice(USER_SEGMENTS),
        })
    return users


users_data = generate_users(500)
print(f"Generated {len(users_data)} users")

users_schema = StructType([
    StructField("user_id", StringType(), False),
    StructField("first_name", StringType(), True),
    StructField("last_name", StringType(), True),
    StructField("email", StringType(), True),
    StructField("phone", StringType(), True),
    StructField("preferred_city", StringType(), True),
    StructField("preferred_state", StringType(), True),
    StructField("budget_min", IntegerType(), True),
    StructField("budget_max", IntegerType(), True),
    StructField("preferred_property_type", StringType(), True),
    StructField("preferred_beds_min", IntegerType(), True),
    StructField("signup_date", DateType(), True),
    StructField("is_active", BooleanType(), True),
    StructField("user_segment", StringType(), True),
])

users_df = spark.createDataFrame(users_data, schema=users_schema)
users_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.users")
print(f"Saved {CATALOG}.{SCHEMA}.users")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Generate Properties (1,000 rows)

# COMMAND ----------

def generate_description(prop_type, city, neighborhood, beds, baths, sqft, year_built):
    styles = [
        f"Beautiful {prop_type.lower()} in the heart of {neighborhood}, {city}.",
        f"Stunning {beds}-bedroom {prop_type.lower()} located in {neighborhood}.",
        f"Charming {prop_type.lower()} with {baths} bathrooms in desirable {neighborhood}.",
    ]
    features = [
        f"Features {sqft:,} sqft of living space",
        f"Built in {year_built}",
        f"Recently updated kitchen and bathrooms",
        f"Hardwood floors throughout",
        f"Open floor plan with natural light",
        f"Private backyard and patio",
        f"Close to restaurants and shops",
        f"Top-rated school district",
    ]
    desc = random.choice(styles) + " " + ". ".join(random.sample(features, random.randint(3, 5))) + "."
    return desc


def generate_properties(n=1000):
    properties = []
    cities = list(METROS.keys())
    listing_statuses = ["active"] * 50 + ["pending"] * 15 + ["auction"] * 25 + ["sold"] * 10
    now = datetime.now()

    for _ in range(n):
        city = random.choice(cities)
        metro = METROS[city]
        prop_type = random.choice(PROPERTY_TYPES)
        base_price = metro["base_price"]
        multiplier = TYPE_MULTIPLIERS[prop_type]

        price = int(base_price * multiplier * random.uniform(0.7, 1.5))
        beds = random.randint(1, 5) if prop_type != "Condo" else random.randint(1, 3)
        baths = round(beds * random.uniform(0.8, 1.5) * 2) / 2  # half-bath increments
        baths = max(1.0, baths)
        sqft = int(beds * random.randint(400, 700) + random.randint(200, 500))
        year_built = random.randint(1920, 2024)
        neighborhood = random.choice(NEIGHBORHOODS[city])
        listing_status = random.choice(listing_statuses)
        days_on_market = random.randint(1, 120)
        school_rating = round(random.uniform(1.0, 10.0), 1)

        # Auction-specific fields
        auction_date = None
        auction_start_price = None
        if listing_status == "auction":
            auction_date = (now + timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d")
            auction_start_price = int(price * random.uniform(0.70, 0.85))

        # HOA fee
        hoa_fee = 0
        if prop_type in ["Condo", "Townhouse"]:
            hoa_fee = random.choice([150, 200, 250, 300, 350, 400, 450, 500])
        elif random.random() < 0.2:
            hoa_fee = random.choice([50, 75, 100, 150])

        # Coordinates
        lat, lon = CITY_COORDS[city]
        lat += random.uniform(-0.1, 0.1)
        lon += random.uniform(-0.1, 0.1)

        zip_code = metro["zip_prefix"] + str(random.randint(10, 99))
        address = f"{random.randint(100, 9999)} {fake.street_name()}"

        description = generate_description(prop_type, city, neighborhood, beds, baths, sqft, year_built)

        properties.append({
            "property_id": str(uuid.uuid4()),
            "address": address,
            "city": city,
            "state": metro["state"],
            "zip_code": zip_code,
            "price": price,
            "beds": beds,
            "baths": baths,
            "sqft": sqft,
            "property_type": prop_type,
            "year_built": year_built,
            "school_rating": school_rating,
            "neighborhood": neighborhood,
            "listing_status": listing_status,
            "days_on_market": days_on_market,
            "auction_date": auction_date,
            "auction_start_price": auction_start_price,
            "hoa_fee": hoa_fee,
            "description": description,
            "image_url": f"https://images.xome.com/properties/{uuid.uuid4().hex[:8]}.jpg",
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
        })
    return properties


properties_data = generate_properties(1000)
print(f"Generated {len(properties_data)} properties")

properties_schema = StructType([
    StructField("property_id", StringType(), False),
    StructField("address", StringType(), True),
    StructField("city", StringType(), True),
    StructField("state", StringType(), True),
    StructField("zip_code", StringType(), True),
    StructField("price", IntegerType(), True),
    StructField("beds", IntegerType(), True),
    StructField("baths", FloatType(), True),
    StructField("sqft", IntegerType(), True),
    StructField("property_type", StringType(), True),
    StructField("year_built", IntegerType(), True),
    StructField("school_rating", FloatType(), True),
    StructField("neighborhood", StringType(), True),
    StructField("listing_status", StringType(), True),
    StructField("days_on_market", IntegerType(), True),
    StructField("auction_date", StringType(), True),
    StructField("auction_start_price", IntegerType(), True),
    StructField("hoa_fee", IntegerType(), True),
    StructField("description", StringType(), True),
    StructField("image_url", StringType(), True),
    StructField("latitude", DoubleType(), True),
    StructField("longitude", DoubleType(), True),
])

properties_df = spark.createDataFrame(properties_data, schema=properties_schema)
properties_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.properties")
print(f"Saved {CATALOG}.{SCHEMA}.properties")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Generate Browsing Activity (10,000 rows)

# COMMAND ----------

def generate_browsing_activity(users, properties, n=10000):
    activities = []
    activity_types = ["view"] * 50 + ["save"] * 20 + ["search"] * 15 + ["share"] * 10 + ["bid"] * 5
    device_types = ["mobile", "desktop", "tablet"]
    referral_sources = ["organic", "email", "social", "paid_ad"]
    now = datetime.now()

    # Build property lookup by city for realistic browsing
    props_by_city = {}
    for p in properties:
        city = p["city"]
        if city not in props_by_city:
            props_by_city[city] = []
        props_by_city[city].append(p)

    search_queries = [
        "homes under {price}k in {city}",
        "{beds} bedroom {type} in {neighborhood}",
        "auction properties in {city}",
        "{type} near good schools",
        "new listings in {neighborhood}",
        "homes with pool in {city}",
        "pet-friendly {type} in {city}",
        "open house this weekend {city}",
    ]

    for _ in range(n):
        user = random.choice(users)
        user_city = user["preferred_city"]

        # 70% chance they browse in their preferred city
        if random.random() < 0.7 and user_city in props_by_city:
            prop = random.choice(props_by_city[user_city])
        else:
            prop = random.choice(properties)

        activity_type = random.choice(activity_types)
        timestamp = now - timedelta(
            days=random.randint(0, 90),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )

        search_query = None
        if activity_type == "search":
            query_template = random.choice(search_queries)
            search_query = query_template.format(
                price=random.choice([300, 400, 500, 600, 700, 800]),
                city=prop["city"],
                beds=random.randint(2, 4),
                type=random.choice(PROPERTY_TYPES).lower(),
                neighborhood=prop["neighborhood"],
            )

        activities.append({
            "activity_id": str(uuid.uuid4()),
            "user_id": user["user_id"],
            "property_id": prop["property_id"],
            "activity_type": activity_type,
            "activity_timestamp": timestamp,
            "session_duration_seconds": random.randint(10, 600),
            "search_query": search_query,
            "device_type": random.choice(device_types),
            "referral_source": random.choice(referral_sources),
        })
    return activities


browsing_data = generate_browsing_activity(users_data, properties_data, 10000)
print(f"Generated {len(browsing_data)} browsing activities")

browsing_schema = StructType([
    StructField("activity_id", StringType(), False),
    StructField("user_id", StringType(), True),
    StructField("property_id", StringType(), True),
    StructField("activity_type", StringType(), True),
    StructField("activity_timestamp", TimestampType(), True),
    StructField("session_duration_seconds", IntegerType(), True),
    StructField("search_query", StringType(), True),
    StructField("device_type", StringType(), True),
    StructField("referral_source", StringType(), True),
])

browsing_df = spark.createDataFrame(browsing_data, schema=browsing_schema)
browsing_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.browsing_activity")
print(f"Saved {CATALOG}.{SCHEMA}.browsing_activity")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Generate Recommendations (5,000 rows)

# COMMAND ----------

def compute_recommendation_score(user, prop):
    """Compute a recommendation score based on budget/city/type/beds match."""
    score = 0.0

    # City match (strongest signal)
    if user["preferred_city"] == prop["city"]:
        score += 0.35
    elif user["preferred_state"] == prop["state"]:
        score += 0.15

    # Budget match
    price = prop["price"]
    if user["budget_min"] <= price <= user["budget_max"]:
        score += 0.30
    elif price < user["budget_min"]:
        score += 0.10
    elif price <= user["budget_max"] * 1.1:
        score += 0.15

    # Property type match
    if user["preferred_property_type"] == prop["property_type"]:
        score += 0.20

    # Beds match
    if prop["beds"] >= user["preferred_beds_min"]:
        score += 0.15
    elif prop["beds"] == user["preferred_beds_min"] - 1:
        score += 0.05

    # Small random factor
    score += random.uniform(-0.05, 0.05)
    return round(max(0.0, min(1.0, score)), 3)


def generate_recommendation_reason(user, prop, score):
    """Generate a template explanation for the recommendation."""
    reasons = []

    if user["preferred_city"] == prop["city"]:
        reasons.append(f"Located in your preferred city of {prop['city']}")
    if user["budget_min"] <= prop["price"] <= user["budget_max"]:
        reasons.append("Within your budget range")
    if user["preferred_property_type"] == prop["property_type"]:
        reasons.append(f"Matches your preferred property type ({prop['property_type']})")
    if prop["beds"] >= user["preferred_beds_min"]:
        reasons.append(f"Meets your minimum bedroom requirement ({prop['beds']} beds)")
    if prop["school_rating"] and float(prop["school_rating"]) >= 7.0:
        reasons.append(f"Excellent school rating ({prop['school_rating']}/10)")
    if prop["listing_status"] == "auction":
        reasons.append("Auction opportunity with potential below-market pricing")

    if not reasons:
        reasons.append("Strong overall match based on your preferences")

    return ". ".join(reasons) + "."


def generate_recommendations(users, properties, n=5000):
    recommendations = []
    now = datetime.now()

    # Only recommend active/pending/auction properties (not sold)
    active_properties = [p for p in properties if p["listing_status"] != "sold"]

    # Build property lookup by city
    props_by_city = {}
    for p in active_properties:
        city = p["city"]
        if city not in props_by_city:
            props_by_city[city] = []
        props_by_city[city].append(p)

    generated = 0
    attempts = 0
    seen_pairs = set()

    while generated < n and attempts < n * 5:
        attempts += 1
        user = random.choice(users)
        user_city = user["preferred_city"]

        # 60% chance recommend from preferred city, 40% from any city
        if random.random() < 0.6 and user_city in props_by_city:
            prop = random.choice(props_by_city[user_city])
        else:
            prop = random.choice(active_properties)

        # Avoid duplicate user-property pairs
        pair_key = (user["user_id"], prop["property_id"])
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        score = compute_recommendation_score(user, prop)
        reason = generate_recommendation_reason(user, prop, score)

        generated_at = now - timedelta(
            days=random.randint(0, 14),
            hours=random.randint(0, 23),
        )

        recommendations.append({
            "recommendation_id": str(uuid.uuid4()),
            "user_id": user["user_id"],
            "property_id": prop["property_id"],
            "recommendation_score": score,
            "recommendation_reason": reason,
            "model_version": "xome-rec-v1.0",
            "generated_at": generated_at,
            "is_active": True,
        })
        generated += 1

    return recommendations


recommendations_data = generate_recommendations(users_data, properties_data, 5000)
print(f"Generated {len(recommendations_data)} recommendations")

recommendations_schema = StructType([
    StructField("recommendation_id", StringType(), False),
    StructField("user_id", StringType(), True),
    StructField("property_id", StringType(), True),
    StructField("recommendation_score", FloatType(), True),
    StructField("recommendation_reason", StringType(), True),
    StructField("model_version", StringType(), True),
    StructField("generated_at", TimestampType(), True),
    StructField("is_active", BooleanType(), True),
])

recommendations_df = spark.createDataFrame(recommendations_data, schema=recommendations_schema)
recommendations_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.recommendations")
print(f"Saved {CATALOG}.{SCHEMA}.recommendations")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Data

# COMMAND ----------

for table in ["users", "properties", "browsing_activity", "recommendations"]:
    count = spark.table(f"{CATALOG}.{SCHEMA}.{table}").count()
    print(f"{CATALOG}.{SCHEMA}.{table}: {count} rows")

# COMMAND ----------

# Show sample data from each table
for table in ["users", "properties", "browsing_activity", "recommendations"]:
    print(f"\n--- {table} (sample) ---")
    display(spark.table(f"{CATALOG}.{SCHEMA}.{table}").limit(3))

# COMMAND ----------

# Verify FK integrity: all user_ids in browsing_activity exist in users
orphan_browsing = spark.sql(f"""
    SELECT COUNT(*) as orphan_count
    FROM {CATALOG}.{SCHEMA}.browsing_activity b
    LEFT JOIN {CATALOG}.{SCHEMA}.users u ON b.user_id = u.user_id
    WHERE u.user_id IS NULL
""")
display(orphan_browsing)

# Verify FK integrity: all property_ids in recommendations exist in properties
orphan_recs = spark.sql(f"""
    SELECT COUNT(*) as orphan_count
    FROM {CATALOG}.{SCHEMA}.recommendations r
    LEFT JOIN {CATALOG}.{SCHEMA}.properties p ON r.property_id = p.property_id
    WHERE p.property_id IS NULL
""")
display(orphan_recs)

print("Data generation complete!")
