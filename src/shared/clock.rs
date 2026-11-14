use std::sync::Mutex;

use chrono::{DateTime, Utc};

pub trait Clock: Send + Sync {
    fn now(&self) -> DateTime<Utc>;
}

pub struct SystemClock;

impl Clock for SystemClock {
    fn now(&self) -> DateTime<Utc> {
        Utc::now()
    }
}

pub struct FakeClock {
    now: Mutex<DateTime<Utc>>,
}

impl FakeClock {
    pub fn new(now: DateTime<Utc>) -> FakeClock {
        FakeClock {
            now: Mutex::new(now),
        }
    }

    pub fn set(&self, now: DateTime<Utc>) {
        *self.now.lock().unwrap() = now;
    }
}

impl Clock for FakeClock {
    fn now(&self) -> DateTime<Utc> {
        *self.now.lock().unwrap()
    }
}

#[cfg(test)]
mod tests {
    use chrono::TimeZone;

    use super::*;

    fn at(hour: u32, minute: u32) -> DateTime<Utc> {
        Utc.with_ymd_and_hms(2026, 1, 15, hour, minute, 0).unwrap()
    }

    #[test]
    fn fake_clock_returns_the_time_it_was_created_with() {
        let clock = FakeClock::new(at(9, 0));

        assert_eq!(clock.now(), at(9, 0));
    }

    #[test]
    fn fake_clock_returns_the_time_it_was_set_to() {
        let clock = FakeClock::new(at(9, 0));

        clock.set(at(18, 30));

        assert_eq!(clock.now(), at(18, 30));
    }

    #[test]
    fn system_clock_returns_the_current_time() {
        let before = Utc::now();

        let now = SystemClock.now();

        assert!(now >= before);
        assert!(now <= Utc::now());
    }
}
