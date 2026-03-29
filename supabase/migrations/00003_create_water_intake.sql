CREATE TABLE water_intake (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount_ml   INT NOT NULL,
    logged_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_water_user_date ON water_intake(user_id, logged_at DESC);

ALTER TABLE water_intake ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own water" ON water_intake FOR ALL
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));
