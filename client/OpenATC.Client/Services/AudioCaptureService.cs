using System;
using NAudio.Wave;

namespace OpenATC.Client.Services;

public class AudioCaptureService : IDisposable
{
    private WaveInEvent? _waveIn;
    private readonly OpusCodec _opusCodec;

    public event Action<byte[]>? OpusFrameAvailable;
    public event Action? RecordingStarted;
    public event Action? RecordingStopped;

    public bool IsRecording { get; private set; }

    public AudioCaptureService(OpusCodec opusCodec)
    {
        _opusCodec = opusCodec;
    }

    public void StartCapture(int deviceNumber = 0)
    {
        if (IsRecording) return;

        _waveIn = new WaveInEvent
        {
            DeviceNumber = deviceNumber,
            WaveFormat = new WaveFormat(16000, 16, 1) // 16kHz, 16-bit, mono
        };

        _waveIn.DataAvailable += OnDataAvailable;
        _waveIn.RecordingStopped += OnRecordingStopped;
        _waveIn.StartRecording();

        IsRecording = true;
        RecordingStarted?.Invoke();
    }

    public void StopCapture()
    {
        _waveIn?.StopRecording();
    }

    private void OnDataAvailable(object? sender, WaveInEventArgs e)
    {
        var opusPacket = _opusCodec.Encode(e.Buffer, 0, e.BytesRecorded);
        if (opusPacket is not null)
        {
            OpusFrameAvailable?.Invoke(opusPacket);
        }
    }

    private void OnRecordingStopped(object? sender, StoppedEventArgs e)
    {
        IsRecording = false;
        _waveIn?.Dispose();
        _waveIn = null;
        RecordingStopped?.Invoke();
    }

    public void Dispose()
    {
        StopCapture();
    }
}
