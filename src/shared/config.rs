const DEFAULT_PORT: u16 = 8000;

#[derive(Debug, Clone, PartialEq)]
pub struct Config {
    pub port: u16,
    pub database_url: String,
}

#[derive(Debug, PartialEq, thiserror::Error)]
pub enum ConfigError {
    #[error("{name} is not set")]
    Missing { name: &'static str },
    #[error("{name} has an invalid value {value:?}")]
    Invalid { name: &'static str, value: String },
}

impl Config {
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
                        value,
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

        Ok(Config { port, database_url })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const DATABASE_URL: &str = "postgres://user:secret@localhost:5432/dreamday";

    fn lookup_from(
        pairs: &'static [(&'static str, &'static str)],
    ) -> impl Fn(&str) -> Option<String> {
        move |name| {
            pairs
                .iter()
                .find(|(key, _)| *key == name)
                .map(|(_, value)| value.to_string())
        }
    }

    #[test]
    fn uses_default_port_when_app_port_is_unset() {
        let config = Config::from_lookup(lookup_from(&[("DATABASE_URL", DATABASE_URL)])).unwrap();

        assert_eq!(config.port, 8000);
    }

    #[test]
    fn reads_port_from_app_port() {
        let config = Config::from_lookup(lookup_from(&[
            ("APP_PORT", "9000"),
            ("DATABASE_URL", DATABASE_URL),
        ]))
        .unwrap();

        assert_eq!(config.port, 9000);
    }

    #[test]
    fn rejects_app_port_that_is_not_a_number() {
        let error = Config::from_lookup(lookup_from(&[
            ("APP_PORT", "abc"),
            ("DATABASE_URL", DATABASE_URL),
        ]))
        .unwrap_err();

        assert_eq!(
            error,
            ConfigError::Invalid {
                name: "APP_PORT",
                value: "abc".to_string(),
            }
        );
        assert_eq!(error.to_string(), "APP_PORT has an invalid value \"abc\"");
    }

    #[test]
    fn reads_database_url() {
        let config = Config::from_lookup(lookup_from(&[("DATABASE_URL", DATABASE_URL)])).unwrap();

        assert_eq!(config.database_url, DATABASE_URL);
    }

    #[test]
    fn rejects_missing_database_url() {
        let error = Config::from_lookup(lookup_from(&[])).unwrap_err();

        assert_eq!(
            error,
            ConfigError::Missing {
                name: "DATABASE_URL"
            }
        );
        assert_eq!(error.to_string(), "DATABASE_URL is not set");
    }

    #[test]
    fn rejects_empty_database_url() {
        let error = Config::from_lookup(lookup_from(&[("DATABASE_URL", "  ")])).unwrap_err();

        assert_eq!(
            error,
            ConfigError::Missing {
                name: "DATABASE_URL"
            }
        );
    }
}
