use std::net::SocketAddr;
use std::sync::Arc;

use dreamday_backend::build_router;
use dreamday_backend::shared::clock::SystemClock;
use dreamday_backend::shared::config::Config;
use dreamday_backend::shared::state::AppState;
use tokio::net::TcpListener;

#[tokio::main]
async fn main() -> std::io::Result<()> {
    tracing_subscriber::fmt::init();

    let config = match Config::from_env() {
        Ok(config) => config,
        Err(error) => {
            eprintln!("configuration error: {error}");
            std::process::exit(1);
        }
    };

    let address = SocketAddr::from(([0, 0, 0, 0], config.port));
    let state = AppState {
        config: Arc::new(config),
        clock: Arc::new(SystemClock),
    };

    let listener = TcpListener::bind(address).await?;
    tracing::info!(%address, "listening");

    axum::serve(listener, build_router(state)).await
}
