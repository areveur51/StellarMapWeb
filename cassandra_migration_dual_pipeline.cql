-- Cassandra Migration: Add Dual-Pipeline Tracking Fields
-- These columns are needed to track which pipeline (BigQuery vs API) processed each account
-- and when processing attempts occurred.

-- Add pipeline_source column to track which pipeline processed the record
ALTER TABLE stellarmapweb_keyspace.stellar_creator_account_lineage 
ADD pipeline_source text;

-- Add last_pipeline_attempt to track the last time either pipeline attempted processing
ALTER TABLE stellarmapweb_keyspace.stellar_creator_account_lineage 
ADD last_pipeline_attempt timestamp;

-- Add processing_started_at to track when current processing started (for stuck detection)
ALTER TABLE stellarmapweb_keyspace.stellar_creator_account_lineage 
ADD processing_started_at timestamp;

-- Verify the schema was updated correctly
DESCRIBE TABLE stellarmapweb_keyspace.stellar_creator_account_lineage;
