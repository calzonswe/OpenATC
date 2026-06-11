using System;
using System.Collections.Generic;
using System.Linq;
using Vortice.DirectInput;

namespace OpenATC.Client.Services;

public class JoystickService : IDisposable
{
    private IDirectInput8? _directInput;
    private List<DeviceInstance>? _devices;

    public event Action<int>? ButtonPressed;
    public event Action<int>? ButtonReleased;

    public List<string> GetJoystickNames()
    {
        _directInput ??= DirectInput8.Create();
        _devices = _directInput.GetDevices(
                DeviceClass.GameControl,
                DeviceEnumerationFlags.AttachedOnly)
            .ToList();

        return _devices.Select(d => d.InstanceName).ToList();
    }

    public void Dispose()
    {
        _directInput?.Dispose();
    }
}
