use sqlx::PgPool;

async fn insert_user(pool: &PgPool, email_hmac: &[u8]) -> Result<(), sqlx::Error> {
    sqlx::query(
        "INSERT INTO users (email_ciphertext, email_hmac, password_hash, display_name_ciphertext, created_at, updated_at)
         VALUES ('\\x01', $1, 'hash', '\\x02', now(), now())",
    )
    .bind(email_hmac)
    .execute(pool)
    .await
    .map(|_| ())
}

async fn insert_session(pool: &PgPool, token_hash: &[u8]) -> Result<(), sqlx::Error> {
    sqlx::query(
        "INSERT INTO sessions (user_id, token_hash, created_at, last_used_at, expires_at)
         VALUES ((SELECT id FROM users LIMIT 1), $1, now(), now(), now() + interval '30 days')",
    )
    .bind(token_hash)
    .execute(pool)
    .await
    .map(|_| ())
}

async fn insert_email_token(
    pool: &PgPool,
    purpose: &str,
    token_hash: &[u8],
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "INSERT INTO email_tokens (user_id, purpose, token_hash, created_at, expires_at)
         VALUES ((SELECT id FROM users LIMIT 1), $1, $2, now(), now() + interval '15 minutes')",
    )
    .bind(purpose)
    .bind(token_hash)
    .execute(pool)
    .await
    .map(|_| ())
}

fn is_unique_violation(error: &sqlx::Error) -> bool {
    error
        .as_database_error()
        .is_some_and(|error| error.is_unique_violation())
}

#[sqlx::test]
async fn users_reject_a_duplicate_email_hmac(pool: PgPool) {
    insert_user(&pool, b"same").await.unwrap();

    let error = insert_user(&pool, b"same").await.unwrap_err();

    assert!(is_unique_violation(&error));
}

#[sqlx::test]
async fn sessions_reject_a_duplicate_token_hash(pool: PgPool) {
    insert_user(&pool, b"an").await.unwrap();
    insert_session(&pool, b"token").await.unwrap();

    let error = insert_session(&pool, b"token").await.unwrap_err();

    assert!(is_unique_violation(&error));
}

#[sqlx::test]
async fn email_tokens_reject_a_duplicate_token_hash(pool: PgPool) {
    insert_user(&pool, b"an").await.unwrap();
    insert_email_token(&pool, "verify_email", b"token")
        .await
        .unwrap();

    let error = insert_email_token(&pool, "reset_password", b"token")
        .await
        .unwrap_err();

    assert!(is_unique_violation(&error));
}

#[sqlx::test]
async fn email_tokens_reject_an_unknown_purpose(pool: PgPool) {
    insert_user(&pool, b"an").await.unwrap();

    let error = insert_email_token(&pool, "login", b"token")
        .await
        .unwrap_err();

    assert!(
        error
            .as_database_error()
            .is_some_and(|error| error.is_check_violation())
    );
}

#[sqlx::test]
async fn login_throttles_keep_one_row_per_email_hmac(pool: PgPool) {
    let insert =
        "INSERT INTO login_throttles (email_hmac, failed_count, updated_at) VALUES ($1, 1, now())";
    sqlx::query(insert)
        .bind(b"an".as_slice())
        .execute(&pool)
        .await
        .unwrap();

    let error = sqlx::query(insert)
        .bind(b"an".as_slice())
        .execute(&pool)
        .await
        .unwrap_err();

    assert!(is_unique_violation(&error));
}
