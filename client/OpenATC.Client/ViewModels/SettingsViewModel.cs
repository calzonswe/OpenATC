using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Linq;
using System.Runtime.CompilerServices;
using OpenATC.Client.Models;
using OpenATC.Client.Services;

namespace OpenATC.Client.ViewModels;

public class SettingsViewModel : INotifyPropertyChanged
{
    private readonly SettingsService _settingsService;
    private readonly JoystickService _joystickService;

    private Settings _settings;
    private string _selectedJoystick = "";

    public ObservableCollection<string> JoystickNames { get; } = new();

    public string ServerAddress
    {
        get => _settings.ServerAddress;
        set { _settings.ServerAddress = value; OnPropertyChanged(); }
    }

    public int ServerPort
    {
        get => _settings.ServerPort;
        set { _settings.ServerPort = value; OnPropertyChanged(); }
    }

    public string Callsign
    {
        get => _settings.Callsign;
        set { _settings.Callsign = value; OnPropertyChanged(); }
    }

    public string PttKey
    {
        get => _settings.PttKey;
        set { _settings.PttKey = value; OnPropertyChanged(); }
    }

    public string SelectedJoystick
    {
        get => _selectedJoystick;
        set { _selectedJoystick = value; OnPropertyChanged(); }
    }

    public int AudioInputDevice
    {
        get => _settings.AudioInputDevice;
        set { _settings.AudioInputDevice = value; OnPropertyChanged(); }
    }

    public float Volume
    {
        get => _settings.Volume;
        set { _settings.Volume = value; OnPropertyChanged(); }
    }

    public SettingsViewModel(SettingsService settingsService, JoystickService joystickService)
    {
        _settingsService = settingsService;
        _joystickService = joystickService;
        _settings = settingsService.Load();

        var names = _joystickService.GetJoystickNames();
        foreach (var name in names)
        {
            JoystickNames.Add(name);
        }

        if (_settings.JoystickDevice is not null && JoystickNames.Contains(_settings.JoystickDevice))
        {
            _selectedJoystick = _settings.JoystickDevice;
        }
    }

    public void Save()
    {
        _settings.JoystickDevice = string.IsNullOrEmpty(SelectedJoystick) ? null : SelectedJoystick;
        _settingsService.Save(_settings);
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    protected void OnPropertyChanged([CallerMemberName] string? name = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
    }
}
