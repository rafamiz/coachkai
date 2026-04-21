CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_id         UUID UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    phone           TEXT UNIQUE NOT NULL,
    phone_verified  BOOLEAN DEFAULT FALSE,
    first_name      TEXT,
    last_name       TEXT,
    email           TEXT,
    avatar_url      TEXT,
    gender          TEXT CHECK (gender IN ('male','female','other')),
    date_of_birth   DATE,
    height_cm       NUMERIC(5,1),
    weight_kg       NUMERIC(5,1),
    activity_level  TEXT CHECK (activity_level IN ('sedentary','light','moderate','active','very_active')),
    goal            TEXT CHECK (goal IN ('lose_weight','gain_muscle','maintain','eat_healthier')),
    target_weight_kg NUMERIC(5,1),
    weekly_goal_kg  NUMERIC(3,2),
    daily_calories  INT,
    protein_g       INT,
    carbs_g         INT,
    fat_g           INT,
    dietary_preference TEXT DEFAULT 'none' CHECK (dietary_preference IN ('none','vegan','vegetarian','pescatarian','keto','paleo','gluten_free','mediterranean')),
    allergies       TEXT[] DEFAULT '{}',
    unit_system     TEXT DEFAULT 'metric' CHECK (unit_system IN ('metric','imperial')),
    timezone        TEXT DEFAULT 'America/New_York',
    language        TEXT DEFAULT 'en',
    fasting_enabled BOOLEAN DEFAULT FALSE,
    fasting_window  JSONB,
    onboarding_completed BOOLEAN DEFAULT FALSE,
    onboarding_step      INT DEFAULT 0,
    wa_provider     TEXT CHECK (wa_provider IN ('twilio','meta')),
    wa_id           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_phone ON users(phone);
CREATE INDEX idx_users_wa_id ON users(wa_id);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can read own data" ON users FOR SELECT USING (auth_id = auth.uid());
CREATE POLICY "Users can update own data" ON users FOR UPDATE USING (auth_id = auth.uid());
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
CREATE TABLE conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content     TEXT NOT NULL,
    intent      TEXT,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conv_user_recent ON conversations(user_id, created_at DESC);

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can read own conversations" ON conversations FOR SELECT
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));
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
