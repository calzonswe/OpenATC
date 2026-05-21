using System;
using System.Timers;
using Microsoft.FlightSimulator.SimConnect;
using OpenATC.Client.Models;

namespace OpenATC.Client.Services;

public class SimConnectService : IDisposable
{
    private SimConnect? _simConnect;
    private Timer? _telemetryTimer;
    private readonly SettingsService _settingsService;

    public event Action<Telemetry>? TelemetryUpdated;
    public event Action<string>? ConnectionStatusChanged;

    public bool IsConnected { get; private set; }

    public SimConnectService(SettingsService settingsService)
    {
        _settingsService = settingsService;
    }

    public void Connect()
    {
        try
        {
            _simConnect = new SimConnect("OpenATC", IntPtr.Zero, 0x0409, null, 0);
            _simConnect.OnRecvOpen += OnSimConnectOpen;
            _simConnect.OnRecvQuit += OnSimConnectQuit;
            IsConnected = true;
            ConnectionStatusChanged?.Invoke("Connected");

            StartTelemetryTimer();
        }
        catch (Exception ex)
        {
            IsConnected = false;
            ConnectionStatusChanged?.Invoke($"Connection failed: {ex.Message}");
        }
    }

    private void OnSimConnectOpen(SimConnect sender, SIMCONNECT_RECV_OPEN data)
    {
        // Register data definitions for telemetry
        _simConnect?.AddToDataDefinition(
            DEFINITIONS.Telemetry,
            "PLANE LATITUDE", "degrees",
            SIMCONNECT_DATATYPE.FLOAT64);
        _simConnect?.AddToDataDefinition(
            DEFINITIONS.Telemetry,
            "PLANE LONGITUDE", "degrees",
            SIMCONNECT_DATATYPE.FLOAT64);
        _simConnect?.AddToDataDefinition(
            DEFINITIONS.Telemetry,
            "PLANE ALTITUDE", "feet",
            SIMCONNECT_DATATYPE.FLOAT64);
        _simConnect?.AddToDataDefinition(
            DEFINITIONS.Telemetry,
            "PLANE HEADING DEGREES TRUE", "degrees",
            SIMCONNECT_DATATYPE.FLOAT64);
        _simConnect?.AddToDataDefinition(
            DEFINITIONS.Telemetry,
            "AIRSPEED INDICATED", "knots",
            SIMCONNECT_DATATYPE.FLOAT64);
        _simConnect?.AddToDataDefinition(
            DEFINITIONS.Telemetry,
            "VERTICAL SPEED", "feet per minute",
            SIMCONNECT_DATATYPE.FLOAT64);
        _simConnect?.AddToDataDefinition(
            DEFINITIONS.Telemetry,
            "SIM ON GROUND", "bool",
            SIMCONNECT_DATATYPE.INT32);
        _simConnect?.AddToDataDefinition(
            DEFINITIONS.Telemetry,
            "TRANSPONDER CODE:1", "number",
            SIMCONNECT_DATATYPE.INT32);

        _simConnect?.RegisterDataDefineStruct<SimData>(DEFINITIONS.Telemetry);
    }

    private void StartTelemetryTimer()
    {
        var settings = _settingsService.Load();
        _telemetryTimer = new Timer(settings.TelemetryIntervalMs);
        _telemetryTimer.Elapsed += OnTelemetryTimer;
        _telemetryTimer.AutoReset = true;
        _telemetryTimer.Start();
    }

    private void OnTelemetryTimer(object? sender, ElapsedEventArgs e)
    {
        if (_simConnect is null || !IsConnected) return;

        try
        {
            _simConnect.RequestDataOnSimObject(
                DATA_REQUESTS.Telemetry,
                DEFINITIONS.Telemetry,
                SIMCONNECT_SIMOBJECT_TYPE.USER,
                SIMCONNECT_PERIOD.SIM_FRAME,
                SIMCONNECT_DATA_REQUEST_FLAG.CHANGED);
        }
        catch
        {
            // SimConnect not ready yet
        }
    }

    public void Dispose()
    {
        _telemetryTimer?.Stop();
        _telemetryTimer?.Dispose();
        _simConnect?.Dispose();
    }

    private enum DEFINITIONS { Telemetry }
    private enum DATA_REQUESTS { Telemetry }

    private struct SimData
    {
        public double Latitude;
        public double Longitude;
        public double AltitudeFt;
        public double Heading;
        public double SpeedKts;
        public double VerticalSpeedFpm;
        public int OnGround;
        public int TransponderCode;
    }
}
