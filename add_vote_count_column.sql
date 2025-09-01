-- Add vote_count column to model_version table
-- Run this script to fix the database schema

ALTER TABLE model_version 
ADD COLUMN IF NOT EXISTS vote_count INTEGER NOT NULL DEFAULT 0;

-- Create index for better performance on ordering by vote_count
CREATE INDEX IF NOT EXISTS idx_model_version_vote_count 
ON model_version(vote_count);

-- Insert some demo model versions if they don't exist
INSERT INTO model_version (version, provider, vote_count) VALUES
    ('gpt-4o-mini', 'openai', 5),
    ('gpt-4o', 'openai', 8),
    ('claude-3-5-sonnet-latest', 'anthropic', 12),
    ('claude-3-5-haiku-latest', 'anthropic', 3),
    ('gemini-1.5-pro', 'google', 7),
    ('gemini-1.5-flash', 'google', 2)
ON CONFLICT (version) DO NOTHING;

-- Show current state
SELECT version, provider, vote_count 
FROM model_version 
ORDER BY vote_count DESC;
