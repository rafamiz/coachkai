CREATE TABLE daily_summaries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    total_calories  INT DEFAULT 0,
    total_protein_g NUMERIC(6,1) DEFAULT 0,
    total_carbs_g   NUMERIC(6,1) DEFAULT 0,
    total_fat_g     NUMERIC(6,1) DEFAULT 0,
    total_fiber_g   NUMERIC(6,1) DEFAULT 0,
    total_water_ml  INT DEFAULT 0,
    meal_count      INT DEFAULT 0,
    exercise_min    INT DEFAULT 0,
    exercise_cal    INT DEFAULT 0,
    avg_goal_score  NUMERIC(3,1),
    calorie_target  INT,
    adherence_pct   NUMERIC(5,1),
    streak_days     INT DEFAULT 0,
    fasting_compliant BOOLEAN,
    summary_sent    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, date)
);

CREATE INDEX idx_daily_user_date ON daily_summaries(user_id, date DESC);

ALTER TABLE daily_summaries ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can read own summaries" ON daily_summaries FOR SELECT
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));
