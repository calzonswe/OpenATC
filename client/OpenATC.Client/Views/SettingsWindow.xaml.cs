using System.Windows;
using NAudio.Wave;
using OpenATC.Client.Models;
using OpenATC.Client.Services;

namespace OpenATC.Client;

public partial class SettingsWindow : Window
{
    private readonly SettingsService _settingsService;
    private Settings _settings;

    public SettingsWindow()
    {
        InitializeComponent();

        var app = (App)Application.Current;
        _settingsService = app.GetService<SettingsService>();
        _settings = _settingsService.Load();

        // Populate fields
        ServerAddressBox.Text = _settings.ServerAddress;
        ServerPortBox.Text = _settings.ServerPort.ToString();
        CallsignBox.Text = _settings.Callsign;
        PttKeyBox.Text = _settings.PttKey;
        VolumeSlider.Value = _settings.Volume;

        // Populate audio devices
        for (int i = 0; i < WaveIn.DeviceCount; i++)
        {
            var caps = WaveIn.GetCapabilities(i);
            AudioDeviceCombo.Items.Add(caps.ProductName);
        }
        AudioDeviceCombo.SelectedIndex = _settings.AudioInputDevice;

        // Populate joysticks
        var joystickService = app.GetService<JoystickService>();
        var names = joystickService.GetJoystickNames();
        foreach (var name in names)
        {
            JoystickCombo.Items.Add(name);
        }
        if (_settings.JoystickDevice is not null)
        {
            JoystickCombo.SelectedItem = _settings.JoystickDevice;
        }

        // PTT key binding via keyboard preview
        PttKeyBox.PreviewKeyDown += (s, e) =>
        {
            PttKeyBox.Text = e.Key.ToString();
            e.Handled = true;
        };
    }

    private void OnSaveClick(object sender, RoutedEventArgs e)
    {
        _settings.ServerAddress = ServerAddressBox.Text;
        _settings.ServerPort = int.TryParse(ServerPortBox.Text, out var port) ? port : 8765;
        _settings.Callsign = CallsignBox.Text.ToUpper();
        _settings.PttKey = PttKeyBox.Text;
        _settings.AudioInputDevice = AudioDeviceCombo.SelectedIndex >= 0
            ? AudioDeviceCombo.SelectedIndex : 0;
        _settings.Volume = (float)VolumeSlider.Value;
        _settings.JoystickDevice = JoystickCombo.SelectedItem as string;

        _settingsService.Save(_settings);
        DialogResult = true;
        Close();
    }

    private void OnCancelClick(object sender, RoutedEventArgs e)
    {
        DialogResult = false;
        Close();
    }
}
