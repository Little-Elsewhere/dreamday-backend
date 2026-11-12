pub mod health;
pub mod shared;

use axum::Router;

use crate::shared::error::AppError;
use crate::shared::state::AppState;

pub fn build_router(state: AppState) -> Router {
    Router::new()
        .merge(health::router())
        .fallback(not_found)
        .with_state(state)
}

async fn not_found() -> AppError {
    AppError::NotFound
}
