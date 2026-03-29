CREATE TABLE meals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    meal_type       TEXT NOT NULL CHECK (meal_type IN ('breakfast','lunch','snack','dinner')),
    description     TEXT,
    foods           JSONB DEFAULT '[]',
    calories        INT,
    protein_g       NUMERIC(6,1),
    carbs_g         NUMERIC(6,1),
    fat_g           NUMERIC(6,1),
    fiber_g         NUMERIC(6,1),
    goal_score      INT CHECK (goal_score BETWEEN 1 AND 5),
    ai_tip          TEXT,
    ai_summary      TEXT,
    photo_url       TEXT,
    photo_storage_path TEXT,
    source          TEXT DEFAULT 'whatsapp' CHECK (source IN ('whatsapp','web','api')),
    logged_at       TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_meals_user_date ON meals(user_id, logged_at DESC);
CREATE INDEX idx_meals_user_type ON meals(user_id, meal_type);

ALTER TABLE meals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own meals" ON meals FOR ALL
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));
