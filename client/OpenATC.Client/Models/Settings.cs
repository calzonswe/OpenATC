using System.Text.Json.Serialization;

namespace OpenATC.Client.Models;

public class Settings
{
    [JsonPropertyName("server_address")]
    public string ServerAddress { get; set; } = "localhost";

    [JsonPropertyName("server_port")]
    public int ServerPort { get; set; } = 8765;

    [JsonPropertyName("callsign")]
    public string Callsign { get; set; } = "DAL123";

    [JsonPropertyName("ptt_key")]
    public string PttKey { get; set; } = "LeftControl";

    [JsonPropertyName("joystick_device")]
    public string? JoystickDevice { get; set; } = null;

    [JsonPropertyName("joystick_button")]
    public int? JoystickButton { get; set; } = null;

    [JsonPropertyName("audio_input_device")]
    public int AudioInputDevice { get; set; } = 0;

    [JsonPropertyName("volume")]
    public float Volume { get; set; } = 1.0f;

    [JsonPropertyName("telemetry_interval_ms")]
    public int TelemetryIntervalMs { get; set; } = 3000;
}
