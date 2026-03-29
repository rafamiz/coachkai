CREATE TABLE fasting_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    started_at      TIMESTAMPTZ NOT NULL,
    ended_at        TIMESTAMPTZ,
    target_hours    INT,
    completed       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fasting_user ON fasting_log(user_id, started_at DESC);

ALTER TABLE fasting_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own fasting" ON fasting_log FOR ALL
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));
