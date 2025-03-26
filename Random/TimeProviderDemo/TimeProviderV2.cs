namespace CodeMonkey.Random.TimeProviderDemo;

public class TimeProviderV2
{
    private readonly TimeProvider _timeProvider;

    public TimeProviderV2(TimeProvider timeProvider)
    {
        _timeProvider = timeProvider;
    }

    public DateTimeResponse IsFunTime() => new DateTimeResponse()
    {
        Created = _timeProvider.GetUtcNow().DateTime,
        Value = _timeProvider.GetUtcNow().DateTime.Hour is >= 12 and <= 14
    };
}
