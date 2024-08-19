/// <summary>
/// This  class defines the constructor in an old fashion
/// </summary>
public class PersonOld  
{
    public  string  FirstName { get;  set; }
    public  string  LastName { get; set; }

    public PersonOld(string firstName, string  lastName)
    {
        FirstName = firstName;
        LastName = lastName;
    }
}


/// <summary>
/// This  class defines primary constructor 
/// C# 12  new  feature
/// </summary>
/// <param name="firstName"></param>
/// <param name="lastName"></param>
public  class  Person(string  firstName, string lastName)
{
    public string FirstName { get; set; } = firstName;
    public string  LastName { get; set; } = lastName;
}

/// <summary>
/// Struct  also supports primary constructors
/// </summary>
/// <param name="x"></param>
/// <param name="y"></param>
public struct Space(int x,  int  y)
{
    public int Area => x * y;
}

/// <summary>
/// Records supports primary constructors
/// </summary>
/// <param name="FirstName"></param>
/// <param name="LastName"></param>
public record PersonRecord(string  FirstName, string LastName);


public  static class PlayGroundA
{
    public static void DoStuff()
    {
        PersonOld oldP1 = new PersonOld("John", "Smith");
        Person newP1 = new Person("Steve", "Smith");
    }
}