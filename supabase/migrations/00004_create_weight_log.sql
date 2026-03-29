CREATE TABLE weight_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    weight_kg   NUMERIC(5,1) NOT NULL,
    note        TEXT,
    logged_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_weight_user_date ON weight_log(user_id, logged_at DESC);

ALTER TABLE weight_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own weight" ON weight_log FOR ALL
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));
