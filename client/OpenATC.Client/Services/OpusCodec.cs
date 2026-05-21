using System;
using Concentus.Ogg;
using Concentus.Structs;

namespace OpenATC.Client.Services;

public class OpusCodec : IDisposable
{
    private readonly OpusEncoder _encoder;
    private readonly OpusDecoder _decoder;
    private readonly int _sampleRate = 16000;
    private readonly int _channels = 1;
    private readonly int _frameSizeMs = 60;
    private readonly int _frameSize;

    public OpusCodec()
    {
        _frameSize = _sampleRate * _frameSizeMs / 1000;
        _encoder = new OpusEncoder(_sampleRate, _channels, OpusApplication.OPUS_APPLICATION_VOIP);
        _encoder.Bitrate = 32000;
        _decoder = new OpusDecoder(_sampleRate, _channels);
    }

    public byte[]? Encode(byte[] pcmData, int offset, int count)
    {
        if (count == 0) return null;

        short[] pcmShorts = new short[count / 2];
        Buffer.BlockCopy(pcmData, offset, pcmShorts, 0, count);

        int frames = (pcmShorts.Length + _frameSize - 1) / _frameSize;
        using var ms = new System.IO.MemoryStream();

        for (int i = 0; i < frames; i++)
        {
            int start = i * _frameSize;
            int len = Math.Min(_frameSize, pcmShorts.Length - start);
            var frame = new short[len];
            Array.Copy(pcmShorts, start, frame, 0, len);

            byte[] opusData = new byte[4000];
            int encodedLen = _encoder.Encode(frame, 0, len, opusData, 0, opusData.Length);
            ms.Write(opusData, 0, encodedLen);
        }

        return ms.ToArray();
    }

    public byte[]? Decode(byte[] opusData, int offset, int count)
    {
        if (count == 0) return null;

        short[] pcmShorts = new short[_frameSize];
        int decodedLen = _decoder.Decode(opusData, offset, count, pcmShorts, 0, _frameSize);

        if (decodedLen <= 0) return null;

        byte[] pcmBytes = new byte[decodedLen * 2];
        Buffer.BlockCopy(pcmShorts, 0, pcmBytes, 0, pcmBytes.Length);
        return pcmBytes;
    }

    public void Dispose()
    {
        _encoder?.Dispose();
        _decoder?.Dispose();
    }
}
