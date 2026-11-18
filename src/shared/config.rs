use crate::shared::crypto::SecretKey;

const DEFAULT_PORT: u16 = 8000;

#[derive(Debug, Clone, PartialEq)]
pub struct Config {
    pub port: u16,
    pub database_url: String,
    pub data_encryption_key: SecretKey,
    pub data_hmac_key: SecretKey,
}

#[derive(Debug, PartialEq, thiserror::Error)]
pub enum ConfigError {
    #[error("{name} is not set")]
    Missing { name: &'static str },
    #[error("{name} has an invalid value {value:?}")]
    Invalid { name: &'static str, value: String },
    #[error("{name} must be 32 bytes encoded as base64")]
    InvalidKey { name: &'static str },
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

fn read_key(
    lookup: &impl Fn(&str) -> Option<String>,
    name: &'static str,
) -> Result<SecretKey, ConfigError> {
    match lookup(name) {
        Some(value) if !value.trim().is_empty() => {
            SecretKey::from_base64(&value).ok_or(ConfigError::InvalidKey { name })
        }
        _ => Err(ConfigError::Missing { name }),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const DATABASE_URL: &str = "postgres://user:secret@localhost:5432/dreamday";
    const ENCRYPTION_KEY: &str = "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=";
    const HMAC_KEY: &str = "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgI=";

    const VALID: [(&str, &str); 3] = [
        ("DATABASE_URL", DATABASE_URL),
        ("DATA_ENCRYPTION_KEY", ENCRYPTION_KEY),
        ("DATA_HMAC_KEY", HMAC_KEY),
    ];

    fn config_with(changes: &[(&str, Option<&str>)]) -> Result<Config, ConfigError> {
        Config::from_lookup(|name| {
            if let Some((_, value)) = changes.iter().find(|(key, _)| *key == name) {
                return value.map(|value| value.to_string());
            }
            VALID
                .iter()
                .find(|(key, _)| *key == name)
                .map(|(_, value)| value.to_string())
        })
    }

    #[test]
    fn uses_default_port_when_app_port_is_unset() {
        let config = config_with(&[]).unwrap();

        assert_eq!(config.port, 8000);
    }

    #[test]
    fn reads_port_from_app_port() {
        let config = config_with(&[("APP_PORT", Some("9000"))]).unwrap();

        assert_eq!(config.port, 9000);
    }

    #[test]
    fn rejects_app_port_that_is_not_a_number() {
        let error = config_with(&[("APP_PORT", Some("abc"))]).unwrap_err();

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
        let config = config_with(&[]).unwrap();

        assert_eq!(config.database_url, DATABASE_URL);
    }

    #[test]
    fn rejects_missing_database_url() {
        let error = config_with(&[("DATABASE_URL", None)]).unwrap_err();

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
        let error = config_with(&[("DATABASE_URL", Some("  "))]).unwrap_err();

        assert_eq!(
            error,
            ConfigError::Missing {
                name: "DATABASE_URL"
            }
        );
    }

    #[test]
    fn reads_encryption_and_hmac_keys() {
        let config = config_with(&[]).unwrap();

        assert_eq!(
            config.data_encryption_key,
            SecretKey::from_base64(ENCRYPTION_KEY).unwrap()
        );
        assert_eq!(
            config.data_hmac_key,
            SecretKey::from_base64(HMAC_KEY).unwrap()
        );
    }

    #[test]
    fn rejects_missing_keys() {
        for name in ["DATA_ENCRYPTION_KEY", "DATA_HMAC_KEY"] {
            let error = config_with(&[(name, None)]).unwrap_err();

            assert_eq!(error, ConfigError::Missing { name });
        }
    }

    #[test]
    fn rejects_keys_with_the_wrong_length_without_echoing_them() {
        for name in ["DATA_ENCRYPTION_KEY", "DATA_HMAC_KEY"] {
            let error = config_with(&[(name, Some("AwMDAwMDAwMDAwMDAwMDAw=="))]).unwrap_err();

            assert_eq!(error, ConfigError::InvalidKey { name });
            assert_eq!(
                error.to_string(),
                format!("{name} must be 32 bytes encoded as base64")
            );
        }
    }
}
