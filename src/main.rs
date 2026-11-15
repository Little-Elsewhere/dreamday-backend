use std::error::Error;
use std::net::SocketAddr;
use std::sync::Arc;

use dreamday_backend::build_router;
use dreamday_backend::shared::clock::SystemClock;
use dreamday_backend::shared::config::Config;
use dreamday_backend::shared::db;
use dreamday_backend::shared::state::AppState;
use tokio::net::TcpListener;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    tracing_subscriber::fmt::init();

    let config = match Config::from_env() {
        Ok(config) => config,
        Err(error) => {
            eprintln!("configuration error: {error}");
            std::process::exit(1);
        }
    };

    let pool = db::connect(&config.database_url).await?;
    db::migrate(&pool).await?;
    tracing::info!("database migrations are up to date");

    let address = SocketAddr::from(([0, 0, 0, 0], config.port));
    let state = AppState {
        config: Arc::new(config),
        clock: Arc::new(SystemClock),
        db: pool,
    };

    let listener = TcpListener::bind(address).await?;
    tracing::info!(%address, "listening");

    axum::serve(listener, build_router(state)).await?;

    Ok(())
}
