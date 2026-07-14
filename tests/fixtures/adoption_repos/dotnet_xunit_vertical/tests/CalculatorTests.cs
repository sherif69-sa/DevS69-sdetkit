using Xunit;

namespace Calculator.Tests;

public sealed class CalculatorTests
{
    [Fact]
    public void AddsNumbers()
    {
        Assert.Equal(4, 1 + 2);
    }
}
