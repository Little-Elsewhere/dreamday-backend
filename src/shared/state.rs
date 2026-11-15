use std::sync::Arc;

use sqlx::PgPool;

use crate::shared::clock::Clock;
use crate::shared::config::Config;

#[derive(Clone)]
pub struct AppState {
    pub config: Arc<Config>,
    pub clock: Arc<dyn Clock>,
    pub db: PgPool,
}
