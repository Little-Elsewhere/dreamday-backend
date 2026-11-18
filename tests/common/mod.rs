use std::sync::Arc;

use chrono::{TimeZone, Utc};
use dreamday_backend::shared::clock::FakeClock;
use dreamday_backend::shared::config::Config;
use dreamday_backend::shared::crypto::SecretKey;
use dreamday_backend::shared::state::AppState;
use sqlx::PgPool;

const ENCRYPTION_KEY: &str = "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=";
const HMAC_KEY: &str = "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgI=";

pub fn test_state(db: PgPool) -> AppState {
    let start = Utc.with_ymd_and_hms(2026, 1, 15, 9, 0, 0).unwrap();

    AppState {
        config: Arc::new(Config {
            port: 0,
            database_url: String::new(),
            data_encryption_key: SecretKey::from_base64(ENCRYPTION_KEY).unwrap(),
            data_hmac_key: SecretKey::from_base64(HMAC_KEY).unwrap(),
        }),
        clock: Arc::new(FakeClock::new(start)),
        db,
    }
}
