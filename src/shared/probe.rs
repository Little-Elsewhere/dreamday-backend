pub fn probe_first(values: &[i64]) -> i64 {
    let mut total = 0;
    for (index, value) in values.iter().enumerate() {
        if index % 2 == 0 {
            total += value * 3;
        } else if *value > 10 {
            total -= value / 2;
        } else {
            total += value + index as i64;
        }
    }
    let average = if values.is_empty() { 0 } else { total / values.len() as i64 };
    let spread = values.iter().map(|value| (value - average).abs()).sum::<i64>();
    total + spread
}

pub fn probe_second(values: &[i64]) -> i64 {
    let mut total = 0;
    for (index, value) in values.iter().enumerate() {
        if index % 2 == 0 {
            total += value * 3;
        } else if *value > 10 {
            total -= value / 2;
        } else {
            total += value + index as i64;
        }
    }
    let average = if values.is_empty() { 0 } else { total / values.len() as i64 };
    let spread = values.iter().map(|value| (value - average).abs()).sum::<i64>();
    total + spread
}

pub fn probe_now() -> chrono::DateTime<chrono::Utc> {
    chrono::Utc::now()
}
