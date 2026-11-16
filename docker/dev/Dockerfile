FROM lukemathwalker/cargo-chef:0.1.78-rust-1.100.0-slim-trixie AS chef

ENV RUSTUP_TOOLCHAIN=${RUST_VERSION} \
    CARGO_TARGET_DIR=/target

WORKDIR /app

FROM chef AS planner

COPY . .

RUN cargo chef prepare --recipe-path recipe.json

FROM chef

RUN CARGO_TARGET_DIR=/tmp/watchexec-build cargo install watchexec-cli --version 2.8.0 --locked \
    && rm -rf /tmp/watchexec-build

COPY --from=planner /app/recipe.json recipe.json

RUN cargo chef cook --recipe-path recipe.json

COPY . .

EXPOSE 8000

CMD ["watchexec", "--restart", "--watch", "src", "--watch", "migrations", "--watch", "Cargo.toml", "--watch", "Cargo.lock", "--", "cargo", "run"]
