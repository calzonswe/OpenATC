using System;
using System.IO;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using OpenATC.Client.Models;

namespace OpenATC.Client.Services;

public class WebSocketService : IDisposable
{
    private ClientWebSocket? _ws;
    private CancellationTokenSource? _cts;
    private readonly SettingsService _settingsService;

    public event Action<AtcResponse>? MessageReceived;
    public event Action<byte[]>? AudioFrameReceived;
    public event Action<string>? ConnectionStateChanged;

    public bool IsConnected => _ws?.State == WebSocketState.Open;

    public WebSocketService(SettingsService settingsService)
    {
        _settingsService = settingsService;
    }

    public async Task ConnectAsync()
    {
        var settings = _settingsService.Load();
        var uri = new Uri($"ws://{settings.ServerAddress}:{settings.ServerPort}/ws");

        _ws?.Dispose();
        _ws = new ClientWebSocket();
        _cts = new CancellationTokenSource();

        try
        {
            await _ws.ConnectAsync(uri, _cts.Token);
            ConnectionStateChanged?.Invoke("Connected");

            // Send register message
            var registerMsg = new
            {
                type = "register",
                callsign = settings.Callsign
            };
            await SendJsonAsync(registerMsg);

            // Start receive loop
            _ = ReceiveLoopAsync();
        }
        catch (Exception ex)
        {
            ConnectionStateChanged?.Invoke($"Connection failed: {ex.Message}");
        }
    }

    public async Task SendJsonAsync(object message)
    {
        if (_ws?.State != WebSocketState.Open) return;

        var json = JsonSerializer.Serialize(message);
        var bytes = Encoding.UTF8.GetBytes(json);
        await _ws.SendAsync(
            new ArraySegment<byte>(bytes),
            WebSocketMessageType.Text,
            true,
            _cts?.Token ?? CancellationToken.None);
    }

    public async Task SendBinaryAsync(byte[] data)
    {
        if (_ws?.State != WebSocketState.Open) return;

        await _ws.SendAsync(
            new ArraySegment<byte>(data),
            WebSocketMessageType.Binary,
            true,
            _cts?.Token ?? CancellationToken.None);
    }

    public async Task SendTelemetryAsync(Telemetry telemetry)
    {
        var msg = new
        {
            type = "telemetry",
            callsign = telemetry.Callsign,
            payload = telemetry
        };
        await SendJsonAsync(msg);
    }

    private async Task ReceiveLoopAsync()
    {
        var buffer = new byte[65536];

        try
        {
            while (_ws?.State == WebSocketState.Open)
            {
                var result = await _ws.ReceiveAsync(
                    new ArraySegment<byte>(buffer),
                    _cts?.Token ?? CancellationToken.None);

                if (result.MessageType == WebSocketMessageType.Text)
                {
                    var json = Encoding.UTF8.GetString(buffer, 0, result.Count);
                    var response = JsonSerializer.Deserialize<AtcResponse>(json);
                    if (response is not null)
                    {
                        MessageReceived?.Invoke(response);
                    }
                }
                else if (result.MessageType == WebSocketMessageType.Binary)
                {
                    var audioData = new byte[result.Count];
                    Array.Copy(buffer, audioData, result.Count);
                    AudioFrameReceived?.Invoke(audioData);
                }
                else if (result.MessageType == WebSocketMessageType.Close)
                {
                    await _ws!.CloseAsync(
                        WebSocketCloseStatus.NormalClosure,
                        "Server closed",
                        CancellationToken.None);
                    ConnectionStateChanged?.Invoke("Disconnected");
                }
            }
        }
        catch (Exception ex)
        {
            ConnectionStateChanged?.Invoke($"Connection lost: {ex.Message}");
        }
    }

    public async Task DisconnectAsync()
    {
        if (_ws?.State == WebSocketState.Open)
        {
            await _ws.CloseAsync(
                WebSocketCloseStatus.NormalClosure,
                "Client closing",
                CancellationToken.None);
        }
        _cts?.Cancel();
        ConnectionStateChanged?.Invoke("Disconnected");
    }

    public void Dispose()
    {
        _cts?.Cancel();
        _ws?.Dispose();
        _cts?.Dispose();
    }
}
