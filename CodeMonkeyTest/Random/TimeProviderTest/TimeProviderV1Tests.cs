using CodeMonkey.Random.TimeProviderDemo;
using FluentAssertions;
using FluentAssertions.Extensions;
using Moq;

namespace CodeMonkeyTest.Random.TimeProviderTest
{
    public class TimeProviderV1Tests
    {
        [Fact]
        public void IsFunTime_SetsCreated()
        {
            //Arrange
            var mockDateTimeProvider = new Mock<IDateTimeProvider>();
            var timeProviderV1 = new TimeProviderV1(mockDateTimeProvider.Object);

            var utcNow = DateTime.UtcNow;
            mockDateTimeProvider.SetupGet(x => x.UtcNow).Returns(utcNow);

            //Act
            var response = timeProviderV1.IsFunTime();

            //Assert
            response.Created.Should().Be(utcNow);
        }

        [Theory]
        [InlineData(9, false)]
        [InlineData(12, true)]
        public void IsFunTime_ReturnsTrue(int hour, bool isFunTime)
        {
            //Arrange
            var mockDateTimeProvider = new Mock<IDateTimeProvider>();
            var timeProviderV1 = new TimeProviderV1(mockDateTimeProvider.Object);

            var utcNow = DateTime.UtcNow.At(hour, 0);
            mockDateTimeProvider.SetupGet(x => x.UtcNow).Returns(utcNow);
           
            //Act
            var response = timeProviderV1.IsFunTime();

            //Assert
            response.Value.Should().Be(isFunTime);
        }
    }
}
