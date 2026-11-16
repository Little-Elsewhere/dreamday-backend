FROM lukemathwalker/cargo-chef:0.1.78-rust-1.100.0-slim-trixie AS chef

ENV RUSTUP_TOOLCHAIN=${RUST_VERSION} \
    CARGO_TARGET_DIR=/target

WORKDIR /app

FROM chef AS planner

COPY . .

RUN cargo chef prepare --recipe-path recipe.json

FROM chef AS builder

COPY --from=planner /app/recipe.json recipe.json

RUN cargo chef cook --release --recipe-path recipe.json

COPY . .

RUN cargo build --release --locked --bin dreamday-backend

FROM debian:trixie-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app \
    && useradd --system --gid app --no-create-home app

COPY --from=builder /target/release/dreamday-backend /usr/local/bin/dreamday-backend

USER app

EXPOSE 8000

CMD ["dreamday-backend"]
