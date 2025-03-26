namespace CodeMonkey.Random.TimeProviderDemo;

public interface IDateTimeProvider
{
    DateTime UtcNow { get; }
}