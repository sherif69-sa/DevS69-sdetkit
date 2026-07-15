package com.example;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

final class CalculatorTest {
    @Test
    void addsTwoNumbers() {
        int left = 1;
        int right = 2;
        int actual = Calculator.add(left, right);

        int expected = 4;

        assertEquals(expected, actual);
    }
}
