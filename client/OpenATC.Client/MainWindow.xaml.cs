using System;
using System.Collections.ObjectModel;
using System.Windows;
using System.Windows.Media;
using System.Windows.Threading;
using OpenATC.Client.Models;
using OpenATC.Client.Services;
using OpenATC.Client.ViewModels;

namespace OpenATC.Client;

public partial class MainWindow : Window
{
    private readonly SettingsService _settingsService;
    private readonly WebSocketService _wsService;
    private readonly SimConnectService _simConnectService;
    private readonly AudioCaptureService _audioCaptureService;
    private readonly AutoConnectService _autoConnectService;
    private readonly ObservableCollection<string> _logEntries = new();

    private bool _pttActive;

    public MainWindow()
    {
        InitializeComponent();

        var app = (App)Application.Current;
        _settingsService = app.GetService<SettingsService>();
        _wsService = app.GetService<WebSocketService>();
        _simConnectService = app.GetService<SimConnectService>();
        _audioCaptureService = app.GetService<AudioCaptureService>();
        _autoConnectService = app.GetService<AutoConnectService>();

        AtcLog.ItemsSource = _logEntries;

        _wsService.ConnectionStateChanged += OnConnectionStateChanged;
        _wsService.MessageReceived += OnMessageReceived;
        _simConnectService.ConnectionStatusChanged += OnSimStateChanged;

        _autoConnectService.Start();
    }

    private void OnConnectionStateChanged(string state)
    {
        Dispatcher.Invoke(() =>
        {
            ConnectionStatusText.Text = state;
            ConnectionStatusDot.Fill = state == "Connected"
                ? Brushes.LimeGreen
                : Brushes.Red;
        });
    }

    private void OnSimStateChanged(string state)
    {
        Dispatcher.Invoke(() =>
        {
            AddLog($"[SIM] {state}");
        });
    }

    private void OnMessageReceived(AtcResponse response)
    {
        Dispatcher.Invoke(() =>
        {
            if (!string.IsNullOrEmpty(response.Text))
            {
                AddLog($"[ATC] {response.Text}");
            }
        });
    }

    private void AddLog(string message)
    {
        var timestamp = DateTime.Now.ToString("HH:mm:ss");
        _logEntries.Add($"[{timestamp}] {message}");
        if (_logEntries.Count > 500)
        {
            _logEntries.RemoveAt(0);
        }
        AtcLog.ScrollIntoView(_logEntries[^1]);
    }

    private void OnSettingsClick(object sender, RoutedEventArgs e)
    {
        var settingsWindow = new SettingsWindow();
        settingsWindow.Owner = this;
        settingsWindow.ShowDialog();
    }

    private void OnPttPressed()
    {
        if (_pttActive) return;
        _pttActive = true;

        _audioCaptureService.StartCapture();
        PttIndicator.Background = new SolidColorBrush(Color.FromRgb(0, 180, 0));
        PttIndicatorText.Text = "TRANSMITTING...";
        PttStatusText.Text = "PTT: TX";

        _ = _wsService.SendJsonAsync(new
        {
            type = "audio_start",
            callsign = _settingsService.Load().Callsign
        });
    }

    private void OnPttReleased()
    {
        if (!_pttActive) return;
        _pttActive = false;

        _audioCaptureService.StopCapture();
        PttIndicator.Background = new SolidColorBrush(Color.FromRgb(224, 224, 224));
        PttIndicatorText.Text = "Press PTT to speak";
        PttStatusText.Text = "PTT: Idle";

        _ = _wsService.SendJsonAsync(new
        {
            type = "audio_end",
            callsign = _settingsService.Load().Callsign
        });
    }

    protected override void OnKeyDown(System.Windows.Input.KeyEventArgs e)
    {
        var settings = _settingsService.Load();
        if (e.Key.ToString() == settings.PttKey && !_pttActive)
        {
            OnPttPressed();
        }
        base.OnKeyDown(e);
    }

    protected override void OnKeyUp(System.Windows.Input.KeyEventArgs e)
    {
        var settings = _settingsService.Load();
        if (e.Key.ToString() == settings.PttKey && _pttActive)
        {
            OnPttReleased();
        }
        base.OnKeyUp(e);
    }

    protected override void OnClosed(EventArgs e)
    {
        _autoConnectService.Stop();
        _audioCaptureService.Dispose();
        _simConnectService.Dispose();
        _wsService.Dispose();
        base.OnClosed(e);
    }
}
