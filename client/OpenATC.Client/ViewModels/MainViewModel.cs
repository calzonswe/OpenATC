using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace OpenATC.Client.ViewModels;

public class MainViewModel : INotifyPropertyChanged
{
    private string _connectionStatus = "Disconnected";
    private string _pttStatus = "Idle";
    private string _lastAtcMessage = "";

    public string ConnectionStatus
    {
        get => _connectionStatus;
        set { _connectionStatus = value; OnPropertyChanged(); }
    }

    public string PttStatus
    {
        get => _pttStatus;
        set { _pttStatus = value; OnPropertyChanged(); }
    }

    public string LastAtcMessage
    {
        get => _lastAtcMessage;
        set { _lastAtcMessage = value; OnPropertyChanged(); }
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    protected void OnPropertyChanged([CallerMemberName] string? name = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
    }
}
