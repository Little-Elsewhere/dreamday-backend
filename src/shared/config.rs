const DEFAULT_PORT: u16 = 8000;

#[derive(Debug, Clone, PartialEq)]
pub struct Config {
    pub port: u16,
}

#[derive(Debug, PartialEq, thiserror::Error)]
pub enum ConfigError {
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

        Ok(Config { port })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn uses_default_port_when_app_port_is_unset() {
        let config = Config::from_lookup(|_| None).unwrap();

        assert_eq!(config.port, 8000);
    }

    #[test]
    fn reads_port_from_app_port() {
        let config = Config::from_lookup(|name| match name {
            "APP_PORT" => Some("9000".to_string()),
            _ => None,
        })
        .unwrap();

        assert_eq!(config.port, 9000);
    }

    #[test]
    fn rejects_app_port_that_is_not_a_number() {
        let error = Config::from_lookup(|_| Some("abc".to_string())).unwrap_err();

        assert_eq!(
            error,
            ConfigError::Invalid {
                name: "APP_PORT",
                value: "abc".to_string(),
            }
        );
        assert_eq!(error.to_string(), "APP_PORT has an invalid value \"abc\"");
    }
}
