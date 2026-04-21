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
