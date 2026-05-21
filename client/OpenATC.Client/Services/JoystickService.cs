using System;
using System.Collections.Generic;
using System.Linq;
using SharpDX.DirectInput;

namespace OpenATC.Client.Services;

public class JoystickService : IDisposable
{
    private DirectInput? _directInput;
    private List<DeviceInstance>? _devices;

    public event Action<int>? ButtonPressed;
    public event Action<int>? ButtonReleased;

    public List<string> GetJoystickNames()
    {
        _directInput ??= new DirectInput();
        _devices = _directInput.GetDevices(
                DeviceClass.GameControl,
                DeviceEnumFlags.AttachedOnly)
            .ToList();

        return _devices.Select(d => d.InstanceName).ToList();
    }

    public void StartPolling(Guid deviceGuid, int buttonIndex)
    {
        // Polling loop would run in a background thread
        // and fire ButtonPressed/ButtonReleased events
    }

    public void Dispose()
    {
        _directInput?.Dispose();
    }
}
