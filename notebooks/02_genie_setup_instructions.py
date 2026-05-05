# Databricks notebook source
# MAGIC %md
# MAGIC # Xome Genie Space Setup
# MAGIC
# MAGIC ## Setup Instructions
# MAGIC
# MAGIC 1. Navigate to **AI/BI Genie Spaces** in your Databricks workspace
# MAGIC 2. Click **Create Genie Space**
# MAGIC 3. Name it: `Xome Real Estate Analytics`
# MAGIC 4. Add the following tables:
# MAGIC    - `serverless_stable_14ey07_catalog.xome.users`
# MAGIC    - `serverless_stable_14ey07_catalog.xome.properties`
# MAGIC    - `serverless_stable_14ey07_catalog.xome.browsing_activity`
# MAGIC    - `serverless_stable_14ey07_catalog.xome.recommendations`
# MAGIC 5. Set the SQL Warehouse to: `1f01d0f9de5b5108`
# MAGIC 6. Add the sample queries below as **Instructions** in the Genie Space
# MAGIC 7. Copy the Genie Space ID from the URL and update `agent_server/config.py`
# MAGIC
# MAGIC ## Sample Queries
# MAGIC
# MAGIC Use the SQL below to test each query in the Genie Space. These also serve as reference queries for the Genie Space instructions.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Query 1: Most Active Users in the Last 30 Days
# MAGIC *"Show me the most active users in the last 30 days"*

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Most active users in the last 30 days
# MAGIC SELECT
# MAGIC     u.user_id,
# MAGIC     u.first_name,
# MAGIC     u.last_name,
# MAGIC     u.email,
# MAGIC     u.preferred_city,
# MAGIC     u.user_segment,
# MAGIC     COUNT(b.activity_id) AS total_activities,
# MAGIC     COUNT(DISTINCT b.property_id) AS unique_properties_viewed,
# MAGIC     SUM(CASE WHEN b.activity_type = 'save' THEN 1 ELSE 0 END) AS saves,
# MAGIC     SUM(CASE WHEN b.activity_type = 'bid' THEN 1 ELSE 0 END) AS bids,
# MAGIC     ROUND(AVG(b.session_duration_seconds), 0) AS avg_session_duration
# MAGIC FROM serverless_stable_14ey07_catalog.xome.users u
# MAGIC JOIN serverless_stable_14ey07_catalog.xome.browsing_activity b ON u.user_id = b.user_id
# MAGIC WHERE b.activity_timestamp >= CURRENT_DATE - INTERVAL 30 DAYS
# MAGIC GROUP BY u.user_id, u.first_name, u.last_name, u.email, u.preferred_city, u.user_segment
# MAGIC ORDER BY total_activities DESC
# MAGIC LIMIT 20

# COMMAND ----------

# MAGIC %md
# MAGIC ### Query 2: Average Property Prices by City and Type
# MAGIC *"What are the average property prices by city and property type?"*

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Average property prices by city and property type
# MAGIC SELECT
# MAGIC     city,
# MAGIC     property_type,
# MAGIC     COUNT(*) AS listing_count,
# MAGIC     ROUND(AVG(price), 0) AS avg_price,
# MAGIC     ROUND(MIN(price), 0) AS min_price,
# MAGIC     ROUND(MAX(price), 0) AS max_price,
# MAGIC     ROUND(AVG(sqft), 0) AS avg_sqft,
# MAGIC     ROUND(AVG(price / sqft), 0) AS avg_price_per_sqft
# MAGIC FROM serverless_stable_14ey07_catalog.xome.properties
# MAGIC WHERE listing_status IN ('active', 'pending', 'auction')
# MAGIC GROUP BY city, property_type
# MAGIC ORDER BY city, avg_price DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ### Query 3: Upcoming Auctions in the Next 14 Days
# MAGIC *"Show me upcoming auctions in the next 14 days"*

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Upcoming auctions in the next 14 days
# MAGIC SELECT
# MAGIC     p.property_id,
# MAGIC     p.address,
# MAGIC     p.city,
# MAGIC     p.state,
# MAGIC     p.property_type,
# MAGIC     p.price AS market_price,
# MAGIC     p.auction_start_price,
# MAGIC     p.auction_date,
# MAGIC     ROUND((p.price - p.auction_start_price) / p.price * 100, 1) AS discount_pct,
# MAGIC     p.beds,
# MAGIC     p.baths,
# MAGIC     p.sqft,
# MAGIC     p.neighborhood,
# MAGIC     COUNT(DISTINCT b.user_id) AS interested_users
# MAGIC FROM serverless_stable_14ey07_catalog.xome.properties p
# MAGIC LEFT JOIN serverless_stable_14ey07_catalog.xome.browsing_activity b ON p.property_id = b.property_id
# MAGIC WHERE p.listing_status = 'auction'
# MAGIC   AND p.auction_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL 14 DAYS
# MAGIC GROUP BY p.property_id, p.address, p.city, p.state, p.property_type,
# MAGIC          p.price, p.auction_start_price, p.auction_date, p.beds, p.baths, p.sqft, p.neighborhood
# MAGIC ORDER BY p.auction_date ASC

# COMMAND ----------

# MAGIC %md
# MAGIC ### Query 4: Campaign Targeting — Lapsed High-Intent Users
# MAGIC *"Find users who saved or bid on properties but haven't been active in 7 days"*

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Users who saved or bid but haven't been active in 7 days (re-engagement targets)
# MAGIC SELECT
# MAGIC     u.user_id,
# MAGIC     u.first_name,
# MAGIC     u.last_name,
# MAGIC     u.email,
# MAGIC     u.preferred_city,
# MAGIC     u.user_segment,
# MAGIC     u.budget_min,
# MAGIC     u.budget_max,
# MAGIC     MAX(b.activity_timestamp) AS last_activity,
# MAGIC     DATEDIFF(CURRENT_DATE, MAX(b.activity_timestamp)) AS days_since_last_activity,
# MAGIC     SUM(CASE WHEN b.activity_type IN ('save', 'bid') THEN 1 ELSE 0 END) AS high_intent_actions
# MAGIC FROM serverless_stable_14ey07_catalog.xome.users u
# MAGIC JOIN serverless_stable_14ey07_catalog.xome.browsing_activity b ON u.user_id = b.user_id
# MAGIC WHERE u.is_active = true
# MAGIC GROUP BY u.user_id, u.first_name, u.last_name, u.email, u.preferred_city,
# MAGIC          u.user_segment, u.budget_min, u.budget_max
# MAGIC HAVING high_intent_actions > 0
# MAGIC   AND days_since_last_activity >= 7
# MAGIC ORDER BY high_intent_actions DESC, days_since_last_activity ASC
# MAGIC LIMIT 50

# COMMAND ----------

# MAGIC %md
# MAGIC ### Query 5: Recommendation Performance by City
# MAGIC *"How are our recommendations performing by city?"*

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Recommendation quality metrics by city
# MAGIC SELECT
# MAGIC     p.city,
# MAGIC     COUNT(*) AS total_recommendations,
# MAGIC     COUNT(DISTINCT r.user_id) AS unique_users,
# MAGIC     COUNT(DISTINCT r.property_id) AS unique_properties,
# MAGIC     ROUND(AVG(r.recommendation_score), 3) AS avg_score,
# MAGIC     ROUND(MIN(r.recommendation_score), 3) AS min_score,
# MAGIC     ROUND(MAX(r.recommendation_score), 3) AS max_score,
# MAGIC     SUM(CASE WHEN r.recommendation_score >= 0.7 THEN 1 ELSE 0 END) AS high_quality_recs,
# MAGIC     ROUND(SUM(CASE WHEN r.recommendation_score >= 0.7 THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS high_quality_pct
# MAGIC FROM serverless_stable_14ey07_catalog.xome.recommendations r
# MAGIC JOIN serverless_stable_14ey07_catalog.xome.properties p ON r.property_id = p.property_id
# MAGIC WHERE r.is_active = true
# MAGIC GROUP BY p.city
# MAGIC ORDER BY avg_score DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ### Query 6: Browsing-to-Bid Conversion Funnel by City
# MAGIC *"Show the browsing-to-bid conversion funnel by city"*

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Browsing-to-bid conversion funnel by city
# MAGIC SELECT
# MAGIC     p.city,
# MAGIC     COUNT(DISTINCT CASE WHEN b.activity_type = 'view' THEN b.user_id END) AS viewers,
# MAGIC     COUNT(DISTINCT CASE WHEN b.activity_type = 'save' THEN b.user_id END) AS savers,
# MAGIC     COUNT(DISTINCT CASE WHEN b.activity_type = 'share' THEN b.user_id END) AS sharers,
# MAGIC     COUNT(DISTINCT CASE WHEN b.activity_type = 'bid' THEN b.user_id END) AS bidders,
# MAGIC     ROUND(COUNT(DISTINCT CASE WHEN b.activity_type = 'save' THEN b.user_id END) /
# MAGIC           NULLIF(COUNT(DISTINCT CASE WHEN b.activity_type = 'view' THEN b.user_id END), 0) * 100, 1) AS view_to_save_pct,
# MAGIC     ROUND(COUNT(DISTINCT CASE WHEN b.activity_type = 'bid' THEN b.user_id END) /
# MAGIC           NULLIF(COUNT(DISTINCT CASE WHEN b.activity_type = 'view' THEN b.user_id END), 0) * 100, 1) AS view_to_bid_pct
# MAGIC FROM serverless_stable_14ey07_catalog.xome.browsing_activity b
# MAGIC JOIN serverless_stable_14ey07_catalog.xome.properties p ON b.property_id = p.property_id
# MAGIC GROUP BY p.city
# MAGIC ORDER BY bidders DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ### Query 7: Properties with Most User Interest
# MAGIC *"Which properties have the most user interest?"*

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Properties with the most user interest (heatmap data)
# MAGIC SELECT
# MAGIC     p.property_id,
# MAGIC     p.address,
# MAGIC     p.city,
# MAGIC     p.neighborhood,
# MAGIC     p.property_type,
# MAGIC     p.price,
# MAGIC     p.listing_status,
# MAGIC     COUNT(DISTINCT b.user_id) AS unique_interested_users,
# MAGIC     COUNT(b.activity_id) AS total_interactions,
# MAGIC     SUM(CASE WHEN b.activity_type = 'view' THEN 1 ELSE 0 END) AS views,
# MAGIC     SUM(CASE WHEN b.activity_type = 'save' THEN 1 ELSE 0 END) AS saves,
# MAGIC     SUM(CASE WHEN b.activity_type = 'bid' THEN 1 ELSE 0 END) AS bids,
# MAGIC     ROUND(AVG(b.session_duration_seconds), 0) AS avg_session_duration
# MAGIC FROM serverless_stable_14ey07_catalog.xome.properties p
# MAGIC JOIN serverless_stable_14ey07_catalog.xome.browsing_activity b ON p.property_id = b.property_id
# MAGIC GROUP BY p.property_id, p.address, p.city, p.neighborhood, p.property_type, p.price, p.listing_status
# MAGIC ORDER BY unique_interested_users DESC
# MAGIC LIMIT 25

# COMMAND ----------

# MAGIC %md
# MAGIC ### Query 8: User Segment Behavior Comparison
# MAGIC *"Compare behavior patterns across user segments"*

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Behavior patterns by user segment
# MAGIC SELECT
# MAGIC     u.user_segment,
# MAGIC     COUNT(DISTINCT u.user_id) AS total_users,
# MAGIC     COUNT(b.activity_id) AS total_activities,
# MAGIC     ROUND(COUNT(b.activity_id) / COUNT(DISTINCT u.user_id), 1) AS avg_activities_per_user,
# MAGIC     ROUND(AVG(b.session_duration_seconds), 0) AS avg_session_duration,
# MAGIC     SUM(CASE WHEN b.activity_type = 'view' THEN 1 ELSE 0 END) AS views,
# MAGIC     SUM(CASE WHEN b.activity_type = 'save' THEN 1 ELSE 0 END) AS saves,
# MAGIC     SUM(CASE WHEN b.activity_type = 'bid' THEN 1 ELSE 0 END) AS bids,
# MAGIC     ROUND(AVG(u.budget_max - u.budget_min), 0) AS avg_budget_range,
# MAGIC     ROUND(AVG(u.budget_max), 0) AS avg_budget_max
# MAGIC FROM serverless_stable_14ey07_catalog.xome.users u
# MAGIC LEFT JOIN serverless_stable_14ey07_catalog.xome.browsing_activity b ON u.user_id = b.user_id
# MAGIC GROUP BY u.user_segment
# MAGIC ORDER BY avg_activities_per_user DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ### Query 9: Device and Channel Engagement Analysis
# MAGIC *"What devices and channels drive the most engagement?"*

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Device type and referral source engagement analysis
# MAGIC SELECT
# MAGIC     b.device_type,
# MAGIC     b.referral_source,
# MAGIC     COUNT(*) AS total_activities,
# MAGIC     COUNT(DISTINCT b.user_id) AS unique_users,
# MAGIC     ROUND(AVG(b.session_duration_seconds), 0) AS avg_session_duration,
# MAGIC     SUM(CASE WHEN b.activity_type = 'view' THEN 1 ELSE 0 END) AS views,
# MAGIC     SUM(CASE WHEN b.activity_type = 'save' THEN 1 ELSE 0 END) AS saves,
# MAGIC     SUM(CASE WHEN b.activity_type = 'bid' THEN 1 ELSE 0 END) AS bids,
# MAGIC     ROUND(SUM(CASE WHEN b.activity_type = 'bid' THEN 1 ELSE 0 END) /
# MAGIC           NULLIF(SUM(CASE WHEN b.activity_type = 'view' THEN 1 ELSE 0 END), 0) * 100, 2) AS bid_conversion_rate
# MAGIC FROM serverless_stable_14ey07_catalog.xome.browsing_activity b
# MAGIC GROUP BY b.device_type, b.referral_source
# MAGIC ORDER BY total_activities DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ### Query 10: Auction vs Standard Listing Performance
# MAGIC *"Compare auction properties versus standard listings"*

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Auction vs standard listing comparison
# MAGIC SELECT
# MAGIC     p.listing_status,
# MAGIC     COUNT(DISTINCT p.property_id) AS property_count,
# MAGIC     ROUND(AVG(p.price), 0) AS avg_price,
# MAGIC     ROUND(AVG(p.sqft), 0) AS avg_sqft,
# MAGIC     ROUND(AVG(p.days_on_market), 0) AS avg_days_on_market,
# MAGIC     ROUND(AVG(p.school_rating), 1) AS avg_school_rating,
# MAGIC     COUNT(DISTINCT b.user_id) AS unique_interested_users,
# MAGIC     COUNT(b.activity_id) AS total_interactions,
# MAGIC     ROUND(COUNT(b.activity_id) / NULLIF(COUNT(DISTINCT p.property_id), 0), 1) AS interactions_per_property,
# MAGIC     SUM(CASE WHEN b.activity_type = 'bid' THEN 1 ELSE 0 END) AS total_bids
# MAGIC FROM serverless_stable_14ey07_catalog.xome.properties p
# MAGIC LEFT JOIN serverless_stable_14ey07_catalog.xome.browsing_activity b ON p.property_id = b.property_id
# MAGIC GROUP BY p.listing_status
# MAGIC ORDER BY property_count DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ## Post-Setup
# MAGIC
# MAGIC After creating the Genie Space:
# MAGIC 1. Copy the Space ID from the URL (e.g., `https://adb-xxx.azuredatabricks.net/genie/spaces/SPACE_ID`)
# MAGIC 2. Update `agent_server/config.py`:
# MAGIC    ```python
# MAGIC    GENIE_SPACE_ID = "your-space-id-here"
# MAGIC    ```
# MAGIC 3. Update `databricks.yml` with the Genie Space resource
# MAGIC 4. Redeploy: `databricks bundle deploy --profile azure11`
