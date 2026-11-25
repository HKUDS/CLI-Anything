using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.Compilation;
using UnityEditor.SceneManagement;
#if !UNITY_2021_2_OR_NEWER
using UnityEditor.Experimental.SceneManagement;
#endif
using UnityEngine;
using UnityEngine.SceneManagement;

namespace CliAnything.Unity
{
    [InitializeOnLoad]
    internal static class UnityCliBridge
    {
        private static readonly string ProjectPath = Path.GetDirectoryName(Application.dataPath);
        private static readonly string QueuePath = Path.Combine(ProjectPath, "Library", "UnityCli");
        private static double _nextCheck;

        static UnityCliBridge()
        {
            if (!Application.isBatchMode)
            {
                EditorApplication.update += Poll;
            }
        }

        private static void Poll()
        {
            if (EditorApplication.timeSinceStartup < _nextCheck)
            {
                return;
            }
            _nextCheck = EditorApplication.timeSinceStartup + 0.25;
            if (EditorApplication.isCompiling || EditorApplication.isUpdating || !Directory.Exists(QueuePath))
            {
                return;
            }

            try
            {
                foreach (var jobPath in Directory.EnumerateDirectories(QueuePath, "request-*"))
                {
                    var requestPath = Path.Combine(jobPath, "request.json");
                    var responsePath = Path.Combine(jobPath, "response.json");
                    if (!File.Exists(requestPath) || File.Exists(responsePath))
                    {
                        continue;
                    }

                    var result = Execute(File.ReadAllText(requestPath));
                    if (Directory.Exists(jobPath))
                    {
                        var temporaryPath = responsePath + ".tmp";
                        File.WriteAllText(temporaryPath, JsonConvert.SerializeObject(result));
                        File.Move(temporaryPath, responsePath);
                    }
                    break;
                }
            }
            catch (DirectoryNotFoundException exception)
            {
                // CLI 超时或中断时可能先清理该请求目录。
                UnityCliLog.Log("[Unity CLI] " + exception.Message);
            }
            catch (Exception exception)
            {
                UnityCliLog.LogError("[Unity CLI] " + exception);
            }
        }

        private static object Execute(string json)
        {
            try
            {
                var args = JObject.Parse(json);
                var deadline = args.Value<long>("ExpiresAt");
                if (deadline <= DateTimeOffset.UtcNow.ToUnixTimeMilliseconds())
                {
                    return new { ok = false, error = "Request expired or missing." };
                }
                return args.Value<string>("Command") == "batch" ? ExecuteBatch(args, deadline) : ExecuteCommand(args);
            }
            catch (Exception exception)
            {
                UnityCliLog.LogError("[Unity CLI] " + exception);
                return new { ok = false, error = exception.Message };
            }
        }

        private static object ExecuteCommand(JObject args)
        {
            try
            {
                var request = args.ToObject<Request>();
                switch (request.Command)
                {
                    case "status":
                        return new { ok = true, data = GetStatus() };
                    case "scenes":
                        return new { ok = true, data = new { scenes = GetScenes() } };
                    case "asset-info":
                        return GetAssetInfo(request.AssetPath);
                    case "editor.play":
                        EditorApplication.EnterPlaymode();
                        return Accepted();
                    case "editor.stop":
                        EditorApplication.ExitPlaymode();
                        return Accepted();
                    case "editor.pause":
                    case "editor.resume":
                        if (!EditorApplication.isPlaying)
                        {
                            return new { ok = false, error = "Unity is not in Play Mode." };
                        }
                        EditorApplication.isPaused = request.Command == "editor.pause";
                        return Accepted();
                    case "editor.undo":
                        Undo.PerformUndo();
                        return Accepted();
                    case "editor.redo":
                        Undo.PerformRedo();
                        return Accepted();
                    case "editor.tags-layers":
                        return new { ok = true, data = new
                        {
                            tags = UnityEditorInternal.InternalEditorUtility.tags,
                            layers = Enumerable.Range(0, 32)
                                .Select(index => new { index, name = LayerMask.LayerToName(index) })
                                .Where(layer => !string.IsNullOrEmpty(layer.name)).ToArray()
                        } };
                    case "editor.refresh":
                        EditorApplication.update -= RefreshAfterRequest;
                        EditorApplication.update += RefreshAfterRequest;
                        return Accepted();
                    case "editor.compile":
                        EditorApplication.update -= CompileAfterRequest;
                        EditorApplication.update += CompileAfterRequest;
                        return Accepted();
                    case "console.read":
                        return new { ok = true, data = UnityCliConsole.Read(request.Filter, request.Limit) };
                    case "console.clear":
                        UnityCliConsole.Clear();
                        return Accepted();
                    case "scene.hierarchy":
                        return new { ok = true, data = GetHierarchy(request.Limit) };
                    case "scene.build-settings":
                        return new { ok = true, data = new
                        {
                            scenes = EditorBuildSettings.scenes.Select(scene => new { path = scene.path, enabled = scene.enabled }).ToArray()
                        } };
                    case "scene.open":
                        if (EditorApplication.isPlayingOrWillChangePlaymode ||
                            PrefabStageUtility.GetCurrentPrefabStage() != null)
                        {
                            return new { ok = false, error = "Open scenes from Edit Mode outside Prefab Mode." };
                        }
                        if (!request.Additive && Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).Any(scene => scene.isDirty))
                        {
                            return new { ok = false, error = "Save the open scenes before replacing them." };
                        }
                        if (!IsAssetPath(request.AssetPath) || AssetDatabase.GetMainAssetTypeAtPath(request.AssetPath) != typeof(SceneAsset))
                        {
                            return new { ok = false, error = "Expected an existing scene asset under Assets/." };
                        }
                        var opened = EditorSceneManager.OpenScene(request.AssetPath, request.Additive ? OpenSceneMode.Additive : OpenSceneMode.Single);
                        return new { ok = true, data = new { path = opened.path } };
                    case "scene.save":
                        var active = SceneManager.GetActiveScene();
                        if (!active.IsValid() || !active.isLoaded || EditorApplication.isPlayingOrWillChangePlaymode ||
                            PrefabStageUtility.GetCurrentPrefabStage() != null)
                        {
                            return new { ok = false, error = "Saving requires a loaded active scene in Edit Mode outside Prefab Mode." };
                        }
                        var output = request.AssetPath;
                        if (string.IsNullOrEmpty(output))
                        {
                            if (string.IsNullOrEmpty(active.path))
                                return new { ok = false, error = "Save the untitled scene with scene save --output Assets/Scene.unity." };
                            output = active.path;
                        }
                        else
                        {
                            if (!IsAssetPath(output) || !output.EndsWith(".unity", StringComparison.OrdinalIgnoreCase))
                                return new { ok = false, error = "Output must be an unused .unity path under Assets/." };
                            var fullPath = Path.Combine(ProjectPath, output);
                            var folder = output.Substring(0, output.LastIndexOf('/'));
                            if (!AssetDatabase.IsValidFolder(folder) || Directory.Exists(fullPath) || File.Exists(fullPath) ||
                                File.Exists(fullPath + ".meta") || AssetDatabase.LoadMainAssetAtPath(output) != null)
                                return new { ok = false, error = "Output must be unused and its parent folder must already exist." };
                        }
                        return EditorSceneManager.SaveScene(active, output)
                            ? (object)new { ok = true, data = new { path = active.path } }
                            : new { ok = false, error = "Unity did not save the active scene." };
                    case "gameobject.find":
                        CheckLimit(request.Limit);
                        var matches = WalkScenes()
                            .Where(transform => transform.name.IndexOf(request.Filter ?? "", StringComparison.OrdinalIgnoreCase) >= 0)
                            .Take(request.Limit + 1).ToArray();
                        return new { ok = true, data = new
                        {
                            nodes = matches.Take(request.Limit).Select(DescribeNode).ToArray(),
                            truncated = matches.Length > request.Limit
                        } };
                    case "component.list":
                        var target = EditorUtility.InstanceIDToObject(request.ObjectId) as GameObject;
                        if (target == null || !target.scene.IsValid())
                        {
                            return new { ok = false, error = "GameObject ID does not identify a loaded scene object." };
                        }
                        return new { ok = true, data = new { components = GetComponents(target) } };
                    case "prefab.inspect":
                        if (!IsAssetPath(request.AssetPath) || !request.AssetPath.EndsWith(".prefab", StringComparison.OrdinalIgnoreCase))
                        {
                            return new { ok = false, error = "Expected a .prefab asset path under Assets/." };
                        }
                        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(request.AssetPath);
                        if (prefab == null)
                        {
                            return new { ok = false, error = "Prefab not found: " + request.AssetPath };
                        }
                        CheckLimit(request.Limit);
                        var prefabNodes = Walk(new[] { prefab }).Take(request.Limit + 1).ToArray();
                        return new { ok = true, data = new
                        {
                            nodes = prefabNodes.Take(request.Limit).Select(transform => new
                            {
                                node = DescribeNode(transform),
                                components = GetComponents(transform.gameObject)
                            }).ToArray(),
                            truncated = prefabNodes.Length > request.Limit
                        } };
                    case "asset.search":
                        CheckLimit(request.Limit);
                        var found = AssetDatabase.FindAssets(request.Filter ?? "", new[] { "Assets" });
                        return new { ok = true, data = new
                        {
                            assets = found.Take(request.Limit).Select(guid => new { guid, path = AssetDatabase.GUIDToAssetPath(guid) }).ToArray(),
                            truncated = found.Length > request.Limit
                        } };
                    case "asset.dependencies":
                        if (!IsAssetPath(request.AssetPath) || AssetDatabase.GetMainAssetTypeAtPath(request.AssetPath) == null)
                        {
                            return new { ok = false, error = "Asset not found: " + request.AssetPath };
                        }
                        return new { ok = true, data = new { paths = AssetDatabase.GetDependencies(request.AssetPath, false) } };
                    default:
                        if (UnityCliEditing.TryExecute(request.Command, args, out var result) ||
                            UnityCliCameraUi.TryExecute(request.Command, args, out result) ||
                            UnityCliAutomation.TryExecute(request.Command, args, out result) ||
                            UnityCliRendering.TryExecute(request.Command, args, out result))
                        {
                            return result;
                        }
                        return new { ok = false, error = "Unsupported Unity CLI command." };
                }
            }
            catch (Exception exception)
            {
                UnityCliLog.LogError("[Unity CLI] " + exception);
                return new { ok = false, error = exception.Message };
            }
        }

        private static object ExecuteBatch(JObject args, long deadline)
        {
            var commands = args["Commands"] as JArray;
            if (commands == null || commands.Count < 1 || commands.Count > 25 ||
                commands.Any(entry => !(entry is JObject command) || command["Command"]?.Type != JTokenType.String ||
                    string.IsNullOrWhiteSpace(command.Value<string>("Command")) || command.Value<string>("Command") == "batch"))
            {
                return new { ok = false, error = "Expected 1 to 25 command objects with nonempty Command names. Nested batches are unsupported." };
            }

            var results = new List<JObject>();
            foreach (var command in commands.Cast<JObject>())
            {
                if (deadline <= DateTimeOffset.UtcNow.ToUnixTimeMilliseconds())
                {
                    return new { ok = false, error = "Batch deadline expired.", data = new { results } };
                }
                var result = JObject.FromObject(ExecuteCommand(command));
                results.Add(result);
                if (!result.Value<bool>("ok"))
                {
                    return new { ok = false, error = $"Batch stopped after command {results.Count}.", data = new { results } };
                }
            }
            return new { ok = true, data = new { results } };
        }

        private static object Accepted()
        {
            return new { ok = true, data = new { requested = true } };
        }

        private static void RefreshAfterRequest()
        {
            EditorApplication.update -= RefreshAfterRequest;
            AssetDatabase.Refresh();
        }

        private static void CompileAfterRequest()
        {
            EditorApplication.update -= CompileAfterRequest;
            CompilationPipeline.RequestScriptCompilation();
        }

        private static object GetStatus()
        {
            return new
            {
                projectPath = ProjectPath,
                unityVersion = Application.unityVersion,
                buildTarget = EditorUserBuildSettings.activeBuildTarget.ToString(),
                isPlaying = EditorApplication.isPlaying,
                isPaused = EditorApplication.isPaused
            };
        }

        private static void CheckLimit(int limit)
        {
            if (limit < 1 || limit > 2000)
            {
                throw new ArgumentOutOfRangeException(nameof(limit), "Limit must be between 1 and 2000.");
            }

        }

        private static object GetHierarchy(int limit)
        {
            CheckLimit(limit);
            var nodes = WalkScenes().Take(limit + 1).ToArray();
            return new { nodes = nodes.Take(limit).Select(DescribeNode).ToArray(), truncated = nodes.Length > limit };
        }

        private static IEnumerable<Transform> WalkScenes()
        {
            for (var i = 0; i < SceneManager.sceneCount; i++)
            {
                var scene = SceneManager.GetSceneAt(i);
                if (!scene.isLoaded)
                {
                    continue;
                }
                foreach (var transform in Walk(scene.GetRootGameObjects()))
                {
                    yield return transform;
                }
            }
        }

        private static IEnumerable<Transform> Walk(GameObject[] roots)
        {
            var pending = new Stack<Transform>(roots.Reverse().Select(root => root.transform));
            while (pending.Count > 0)
            {
                var transform = pending.Pop();
                yield return transform;
                for (var child = transform.childCount - 1; child >= 0; child--)
                {
                    pending.Push(transform.GetChild(child));
                }
            }
        }

        private static object DescribeNode(Transform transform)
        {
            var gameObject = transform.gameObject;
            return new
            {
                id = gameObject.GetInstanceID(),
                parentId = transform.parent == null ? (int?)null : transform.parent.gameObject.GetInstanceID(),
                name = gameObject.name,
                scene = gameObject.scene.path,
                active = gameObject.activeSelf
            };
        }

        private static string[] GetComponents(GameObject gameObject)
        {
            return gameObject.GetComponents<Component>().Select(component => component == null ? null : component.GetType().FullName).ToArray();
        }

        private static bool IsAssetPath(string path)
        {
            return !string.IsNullOrEmpty(path) && path.StartsWith("Assets/", StringComparison.Ordinal) &&
                !path.Contains("\\") && !path.Split('/').Any(segment => segment == "" || segment == "." || segment == "..");
        }

        private static object[] GetScenes()
        {
            var activeScene = SceneManager.GetActiveScene();
            return Enumerable.Range(0, SceneManager.sceneCount)
                .Select(SceneManager.GetSceneAt)
                .Select(scene => new
                {
                    name = scene.name,
                    path = scene.path,
                    loaded = scene.isLoaded,
                    dirty = scene.isDirty,
                    active = scene == activeScene
                })
                .ToArray();
        }

        private static object GetAssetInfo(string path)
        {
            if (!IsAssetPath(path))
            {
                return new { ok = false, error = "Use a project-relative asset path starting with Assets/." };
            }
            var type = AssetDatabase.GetMainAssetTypeAtPath(path);
            if (type == null)
            {
                return new { ok = false, error = "Asset not found: " + path };
            }
            var guid = AssetDatabase.AssetPathToGUID(path);
            return new { ok = true, data = new { path = AssetDatabase.GUIDToAssetPath(guid), guid, type = type.FullName } };
        }

        private sealed class Request
        {
            public string Command { get; set; }
            public string AssetPath { get; set; }
            public string Filter { get; set; }
            public int Limit { get; set; }
            public int ObjectId { get; set; }
            public bool Additive { get; set; }
        }
    }
}
