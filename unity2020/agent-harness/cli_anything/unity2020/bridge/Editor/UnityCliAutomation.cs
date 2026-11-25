using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.PackageManager;
using UnityEditor.PackageManager.Requests;
using UnityEditor.TestTools.TestRunner.Api;
using UnityEngine;

namespace CliAnything.Unity
{
    // 脚本、ScriptableObject、菜单、测试、构建与包查询/显式增删。由 UnityCliBridge.Execute 调用 TryExecute。
    internal static class UnityCliAutomation
    {
        private const string MenuExecuteCommand = "menu.execute";
        private const string ActiveTestJobKey = "UnityCli.Automation.ActiveTestJob";
        private const string LastTestJobKey = "UnityCli.Automation.LastTestJob";
        private const string TestJobKeyPrefix = "UnityCli.Automation.TestJob.";
        private const string LastPackageJobKey = "UnityCli.Automation.LastPackageJob";
        private const string PackageJobKeyPrefix = "UnityCli.Automation.PackageJob.";
        private static readonly string ProjectPath = Path.GetDirectoryName(Application.dataPath);
        private static readonly Dictionary<string, TestJob> TestJobs = new Dictionary<string, TestJob>();
        private static readonly Dictionary<string, BuildJob> BuildJobs = new Dictionary<string, BuildJob>();
        private static readonly Dictionary<string, PackageJob> PackageJobs = new Dictionary<string, PackageJob>();
        private static TestRunnerApi _testRunner;
        private static TestCallbacks _testCallbacks;
        private static string _activeTestJobId;
        private static string _lastTestJobId;
        private static string _lastBuildJobId;
        private static string _lastPackageJobId;
        private static string _activePackageJobId;

        internal static bool TryExecute(string command, JObject args, out object result)
        {
            result = null;
            if (string.IsNullOrEmpty(command))
            {
                return false;
            }

            var isOwned =
                command.StartsWith("script.", StringComparison.Ordinal) ||
                command.StartsWith("scriptable-object.", StringComparison.Ordinal) ||
                command == MenuExecuteCommand ||
                command.StartsWith("test.", StringComparison.Ordinal) ||
                command.StartsWith("build.", StringComparison.Ordinal) ||
                command.StartsWith("package.", StringComparison.Ordinal);
            if (!isOwned)
            {
                return false;
            }

            try
            {
                result = Dispatch(command, args ?? new JObject());
            }
            catch (ArgumentException exception)
            {
                result = Error(exception.Message);
            }
            catch (Exception exception)
            {
                UnityCliLog.LogError("[Unity CLI] " + command + ": " + exception);
                result = Error(exception.Message);
            }
            return true;
        }

        private static object Dispatch(string command, JObject args)
        {
            switch (command)
            {
                case "script.info":
                    return GetScriptInfo(RequireAssetPath(args, "ScriptPath", ".cs"));
                case "script.read":
                    return ReadScript(args);
                case "script.edit":
                    return ApplyScriptEdits(args);
                case "script.validate":
                    return ValidateScript(args);
                case "script.search":
                    return SearchScripts(args);
                case "scriptable-object.types":
                    return GetScriptableObjectTypes(args);
                case "scriptable-object.inspect":
                    return InspectScriptableObject(args);
                case "scriptable-object.create":
                    return CreateScriptableObject(args);
                case MenuExecuteCommand:
                    return ExecuteMenu(args);
                case "test.run":
                    return StartTests(args);
                case "test.job":
                    return GetTestJob(args);
                case "build.info":
                    return GetBuildInfo();
                case "build.targets":
                    return GetBuildTargets();
                case "build.start":
                    return StartBuild(args);
                case "build.job":
                    return GetBuildJob(args);
                case "build.cancel":
                    return CancelBuild(args);
                case "package.list":
                    return StartPackageList(args);
                case "package.add":
                    return StartPackageMutation(args, false);
                case "package.remove":
                    return StartPackageMutation(args, true);
                case "package.job":
                    return GetPackageJob(args);
                default:
                    return Error("Unsupported automation command: " + command);
            }
        }

        private static object GetScriptInfo(string assetPath)
        {
            var script = AssetDatabase.LoadAssetAtPath<MonoScript>(assetPath);
            if (script == null)
            {
                return Error("Script not found or not a MonoScript: " + assetPath);
            }

            var type = script.GetClass();
            var fullPath = ToAbsoluteAssetPath(assetPath);
            var file = new FileInfo(fullPath);
            return Ok(new
            {
                path = assetPath,
                guid = AssetDatabase.AssetPathToGUID(assetPath),
                className = type == null ? script.name : type.Name,
                typeFullName = type == null ? null : type.FullName,
                namespaceName = type == null ? null : type.Namespace,
                assemblyName = type == null ? null : type.Assembly.GetName().Name,
                baseType = type == null || type.BaseType == null ? null : type.BaseType.FullName,
                sizeBytes = file.Exists ? file.Length : 0,
                lineCount = file.Exists ? File.ReadAllLines(fullPath).Length : 0,
                modifiedUtc = file.Exists ? file.LastWriteTimeUtc.ToString("o") : null,
                sha256 = file.Exists ? HashFile(fullPath) : null
            });
        }

        private static object ReadScript(JObject args)
        {
            var assetPath = RequireAssetPath(args, "ScriptPath", ".cs");
            var startLine = GetInt(args, "StartLine", 1);
            var lineCount = GetInt(args, "LineCount", 0);
            var maxBytes = GetInt(args, "MaxBytes", 200000);
            CheckRange(startLine, 1, 1000000, "StartLine");
            CheckRange(lineCount, 0, 1000000, "LineCount");
            CheckRange(maxBytes, 1, 2000000, "MaxBytes");

            var fullPath = ToAbsoluteAssetPath(assetPath);
            var file = new FileInfo(fullPath);
            if (!file.Exists)
            {
                return Error("Script file not found: " + assetPath);
            }
            if (file.Length > 4L * 1024 * 1024)
            {
                return Error("Script is larger than 4 MB; raise the limit in code if this is expected.");
            }

            var lines = File.ReadAllLines(fullPath);
            var firstIndex = Math.Min(startLine - 1, lines.Length);
            var available = lines.Length - firstIndex;
            var taken = lineCount == 0 ? available : Math.Min(lineCount, available);
            var content = string.Join("\n", lines.Skip(firstIndex).Take(taken));
            var byteTruncated = Encoding.UTF8.GetByteCount(content) > maxBytes;
            if (byteTruncated)
            {
                var builder = new StringBuilder(maxBytes);
                var used = 0;
                foreach (var character in content)
                {
                    var size = character > 127 ? 3 : 1;
                    if (used + size > maxBytes)
                    {
                        break;
                    }
                    builder.Append(character);
                    used += size;
                }
                content = builder.ToString();
            }

            return Ok(new
            {
                path = assetPath,
                totalLines = lines.Length,
                startLine = firstIndex + 1,
                returnedLines = byteTruncated ? (content.Length == 0 ? 0 : content.Split('\n').Length) : taken,
                content,
                truncated = byteTruncated || firstIndex + taken < lines.Length
            });
        }

        private static object ApplyScriptEdits(JObject args)
        {
            var assetPath = RequireAssetPath(args, "ScriptPath", ".cs");
            if (EditorApplication.isCompiling || EditorApplication.isUpdating)
            {
                return Error("Wait for script compilation and asset import before editing a script.");
            }
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                return Error("Exit Play Mode before editing a script.");
            }

            var expectedHash = RequireString(args, "ExpectedSha256").Trim();
            if (expectedHash.StartsWith("sha256:", StringComparison.OrdinalIgnoreCase))
            {
                expectedHash = expectedHash.Substring(7).Trim();
            }
            if (!Regex.IsMatch(expectedHash, "^[0-9a-fA-F]{64}$"))
            {
                return Error("ExpectedSha256 must be a 64-character SHA-256 hex digest.");
            }

            var editTokens = args?["Edits"] as JArray;
            if (editTokens == null || editTokens.Count == 0)
            {
                return Error("Edits must be a non-empty array of {StartLine, StartColumn, EndLine, EndColumn, NewText} objects.");
            }
            if (editTokens.Count > 100)
            {
                return Error("At most 100 edits are accepted per request.");
            }

            var fullPath = ToAbsoluteAssetPath(assetPath);
            var file = new FileInfo(fullPath);
            if (!file.Exists)
            {
                return Error("Script file not found: " + assetPath);
            }
            if (file.Length > 4L * 1024 * 1024)
            {
                return Error("Script is larger than 4 MB; edit it outside Unity CLI.");
            }
            if ((file.Attributes & FileAttributes.ReadOnly) != 0)
            {
                return Error("Script is read-only: " + assetPath);
            }

            var originalBytes = File.ReadAllBytes(fullPath);
            var actualHash = HashBytes(originalBytes);
            if (!string.Equals(actualHash, expectedHash, StringComparison.OrdinalIgnoreCase))
            {
                return Error("Script changed since it was read: expected SHA-256 " + expectedHash +
                    ", actual " + actualHash + ". Re-read script.read and retry.");
            }

            var hasBom = originalBytes.Length >= 3 &&
                originalBytes[0] == 0xEF && originalBytes[1] == 0xBB && originalBytes[2] == 0xBF;
            string original;
            string decodeError;
            if (!TryDecodeUtf8(originalBytes, hasBom, out original, out decodeError))
            {
                return Error("Script is not valid UTF-8: " + decodeError);
            }

            var edits = new List<ScriptTextEdits.Edit>();
            for (var index = 0; index < editTokens.Count; index++)
            {
                var token = editTokens[index] as JObject;
                if (token == null)
                {
                    return Error("Edits[" + index + "] must be an object.");
                }
                var startLine = GetInt(token, "StartLine", -1);
                var startColumn = GetInt(token, "StartColumn", -1);
                var endLine = GetInt(token, "EndLine", -1);
                var endColumn = GetInt(token, "EndColumn", -1);
                if (startLine < 1 || startColumn < 1 || endLine < 1 || endColumn < 1)
                {
                    return Error("Edits[" + index + "] requires positive StartLine, StartColumn, EndLine and EndColumn.");
                }
                edits.Add(new ScriptTextEdits.Edit
                {
                    StartLine = startLine,
                    StartColumn = startColumn,
                    EndLine = endLine,
                    EndColumn = endColumn,
                    NewText = GetString(token, "NewText", "") ?? ""
                });
            }

            string updated;
            try
            {
                updated = ScriptTextEdits.Apply(original, edits);
            }
            catch (ArgumentException exception)
            {
                return Error(exception.Message);
            }
            if (string.Equals(updated, original, StringComparison.Ordinal))
            {
                return Error("Edits do not change the file content.");
            }

            var encoding = new UTF8Encoding(hasBom);
            var body = encoding.GetBytes(updated);
            var newBytes = hasBom ? encoding.GetPreamble().Concat(body).ToArray() : body;
            var currentHash = HashBytes(File.ReadAllBytes(fullPath));
            if (!string.Equals(currentHash, actualHash, StringComparison.OrdinalIgnoreCase))
            {
                return Error("Script changed during the edit: expected SHA-256 " + actualHash +
                    ", actual " + currentHash + ". No bytes were written.");
            }
            var writeError = WriteFileAtomically(fullPath, newBytes);
            if (writeError != null)
            {
                return Error("Could not write script: " + writeError);
            }

            var expectedNewHash = HashBytes(newBytes);
            var writtenHash = HashBytes(File.ReadAllBytes(fullPath));
            if (!string.Equals(expectedNewHash, writtenHash, StringComparison.OrdinalIgnoreCase))
            {
                return Error("Script changed after replacement: " + assetPath + ". Current SHA-256: " + writtenHash +
                    ". Re-read the script before trying again.");
            }

            string reimportError = null;
            try
            {
                AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceUpdate);
            }
            catch (Exception exception)
            {
                reimportError = exception.Message;
                UnityCliLog.LogError("[Unity CLI] Reimport " + assetPath + ": " + exception);
            }

            return Ok(new
            {
                path = assetPath,
                oldSha256 = actualHash,
                newSha256 = writtenHash,
                editsApplied = edits.Count,
                bytesBefore = originalBytes.Length,
                bytesAfter = newBytes.Length,
                lineCount = ScriptTextEdits.CountLines(updated),
                reimportRequested = true,
                reimportError
            });
        }

        private static object ValidateScript(JObject args)
        {
            var assetPath = RequireAssetPath(args, "ScriptPath", ".cs");
            var fullPath = ToAbsoluteAssetPath(assetPath);
            var file = new FileInfo(fullPath);
            if (!file.Exists)
            {
                return Error("Script file not found: " + assetPath);
            }
            if (file.Length > 4L * 1024 * 1024)
            {
                return Error("Script is larger than 4 MB; validate it outside Unity CLI.");
            }

            var bytes = File.ReadAllBytes(fullPath);
            var hasBom = bytes.Length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF;
            string text;
            string decodeError;
            var utf8Valid = TryDecodeUtf8(bytes, hasBom, out text, out decodeError);
            var lineCount = 0;
            var crlfLines = 0;
            var lfLines = 0;
            var trailingNewline = false;
            if (utf8Valid)
            {
                lineCount = ScriptTextEdits.CountLines(text);
                for (var index = 0; index < text.Length; index++)
                {
                    if (text[index] != '\n')
                    {
                        continue;
                    }
                    if (index > 0 && text[index - 1] == '\r')
                    {
                        crlfLines++;
                    }
                    else
                    {
                        lfLines++;
                    }
                }
                trailingNewline = text.EndsWith("\n", StringComparison.Ordinal);
            }

            return Ok(new
            {
                path = assetPath,
                supported = false,
                syntaxValidated = false,
                sha256 = HashBytes(bytes),
                sizeBytes = bytes.Length,
                reason = "Unity 2020.3 has no in-process C# parser. Syntax and type checking only happen when Unity compiles the whole assembly after import, so a file-local 'validate' cannot prove that the script compiles and must not be reported as one.",
                hint = "Use script.edit with ExpectedSha256 for guarded edits, then editor.compile and console.read to inspect real compiler diagnostics.",
                checks = new
                {
                    utf8Valid,
                    decodeError,
                    hasByteOrderMark = hasBom,
                    lineCount,
                    crlfLines,
                    lfLines,
                    mixedLineEndings = crlfLines > 0 && lfLines > 0,
                    trailingNewline
                }
            });
        }

        private static object SearchScripts(JObject args)
        {
            var pattern = RequireString(args, "Pattern");
            var under = GetString(args, "Under", "Assets") ?? "Assets";
            if (!IsAssetPath(under))
            {
                return Error("Under must be an Assets/... path.");
            }
            var limit = Math.Min(GetInt(args, "Limit", 100), 500);
            var maxFiles = Math.Min(GetInt(args, "MaxFiles", 5000), 20000);
            var ignoreCase = GetBool(args, "IgnoreCase", false);
            CheckRange(limit, 1, 500, "Limit");
            CheckRange(maxFiles, 1, 20000, "MaxFiles");

            Regex regex;
            try
            {
                var options = RegexOptions.CultureInvariant | (ignoreCase ? RegexOptions.IgnoreCase : RegexOptions.None);
                regex = new Regex(pattern, options, TimeSpan.FromSeconds(2));
            }
            catch (ArgumentException exception)
            {
                return Error("Invalid regular expression: " + exception.Message);
            }

            var searchRoot = ToAbsoluteAssetPath(under);
            IEnumerable<string> files;
            if (File.Exists(searchRoot))
            {
                files = new[] { searchRoot };
            }
            else if (Directory.Exists(searchRoot))
            {
                files = Directory.EnumerateFiles(searchRoot, "*.cs", SearchOption.AllDirectories);
            }
            else
            {
                return Error("Search path not found: " + under);
            }

            var matches = new List<object>();
            var filesScanned = 0;
            var truncated = false;
            foreach (var filePath in files)
            {
                if (filesScanned >= maxFiles)
                {
                    truncated = true;
                    break;
                }
                var info = new FileInfo(filePath);
                if (!info.Exists || info.Length > 2L * 1024 * 1024)
                {
                    continue;
                }
                filesScanned++;
                var lines = File.ReadAllLines(filePath);
                for (var index = 0; index < lines.Length; index++)
                {
                    Match match;
                    try
                    {
                        match = regex.Match(lines[index]);
                    }
                    catch (RegexMatchTimeoutException)
                    {
                        return Error("Regular expression timed out near file: " + ToAssetPath(filePath));
                    }
                    if (!match.Success)
                    {
                        continue;
                    }
                    if (matches.Count >= limit)
                    {
                        truncated = true;
                        break;
                    }
                    matches.Add(new
                    {
                        path = ToAssetPath(filePath),
                        line = index + 1,
                        column = match.Index + 1,
                        text = Truncate(lines[index].Trim(), 300)
                    });
                }
                if (truncated)
                {
                    break;
                }
            }

            return Ok(new { matches, truncated, filesScanned });
        }

        private static object GetScriptableObjectTypes(JObject args)
        {
            var filter = GetString(args, "Filter");
            var limit = GetInt(args, "Limit", 100);
            CheckRange(limit, 1, 1000, "Limit");

            var names = AllTypes()
                .Where(type => typeof(ScriptableObject).IsAssignableFrom(type) &&
                    !type.IsAbstract && !type.ContainsGenericParameters)
                .Select(type => type.FullName)
                .Where(name => !string.IsNullOrEmpty(name))
                .Where(name => string.IsNullOrEmpty(filter) ||
                    name.IndexOf(filter, StringComparison.OrdinalIgnoreCase) >= 0)
                .OrderBy(name => name, StringComparer.Ordinal)
                .ToArray();
            return Ok(new { types = names.Take(limit).ToArray(), total = names.Length, truncated = names.Length > limit });
        }

        private static object InspectScriptableObject(JObject args)
        {
            var assetPath = RequireAssetPath(args, "AssetPath", ".asset");
            var depth = GetInt(args, "Depth", 2);
            var limit = GetInt(args, "Limit", 200);
            CheckRange(depth, 0, 16, "Depth");
            CheckRange(limit, 1, 2000, "Limit");

            var target = AssetDatabase.LoadMainAssetAtPath(assetPath) as ScriptableObject;
            if (target == null)
            {
                return Error("Asset is missing or is not a ScriptableObject: " + assetPath);
            }

            var properties = new List<object>();
            var truncated = false;
            try
            {
                var serialized = new SerializedObject(target);
                var iterator = serialized.GetIterator();
                var enterChildren = true;
                while (iterator.NextVisible(enterChildren))
                {
                    if (properties.Count >= limit)
                    {
                        truncated = true;
                        break;
                    }
                    properties.Add(DescribeProperty(iterator));
                    enterChildren = iterator.depth < depth;
                }
            }
            catch (Exception exception)
            {
                UnityCliLog.LogError("[Unity CLI] Inspect " + assetPath + ": " + exception);
                return Error("Could not read serialized fields: " + exception.Message);
            }

            return Ok(new
            {
                path = assetPath,
                guid = AssetDatabase.AssetPathToGUID(assetPath),
                name = target.name,
                typeFullName = target.GetType().FullName,
                properties,
                truncated
            });
        }

        private static object CreateScriptableObject(JObject args)
        {
            var typeName = RequireString(args, "TypeName");
            var assetPath = RequireAssetPath(args, "AssetPath", ".asset");
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                return Error("Exit Play Mode before creating a ScriptableObject asset.");
            }

            var matches = AllTypes()
                .Where(type => typeof(ScriptableObject).IsAssignableFrom(type) &&
                    !type.IsAbstract && !type.ContainsGenericParameters)
                .Where(type => string.Equals(type.FullName, typeName, StringComparison.Ordinal) ||
                    string.Equals(type.Name, typeName, StringComparison.Ordinal))
                .ToArray();
            if (matches.Length == 0)
            {
                return Error("ScriptableObject type not found: " + typeName);
            }
            if (matches.Length > 1)
            {
                return Error("Type name is ambiguous; use the namespace-qualified name: " +
                    string.Join(", ", matches.Take(10).Select(type => type.FullName).ToArray()));
            }

            var selectedType = matches[0];
            if (selectedType.GetConstructor(BindingFlags.Public | BindingFlags.Instance, null, Type.EmptyTypes, null) == null)
            {
                return Error("Type has no public parameterless constructor: " + selectedType.FullName);
            }

            var fullPath = ToAbsoluteAssetPath(assetPath);
            if (File.Exists(fullPath))
            {
                return Error("Asset already exists: " + assetPath);
            }
            var folder = Path.GetDirectoryName(fullPath);
            var folderAssetPath = folder == null ? null : ToAssetPath(folder);
            if (string.IsNullOrEmpty(folderAssetPath) || !AssetDatabase.IsValidFolder(folderAssetPath))
            {
                return Error("Parent folder does not exist under Assets/: " + assetPath);
            }

            var instance = ScriptableObject.CreateInstance(selectedType);
            if (instance == null)
            {
                return Error("Unity could not instantiate: " + selectedType.FullName);
            }
            instance.name = Path.GetFileNameWithoutExtension(assetPath);
            try
            {
                AssetDatabase.CreateAsset(instance, assetPath);
                if (AssetDatabase.LoadMainAssetAtPath(assetPath) == null)
                {
                    throw new InvalidOperationException("Unity did not create the asset: " + assetPath);
                }
                AssetDatabase.SaveAssets();
            }
            catch (Exception)
            {
                UnityEngine.Object.DestroyImmediate(instance);
                if (File.Exists(fullPath))
                {
                    AssetDatabase.DeleteAsset(assetPath);
                }
                throw;
            }

            return Ok(new
            {
                path = assetPath,
                guid = AssetDatabase.AssetPathToGUID(assetPath),
                name = instance.name,
                typeFullName = selectedType.FullName
            });
        }

        private static object ExecuteMenu(JObject args)
        {
            var menuPath = RequireString(args, "MenuPath");
            if (EditorApplication.isCompiling || EditorApplication.isUpdating)
            {
                return Error("Wait for script compilation and asset import before executing a menu item.");
            }
            if (!EditorApplication.ExecuteMenuItem(menuPath))
            {
                return Error("Menu item was not found, disabled, or threw: " + menuPath);
            }
            return Ok(new { menuPath, executed = true });
        }

        private static object StartTests(JObject args)
        {
            if (EditorApplication.isCompiling || EditorApplication.isUpdating)
            {
                return Error("Wait for script compilation and asset import before running tests.");
            }
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                return Error("Exit Play Mode before starting a test run.");
            }
            if (_activeTestJobId != null &&
                TestJobs.TryGetValue(_activeTestJobId, out var active) &&
                active.Status == "running")
            {
                return Error("A test run is already active: " + _activeTestJobId);
            }

            var modeText = GetString(args, "Mode", "EditMode") ?? "EditMode";
            TestMode mode;
            switch (modeText.ToLowerInvariant())
            {
                case "editmode":
                    mode = TestMode.EditMode;
                    break;
                case "playmode":
                    mode = TestMode.PlayMode;
                    break;
                default:
                    return Error("Mode must be EditMode or PlayMode; start separate jobs to run both.");
            }

            var filter = new Filter
            {
                testMode = mode,
                testNames = EmptyToNull(GetStrings(args, "TestNames")),
                groupNames = EmptyToNull(GetStrings(args, "GroupNames")),
                categoryNames = EmptyToNull(GetStrings(args, "CategoryNames")),
                assemblyNames = EmptyToNull(GetStrings(args, "AssemblyNames"))
            };
            var settings = new ExecutionSettings(filter);
            var job = new TestJob
            {
                Id = NextJobId("test"),
                Mode = modeText,
                Status = "running",
                StartedUtc = DateTime.UtcNow.ToString("o")
            };

            try
            {
                EnsureTestRunner();
                _activeTestJobId = job.Id;
                _lastTestJobId = job.Id;
                TestJobs[job.Id] = job;
                TrimJobs(TestJobs, job.Id);
                PersistTestJob(job, true);
                job.RunnerId = _testRunner.Execute(settings);
                PersistTestJob(job, true);
            }
            catch (Exception exception)
            {
                job.Status = "error";
                job.Error = exception.Message;
                job.FinishedUtc = DateTime.UtcNow.ToString("o");
                _activeTestJobId = null;
                PersistTestJob(job, false);
                UnityCliLog.LogError("[Unity CLI] test.run: " + exception);
                return Error("Could not start tests: " + exception.Message);
            }

            return Ok(DescribeTestJob(job, true));
        }

        private static object GetTestJob(JObject args)
        {
            var jobId = GetString(args, "JobId");
            if (string.IsNullOrEmpty(jobId))
            {
                jobId = _lastTestJobId;
            }
            if (string.IsNullOrEmpty(jobId) || !TestJobs.TryGetValue(jobId, out var job))
            {
                return Error("Unknown test job" +
                    (TestJobs.Count == 0 ? ". No test run has started in this Editor session." :
                    ". Known jobs: " + string.Join(", ", TestJobs.Keys.ToArray())));
            }
            var includeDetails = GetBool(args, "IncludeDetails", false);
            return Ok(DescribeTestJob(job, includeDetails));
        }

        private static object GetBuildInfo()
        {
            var target = EditorUserBuildSettings.activeBuildTarget;
            var group = BuildPipeline.GetBuildTargetGroup(target);
            return Ok(new
            {
                activeBuildTarget = target.ToString(),
                buildTargetGroup = group.ToString(),
                targetSupported = BuildPipeline.IsBuildTargetSupported(group, target),
                development = EditorUserBuildSettings.development,
                allowDebugging = EditorUserBuildSettings.allowDebugging,
                productName = PlayerSettings.productName,
                companyName = PlayerSettings.companyName,
                applicationIdentifier = PlayerSettings.applicationIdentifier,
                bundleVersion = PlayerSettings.bundleVersion,
                scriptingBackend = SafePlayerSetting(() => PlayerSettings.GetScriptingBackend(group).ToString()),
                apiCompatibilityLevel = SafePlayerSetting(() => PlayerSettings.GetApiCompatibilityLevel(group).ToString()),
                scenes = EditorBuildSettings.scenes.Select(scene => new { path = scene.path, enabled = scene.enabled }).ToArray(),
                enabledSceneCount = EditorBuildSettings.scenes.Count(scene => scene.enabled)
            });
        }

        private static object GetBuildTargets()
        {
            var targets = new List<object>();
            foreach (BuildTarget target in Enum.GetValues(typeof(BuildTarget)))
            {
                if (target == BuildTarget.NoTarget)
                {
                    continue;
                }
                string groupName;
                bool supported;
                try
                {
                    var group = BuildPipeline.GetBuildTargetGroup(target);
                    if (group == BuildTargetGroup.Unknown)
                    {
                        continue;
                    }
                    groupName = group.ToString();
                    supported = BuildPipeline.IsBuildTargetSupported(group, target);
                }
                catch (Exception)
                {
                    continue;
                }
                targets.Add(new
                {
                    name = target.ToString(),
                    group = groupName,
                    supported,
                    active = target == EditorUserBuildSettings.activeBuildTarget
                });
            }
            return Ok(new { targets });
        }

        private static object StartBuild(JObject args)
        {
            if (EditorApplication.isCompiling || EditorApplication.isUpdating)
            {
                return Error("Wait for script compilation and asset import before starting a build.");
            }
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                return Error("Exit Play Mode before starting a build.");
            }

            var targetText = RequireString(args, "Target");
            if (!Enum.GetValues(typeof(BuildTarget)).Cast<BuildTarget>()
                .Any(value => string.Equals(value.ToString(), targetText, StringComparison.OrdinalIgnoreCase)))
            {
                return Error("Unknown build target: " + targetText + ". Run build.targets to list names.");
            }
            var target = (BuildTarget)Enum.Parse(typeof(BuildTarget), targetText, true);
            if (target == BuildTarget.NoTarget)
            {
                return Error("NoTarget cannot be built.");
            }
            var group = BuildPipeline.GetBuildTargetGroup(target);
            if (!BuildPipeline.IsBuildTargetSupported(group, target))
            {
                return Error("Build target is not installed in this Editor: " + target + " (" + group + ").");
            }

            var outputPath = NormalizeProjectRelativePath(RequireString(args, "OutputPath"));
            var development = GetBool(args, "Development", false);
            var allowDebugging = GetBool(args, "AllowDebugging", false);
            if (allowDebugging && !development)
            {
                return Error("AllowDebugging requires Development=true.");
            }

            var scenePaths = GetStrings(args, "ScenePaths");
            if (scenePaths == null || scenePaths.Length == 0)
            {
                scenePaths = EditorBuildSettings.scenes.Where(scene => scene.enabled).Select(scene => scene.path).ToArray();
            }
            if (scenePaths.Length == 0)
            {
                return Error("No scenes selected. Enable Build Settings scenes or pass ScenePaths.");
            }
            foreach (var scenePath in scenePaths)
            {
                if (!IsAssetPath(scenePath, ".unity"))
                {
                    return Error("ScenePaths must be project-relative .unity paths under Assets/: " + scenePath);
                }
                if (!File.Exists(ToAbsoluteAssetPath(scenePath)))
                {
                    return Error("Scene not found: " + scenePath);
                }
            }

            var quoteViolation = scenePaths.Where(path => path.IndexOf('"') >= 0).ToArray();
            if (quoteViolation.Length > 0)
            {
                return Error("Scene paths must not contain quotes: " + quoteViolation[0]);
            }

            var job = new BuildJob
            {
                Id = NextJobId("build"),
                Status = "queued",
                Target = target.ToString(),
                OutputPath = outputPath,
                ScenePaths = scenePaths,
                Development = development,
                AllowDebugging = allowDebugging,
                StartedUtc = DateTime.UtcNow.ToString("o")
            };
            BuildJobs[job.Id] = job;
            _lastBuildJobId = job.Id;
            TrimJobs(BuildJobs, job.Id);
            var jobId = job.Id;
            EditorApplication.delayCall += () => ExecuteBuild(jobId);
            return Ok(DescribeBuildJob(job));
        }

        private static object GetBuildJob(JObject args)
        {
            var jobId = GetString(args, "JobId");
            if (string.IsNullOrEmpty(jobId))
            {
                jobId = _lastBuildJobId;
            }
            if (string.IsNullOrEmpty(jobId) || !BuildJobs.TryGetValue(jobId, out var job))
            {
                return Error("Unknown build job" +
                    (BuildJobs.Count == 0 ? ". No build has started in this Editor session." :
                    ". Known jobs: " + string.Join(", ", BuildJobs.Keys.ToArray())));
            }
            return Ok(DescribeBuildJob(job));
        }

        private static object CancelBuild(JObject args)
        {
            var jobId = GetString(args, "JobId");
            if (string.IsNullOrEmpty(jobId))
            {
                jobId = _lastBuildJobId;
            }
            if (string.IsNullOrEmpty(jobId) || !BuildJobs.TryGetValue(jobId, out var job))
            {
                return Error("Unknown build job.");
            }
            if (job.Status == "running")
            {
                return Error("BuildPipeline.BuildPlayer cannot be cancelled once it has started.");
            }
            if (job.Status != "queued")
            {
                return Error("Build job is already " + job.Status + ".");
            }
            job.Status = "cancelled";
            job.FinishedUtc = DateTime.UtcNow.ToString("o");
            return Ok(DescribeBuildJob(job));
        }

        private static object StartPackageList(JObject args)
        {
            var running = FindRunningPackageJob();
            if (running != null)
            {
                return Error("A package request is already running (" + running.Id + ", " + running.Action +
                    "). Poll package.job before starting another request.");
            }
            var offline = GetBool(args, "Offline", true);
            var includeIndirect = GetBool(args, "IncludeIndirect", false);
            ListRequest request;
            try
            {
                request = Client.List(offline, includeIndirect);
            }
            catch (Exception exception)
            {
                UnityCliLog.LogError("[Unity CLI] package.list: " + exception);
                return Error("Could not start package listing: " + exception.Message);
            }

            var job = new PackageJob
            {
                Id = NextJobId("package"),
                Action = "list",
                Status = "running",
                Offline = offline,
                IncludeIndirect = includeIndirect,
                Request = request,
                StartedUtc = DateTime.UtcNow.ToString("o")
            };
            PackageJobs[job.Id] = job;
            _lastPackageJobId = job.Id;
            TrimJobs(PackageJobs, job.Id);
            return Ok(DescribePackageJob(job));
        }

        private static object StartPackageMutation(JObject args, bool remove)
        {
            if (EditorApplication.isCompiling || EditorApplication.isUpdating)
            {
                return Error("Wait for script compilation and asset import before changing packages.");
            }
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                return Error("Exit Play Mode before changing packages.");
            }
            var running = FindRunningPackageJob();
            if (running != null)
            {
                return Error("A package request is already running (" + running.Id + ", " + running.Action +
                    "). Poll package.job before starting another request.");
            }

            var identifier = remove ? RequireString(args, "Name") : RequireString(args, "Identifier");
            if (identifier.Length > 256)
            {
                return Error((remove ? "Name" : "Identifier") + " is longer than 256 characters.");
            }
            if (identifier.Any(char.IsControl))
            {
                return Error((remove ? "Name" : "Identifier") + " must not contain control characters.");
            }
            if (remove && identifier.Any(char.IsWhiteSpace))
            {
                return Error("Name must be a package name without whitespace.");
            }
            if (remove && identifier.IndexOf('@') >= 0)
            {
                return Error("Name must be a package name without @version.");
            }

            Request request;
            try
            {
                request = remove ? (Request)Client.Remove(identifier) : (Request)Client.Add(identifier);
            }
            catch (Exception exception)
            {
                UnityCliLog.LogError("[Unity CLI] package." + (remove ? "remove" : "add") + ": " + exception);
                return Error("Could not start package " + (remove ? "remove" : "add") + ": " + exception.Message);
            }

            var job = new PackageJob
            {
                Id = NextJobId("package"),
                Action = remove ? "remove" : "add",
                Target = identifier,
                Status = "running",
                Offline = false,
                IncludeIndirect = false,
                Request = request,
                StartedUtc = DateTime.UtcNow.ToString("o")
            };
            PackageJobs[job.Id] = job;
            _lastPackageJobId = job.Id;
            _activePackageJobId = job.Id;
            TrimJobs(PackageJobs, job.Id);
            PersistPackageJob(job);
            return Ok(DescribePackageJob(job));
        }

        private static PackageJob FindRunningPackageJob()
        {
            return PackageJobs.Values.FirstOrDefault(job => job.Status == "running");
        }

        private static object GetPackageJob(JObject args)
        {
            var jobId = GetString(args, "JobId");
            if (string.IsNullOrEmpty(jobId))
            {
                jobId = _lastPackageJobId;
            }
            if (string.IsNullOrEmpty(jobId) || !PackageJobs.TryGetValue(jobId, out var job))
            {
                return Error("Unknown package job" +
                    (PackageJobs.Count == 0 ? ". No package request has started in this Editor session." :
                    ". Known jobs: " + string.Join(", ", PackageJobs.Keys.ToArray())));
            }
            UpdatePackageJob(job);
            return Ok(DescribePackageJob(job));
        }

        private static void EnsureTestRunner()
        {
            if (_testRunner != null && _testCallbacks != null)
            {
                return;
            }
            _testCallbacks = new TestCallbacks();
            _testRunner = ScriptableObject.CreateInstance<TestRunnerApi>();
            _testRunner.hideFlags = HideFlags.HideAndDontSave;
            _testRunner.RegisterCallbacks(_testCallbacks);
        }

        // PlayMode 测试会触发域重载；SessionState 保存的任务让回调和轮询跨重载继续可用。
        [InitializeOnLoadMethod]
        private static void RestoreTestJobAfterReload()
        {
            var lastJobId = SessionState.GetString(LastTestJobKey, "");
            if (string.IsNullOrEmpty(lastJobId) || TestJobs.ContainsKey(lastJobId))
            {
                return;
            }
            var snapshot = SessionState.GetString(TestJobKeyPrefix + lastJobId, "");
            if (string.IsNullOrEmpty(snapshot))
            {
                return;
            }
            try
            {
                var job = JsonConvert.DeserializeObject<TestJob>(snapshot);
                if (job == null || string.IsNullOrEmpty(job.Id))
                {
                    return;
                }
                TestJobs[job.Id] = job;
                _lastTestJobId = job.Id;
                if (SessionState.GetString(ActiveTestJobKey, "") == job.Id && job.Status == "running")
                {
                    _activeTestJobId = job.Id;
                    EnsureTestRunner();
                }
            }
            catch (Exception exception)
            {
                UnityCliLog.LogError("[Unity CLI] Restore test job: " + exception.Message);
            }
        }

        private static void PersistTestJob(TestJob job, bool active)
        {
            try
            {
                SessionState.SetString(TestJobKeyPrefix + job.Id, JsonConvert.SerializeObject(job));
                SessionState.SetString(LastTestJobKey, job.Id);
                if (active)
                {
                    SessionState.SetString(ActiveTestJobKey, job.Id);
                }
                else if (SessionState.GetString(ActiveTestJobKey, "") == job.Id)
                {
                    SessionState.EraseString(ActiveTestJobKey);
                }
            }
            catch (Exception exception)
            {
                UnityCliLog.LogError("[Unity CLI] Persist test job: " + exception.Message);
            }
        }

        // 包增删会触发域重载；保存最后一个写任务，使 package.job 在重载后仍能说明结果。
        [InitializeOnLoadMethod]
        private static void RestorePackageJobAfterReload()
        {
            var lastJobId = SessionState.GetString(LastPackageJobKey, "");
            if (string.IsNullOrEmpty(lastJobId) || PackageJobs.ContainsKey(lastJobId))
            {
                return;
            }
            var snapshot = SessionState.GetString(PackageJobKeyPrefix + lastJobId, "");
            if (string.IsNullOrEmpty(snapshot))
            {
                return;
            }
            try
            {
                var job = JsonConvert.DeserializeObject<PackageJob>(snapshot);
                if (job == null || string.IsNullOrEmpty(job.Id))
                {
                    return;
                }
                job.Request = null;
                if (job.Status == "running")
                {
                    job.Status = "unknown";
                    job.Error = "Unity reloaded before the package request completed. Run package.list to confirm the installed package set.";
                    PersistPackageJob(job);
                }
                PackageJobs[job.Id] = job;
                _lastPackageJobId = job.Id;
            }
            catch (Exception exception)
            {
                UnityCliLog.LogError("[Unity CLI] Restore package job: " + exception.Message);
            }
        }

        private static void PersistPackageJob(PackageJob job)
        {
            try
            {
                SessionState.SetString(PackageJobKeyPrefix + job.Id, JsonConvert.SerializeObject(job));
                SessionState.SetString(LastPackageJobKey, job.Id);
            }
            catch (Exception exception)
            {
                UnityCliLog.LogError("[Unity CLI] Persist package job: " + exception.Message);
            }
        }

        private static void ExecuteBuild(string jobId)
        {
            if (!BuildJobs.TryGetValue(jobId, out var job) || job.Status != "queued")
            {
                return;
            }
            job.Status = "running";
            job.StartedUtc = DateTime.UtcNow.ToString("o");
            var started = DateTime.UtcNow;
            try
            {
                if (EditorApplication.isPlayingOrWillChangePlaymode)
                {
                    throw new InvalidOperationException("Unity entered Play Mode before the build started.");
                }
                var fullOutputPath = Path.GetFullPath(Path.Combine(ProjectPath, job.OutputPath.Replace('/', Path.DirectorySeparatorChar)));
                var directory = Path.GetDirectoryName(fullOutputPath);
                if (!string.IsNullOrEmpty(directory))
                {
                    Directory.CreateDirectory(directory);
                }
                var options = new BuildPlayerOptions
                {
                    scenes = job.ScenePaths,
                    locationPathName = fullOutputPath,
                    target = (BuildTarget)Enum.Parse(typeof(BuildTarget), job.Target),
                    targetGroup = BuildPipeline.GetBuildTargetGroup((BuildTarget)Enum.Parse(typeof(BuildTarget), job.Target)),
                    options = BuildOptions.None |
                        (job.Development ? BuildOptions.Development : BuildOptions.None) |
                        (job.AllowDebugging ? BuildOptions.AllowDebugging : BuildOptions.None)
                };
                var report = BuildPipeline.BuildPlayer(options);
                if (report == null)
                {
                    throw new InvalidOperationException("BuildPipeline returned no report.");
                }
                job.Result = report.summary.result.ToString();
                job.ReportPath = report.summary.outputPath;
                job.TotalSize = report.summary.totalSize;
                job.TotalErrors = report.summary.totalErrors;
                job.TotalWarnings = report.summary.totalWarnings;
                job.Status = report.summary.result == BuildResult.Succeeded ? "complete" : "failed";
                if (job.Status == "failed")
                {
                    job.Error = "Build finished with " + job.TotalErrors + " error(s).";
                }
            }
            catch (Exception exception)
            {
                UnityCliLog.LogError("[Unity CLI] build " + jobId + ": " + exception);
                job.Status = "error";
                job.Error = exception.Message;
            }
            finally
            {
                job.DurationSeconds = (DateTime.UtcNow - started).TotalSeconds;
                job.FinishedUtc = DateTime.UtcNow.ToString("o");
            }
        }

        private static void UpdatePackageJob(PackageJob job)
        {
            if (job.Status != "running" || job.Request == null)
            {
                return;
            }
            if (!job.Request.IsCompleted)
            {
                return;
            }
            job.FinishedUtc = DateTime.UtcNow.ToString("o");
            var request = job.Request;
            job.Request = null;
            if (request.Status != StatusCode.Success)
            {
                job.Status = "error";
                job.Error = request.Error == null ? "Package Manager request failed." : request.Error.message;
            }
            else if (job.Action == "list")
            {
                var listRequest = request as ListRequest;
                if (listRequest == null || listRequest.Result == null)
                {
                    job.Status = "error";
                    job.Error = "Package list request returned no collection.";
                }
                else
                {
                    job.Packages = listRequest.Result
                        .Select(ToPackageEntry)
                        .OrderBy(package => package.Name, StringComparer.Ordinal)
                        .ToArray();
                    job.Status = "complete";
                }
            }
            else if (job.Action == "add")
            {
                var addRequest = request as AddRequest;
                if (addRequest == null || addRequest.Result == null)
                {
                    job.Status = "error";
                    job.Error = "Package add request returned no package.";
                }
                else
                {
                    job.Package = ToPackageEntry(addRequest.Result);
                    job.Status = "complete";
                }
            }
            else if (job.Action == "remove")
            {
                job.Status = "complete";
            }
            else
            {
                job.Status = "error";
                job.Error = "Unknown package action: " + job.Action;
            }
            if (string.Equals(_activePackageJobId, job.Id, StringComparison.Ordinal))
            {
                _activePackageJobId = null;
            }
            if (job.Action != "list")
            {
                PersistPackageJob(job);
            }
        }

        private static PackageEntry ToPackageEntry(UnityEditor.PackageManager.PackageInfo package)
        {
            return new PackageEntry
            {
                Name = package.name,
                DisplayName = package.displayName,
                Version = package.version,
                Source = package.source.ToString(),
                IsDirectDependency = package.isDirectDependency,
                ResolvedPath = package.resolvedPath
            };
        }

        private static object DescribeTestJob(TestJob job, bool includeDetails)
        {
            return new
            {
                jobId = job.Id,
                runnerId = job.RunnerId,
                mode = job.Mode,
                status = job.Status,
                totalTests = job.TotalTests,
                passed = job.Passed,
                failed = job.Failed,
                skipped = job.Skipped,
                inconclusive = job.Inconclusive,
                startedUtc = job.StartedUtc,
                finishedUtc = job.FinishedUtc,
                durationSeconds = job.DurationSeconds,
                error = job.Error,
                failures = job.Failures.Select(failure => new
                {
                    name = failure.Name,
                    message = failure.Message,
                    stackTrace = includeDetails ? failure.StackTrace : null
                }).ToArray(),
                failuresTruncated = job.FailuresTruncated
            };
        }

        private static object DescribeBuildJob(BuildJob job)
        {
            return new
            {
                jobId = job.Id,
                status = job.Status,
                target = job.Target,
                outputPath = job.OutputPath,
                reportPath = job.ReportPath,
                development = job.Development,
                allowDebugging = job.AllowDebugging,
                scenes = job.ScenePaths,
                result = job.Result,
                totalSize = job.TotalSize,
                totalErrors = job.TotalErrors,
                totalWarnings = job.TotalWarnings,
                startedUtc = job.StartedUtc,
                finishedUtc = job.FinishedUtc,
                durationSeconds = job.DurationSeconds,
                error = job.Error
            };
        }

        private static object DescribePackageJob(PackageJob job)
        {
            return new
            {
                jobId = job.Id,
                action = job.Action,
                target = job.Target,
                status = job.Status,
                offline = job.Offline,
                includeIndirect = job.IncludeIndirect,
                startedUtc = job.StartedUtc,
                finishedUtc = job.FinishedUtc,
                error = job.Error,
                package = job.Package == null ? null : DescribePackageEntry(job.Package),
                packages = job.Packages == null ? null : job.Packages.Select(DescribePackageEntry).ToArray()
            };
        }

        private static object DescribePackageEntry(PackageEntry package)
        {
            return new
            {
                name = package.Name,
                displayName = package.DisplayName,
                version = package.Version,
                source = package.Source,
                isDirectDependency = package.IsDirectDependency,
                resolvedPath = package.ResolvedPath
            };
        }

        private static object DescribeProperty(SerializedProperty property)
        {
            object value = null;
            SerializedPropertyType type = property.propertyType;
            switch (type)
            {
                case SerializedPropertyType.Integer:
                case SerializedPropertyType.LayerMask:
                    value = property.longValue;
                    break;
                case SerializedPropertyType.Boolean:
                    value = property.boolValue;
                    break;
                case SerializedPropertyType.Float:
                    value = property.floatValue;
                    break;
                case SerializedPropertyType.String:
                    value = Truncate(property.stringValue, 500);
                    break;
                case SerializedPropertyType.Color:
                    value = property.colorValue.ToString();
                    break;
                case SerializedPropertyType.Vector2:
                    value = property.vector2Value.ToString();
                    break;
                case SerializedPropertyType.Vector3:
                    value = property.vector3Value.ToString();
                    break;
                case SerializedPropertyType.Vector4:
                    value = property.vector4Value.ToString();
                    break;
                case SerializedPropertyType.Quaternion:
                    value = property.quaternionValue.ToString();
                    break;
                case SerializedPropertyType.Enum:
                    var index = property.enumValueIndex;
                    value = property.enumDisplayNames != null && index >= 0 && index < property.enumDisplayNames.Length
                        ? property.enumDisplayNames[index]
                        : index.ToString();
                    break;
                case SerializedPropertyType.ArraySize:
                    value = property.intValue;
                    break;
                case SerializedPropertyType.Character:
                    value = ((char)property.intValue).ToString();
                    break;
                case SerializedPropertyType.ObjectReference:
                    var reference = property.objectReferenceValue;
                    if (reference != null)
                    {
                        value = new
                        {
                            name = reference.name,
                            type = reference.GetType().FullName,
                            assetPath = AssetDatabase.GetAssetPath(reference),
                            guid = AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(reference))
                        };
                    }
                    break;
            }

            return new
            {
                path = property.propertyPath,
                displayName = property.displayName,
                type = type.ToString(),
                depth = property.depth,
                isArray = property.isArray,
                value
            };
        }

        private sealed class TestCallbacks : ICallbacks
        {
            public void RunStarted(ITestAdaptor testsToRun)
            {
                var job = ActiveTestJob();
                if (job != null && testsToRun != null)
                {
                    job.TotalTests = testsToRun.TestCaseCount;
                }
            }

            public void TestStarted(ITestAdaptor test)
            {
            }

            public void TestFinished(ITestResultAdaptor result)
            {
                if (result == null || result.HasChildren || result.TestStatus != TestStatus.Failed)
                {
                    return;
                }
                var job = ActiveTestJob();
                if (job == null)
                {
                    return;
                }
                if (job.Failures.Count >= 50)
                {
                    job.FailuresTruncated = true;
                    return;
                }
                job.Failures.Add(new TestFailure
                {
                    Name = result.FullName,
                    Message = Truncate(result.Message, 1000),
                    StackTrace = Truncate(result.StackTrace, 2000)
                });
                PersistTestJob(job, true);
            }

            public void RunFinished(ITestResultAdaptor result)
            {
                var job = ActiveTestJob();
                _activeTestJobId = null;
                if (job == null || result == null)
                {
                    return;
                }
                job.TotalTests = Math.Max(job.TotalTests, result.PassCount + result.FailCount + result.SkipCount);
                job.Passed = result.PassCount;
                job.Failed = result.FailCount;
                job.Skipped = result.SkipCount;
                job.Inconclusive = result.InconclusiveCount;
                job.Status = result.ResultState == "Cancelled" ? "cancelled" :
                    result.FailCount > 0 || result.TestStatus == TestStatus.Failed ? "failed" : "complete";
                job.FinishedUtc = DateTime.UtcNow.ToString("o");
                job.DurationSeconds = Math.Max(0, (result.EndTime - result.StartTime).TotalSeconds);
                if (job.Status == "failed" && job.Failed == 0)
                {
                    job.Error = "Test run ended with state " + result.ResultState + ".";
                }
                PersistTestJob(job, false);
            }

            private static TestJob ActiveTestJob()
            {
                if (string.IsNullOrEmpty(_activeTestJobId))
                {
                    return null;
                }
                TestJobs.TryGetValue(_activeTestJobId, out var job);
                return job;
            }
        }

        private sealed class TestJob
        {
            public string Id;
            public string RunnerId;
            public string Mode;
            public string Status;
            public string StartedUtc;
            public string FinishedUtc;
            public string Error;
            public int TotalTests;
            public int Passed;
            public int Failed;
            public int Skipped;
            public int Inconclusive;
            public double DurationSeconds;
            public bool FailuresTruncated;
            public List<TestFailure> Failures = new List<TestFailure>();
        }

        private sealed class TestFailure
        {
            public string Name;
            public string Message;
            public string StackTrace;
        }

        private sealed class BuildJob
        {
            public string Id;
            public string Status;
            public string Target;
            public string OutputPath;
            public string ReportPath;
            public string[] ScenePaths;
            public bool Development;
            public bool AllowDebugging;
            public string Result;
            public ulong TotalSize;
            public int TotalErrors;
            public int TotalWarnings;
            public string StartedUtc;
            public string FinishedUtc;
            public double DurationSeconds;
            public string Error;
        }

        private sealed class PackageJob
        {
            public string Id;
            public string Action;
            public string Target;
            public string Status;
            public bool Offline;
            public bool IncludeIndirect;
            [JsonIgnore]
            public Request Request;
            public PackageEntry Package;
            public PackageEntry[] Packages;
            public string StartedUtc;
            public string FinishedUtc;
            public string Error;
        }

        private sealed class PackageEntry
        {
            public string Name;
            public string DisplayName;
            public string Version;
            public string Source;
            public bool IsDirectDependency;
            public string ResolvedPath;
        }

        private static object Ok(object data)
        {
            return new { ok = true, data };
        }

        private static object Error(string message)
        {
            return new { ok = false, error = message };
        }

        private static string NextJobId(string prefix)
        {
            return prefix + "-" + Guid.NewGuid().ToString("N").Substring(0, 12);
        }

        private static void TrimJobs<T>(Dictionary<string, T> jobs, string preserveId)
        {
            if (jobs.Count <= 20)
            {
                return;
            }
            var finished = jobs.FirstOrDefault(pair =>
                pair.Key != preserveId && pair.Key != _activeTestJobId && pair.Key != _activePackageJobId);
            if (!string.IsNullOrEmpty(finished.Key))
            {
                jobs.Remove(finished.Key);
            }
        }

        private static string RequireString(JObject args, string name)
        {
            var value = GetString(args, name);
            if (string.IsNullOrWhiteSpace(value))
            {
                throw new ArgumentException(name + " is required.");
            }
            return value.Trim();
        }

        private static string RequireAssetPath(JObject args, string name, string extension)
        {
            var value = RequireString(args, name);
            if (!IsAssetPath(value, extension))
            {
                throw new ArgumentException(name + " must be a project-relative " + extension +
                    " path under Assets/, for example Assets/Folder/Name" + extension + ".");
            }
            return value;
        }

        private static string GetString(JObject args, string name, string fallback = null)
        {
            var token = args?[name];
            if (token == null || token.Type == JTokenType.Null)
            {
                return fallback;
            }
            return token.Value<string>();
        }

        private static bool GetBool(JObject args, string name, bool fallback)
        {
            var token = args?[name];
            if (token == null || token.Type == JTokenType.Null)
            {
                return fallback;
            }
            if (token.Type == JTokenType.Boolean)
            {
                return token.Value<bool>();
            }
            bool parsed;
            return bool.TryParse(token.Value<string>(), out parsed) ? parsed : fallback;
        }

        private static int GetInt(JObject args, string name, int fallback)
        {
            var token = args?[name];
            if (token == null || token.Type == JTokenType.Null)
            {
                return fallback;
            }
            int parsed;
            if (token.Type == JTokenType.Integer || int.TryParse(token.Value<string>(), out parsed))
            {
                return token.Value<int>();
            }
            return fallback;
        }

        private static string[] GetStrings(JObject args, string name)
        {
            var token = args?[name];
            if (token == null || token.Type == JTokenType.Null)
            {
                return new string[0];
            }
            if (token.Type == JTokenType.Array)
            {
                return token.Values<string>()
                    .Where(value => !string.IsNullOrWhiteSpace(value))
                    .Select(value => value.Trim())
                    .ToArray();
            }
            var single = token.Value<string>();
            return string.IsNullOrWhiteSpace(single) ? new string[0] : new[] { single.Trim() };
        }

        private static string[] EmptyToNull(string[] values)
        {
            return values == null || values.Length == 0 ? null : values;
        }

        private static void CheckRange(int value, int min, int max, string name)
        {
            if (value < min || value > max)
            {
                throw new ArgumentException(name + " must be between " + min + " and " + max + ".");
            }
        }

        private static bool IsAssetPath(string path, string extension = null)
        {
            if (string.IsNullOrEmpty(path) || !path.StartsWith("Assets/", StringComparison.Ordinal))
            {
                return false;
            }
            if (path.Contains("\\") || path.Contains(":") ||
                path.Split('/').Any(segment => segment.Length == 0 || segment == "." || segment == ".."))
            {
                return false;
            }
            return extension == null || path.EndsWith(extension, StringComparison.OrdinalIgnoreCase);
        }

        private static string ToAbsoluteAssetPath(string assetPath)
        {
            return Path.GetFullPath(Path.Combine(ProjectPath, assetPath.Replace('/', Path.DirectorySeparatorChar)));
        }

        private static string ToAssetPath(string absolutePath)
        {
            var relative = absolutePath.StartsWith(ProjectPath, StringComparison.OrdinalIgnoreCase)
                ? absolutePath.Substring(ProjectPath.Length).TrimStart('\\', '/')
                : absolutePath;
            return relative.Replace('\\', '/');
        }

        private static string NormalizeProjectRelativePath(string path)
        {
            var value = path.Trim();
            if (Path.IsPathRooted(value) || value.IndexOf(':') >= 0)
            {
                throw new ArgumentException("OutputPath must be relative to the Unity project directory.");
            }
            var normalized = value.Replace('\\', '/');
            if (normalized.Split('/').Any(segment => segment.Length == 0 || segment == "." || segment == ".."))
            {
                throw new ArgumentException("OutputPath must not contain empty, '.' or '..' segments.");
            }
            var fullPath = Path.GetFullPath(Path.Combine(ProjectPath, normalized.Replace('/', Path.DirectorySeparatorChar)));
            if (!fullPath.StartsWith(ProjectPath + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            {
                throw new ArgumentException("OutputPath must stay inside the Unity project directory.");
            }
            return normalized;
        }

        private static string SafePlayerSetting(Func<string> read)
        {
            try
            {
                return read();
            }
            catch (Exception)
            {
                return null;
            }
        }

        private static string HashBytes(byte[] bytes)
        {
            using (var sha = SHA256.Create())
            {
                return ToHex(sha.ComputeHash(bytes));
            }
        }

        private static string ToHex(byte[] bytes)
        {
            return BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant();
        }

        private static bool TryDecodeUtf8(byte[] bytes, bool hasBom, out string text, out string error)
        {
            try
            {
                var encoding = new UTF8Encoding(false, true);
                text = hasBom ? encoding.GetString(bytes, 3, bytes.Length - 3) : encoding.GetString(bytes);
                error = null;
                return true;
            }
            catch (DecoderFallbackException exception)
            {
                text = null;
                error = exception.Message;
                return false;
            }
        }

        private static string WriteFileAtomically(string fullPath, byte[] bytes)
        {
            var directory = Path.GetDirectoryName(fullPath);
            var tempPath = Path.Combine(directory ?? ProjectPath,
                Path.GetFileName(fullPath) + ".unitycli-" + Guid.NewGuid().ToString("N") + ".tmp");
            try
            {
                File.WriteAllBytes(tempPath, bytes);
                if (!File.Exists(fullPath))
                {
                    File.Move(tempPath, fullPath);
                    return null;
                }
                try
                {
                    File.Replace(tempPath, fullPath, null);
                }
                catch (Exception)
                {
                    if (File.Exists(tempPath))
                    {
                        File.Copy(tempPath, fullPath, true);
                        try
                        {
                            File.Delete(tempPath);
                        }
                        catch (Exception)
                        {
                        }
                    }
                }
                return null;
            }
            catch (Exception exception)
            {
                try
                {
                    if (File.Exists(tempPath))
                    {
                        File.Delete(tempPath);
                    }
                }
                catch (Exception)
                {
                }
                return exception.Message;
            }
        }

        private static string HashFile(string path)
        {
            using (var stream = File.OpenRead(path))
            using (var sha = SHA256.Create())
            {
                return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
            }
        }

        private static string Truncate(string value, int length)
        {
            if (string.IsNullOrEmpty(value) || value.Length <= length)
            {
                return value;
            }
            return value.Substring(0, length) + "...";
        }

        private static IEnumerable<Type> AllTypes()
        {
            var assemblies = AppDomain.CurrentDomain.GetAssemblies();
            foreach (var assembly in assemblies)
            {
                Type[] types;
                try
                {
                    types = assembly.GetTypes();
                }
                catch (ReflectionTypeLoadException exception)
                {
                    types = exception.Types.Where(type => type != null).ToArray();
                }
                catch (Exception exception)
                {
                    UnityCliLog.LogError("[Unity CLI] Skip assembly " + assembly.GetName().Name + ": " + exception.Message);
                    continue;
                }
                foreach (var type in types)
                {
                    yield return type;
                }
            }
        }
    }

    // Pure text-range editing used by script.edit; intentionally independent of UnityEditor
    // so the line/column and overlap rules can be exercised without an Editor instance.
    internal static class ScriptTextEdits
    {
        internal sealed class Edit
        {
            public int StartLine;
            public int StartColumn;
            public int EndLine;
            public int EndColumn;
            public string NewText;
            public int StartIndex;
            public int EndIndex;
        }

        internal static int CountLines(string text)
        {
            return BuildLineMap(text).Count;
        }

        internal static string Apply(string text, List<Edit> edits)
        {
            if (edits == null || edits.Count == 0)
            {
                throw new ArgumentException("At least one edit is required.");
            }

            var lines = BuildLineMap(text);
            foreach (var edit in edits)
            {
                edit.StartIndex = ResolvePosition(lines, text, edit.StartLine, edit.StartColumn, "Start");
                edit.EndIndex = ResolvePosition(lines, text, edit.EndLine, edit.EndColumn, "End");
                if (edit.StartIndex > edit.EndIndex)
                {
                    throw new ArgumentException("Edit start is after its end.");
                }
            }

            var ordered = edits.OrderBy(edit => edit.StartIndex).ThenBy(edit => edit.EndIndex).ToList();
            for (var index = 1; index < ordered.Count; index++)
            {
                if (ordered[index].StartIndex < ordered[index - 1].EndIndex ||
                    ordered[index].StartIndex == ordered[index - 1].StartIndex)
                {
                    throw new ArgumentException("Edits overlap or share a start position.");
                }
            }

            var builder = new StringBuilder(text);
            for (var index = ordered.Count - 1; index >= 0; index--)
            {
                var edit = ordered[index];
                builder.Remove(edit.StartIndex, edit.EndIndex - edit.StartIndex);
                builder.Insert(edit.StartIndex, edit.NewText ?? "");
            }
            return builder.ToString();
        }

        private static List<Line> BuildLineMap(string text)
        {
            var lines = new List<Line>();
            var index = 0;
            while (index < text.Length)
            {
                var newline = text.IndexOf('\n', index);
                if (newline < 0)
                {
                    lines.Add(new Line { Start = index, ContentLength = text.Length - index });
                    break;
                }
                var contentEnd = newline;
                if (contentEnd > index && text[contentEnd - 1] == '\r')
                {
                    contentEnd--;
                }
                lines.Add(new Line { Start = index, ContentLength = contentEnd - index });
                index = newline + 1;
            }
            return lines;
        }

        private static int ResolvePosition(List<Line> lines, string text, int line, int column, string label)
        {
            if (line == lines.Count + 1 && column == 1)
            {
                return text.Length;
            }
            if (line < 1 || line > lines.Count)
            {
                throw new ArgumentException(label + " line " + line + " is outside 1.." + lines.Count + ".");
            }
            var current = lines[line - 1];
            if (column < 1 || column > current.ContentLength + 1)
            {
                throw new ArgumentException(label + " column " + column + " is outside 1.." +
                    (current.ContentLength + 1) + " on line " + line + ".");
            }
            var position = current.Start + column - 1;
            if (position > 0 && position < text.Length &&
                char.IsHighSurrogate(text[position - 1]) && char.IsLowSurrogate(text[position]))
            {
                throw new ArgumentException(label + " position splits a surrogate pair at line " +
                    line + ", column " + column + ".");
            }
            return position;
        }

        private sealed class Line
        {
            public int Start;
            public int ContentLength;
        }
    }
}
