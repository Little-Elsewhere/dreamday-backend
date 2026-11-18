use std::fmt;

use ::hmac::{Hmac, KeyInit, Mac};
use aes_gcm::aead::{Aead, Generate};
use aes_gcm::{Aes256Gcm, Nonce};
use base64::Engine;
use base64::engine::general_purpose::STANDARD;
use sha2::Sha256;

const KEY_VERSION: u8 = 1;
const NONCE_LENGTH: usize = 12;
const HEADER_LENGTH: usize = 1 + NONCE_LENGTH;

type HmacSha256 = Hmac<Sha256>;

#[derive(Clone, PartialEq)]
pub struct SecretKey([u8; 32]);

impl SecretKey {
    pub fn from_base64(value: &str) -> Option<SecretKey> {
        let bytes = STANDARD.decode(value.trim()).ok()?;
        let key: [u8; 32] = bytes.try_into().ok()?;
        Some(SecretKey(key))
    }

    fn cipher(&self) -> Aes256Gcm {
        Aes256Gcm::new(&self.0.into())
    }
}

impl fmt::Debug for SecretKey {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("SecretKey(..)")
    }
}

#[derive(Debug, PartialEq, thiserror::Error)]
pub enum CryptoError {
    #[error("stored value could not be decrypted")]
    Decrypt,
}

pub fn encrypt(key: &SecretKey, plaintext: &str) -> Vec<u8> {
    let nonce = Nonce::generate();
    let ciphertext = key
        .cipher()
        .encrypt(&nonce, plaintext.as_bytes())
        .expect("AES-GCM encrypts any value shorter than 64 GiB");

    let mut stored = Vec::with_capacity(HEADER_LENGTH + ciphertext.len());
    stored.push(KEY_VERSION);
    stored.extend_from_slice(&nonce);
    stored.extend_from_slice(&ciphertext);
    stored
}

pub fn decrypt(key: &SecretKey, stored: &[u8]) -> Result<String, CryptoError> {
    if stored.len() < HEADER_LENGTH || stored[0] != KEY_VERSION {
        return Err(CryptoError::Decrypt);
    }

    let nonce = Nonce::try_from(&stored[1..HEADER_LENGTH]).map_err(|_| CryptoError::Decrypt)?;
    let plaintext = key
        .cipher()
        .decrypt(&nonce, &stored[HEADER_LENGTH..])
        .map_err(|_| CryptoError::Decrypt)?;

    String::from_utf8(plaintext).map_err(|_| CryptoError::Decrypt)
}

pub fn hmac(key: &SecretKey, value: &str) -> Vec<u8> {
    let mut mac = HmacSha256::new_from_slice(&key.0).expect("HMAC accepts keys of any length");
    mac.update(value.as_bytes());
    mac.finalize().into_bytes().to_vec()
}

#[cfg(test)]
mod tests {
    use super::*;

    const KEY: &str = "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=";
    const OTHER_KEY: &str = "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgI=";

    fn key(value: &str) -> SecretKey {
        SecretKey::from_base64(value).unwrap()
    }

    #[test]
    fn reads_a_32_byte_base64_key() {
        assert_eq!(key(KEY), SecretKey([1; 32]));
    }

    #[test]
    fn rejects_keys_that_are_not_32_bytes_of_base64() {
        assert_eq!(SecretKey::from_base64("AwMDAwMDAwMDAwMDAwMDAw=="), None);
        assert_eq!(SecretKey::from_base64("not base64!"), None);
        assert_eq!(SecretKey::from_base64(""), None);
    }

    #[test]
    fn debug_output_hides_the_key() {
        assert_eq!(format!("{:?}", key(KEY)), "SecretKey(..)");
    }

    #[test]
    fn decrypts_what_it_encrypted() {
        let stored = encrypt(&key(KEY), "an@example.com");

        assert_eq!(
            decrypt(&key(KEY), &stored),
            Ok("an@example.com".to_string())
        );
    }

    #[test]
    fn stores_key_version_nonce_ciphertext_and_tag() {
        let stored = encrypt(&key(KEY), "Nguyễn Văn An");

        assert_eq!(stored[0], 1);
        assert_eq!(stored.len(), 1 + 12 + "Nguyễn Văn An".len() + 16);
    }

    #[test]
    fn encrypting_the_same_value_twice_gives_different_results() {
        let first = encrypt(&key(KEY), "an@example.com");
        let second = encrypt(&key(KEY), "an@example.com");

        assert_ne!(first, second);
    }

    #[test]
    fn decrypting_with_the_wrong_key_fails() {
        let stored = encrypt(&key(KEY), "an@example.com");

        assert_eq!(decrypt(&key(OTHER_KEY), &stored), Err(CryptoError::Decrypt));
    }

    #[test]
    fn decrypting_tampered_data_fails() {
        let mut stored = encrypt(&key(KEY), "an@example.com");
        let last = stored.len() - 1;
        stored[last] ^= 1;

        assert_eq!(decrypt(&key(KEY), &stored), Err(CryptoError::Decrypt));
    }

    #[test]
    fn decrypting_an_unknown_key_version_fails() {
        let mut stored = encrypt(&key(KEY), "an@example.com");
        stored[0] = 2;

        assert_eq!(decrypt(&key(KEY), &stored), Err(CryptoError::Decrypt));
    }

    #[test]
    fn decrypting_data_that_is_too_short_fails() {
        assert_eq!(decrypt(&key(KEY), &[1, 2, 3]), Err(CryptoError::Decrypt));
    }

    #[test]
    fn hmac_is_stable_for_the_same_key_and_value() {
        assert_eq!(
            hmac(&key(KEY), "an@example.com"),
            hmac(&key(KEY), "an@example.com")
        );
        assert_eq!(hmac(&key(KEY), "an@example.com").len(), 32);
    }

    #[test]
    fn hmac_differs_by_value_and_by_key() {
        assert_ne!(
            hmac(&key(KEY), "an@example.com"),
            hmac(&key(KEY), "binh@example.com")
        );
        assert_ne!(
            hmac(&key(KEY), "an@example.com"),
            hmac(&key(OTHER_KEY), "an@example.com")
        );
    }
}
