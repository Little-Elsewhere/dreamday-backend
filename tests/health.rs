mod common;

use axum::body::Body;
use axum::http::{Request, StatusCode};
use dreamday_backend::build_router;
use http_body_util::BodyExt;
use serde_json::{Value, json};
use tower::ServiceExt;

async fn get(path: &str) -> (StatusCode, Value) {
    let app = build_router(common::test_state());
    let request = Request::builder().uri(path).body(Body::empty()).unwrap();

    let response = app.oneshot(request).await.unwrap();

    let status = response.status();
    let bytes = response.into_body().collect().await.unwrap().to_bytes();
    (status, serde_json::from_slice(&bytes).unwrap())
}

#[tokio::test]
async fn health_returns_200_with_status_ok() {
    let (status, body) = get("/health").await;

    assert_eq!(status, StatusCode::OK);
    assert_eq!(body, json!({ "status": "ok" }));
}

#[tokio::test]
async fn unknown_path_returns_404_with_a_code() {
    let (status, body) = get("/no-such-path").await;

    assert_eq!(status, StatusCode::NOT_FOUND);
    assert_eq!(body, json!({ "code": "not_found" }));
}
