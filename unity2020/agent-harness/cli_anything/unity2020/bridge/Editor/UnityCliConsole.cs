using System;
using System.Collections.Generic;
using UnityEditor;

namespace CliAnything.Unity
{
    internal static class UnityCliConsole
    {
        private static readonly Type Entries = typeof(EditorApplication).Assembly.GetType("UnityEditor.LogEntries", true);
        private static readonly Type Entry = typeof(EditorApplication).Assembly.GetType("UnityEditor.LogEntry", true);
        private static readonly Type Mode = typeof(EditorApplication).Assembly.GetType("UnityEditor.ConsoleWindow+Mode", true);
        private static readonly int Errors = GetMask("Error, Assert, Fatal, AssetImportError, ScriptingError, ScriptCompileError, StickyError, ScriptingException, GraphCompileError, ScriptingAssertion");
        private static readonly int Warnings = GetMask("AssetImportWarning, ScriptingWarning, ScriptCompileWarning");

        private static int GetMask(string names)
        {
            return Convert.ToInt32(Enum.Parse(Mode, names));
        }

        internal static object Read(string filter, int limit)
        {
            if (limit < 1 || limit > 200)
            {
                throw new ArgumentOutOfRangeException(nameof(limit), "Limit must be between 1 and 200.");
            }
            var getEntry = Entries.GetMethod("GetEntryInternal");
            var messageField = Entry.GetField("message");
            var fileField = Entry.GetField("file");
            var lineField = Entry.GetField("line");
            var modeField = Entry.GetField("mode");
            var entry = Activator.CreateInstance(Entry, true);
            var arguments = new[] { (object)0, entry };
            var logs = new List<object>();
            var count = (int)Entries.GetMethod("StartGettingEntries").Invoke(null, null);
            try
            {
                for (var row = count - 1; row >= 0 && logs.Count < limit; row--)
                {
                    arguments[0] = row;
                    if (!(bool)getEntry.Invoke(null, arguments))
                    {
                        continue;
                    }
                    var mode = (int)modeField.GetValue(entry);
                    var type = (mode & Errors) != 0 ? "error" : (mode & Warnings) != 0 ? "warning" : "log";
                    if (filter == type || filter == "all")
                    {
                        logs.Add(new { type, message = messageField.GetValue(entry), file = fileField.GetValue(entry), line = lineField.GetValue(entry) });
                    }
                }
            }
            finally
            {
                Entries.GetMethod("EndGettingEntries").Invoke(null, null);
            }
            return new { logs, visibleRows = count };
        }

        internal static void Clear()
        {
            Entries.GetMethod("Clear").Invoke(null, null);
        }
    }
}
