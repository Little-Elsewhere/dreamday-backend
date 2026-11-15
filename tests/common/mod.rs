use std::sync::Arc;

use chrono::{TimeZone, Utc};
use dreamday_backend::shared::clock::FakeClock;
use dreamday_backend::shared::config::Config;
use dreamday_backend::shared::state::AppState;
use sqlx::PgPool;

pub fn test_state(db: PgPool) -> AppState {
    let start = Utc.with_ymd_and_hms(2026, 1, 15, 9, 0, 0).unwrap();

    AppState {
        config: Arc::new(Config {
            port: 0,
            database_url: String::new(),
        }),
        clock: Arc::new(FakeClock::new(start)),
        db,
    }
}
