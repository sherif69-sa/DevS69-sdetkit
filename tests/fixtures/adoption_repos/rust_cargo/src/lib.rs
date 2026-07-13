pub fn add(left: i32, right: i32) -> i32 {
    left + right
}

#[cfg(test)]
mod tests {
    use super::add;

    #[test]
    fn adds_numbers() {
        assert_eq!(add(1, 2), 4);
    }
}
