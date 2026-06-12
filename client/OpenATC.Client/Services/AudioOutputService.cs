using System;
using NAudio.Wave;

namespace OpenATC.Client.Services;

public class AudioOutputService : IDisposable
{
    private WaveOutEvent? _waveOut;
    private BufferedWaveProvider? _bufferProvider;
    private readonly int _sampleRate = 22050;

    public AudioOutputService()
    {
        try
        {
            _waveOut = new WaveOutEvent();
            _bufferProvider = new BufferedWaveProvider(new WaveFormat(_sampleRate, 16, 1))
            {
                BufferDuration = TimeSpan.FromSeconds(5),
                DiscardOnBufferOverflow = true,
            };
            _waveOut.Init(_bufferProvider);
            _waveOut.Play();
        }
        catch
        {
            _waveOut = null;
            _bufferProvider = null;
        }
    }

    public void EnqueuePcm(byte[] pcmData)
    {
        if (_bufferProvider is null || pcmData.Length == 0)
            return;
        _bufferProvider.AddSamples(pcmData, 0, pcmData.Length);
    }

    public void Dispose()
    {
        _waveOut?.Stop();
        _waveOut?.Dispose();
        _waveOut = null;
        _bufferProvider = null;
    }
}
