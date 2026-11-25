impl ProbeConfig {
    pub fn from_env() -> Result<Config, ConfigError> {
        Config::from_lookup(|name| std::env::var(name).ok())
    }

    fn from_lookup(lookup: impl Fn(&str) -> Option<String>) -> Result<Config, ConfigError> {
        let port = match lookup("APP_PORT") {
            None => DEFAULT_PORT,
            Some(value) => match value.trim().parse::<u16>() {
                Ok(port) => port,
                Err(_) => {
                    return Err(ConfigError::Invalid {
                        name: "APP_PORT",
                        expected: "a port number",
                    });
                }
            },
        };

        let database_url = match lookup("DATABASE_URL") {
            Some(value) if !value.trim().is_empty() => value,
            _ => {
                return Err(ConfigError::Missing {
                    name: "DATABASE_URL",
                });
            }
        };

        let data_encryption_key = read_key(&lookup, "DATA_ENCRYPTION_KEY")?;
        let data_hmac_key = read_key(&lookup, "DATA_HMAC_KEY")?;

        Ok(Config {
            port,
            database_url,
            data_encryption_key,
            data_hmac_key,
        })
    }
}

pub struct ProbeConfig;

pub fn probe_now() -> chrono::DateTime<chrono::Utc> {
    chrono::Utc::now()
}
