use axum::Json;
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use serde::Serialize;

#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("not found")]
    NotFound,
    #[error("internal error: {0}")]
    Internal(String),
}

#[derive(Serialize)]
struct ErrorBody {
    code: &'static str,
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, code) = match &self {
            AppError::NotFound => (StatusCode::NOT_FOUND, "not_found"),
            AppError::Internal(detail) => {
                tracing::error!(detail, "internal error");
                (StatusCode::INTERNAL_SERVER_ERROR, "internal_error")
            }
        };

        (status, Json(ErrorBody { code })).into_response()
    }
}

#[cfg(test)]
mod tests {
    use http_body_util::BodyExt;

    use super::*;

    async fn status_and_body(error: AppError) -> (StatusCode, String) {
        let response = error.into_response();
        let status = response.status();
        let bytes = response.into_body().collect().await.unwrap().to_bytes();
        (status, String::from_utf8(bytes.to_vec()).unwrap())
    }

    #[tokio::test]
    async fn not_found_becomes_404_with_a_code() {
        let (status, body) = status_and_body(AppError::NotFound).await;

        assert_eq!(status, StatusCode::NOT_FOUND);
        assert_eq!(body, r#"{"code":"not_found"}"#);
    }

    #[tokio::test]
    async fn internal_becomes_500_without_leaking_the_detail() {
        let error = AppError::Internal("connection refused at 10.0.0.5".to_string());

        let (status, body) = status_and_body(error).await;

        assert_eq!(status, StatusCode::INTERNAL_SERVER_ERROR);
        assert_eq!(body, r#"{"code":"internal_error"}"#);
    }
}
