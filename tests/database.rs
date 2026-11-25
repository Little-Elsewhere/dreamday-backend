use sqlx::PgPool;

#[sqlx::test]
async fn test_database_is_reachable_and_migrated(pool: PgPool) {
    let answer: i32 = sqlx::query_scalar("SELECT 1")
        .fetch_one(&pool)
        .await
        .unwrap();
    let applied: i64 = sqlx::query_scalar("SELECT count(*) FROM _sqlx_migrations WHERE success")
        .fetch_one(&pool)
        .await
        .unwrap();

    assert_eq!(answer, 1);
    assert_eq!(applied, sqlx::migrate!().iter().count() as i64);
}
