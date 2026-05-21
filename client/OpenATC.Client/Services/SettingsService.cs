using System.IO;
using System.Text.Json;
using OpenATC.Client.Models;

namespace OpenATC.Client.Services;

public class SettingsService
{
    private static readonly string SettingsPath = Path.Combine(
        AppDomain.CurrentDomain.BaseDirectory, "settings.json");

    private Settings? _cached;

    public Settings Load()
    {
        if (_cached is not null)
            return _cached;

        if (!File.Exists(SettingsPath))
        {
            _cached = new Settings();
            Save(_cached);
            return _cached;
        }

        var json = File.ReadAllText(SettingsPath);
        _cached = JsonSerializer.Deserialize<Settings>(json) ?? new Settings();
        return _cached;
    }

    public void Save(Settings settings)
    {
        var json = JsonSerializer.Serialize(settings, new JsonSerializerOptions
        {
            WriteIndented = true
        });
        File.WriteAllText(SettingsPath, json);
        _cached = settings;
    }
}
