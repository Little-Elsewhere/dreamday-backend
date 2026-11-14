use std::sync::Arc;

use chrono::{TimeZone, Utc};
use dreamday_backend::shared::clock::FakeClock;
use dreamday_backend::shared::config::Config;
use dreamday_backend::shared::state::AppState;

pub fn test_state() -> AppState {
    let start = Utc.with_ymd_and_hms(2026, 1, 15, 9, 0, 0).unwrap();

    AppState {
        config: Arc::new(Config { port: 0 }),
        clock: Arc::new(FakeClock::new(start)),
    }
}
