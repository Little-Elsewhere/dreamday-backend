use axum::routing::get;
use axum::{Json, Router};
use serde::Serialize;

use crate::shared::state::AppState;

#[derive(Serialize)]
struct HealthBody {
    status: &'static str,
}

pub fn router() -> Router<AppState> {
    Router::new().route("/health", get(health))
}

async fn health() -> Json<HealthBody> {
    Json(HealthBody { status: "ok" })
}
