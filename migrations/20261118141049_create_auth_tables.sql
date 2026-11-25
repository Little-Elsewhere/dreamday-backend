CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    email_ciphertext bytea NOT NULL,
    email_hmac bytea NOT NULL UNIQUE,
    password_hash text NOT NULL,
    display_name_ciphertext bytea NOT NULL,
    email_verified_at timestamptz,
    avatar_key text,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE sessions (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    user_id uuid NOT NULL REFERENCES users (id),
    token_hash bytea NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    last_used_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz
);

CREATE TABLE email_tokens (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    user_id uuid NOT NULL REFERENCES users (id),
    purpose text NOT NULL CHECK (purpose IN ('verify_email', 'reset_password')),
    token_hash bytea NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    revoked_at timestamptz
);

CREATE TABLE login_throttles (
    email_hmac bytea PRIMARY KEY,
    failed_count integer NOT NULL,
    locked_until timestamptz,
    updated_at timestamptz NOT NULL
);
