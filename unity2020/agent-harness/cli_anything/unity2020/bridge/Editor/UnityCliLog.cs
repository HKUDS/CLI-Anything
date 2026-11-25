using UnityEngine;

namespace CliAnything.Unity
{
    internal static class UnityCliLog
    {
        internal static void Log(string message) => Debug.Log(message);
        internal static void LogError(string message) => Debug.LogError(message);
    }
}
