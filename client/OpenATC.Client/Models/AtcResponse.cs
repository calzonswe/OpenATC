using System.Text.Json.Serialization;

namespace OpenATC.Client.Models;

public class AtcResponse
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("callsign")]
    public string? Callsign { get; set; }

    [JsonPropertyName("text")]
    public string? Text { get; set; }

    [JsonPropertyName("payload")]
    public Dictionary<string, object>? Payload { get; set; }
}
