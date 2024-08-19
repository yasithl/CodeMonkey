using System.Collections;
using System.Collections.Immutable;
using System.Runtime.CompilerServices;

public class CollectionTest 
{
    public static readonly ImmutableArray<int> numbers = [1, 2, 3];

    public IEnumerable<int> Ints => [1, 2,  3];
}

[CollectionBuilder(typeof(LineBufferBuilder), "Create")]
public class LineBuffer(ReadOnlySpan<char>  chars) : IEnumerable<char>
{
    private readonly  char[] charBuffer = new  char[80];

    public IEnumerator<char> GetEnumerator()
        => charBuffer.AsEnumerable().GetEnumerator();

    IEnumerator IEnumerable.GetEnumerator()
        => charBuffer.GetEnumerator();
}

internal static class LineBufferBuilder
{
    internal static LineBuffer Create(ReadOnlySpan<char> values) 
        => new LineBuffer(values);
}

public static class PlayGroundB
{
    public static void DoStuff()
    {
        var  multiply  =  (int x = 1) => x * 2;
        var result   = multiply(5);

        var niceColors =  new [] { "Blue", "Purple", "Pink "};
        //Collection Expressions
        string[] otherColors = ["Green", "Orange", "Red"];
        //Won't work during compile time, const string[] constOtherColors = ["Green", "Orange", "Red"];
        List<string> otherColorsList = ["Green", "Orange", "Red"];


        //spread  operator
        string[] allColors = [..niceColors, ..otherColors];

        Span<int> numbers = stackalloc[] { 1, 2, 3 };
        //New
        Span<int> numbersCE = [1, 2,  3 ];

        int Sum(IEnumerable<int> numbers) => numbers.Sum(x=>x);

        Sum([4, 5, 6]);

        LineBuffer buffer = ['x', 'y', 'z'];

    }

}