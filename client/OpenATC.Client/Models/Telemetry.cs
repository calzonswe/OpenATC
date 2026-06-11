using System.Text.Json.Serialization;

namespace OpenATC.Client.Models;

public class Telemetry
{
    [JsonPropertyName("callsign")]
    public string Callsign { get; set; } = "";

    [JsonPropertyName("latitude")]
    public double Latitude { get; set; }

    [JsonPropertyName("longitude")]
    public double Longitude { get; set; }

    [JsonPropertyName("altitude_ft")]
    public double AltitudeFt { get; set; }

    [JsonPropertyName("heading")]
    public double Heading { get; set; }

    [JsonPropertyName("speed_kts")]
    public double SpeedKts { get; set; }

    [JsonPropertyName("vertical_speed_fpm")]
    public double VerticalSpeedFpm { get; set; }

    [JsonPropertyName("on_ground")]
    public bool OnGround { get; set; }

    [JsonPropertyName("transponder_code")]
    public int? TransponderCode { get; set; }

    [JsonPropertyName("origin_icao")]
    public string? OriginIcao { get; set; }

    [JsonPropertyName("dest_icao")]
    public string? DestIcao { get; set; }

    [JsonPropertyName("flight_rules")]
    public string? FlightRules { get; set; }

    [JsonPropertyName("timestamp")]
    public double Timestamp { get; set; }
}
