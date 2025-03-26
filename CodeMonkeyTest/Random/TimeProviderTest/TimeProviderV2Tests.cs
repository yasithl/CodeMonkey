using CodeMonkey.Random.TimeProviderDemo;
using FluentAssertions;
using FluentAssertions.Extensions;
using Microsoft.Extensions.Time.Testing;

namespace CodeMonkeyTest.Random.TimeProviderTest
{
    public class TimeProviderV2Tests
    {
        [Fact]
        public void IsFunTime_SetsCreated()
        {
            //Arrange
            var timeProvider = new FakeTimeProvider();
            var timeProviderV2 = new TimeProviderV2(timeProvider);

            var utcNow = DateTime.UtcNow;
            timeProvider.SetUtcNow(utcNow);

            //Act
            var response = timeProviderV2.IsFunTime();

            //Assert
            response.Created.Should().Be(utcNow);
        }

        [Theory]
        [InlineData(9, false)]
        [InlineData(12, true)]
        public void IsFunTime_ReturnsTrue(int hour, bool isFunTime)
        {
            //Arrange
            var timeProvider = new FakeTimeProvider();
            var timeProviderV2 = new TimeProviderV2(timeProvider);

            var utcNow = DateTime.UtcNow.At(hour, 0);
            timeProvider.SetUtcNow(utcNow);

            //Act
            var response = timeProviderV2.IsFunTime();

            //Assert
            response.Value.Should().Be(isFunTime);
        }
    }
}
