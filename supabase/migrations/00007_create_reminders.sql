CREATE TABLE reminders (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type        TEXT NOT NULL CHECK (type IN ('meal','water','weigh_in','custom')),
    label       TEXT,
    time_utc    TIME NOT NULL,
    days        INT[] DEFAULT '{1,2,3,4,5,6,7}',
    enabled     BOOLEAN DEFAULT TRUE,
    last_sent   TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_reminders_active ON reminders(enabled, time_utc) WHERE enabled = TRUE;

ALTER TABLE reminders ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own reminders" ON reminders FOR ALL
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));
