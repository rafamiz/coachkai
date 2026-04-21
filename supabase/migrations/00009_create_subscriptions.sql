CREATE TABLE subscriptions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stripe_customer_id  TEXT UNIQUE,
    stripe_sub_id       TEXT UNIQUE,
    plan                TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free','monthly','yearly')),
    status              TEXT NOT NULL DEFAULT 'trialing' CHECK (status IN ('trialing','active','past_due','canceled','expired')),
    trial_ends_at       TIMESTAMPTZ,
    current_period_end  TIMESTAMPTZ,
    cancel_at           TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can read own subscription" ON subscriptions FOR SELECT
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));
