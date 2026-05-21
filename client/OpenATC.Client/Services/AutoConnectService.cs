using System;
using System.Threading;
using System.Threading.Tasks;

namespace OpenATC.Client.Services;

public class AutoConnectService
{
    private readonly WebSocketService _wsService;
    private readonly SimConnectService _simConnectService;
    private CancellationTokenSource? _cts;

    public AutoConnectService(
        WebSocketService wsService,
        SimConnectService simConnectService)
    {
        _wsService = wsService;
        _simConnectService = simConnectService;
    }

    public void Start()
    {
        _cts = new CancellationTokenSource();
        _ = ConnectionLoopAsync(_cts.Token);
    }

    private async Task ConnectionLoopAsync(CancellationToken ct)
    {
        const int retryDelayMs = 5000;

        while (!ct.IsCancellationRequested)
        {
            if (!_wsService.IsConnected)
            {
                try
                {
                    await _wsService.ConnectAsync();
                }
                catch
                {
                    // Will retry
                }
            }

            if (!_simConnectService.IsConnected)
            {
                _simConnectService.Connect();
            }

            try
            {
                await Task.Delay(retryDelayMs, ct);
            }
            catch (TaskCanceledException)
            {
                break;
            }
        }
    }

    public void Stop()
    {
        _cts?.Cancel();
    }
}
