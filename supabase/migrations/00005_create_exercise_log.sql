CREATE TABLE exercise_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exercise_type   TEXT NOT NULL,
    duration_min    INT,
    calories_burned INT,
    description     TEXT,
    logged_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_exercise_user_date ON exercise_log(user_id, logged_at DESC);

ALTER TABLE exercise_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own exercise" ON exercise_log FOR ALL
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));
