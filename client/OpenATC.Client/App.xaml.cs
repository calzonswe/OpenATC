using System.Windows;
using Microsoft.Extensions.DependencyInjection;
using OpenATC.Client.Services;
using OpenATC.Client.ViewModels;

namespace OpenATC.Client;

public partial class App : Application
{
    private ServiceProvider _serviceProvider = null!;

    protected override void OnStartup(StartupEventArgs e)
    {
        var services = new ServiceCollection();

        services.AddSingleton<SettingsService>();
        services.AddSingleton<SimConnectService>();
        services.AddSingleton<AudioCaptureService>();
        services.AddSingleton<AudioOutputService>();
        services.AddSingleton<OpusCodec>();
        services.AddSingleton<WebSocketService>();
        services.AddSingleton<JoystickService>();
        services.AddSingleton<AutoConnectService>();

        services.AddTransient<SettingsViewModel>();
        services.AddTransient<SettingsWindow>();

        _serviceProvider = services.BuildServiceProvider();
    }

    public T GetService<T>() where T : notnull =>
        _serviceProvider.GetRequiredService<T>();
}
