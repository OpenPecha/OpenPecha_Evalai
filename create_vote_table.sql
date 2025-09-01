-- Create Vote table for 5-star rating system
-- Run this script to add the new voting functionality

-- Create the Vote table
CREATE TABLE IF NOT EXISTS vote (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR NOT NULL,
    model_version_id UUID NOT NULL,
    score INTEGER NOT NULL CHECK (score >= 1 AND score <= 5),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Foreign key constraint
    CONSTRAINT fk_vote_model_version FOREIGN KEY (model_version_id) REFERENCES model_version(id) ON DELETE CASCADE,
    
    -- Unique constraint: one vote per user per model
    CONSTRAINT unique_user_model_vote UNIQUE (user_id, model_version_id)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_vote_user_id ON vote(user_id);
CREATE INDEX IF NOT EXISTS idx_vote_model_version_id ON vote(model_version_id);
CREATE INDEX IF NOT EXISTS idx_vote_score ON vote(score);
CREATE INDEX IF NOT EXISTS idx_vote_created_at ON vote(created_at);

-- Insert some demo vote data (optional)
-- First ensure we have some model versions
INSERT INTO model_version (id, version, provider, created_at) VALUES
    (gen_random_uuid(), 'gpt-4o-mini', 'openai', NOW()),
    (gen_random_uuid(), 'claude-3-5-sonnet-20241022', 'anthropic', NOW()),
    (gen_random_uuid(), 'gemini-1.5-pro', 'google', NOW())
ON CONFLICT (version) DO NOTHING;

-- Add some demo votes with realistic score distribution
-- (Higher quality models get better average scores)
DO $$
DECLARE
    gpt_id UUID;
    claude_id UUID;
    gemini_id UUID;
    demo_users TEXT[] := ARRAY['user1', 'user2', 'user3', 'user4', 'user5', 'user6', 'user7', 'user8', 'user9', 'user10'];
    user_name TEXT;
BEGIN
    -- Get model IDs
    SELECT id INTO gpt_id FROM model_version WHERE version = 'gpt-4o-mini';
    SELECT id INTO claude_id FROM model_version WHERE version = 'claude-3-5-sonnet-20241022';
    SELECT id INTO gemini_id FROM model_version WHERE version = 'gemini-1.5-pro';
    
    -- Add votes for each model with realistic distributions
    FOREACH user_name IN ARRAY demo_users LOOP
        -- GPT-4o-mini gets mostly 4-5 star ratings (high quality)
        INSERT INTO vote (user_id, model_version_id, score) VALUES
            (user_name, gpt_id, CASE 
                WHEN random() < 0.6 THEN 5
                WHEN random() < 0.9 THEN 4
                ELSE 3
            END)
        ON CONFLICT (user_id, model_version_id) DO NOTHING;
        
        -- Claude gets mixed ratings (good but variable)
        INSERT INTO vote (user_id, model_version_id, score) VALUES
            (user_name, claude_id, CASE 
                WHEN random() < 0.4 THEN 5
                WHEN random() < 0.7 THEN 4
                WHEN random() < 0.9 THEN 3
                ELSE 2
            END)
        ON CONFLICT (user_id, model_version_id) DO NOTHING;
        
        -- Gemini gets lower ratings (needs improvement)
        INSERT INTO vote (user_id, model_version_id, score) VALUES
            (user_name, gemini_id, CASE 
                WHEN random() < 0.2 THEN 5
                WHEN random() < 0.4 THEN 4
                WHEN random() < 0.7 THEN 3
                WHEN random() < 0.9 THEN 2
                ELSE 1
            END)
        ON CONFLICT (user_id, model_version_id) DO NOTHING;
    END LOOP;
END $$;

-- Display summary statistics
SELECT 
    mv.version,
    mv.provider,
    COUNT(v.id) as total_votes,
    ROUND(AVG(v.score), 2) as average_score,
    ROUND((AVG(v.score) / 5.0) * 100, 1) as score_percentage,
    STRING_AGG(
        v.score || '★: ' || COUNT(*) OVER (PARTITION BY mv.id, v.score), 
        ', ' ORDER BY v.score DESC
    ) as score_breakdown
FROM model_version mv
LEFT JOIN vote v ON mv.id = v.model_version_id
GROUP BY mv.id, mv.version, mv.provider
ORDER BY AVG(v.score) DESC NULLS LAST;
