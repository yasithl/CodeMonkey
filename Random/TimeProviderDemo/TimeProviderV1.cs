namespace CodeMonkey.Random.TimeProviderDemo;

public class TimeProviderV1
{
    private readonly IDateTimeProvider _dateTimeProvider;

    public TimeProviderV1(IDateTimeProvider dateTimeProvider)
    {
        _dateTimeProvider = dateTimeProvider;
    }

    public DateTimeResponse IsFunTime() => new DateTimeResponse()
    {
        Created = _dateTimeProvider.UtcNow,
        Value = _dateTimeProvider.UtcNow.Hour is >= 12 <= 14
    };
}

public class DateTimeResponse
{
    public DateTime Created { get; set; }
    public bool Value { get; set; }
}