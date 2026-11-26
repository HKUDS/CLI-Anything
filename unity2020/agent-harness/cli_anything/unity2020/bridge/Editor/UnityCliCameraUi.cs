using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using UIElements = UnityEngine.UIElements;

namespace CliAnything.Unity
{
    /// <summary>
    /// Camera and UI commands dispatched by <see cref="UnityCliBridge"/>.
    /// Read-only: camera.list, camera.inspect, ui.list, ui.inspect, ui.toolkit.inspect.
    /// Explicit writes: camera.set, camera.capture, ui.canvas.create, ui.element.create, ui.toolkit.create.
    /// UI Toolkit creation is limited to UXML/USS assets: Unity 2020.3 ships the editor UI Toolkit
    /// without UIDocument/PanelSettings, so runtime documents need the com.unity.ui package.
    /// </summary>
    internal static class UnityCliCameraUi
    {
        private const string CaptureFolder = "Temp/UnityCli/captures";
        private const int MaxCaptureEdge = 8192;
        private const string UndoCreateCanvas = "Unity CLI Create Canvas";
        private const string UndoCreateElement = "Unity CLI Create UI Element";
        private const string UndoSetCamera = "Unity CLI Set Camera";
#if UNITY_2022_2_OR_NEWER
        private const string BuiltInFontPath = "LegacyRuntime.ttf";
#else
        private const string BuiltInFontPath = "Arial.ttf";
#endif

        internal static bool TryExecute(string command, JObject args, out object result)
        {
            result = null;
            if (string.IsNullOrEmpty(command))
            {
                return false;
            }
            var owned = command.StartsWith("camera.", StringComparison.Ordinal) || command.StartsWith("ui.", StringComparison.Ordinal);
            if (!owned)
            {
                return false;
            }
            args = args ?? new JObject();
            try
            {
                switch (command)
                {
                    case "camera.list":
                        result = Ok(ListCameras(GetInt(args, "Limit") ?? 100));
                        return true;
                    case "camera.inspect":
                        result = Ok(InspectCamera(ResolveTarget(args, "camera")));
                        return true;
                    case "camera.set":
                        result = Ok(SetCamera(args));
                        return true;
                    case "camera.capture":
                        result = Ok(CaptureCamera(args));
                        return true;
                    case "ui.canvas.create":
                        result = Ok(CreateCanvas(args));
                        return true;
                    case "ui.element.create":
                        result = Ok(CreateElement(args));
                        return true;
                    case "ui.list":
                        result = Ok(ListUi(args));
                        return true;
                    case "ui.inspect":
                        result = Ok(InspectUiElement(ResolveTarget(args, "uGUI element")));
                        return true;
                    case "ui.toolkit.inspect":
                        result = Ok(InspectToolkit(GetString(args, "AssetPath"), GetInt(args, "Limit") ?? 200));
                        return true;
                    case "ui.toolkit.create":
                        result = Ok(CreateToolkitAssets(args));
                        return true;
                    default:
                        result = Fail("Unsupported Unity CLI camera/ui command: " + command);
                        return true;
                }
            }
            catch (Exception exception)
            {
                UnityCliLog.LogError("[Unity CLI] " + exception);
                result = Fail(exception.Message);
                return true;
            }
        }

        private static object Ok(object data)
        {
            return new { ok = true, data };
        }

        private static object Fail(string error)
        {
            return new { ok = false, error };
        }

        private static void RequireIdleEditor()
        {
            if (EditorApplication.isCompiling || EditorApplication.isUpdating)
            {
                throw new InvalidOperationException("Unity is compiling or importing assets. Retry after the Editor settles.");
            }
        }

        private static void RequireEditMode(string action)
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                throw new InvalidOperationException("Exit Play Mode before " + action + ".");
            }
        }

        // ---------------------------------------------------------------- camera

        private static object ListCameras(int limit)
        {
            CheckLimit(limit);
            var cameras = WalkScenes()
                .SelectMany(transform => transform.GetComponents<Camera>())
                .Select(camera => new { camera, path = GetPath(camera.transform) })
                .ToArray();
            return new
            {
                cameras = cameras.Take(limit).Select(item => new
                {
                    objectId = item.camera.gameObject.GetInstanceID(),
                    name = item.camera.name,
                    path = item.path,
                    scene = item.camera.gameObject.scene.path,
                    enabled = item.camera.enabled,
                    active = item.camera.gameObject.activeInHierarchy,
                    depth = item.camera.depth,
                    orthographic = item.camera.orthographic,
                    fieldOfView = item.camera.fieldOfView,
                    clearFlags = item.camera.clearFlags.ToString(),
                    cinemachineBrain = HasComponent(item.camera.gameObject, "Cinemachine.CinemachineBrain")
                }).ToArray(),
                counts = new
                {
                    total = cameras.Length,
                    cinemachineVirtualCameras = WalkScenes().Count(transform => HasComponent(transform.gameObject, "Cinemachine.CinemachineVirtualCamera"))
                },
                truncated = cameras.Length > limit,
                renderPipeline = CurrentRenderPipelineName()
            };
        }

        private static object InspectCamera(Transform transform)
        {
            var camera = transform.GetComponent<Camera>();
            if (camera == null)
            {
                throw new InvalidOperationException("GameObject has no Camera component: " + GetPath(transform));
            }
            var position = transform.position;
            var euler = transform.eulerAngles;
            var scale = transform.lossyScale;
            var rect = camera.rect;
            var pixelRect = camera.pixelRect;
            return new
            {
                objectId = camera.gameObject.GetInstanceID(),
                name = camera.name,
                path = GetPath(transform),
                scene = camera.gameObject.scene.path,
                enabled = camera.enabled,
                active = camera.gameObject.activeInHierarchy,
                transform = new
                {
                    position = new[] { position.x, position.y, position.z },
                    rotation = new[] { euler.x, euler.y, euler.z },
                    scale = new[] { scale.x, scale.y, scale.z }
                },
                depth = camera.depth,
                clearFlags = camera.clearFlags.ToString(),
                backgroundColor = "#" + ColorUtility.ToHtmlStringRGB(camera.backgroundColor),
                cullingMask = camera.cullingMask,
                fieldOfView = camera.fieldOfView,
                nearClipPlane = camera.nearClipPlane,
                farClipPlane = camera.farClipPlane,
                orthographic = camera.orthographic,
                orthographicSize = camera.orthographicSize,
                aspect = camera.aspect,
                rect = new { x = rect.x, y = rect.y, width = rect.width, height = rect.height },
                pixelRect = new { x = pixelRect.x, y = pixelRect.y, width = pixelRect.width, height = pixelRect.height },
                targetDisplay = camera.targetDisplay,
                targetTexture = camera.targetTexture == null ? null : camera.targetTexture.name,
                allowHDR = camera.allowHDR,
                allowMSAA = camera.allowMSAA,
                useOcclusionCulling = camera.useOcclusionCulling,
                components = ComponentNames(camera.gameObject),
                cinemachineBrain = HasComponent(camera.gameObject, "Cinemachine.CinemachineBrain"),
                cinemachineVirtualCameras = WalkScenes()
                    .Where(item => HasComponent(item.gameObject, "Cinemachine.CinemachineVirtualCamera"))
                    .Select(GetPath).ToArray(),
                renderPipeline = CurrentRenderPipelineName()
            };
        }

        private static object SetCamera(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("changing a camera");
            var transform = ResolveTarget(args, "camera");
            var camera = transform.GetComponent<Camera>();
            if (camera == null)
            {
                throw new InvalidOperationException("GameObject has no Camera component: " + GetPath(transform));
            }
            var changed = new List<object>();
            var enabled = GetBool(args, "Enabled");
            var depth = GetFloat(args, "Depth");
            var fieldOfView = GetFloat(args, "FieldOfView");
            var nearClip = GetFloat(args, "NearClipPlane");
            var farClip = GetFloat(args, "FarClipPlane");
            var orthographic = GetBool(args, "Orthographic");
            var orthographicSize = GetFloat(args, "OrthographicSize");
            var clearFlags = GetString(args, "ClearFlags");
            var background = GetString(args, "BackgroundColor");
            if (enabled == null && depth == null && fieldOfView == null && nearClip == null && farClip == null &&
                orthographic == null && orthographicSize == null && clearFlags == null && background == null)
            {
                throw new InvalidOperationException("No camera setting supplied. Pass at least one of Enabled, Depth, FieldOfView, NearClipPlane, FarClipPlane, Orthographic, OrthographicSize, ClearFlags or BackgroundColor.");
            }

            // Validate every supplied value before the first mutation so a rejected
            // request never leaves a half-applied camera.
            if (fieldOfView != null)
            {
                RequireRange("FieldOfView", fieldOfView.Value, 1f, 179f);
            }
            if (nearClip != null)
            {
                RequirePositive("NearClipPlane", nearClip.Value);
            }
            if (farClip != null)
            {
                RequirePositive("FarClipPlane", farClip.Value);
            }
            if (orthographicSize != null)
            {
                RequirePositive("OrthographicSize", orthographicSize.Value);
            }
            CameraClearFlags? parsedClearFlags = null;
            if (clearFlags != null)
            {
                if (!Enum.TryParse(clearFlags, true, out CameraClearFlags parsed))
                {
                    throw new ArgumentException("ClearFlags must be Skybox, SolidColor, Depth or Nothing.");
                }
                parsedClearFlags = parsed;
            }
            Color? parsedBackground = null;
            if (background != null)
            {
                parsedBackground = ParseColor(background);
            }
            var effectiveNear = nearClip ?? camera.nearClipPlane;
            var effectiveFar = farClip ?? camera.farClipPlane;
            if (effectiveNear >= effectiveFar)
            {
                throw new InvalidOperationException("NearClipPlane must stay below FarClipPlane (" + effectiveNear + " >= " + effectiveFar + ").");
            }

            Undo.RecordObject(camera, UndoSetCamera);
            Undo.RecordObject(camera.gameObject, UndoSetCamera);

            if (enabled != null)
            {
                changed.Add(Change("enabled", camera.enabled, enabled.Value));
                camera.enabled = enabled.Value;
            }
            if (depth != null)
            {
                changed.Add(Change("depth", camera.depth, depth.Value));
                camera.depth = depth.Value;
            }
            if (fieldOfView != null)
            {
                changed.Add(Change("fieldOfView", camera.fieldOfView, fieldOfView.Value));
                camera.fieldOfView = fieldOfView.Value;
            }
            if (nearClip != null)
            {
                changed.Add(Change("nearClipPlane", camera.nearClipPlane, nearClip.Value));
                camera.nearClipPlane = nearClip.Value;
            }
            if (farClip != null)
            {
                changed.Add(Change("farClipPlane", camera.farClipPlane, farClip.Value));
                camera.farClipPlane = farClip.Value;
            }
            if (orthographic != null)
            {
                changed.Add(Change("orthographic", camera.orthographic, orthographic.Value));
                camera.orthographic = orthographic.Value;
            }
            if (orthographicSize != null)
            {
                changed.Add(Change("orthographicSize", camera.orthographicSize, orthographicSize.Value));
                camera.orthographicSize = orthographicSize.Value;
            }
            if (parsedClearFlags != null)
            {
                changed.Add(Change("clearFlags", camera.clearFlags.ToString(), parsedClearFlags.Value.ToString()));
                camera.clearFlags = parsedClearFlags.Value;
            }
            if (parsedBackground != null)
            {
                changed.Add(Change("backgroundColor", "#" + ColorUtility.ToHtmlStringRGB(camera.backgroundColor), "#" + ColorUtility.ToHtmlStringRGB(parsedBackground.Value)));
                camera.backgroundColor = parsedBackground.Value;
            }

            EditorUtility.SetDirty(camera);
            MarkDirty(camera.gameObject);
            return new
            {
                objectId = camera.gameObject.GetInstanceID(),
                path = GetPath(camera.transform),
                changed,
                prefabInstance = PrefabUtility.GetPrefabInstanceStatus(camera.gameObject) != PrefabInstanceStatus.NotAPrefab,
                prefabStage = EditorSceneManager.IsPreviewScene(camera.gameObject.scene)
            };
        }

        private static object CaptureCamera(JObject args)
        {
            RequireIdleEditor();
            var transform = ResolveTarget(args, "camera");
            var camera = transform.GetComponent<Camera>();
            if (camera == null)
            {
                throw new InvalidOperationException("GameObject has no Camera component: " + GetPath(transform));
            }
            var width = GetInt(args, "Width") ?? camera.pixelWidth;
            var height = GetInt(args, "Height") ?? camera.pixelHeight;
            if (width < 1 || height < 1)
            {
                throw new InvalidOperationException("Camera pixel size is unavailable (" + width + "x" + height + "). Pass Width and Height.");
            }
            if (width > MaxCaptureEdge || height > MaxCaptureEdge)
            {
                throw new ArgumentOutOfRangeException("Width", "Capture edges must be between 1 and " + MaxCaptureEdge + " pixels.");
            }
            var maxTexture = SystemInfo.maxTextureSize;
            if (width > maxTexture || height > maxTexture)
            {
                throw new InvalidOperationException("Requested capture exceeds the GPU texture limit of " + maxTexture + " pixels per edge.");
            }

            var output = ResolveCapturePath(GetString(args, "OutputPath"), camera.name);
            if (File.Exists(output.AbsolutePath))
            {
                throw new IOException("Capture output already exists: " + output.RelativePath);
            }
            var previousTarget = camera.targetTexture;
            var previousActive = RenderTexture.active;
            var target = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            Texture2D texture = null;
            Texture2D verification = null;
            byte[] png;
            try
            {
                if (!target.Create())
                {
                    throw new InvalidOperationException("RenderTexture.Create returned false. Reduce Width and Height or free GPU memory.");
                }
                camera.targetTexture = target;
                camera.Render();
                RenderTexture.active = target;
                texture = new Texture2D(width, height, TextureFormat.RGBA32, false, false);
                texture.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                texture.Apply(false, false);
                png = ImageConversion.EncodeToPNG(texture);
            }
            finally
            {
                camera.targetTexture = previousTarget;
                RenderTexture.active = previousActive;
                target.Release();
                UnityEngine.Object.DestroyImmediate(target);
                if (texture != null)
                {
                    UnityEngine.Object.DestroyImmediate(texture);
                }
            }

            if (png == null || png.Length == 0)
            {
                throw new InvalidOperationException("PNG encoding produced no data. Check the camera target texture and graphics device.");
            }
            var verified = false;
            try
            {
                verification = new Texture2D(2, 2, TextureFormat.RGBA32, false, false);
                verified = ImageConversion.LoadImage(verification, png) && verification.width == width && verification.height == height;
            }
            finally
            {
                if (verification != null)
                {
                    UnityEngine.Object.DestroyImmediate(verification);
                }
            }
            if (!verified)
            {
                throw new InvalidOperationException("PNG round-trip verification failed for " + width + "x" + height + ".");
            }

            using (var file = new FileStream(output.AbsolutePath, FileMode.CreateNew, FileAccess.Write))
            {
                file.Write(png, 0, png.Length);
            }
            if (output.AssetPath != null)
            {
                AssetDatabase.ImportAsset(output.AssetPath, ImportAssetOptions.ForceUpdate);
            }
            return new
            {
                objectId = camera.gameObject.GetInstanceID(),
                name = camera.name,
                path = GetPath(camera.transform),
                width,
                height,
                bytes = png.Length,
                md5 = Md5Hex(png),
                pngVerified = true,
                filePath = output.RelativePath,
                assetPath = output.AssetPath,
                playMode = EditorApplication.isPlaying,
                renderPipeline = CurrentRenderPipelineName()
            };
        }

        // ---------------------------------------------------------------- uGUI

        private static object CreateCanvas(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("creating a Canvas");
            var name = GetString(args, "Name") ?? "Canvas";
            var parent = ResolveOptionalParent(args);
            var renderModeText = GetString(args, "RenderMode") ?? "ScreenSpaceOverlay";
            if (!Enum.TryParse(renderModeText, true, out RenderMode renderMode))
            {
                throw new ArgumentException("RenderMode must be ScreenSpaceOverlay, ScreenSpaceCamera or WorldSpace.");
            }
            Camera worldCamera = null;
            var cameraId = GetInt(args, "CameraId");
            if (cameraId != null)
            {
                var cameraObject = EditorUtility.InstanceIDToObject(cameraId.Value) as GameObject;
                worldCamera = cameraObject == null ? null : cameraObject.GetComponent<Camera>();
                if (worldCamera == null)
                {
                    throw new InvalidOperationException("CameraId does not identify a GameObject with a Camera component.");
                }
            }
            if (renderMode == RenderMode.ScreenSpaceCamera && worldCamera == null)
            {
                throw new InvalidOperationException("ScreenSpaceCamera requires CameraId of a scene camera.");
            }
            var scalerText = GetString(args, "ScalerMode") ?? "ScaleWithScreenSize";
            if (!Enum.TryParse(scalerText, true, out CanvasScaler.ScaleMode scalerMode))
            {
                throw new ArgumentException("ScalerMode must be ConstantPixelSize, ScaleWithScreenSize or ConstantPhysicalSize.");
            }
            var resolution = new Vector2Int(1920, 1080);
            var matchWidthOrHeight = 0.5f;
            if (scalerMode == CanvasScaler.ScaleMode.ScaleWithScreenSize)
            {
                resolution = GetIntPair(args, "ReferenceResolution") ?? resolution;
                if (resolution.x < 1 || resolution.y < 1)
                {
                    throw new ArgumentException("ReferenceResolution must be two positive integers.");
                }
                matchWidthOrHeight = Mathf.Clamp01(GetFloat(args, "MatchWidthOrHeight") ?? 0.5f);
            }

            var gameObject = new GameObject(name, typeof(RectTransform));
            Undo.RegisterCreatedObjectUndo(gameObject, UndoCreateCanvas);
            if (parent != null)
            {
                Undo.SetTransformParent(gameObject.transform, parent, UndoCreateCanvas);
            }
            var uiLayer = LayerMask.NameToLayer("UI");
            if (uiLayer >= 0)
            {
                gameObject.layer = uiLayer;
            }
            var canvas = gameObject.AddComponent<Canvas>();
            canvas.renderMode = renderMode;
            if (worldCamera != null)
            {
                canvas.worldCamera = worldCamera;
            }
            canvas.sortingOrder = GetInt(args, "SortingOrder") ?? 0;

            var scaler = gameObject.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = scalerMode;
            if (scalerMode == CanvasScaler.ScaleMode.ScaleWithScreenSize)
            {
                scaler.referenceResolution = new Vector2(resolution.x, resolution.y);
                scaler.matchWidthOrHeight = matchWidthOrHeight;
            }
            gameObject.AddComponent<GraphicRaycaster>();
            Selection.activeGameObject = gameObject;
            MarkDirty(gameObject);
            return new
            {
                objectId = gameObject.GetInstanceID(),
                name = gameObject.name,
                path = GetPath(gameObject.transform),
                scene = gameObject.scene.path,
                layer = LayerMask.LayerToName(gameObject.layer),
                renderMode = canvas.renderMode.ToString(),
                scalerMode = scaler.uiScaleMode.ToString(),
                referenceResolution = scaler.uiScaleMode == CanvasScaler.ScaleMode.ScaleWithScreenSize
                    ? new[] { scaler.referenceResolution.x, scaler.referenceResolution.y }
                    : null,
                sortingOrder = canvas.sortingOrder,
                components = ComponentNames(gameObject),
                prefabStage = EditorSceneManager.IsPreviewScene(gameObject.scene)
            };
        }

        private static object CreateElement(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("creating a uGUI element");
            var type = (GetString(args, "Type") ?? "").Trim().ToLowerInvariant();
            if (type != "text" && type != "button" && type != "image" && type != "panel")
            {
                throw new ArgumentException("Type must be text, button, image or panel.");
            }
            var parent = ResolveRequiredUiParent(args);
            var name = GetString(args, "Name") ?? (type == "panel" ? "Panel" : char.ToUpperInvariant(type[0]) + type.Substring(1));
            var color = ParseOptionalColor(args);
            var sprite = LoadSpriteAsset(GetString(args, "SpritePath"));
            var anchorMin = GetVector2(args, "AnchorMin") ?? new Vector2(0.5f, 0.5f);
            var anchorMax = GetVector2(args, "AnchorMax") ?? anchorMin;
            var pivot = GetVector2(args, "Pivot") ?? new Vector2(0.5f, 0.5f);
            var position = GetVector2(args, "AnchoredPosition") ?? Vector2.zero;
            var defaultSize = type == "text" || type == "button" ? new Vector2(200f, 60f) : new Vector2(100f, 100f);
            var width = GetFloat(args, "Width") ?? defaultSize.x;
            var height = GetFloat(args, "Height") ?? defaultSize.y;
            var raycast = GetBool(args, "RaycastTarget");
            var createdObjects = new List<GameObject>();

            var gameObject = new GameObject(name, typeof(RectTransform));
            createdObjects.Add(gameObject);
            try
            {
                Undo.RegisterCreatedObjectUndo(gameObject, UndoCreateElement);
                Undo.SetTransformParent(gameObject.transform, parent, UndoCreateElement);
                gameObject.layer = parent.gameObject.layer;
                var rect = gameObject.GetComponent<RectTransform>();
                rect.anchorMin = anchorMin;
                rect.anchorMax = anchorMax;
                rect.pivot = pivot;
                rect.anchoredPosition = position;
                rect.sizeDelta = new Vector2(width, height);

                if (type == "text")
                {
                    var text = gameObject.AddComponent<Text>();
                    ApplyFont(text, GetString(args, "FontPath"));
                    text.text = GetString(args, "Text") ?? "Text";
                    text.fontSize = Mathf.Clamp(GetInt(args, "FontSize") ?? 24, 1, 300);
                    text.color = color ?? Color.white;
                    text.alignment = ParseAlignment(GetString(args, "Alignment"));
                    text.raycastTarget = raycast ?? false;
                }
                else
                {
                    var image = gameObject.AddComponent<Image>();
                    image.sprite = sprite;
                    image.color = color ?? Color.white;
                    image.raycastTarget = raycast ?? true;
                    if (type == "button")
                    {
                        var button = gameObject.AddComponent<Button>();
                        button.targetGraphic = image;
                        var label = new GameObject("Label", typeof(RectTransform));
                        createdObjects.Add(label);
                        Undo.RegisterCreatedObjectUndo(label, UndoCreateElement);
                        Undo.SetTransformParent(label.transform, gameObject.transform, UndoCreateElement);
                        label.layer = gameObject.layer;
                        var labelRect = label.GetComponent<RectTransform>();
                        labelRect.anchorMin = Vector2.zero;
                        labelRect.anchorMax = Vector2.one;
                        labelRect.offsetMin = Vector2.zero;
                        labelRect.offsetMax = Vector2.zero;
                        var labelText = label.AddComponent<Text>();
                        ApplyFont(labelText, GetString(args, "FontPath"));
                        labelText.text = GetString(args, "Text") ?? "Button";
                        labelText.fontSize = Mathf.Clamp(GetInt(args, "FontSize") ?? 24, 1, 300);
                        labelText.color = Color.white;
                        labelText.alignment = TextAnchor.MiddleCenter;
                        labelText.raycastTarget = false;
                    }
                }
                Selection.activeGameObject = gameObject;
                MarkDirty(gameObject);
            }
            catch (Exception)
            {
                foreach (var createdObject in createdObjects)
                {
                    if (createdObject != null)
                    {
                        UnityEngine.Object.DestroyImmediate(createdObject);
                    }
                }
                throw;
            }

            return new
            {
                objectId = gameObject.GetInstanceID(),
                name = gameObject.name,
                path = GetPath(gameObject.transform),
                type,
                parentId = parent.gameObject.GetInstanceID(),
                parentPath = GetPath(parent),
                scene = gameObject.scene.path,
                sprite = sprite == null ? null : AssetDatabase.GetAssetPath(sprite),
                color = "#" + ColorUtility.ToHtmlStringRGB(gameObject.GetComponent<Graphic>().color),
                sizeDelta = new[] { width, height },
                anchors = new
                {
                    min = new[] { anchorMin.x, anchorMin.y },
                    max = new[] { anchorMax.x, anchorMax.y },
                    pivot = new[] { pivot.x, pivot.y },
                    position = new[] { position.x, position.y }
                },
                children = gameObject.transform.childCount,
                components = ComponentNames(gameObject),
                prefabStage = EditorSceneManager.IsPreviewScene(gameObject.scene)
            };
        }

        private static object ListUi(JObject args)
        {
            var limit = GetInt(args, "Limit") ?? 100;
            CheckLimit(limit);
            var filter = GetString(args, "Filter") ?? "";
            var transforms = WalkScenes().ToArray();
            var canvases = transforms
                .Select(transform => transform.GetComponent<Canvas>())
                .Where(canvas => canvas != null)
                .ToArray();
            var elements = transforms
                .Where(transform => transform.name.IndexOf(filter, StringComparison.OrdinalIgnoreCase) >= 0)
                .Select(transform => new { transform, graphic = transform.GetComponent<Graphic>(), button = transform.GetComponent<Button>() })
                .Where(item => item.graphic != null || item.button != null)
                .ToArray();
            return new
            {
                canvases = canvases.Select(canvas => new
                {
                    objectId = canvas.gameObject.GetInstanceID(),
                    name = canvas.name,
                    path = GetPath(canvas.transform),
                    scene = canvas.gameObject.scene.path,
                    renderMode = canvas.renderMode.ToString(),
                    sortingOrder = canvas.sortingOrder,
                    rootCanvas = canvas.isRootCanvas,
                    childCount = canvas.transform.childCount
                }).ToArray(),
                elements = elements.Take(limit).Select(item => new
                {
                    objectId = item.transform.gameObject.GetInstanceID(),
                    name = item.transform.name,
                    path = GetPath(item.transform),
                    type = DescribeGraphic(item.graphic, item.button),
                    text = ReadText(item.transform.gameObject),
                    active = item.transform.gameObject.activeInHierarchy
                }).ToArray(),
                totalElements = elements.Length,
                totalCanvases = canvases.Length,
                truncated = elements.Length > limit
            };
        }

        private static object InspectUiElement(Transform transform)
        {
            var gameObject = transform.gameObject;
            var rect = transform as RectTransform;
            if (rect == null)
            {
                throw new InvalidOperationException("GameObject has no RectTransform: " + GetPath(transform));
            }
            var graphic = gameObject.GetComponent<Graphic>();
            var button = gameObject.GetComponent<Button>();
            var canvas = gameObject.GetComponentInParent<Canvas>();
            var offsetMin = rect.offsetMin;
            var offsetMax = rect.offsetMax;
            var anchored = rect.anchoredPosition;
            var size = rect.sizeDelta;
            return new
            {
                objectId = gameObject.GetInstanceID(),
                name = gameObject.name,
                path = GetPath(transform),
                scene = gameObject.scene.path,
                active = gameObject.activeInHierarchy,
                layer = LayerMask.LayerToName(gameObject.layer),
                rect = new
                {
                    anchorMin = new[] { rect.anchorMin.x, rect.anchorMin.y },
                    anchorMax = new[] { rect.anchorMax.x, rect.anchorMax.y },
                    pivot = new[] { rect.pivot.x, rect.pivot.y },
                    anchoredPosition = new[] { anchored.x, anchored.y },
                    sizeDelta = new[] { size.x, size.y },
                    offsetMin = new[] { offsetMin.x, offsetMin.y },
                    offsetMax = new[] { offsetMax.x, offsetMax.y },
                    width = rect.rect.width,
                    height = rect.rect.height
                },
                type = DescribeGraphic(graphic, button),
                text = ReadText(gameObject),
                sprite = graphic is Image image && image.sprite != null ? AssetDatabase.GetAssetPath(image.sprite) : null,
                color = graphic == null ? null : "#" + ColorUtility.ToHtmlStringRGB(graphic.color),
                raycastTarget = graphic != null && graphic.raycastTarget,
                button = button == null ? null : new
                {
                    interactable = button.interactable,
                    targetGraphic = button.targetGraphic == null ? null : button.targetGraphic.name
                },
                canvas = canvas == null ? null : new
                {
                    objectId = canvas.gameObject.GetInstanceID(),
                    path = GetPath(canvas.transform),
                    renderMode = canvas.renderMode.ToString(),
                    sortingOrder = canvas.sortingOrder
                },
                children = transform.childCount,
                components = ComponentNames(gameObject)
            };
        }

        // ------------------------------------------------------------ UI Toolkit

        private static object InspectToolkit(string assetPath, int limit)
        {
            CheckLimit(limit);
            if (!IsAssetPath(assetPath))
            {
                throw new ArgumentException("AssetPath must be a project-relative path starting with Assets/.");
            }
            if (AssetDatabase.IsValidFolder(assetPath))
            {
                var assetPaths = AssetDatabase.FindAssets("", new[] { assetPath })
                    .Select(AssetDatabase.GUIDToAssetPath)
                    .Where(path => !string.IsNullOrEmpty(path) && !AssetDatabase.IsValidFolder(path))
                    .OrderBy(path => path, StringComparer.Ordinal)
                    .ToArray();
                var uxmlPaths = assetPaths
                    .Where(path => path.EndsWith(".uxml", StringComparison.OrdinalIgnoreCase))
                    .ToArray();
                var ussPaths = assetPaths
                    .Where(path => path.EndsWith(".uss", StringComparison.OrdinalIgnoreCase))
                    .ToArray();
                var uxmlTruncated = uxmlPaths.Length > limit;
                var ussTruncated = ussPaths.Length > limit;
                return new
                {
                    assetPath,
                    folder = true,
                    uxml = uxmlPaths.Take(limit).Select(path => SummarizeAsset(path)).ToArray(),
                    uss = ussPaths.Take(limit).Select(path => SummarizeAsset(path)).ToArray(),
                    uxmlTruncated,
                    ussTruncated,
                    truncated = uxmlTruncated || ussTruncated,
                    runtimeDocumentSupported = false
                };
            }
            var extension = Path.GetExtension(assetPath).ToLowerInvariant();
            if (extension == ".uxml")
            {
                var asset = AssetDatabase.LoadAssetAtPath<UIElements.VisualTreeAsset>(assetPath);
                if (asset == null)
                {
                    throw new InvalidOperationException("UXML asset is missing or not imported: " + assetPath);
                }
                var container = new UIElements.VisualElement();
                asset.CloneTree(container);
                var nodes = new List<object>();
                var pending = new Queue<KeyValuePair<UIElements.VisualElement, int>>();
                for (var index = 0; index < container.childCount; index++)
                {
                    pending.Enqueue(new KeyValuePair<UIElements.VisualElement, int>(container.ElementAt(index), 0));
                }
                var truncated = false;
                while (pending.Count > 0)
                {
                    var item = pending.Dequeue();
                    if (nodes.Count >= limit)
                    {
                        truncated = true;
                        break;
                    }
                    var element = item.Key;
                    nodes.Add(new
                    {
                        depth = item.Value,
                        type = element.GetType().Name,
                        name = element.name,
                        classes = element.GetClasses().ToArray(),
                        text = element is UIElements.TextElement textElement ? textElement.text : null,
                        children = element.childCount
                    });
                    for (var index = 0; index < element.childCount; index++)
                    {
                        pending.Enqueue(new KeyValuePair<UIElements.VisualElement, int>(element.ElementAt(index), item.Value + 1));
                    }
                }
                return new
                {
                    assetPath,
                    folder = false,
                    kind = "uxml",
                    contentHash = asset.contentHash,
                    stylesheets = asset.stylesheets.Select(sheet => sheet == null ? null : sheet.name).ToArray(),
                    nodes,
                    truncated,
                    runtimeDocumentSupported = false
                };
            }
            if (extension == ".uss")
            {
                var type = AssetDatabase.GetMainAssetTypeAtPath(assetPath);
                if (type == null)
                {
                    throw new InvalidOperationException("USS asset is missing or not imported: " + assetPath);
                }
                var bytes = File.ReadAllBytes(assetPath);
                var selectors = ReadUssSelectors(Encoding.UTF8.GetString(bytes), limit, out var selectorTruncated);
                return new
                {
                    assetPath,
                    folder = false,
                    kind = "uss",
                    importerType = type.FullName,
                    bytes = bytes.Length,
                    md5 = Md5Hex(bytes),
                    selectors,
                    selectorSource = "text",
                    truncated = selectorTruncated,
                    runtimeDocumentSupported = false
                };
            }
            throw new ArgumentException("AssetPath must be an .uxml file, .uss file or an Assets/ folder.");
        }

        private static object CreateToolkitAssets(JObject args)
        {
            RequireIdleEditor();
            var uxmlPath = NormalizeNewAssetPath(GetString(args, "UxmlPath"), ".uxml", "UxmlPath");
            var ussPath = NormalizeNewAssetPath(GetString(args, "UssPath"), ".uss", "UssPath");
            if (uxmlPath == null && ussPath == null)
            {
                throw new ArgumentException("Pass UxmlPath and/or UssPath.");
            }
            var force = GetBool(args, "Force") ?? false;

            var writes = new List<ToolkitWriteRequest>();
            if (uxmlPath != null)
            {
                var name = GetString(args, "Name") ?? Path.GetFileNameWithoutExtension(uxmlPath);
                writes.Add(new ToolkitWriteRequest(uxmlPath, BuildUxml(name, GetString(args, "Label"))));
            }
            if (ussPath != null)
            {
                var className = GetString(args, "Name") ?? (uxmlPath == null ? "root" : Path.GetFileNameWithoutExtension(uxmlPath));
                writes.Add(new ToolkitWriteRequest(ussPath, BuildUss(className)));
            }

            foreach (var write in writes)
            {
                var absolute = AssetPathToAbsolute(write.AssetPath);
                if (Directory.Exists(absolute))
                {
                    throw new InvalidOperationException("Asset path is a directory: " + write.AssetPath + ".");
                }
                if (!force && File.Exists(absolute))
                {
                    throw new InvalidOperationException(
                        "Asset already exists: " + write.AssetPath + ". Pass Force to overwrite.");
                }
            }

            var created = writes.Select(write => write.AssetPath).ToList();
            var backups = new List<ToolkitWriteBackup>();
            try
            {
                foreach (var write in writes)
                {
                    backups.Add(ToolkitWriteBackup.Capture(write.AssetPath));
                    WriteAsset(write.AssetPath, write.Content, force);
                }

                var uxmlVerification = uxmlPath == null ? (int?)null : VerifyUxml(uxmlPath);
                var ussType = ussPath == null ? null : AssetDatabase.GetMainAssetTypeAtPath(ussPath);
                if (ussPath != null && ussType != typeof(UIElements.StyleSheet))
                {
                    throw new InvalidOperationException("Unity did not import the USS asset as a StyleSheet: " + ussPath);
                }
                return new
                {
                    created,
                    uxml = uxmlPath == null ? null : new { assetPath = uxmlPath, nodes = uxmlVerification },
                    uss = ussPath == null ? null : new { assetPath = ussPath, importerType = ussType.FullName },
                    runtimeDocumentSupported = false
                };
            }
            catch
            {
                foreach (var backup in backups)
                {
                    backup.Restore();
                }
                throw;
            }
        }

        private sealed class ToolkitWriteRequest
        {
            public ToolkitWriteRequest(string assetPath, string content)
            {
                AssetPath = assetPath;
                Content = content;
            }

            public string AssetPath { get; }

            public string Content { get; }
        }

        private sealed class ToolkitWriteBackup
        {
            private string _assetPath;
            private string _absolutePath;
            private byte[] _originalBytes;
            private bool _metaExisted;

            public static ToolkitWriteBackup Capture(string assetPath)
            {
                var absolute = AssetPathToAbsolute(assetPath);
                return new ToolkitWriteBackup
                {
                    _assetPath = assetPath,
                    _absolutePath = absolute,
                    _originalBytes = File.Exists(absolute) ? File.ReadAllBytes(absolute) : null,
                    _metaExisted = File.Exists(absolute + ".meta")
                };
            }

            public void Restore()
            {
                try
                {
                    if (_originalBytes != null)
                    {
                        Directory.CreateDirectory(Path.GetDirectoryName(_absolutePath));
                        File.WriteAllBytes(_absolutePath, _originalBytes);
                        AssetDatabase.ImportAsset(_assetPath, ImportAssetOptions.ForceUpdate);
                        return;
                    }
                    if (File.Exists(_absolutePath))
                    {
                        File.Delete(_absolutePath);
                    }
                    if (!_metaExisted && File.Exists(_absolutePath + ".meta"))
                    {
                        File.Delete(_absolutePath + ".meta");
                    }
                    AssetDatabase.Refresh();
                }
                catch (Exception exception)
                {
                    UnityCliLog.LogError("[Unity CLI] Could not roll back " + _assetPath + ": " + exception.Message);
                }
            }
        }

        private static int VerifyUxml(string assetPath)
        {
            var asset = AssetDatabase.LoadAssetAtPath<UIElements.VisualTreeAsset>(assetPath);
            if (asset == null)
            {
                throw new InvalidOperationException("Unity did not import the UXML asset: " + assetPath);
            }
            var container = new UIElements.VisualElement();
            asset.CloneTree(container);
            return container.childCount;
        }

        private static string BuildUxml(string name, string label)
        {
            var builder = new StringBuilder();
            builder.AppendLine("<?xml version=\"1.0\" encoding=\"utf-8\"?>");
            builder.AppendLine("<ui:UXML xmlns:ui=\"UnityEngine.UIElements\" xmlns:uie=\"UnityEditor.UIElements\" editor-extension-mode=\"False\">");
            builder.AppendFormat("    <ui:VisualElement name=\"{0}\" class=\"root\" style=\"flex-grow: 1; flex-direction: column;\">{1}", EscapeXml(name), Environment.NewLine);
            if (!string.IsNullOrEmpty(label))
            {
                builder.AppendFormat("        <ui:Label text=\"{0}\" name=\"label\" />{1}", EscapeXml(label), Environment.NewLine);
            }
            builder.AppendLine("    </ui:VisualElement>");
            builder.AppendLine("</ui:UXML>");
            return builder.ToString();
        }

        private static string BuildUss(string className)
        {
            var builder = new StringBuilder();
            builder.AppendLine("." + className + " {");
            builder.AppendLine("    flex-grow: 1;");
            builder.AppendLine("}");
            return builder.ToString();
        }

        private static void WriteAsset(string assetPath, string content, bool overwrite)
        {
            var absolute = AssetPathToAbsolute(assetPath);
            var directory = Path.GetDirectoryName(absolute);
            if (!string.IsNullOrEmpty(directory))
            {
                Directory.CreateDirectory(directory);
            }
            using (var stream = new FileStream(absolute, overwrite ? FileMode.Create : FileMode.CreateNew, FileAccess.Write))
            using (var writer = new StreamWriter(stream, new UTF8Encoding(false)))
            {
                writer.Write(content);
            }
            AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceUpdate);
        }

        private static object SummarizeAsset(string path)
        {
            var type = AssetDatabase.GetMainAssetTypeAtPath(path);
            var absolute = AssetPathToAbsolute(path);
            var bytes = File.Exists(absolute) ? new FileInfo(absolute).Length : 0;
            return new { assetPath = path, importerType = type == null ? null : type.FullName, bytes };
        }

        private static string[] ReadUssSelectors(string content, int limit, out bool truncated)
        {
            var selectors = new List<string>();
            truncated = false;
            var start = 0;
            while (start < content.Length)
            {
                var open = content.IndexOf('{', start);
                if (open < 0)
                {
                    break;
                }
                var header = content.Substring(start, open - start);
                var stripped = StripUssComments(header).Trim();
                if (stripped.Length > 0)
                {
                    foreach (var selector in stripped.Split(','))
                    {
                        var trimmed = selector.Trim();
                        if (trimmed.Length == 0)
                        {
                            continue;
                        }
                        if (selectors.Count >= limit)
                        {
                            truncated = true;
                            return selectors.ToArray();
                        }
                        selectors.Add(trimmed);
                    }
                }
                var close = content.IndexOf('}', open);
                if (close < 0)
                {
                    break;
                }
                start = close + 1;
            }
            return selectors.ToArray();
        }

        private static string StripUssComments(string text)
        {
            var builder = new StringBuilder(text.Length);
            var index = 0;
            while (index < text.Length)
            {
                var comment = text.IndexOf("/*", index, StringComparison.Ordinal);
                if (comment < 0)
                {
                    builder.Append(text.Substring(index));
                    break;
                }
                builder.Append(text.Substring(index, comment - index));
                var end = text.IndexOf("*/", comment + 2, StringComparison.Ordinal);
                if (end < 0)
                {
                    break;
                }
                index = end + 2;
            }
            return builder.ToString();
        }

        // ---------------------------------------------------------------- helpers

        private static Transform ResolveTarget(JObject args, string label)
        {
            return ResolveByIdOrPath(GetInt(args, "ObjectId"), GetString(args, "Path"), GetString(args, "ScenePath"), label);
        }

        private static Transform ResolveByIdOrPath(int? objectId, string path, string scenePath, string label)
        {
            if (objectId != null)
            {
                var gameObject = EditorUtility.InstanceIDToObject(objectId.Value) as GameObject;
                if (gameObject == null || !gameObject.scene.IsValid())
                {
                    throw new InvalidOperationException(label + " instance ID does not identify a loaded scene object: " + objectId.Value);
                }
                return gameObject.transform;
            }
            if (string.IsNullOrEmpty(path))
            {
                throw new InvalidOperationException("Provide ObjectId or Path for the " + label + ".");
            }
            var normalized = path.Trim('/');
            var matches = WalkScenes()
                .Where(transform => string.Equals(GetPath(transform), normalized, StringComparison.Ordinal))
                .Where(transform => string.IsNullOrEmpty(scenePath) || transform.gameObject.scene.path == scenePath)
                .ToArray();
            if (matches.Length == 0)
            {
                throw new InvalidOperationException("No loaded scene object matches path: " + path);
            }
            if (matches.Length > 1)
            {
                throw new InvalidOperationException("Path matches " + matches.Length + " objects. Pass ObjectId or ScenePath.");
            }
            return matches[0];
        }

        private static Transform ResolveOptionalParent(JObject args)
        {
            var parentId = GetInt(args, "ParentId");
            var parentPath = GetString(args, "ParentPath");
            if (parentId == null && string.IsNullOrEmpty(parentPath))
            {
                return null;
            }
            return ResolveByIdOrPath(parentId, parentPath, GetString(args, "ScenePath"), "parent");
        }

        private static Transform ResolveRequiredUiParent(JObject args)
        {
            var parentId = GetInt(args, "ParentId");
            var parentPath = GetString(args, "ParentPath");
            if (parentId == null && string.IsNullOrEmpty(parentPath))
            {
                throw new InvalidOperationException("Provide ParentId or ParentPath of a Canvas or UI element.");
            }
            var parent = ResolveByIdOrPath(parentId, parentPath, GetString(args, "ScenePath"), "parent");
            if (!(parent is RectTransform))
            {
                throw new InvalidOperationException("Parent has no RectTransform; create a Canvas first: " + GetPath(parent));
            }
            return parent;
        }

        private static IEnumerable<Transform> WalkScenes()
        {
            for (var index = 0; index < SceneManager.sceneCount; index++)
            {
                var scene = SceneManager.GetSceneAt(index);
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
                for (var index = transform.childCount - 1; index >= 0; index--)
                {
                    pending.Push(transform.GetChild(index));
                }
            }
        }

        private static string GetPath(Transform transform)
        {
            var names = new List<string>();
            for (var current = transform; current != null; current = current.parent)
            {
                names.Add(current.name);
            }
            names.Reverse();
            return string.Join("/", names);
        }

        private static string[] ComponentNames(GameObject gameObject)
        {
            return gameObject.GetComponents<Component>()
                .Select(component => component == null ? null : component.GetType().FullName)
                .ToArray();
        }

        private static bool HasComponent(GameObject gameObject, string fullName)
        {
            return gameObject.GetComponents<Component>()
                .Any(component => component != null && component.GetType().FullName == fullName);
        }

        private static string DescribeGraphic(Graphic graphic, Button button)
        {
            if (button != null)
            {
                return button.GetType().FullName;
            }
            return graphic == null ? null : graphic.GetType().FullName;
        }

        private static string ReadText(GameObject gameObject)
        {
            var text = gameObject.GetComponent<Text>();
            if (text != null)
            {
                return text.text;
            }
            foreach (var component in gameObject.GetComponents<Component>())
            {
                if (component == null)
                {
                    continue;
                }
                var type = component.GetType();
                if (type.FullName != "TMPro.TextMeshProUGUI" && type.FullName != "TMPro.TMP_Text")
                {
                    continue;
                }
                var property = type.GetProperty("text", BindingFlags.Public | BindingFlags.Instance);
                if (property != null)
                {
                    return property.GetValue(component, null) as string;
                }
            }
            return null;
        }

        private static void ApplyFont(Text text, string fontPath)
        {
            Font font;
            if (string.IsNullOrEmpty(fontPath))
            {
                font = Resources.GetBuiltinResource<Font>(BuiltInFontPath);
                if (font == null)
                {
                    throw new InvalidOperationException("The built-in legacy font is unavailable in this Unity version. Pass FontPath.");
                }
            }
            else
            {
                font = AssetDatabase.LoadAssetAtPath<Font>(fontPath);
                if (font == null)
                {
                    throw new InvalidOperationException("Font asset not found: " + fontPath);
                }
            }
            text.font = font;
        }

        private static Sprite LoadSpriteAsset(string assetPath)
        {
            if (string.IsNullOrEmpty(assetPath))
            {
                return null;
            }
            var sprite = AssetDatabase.LoadAssetAtPath<Sprite>(assetPath);
            if (sprite == null)
            {
                throw new InvalidOperationException("Sprite asset not found or not imported as a Sprite: " + assetPath);
            }
            return sprite;
        }

        private static TextAnchor ParseAlignment(string alignment)
        {
            if (string.IsNullOrEmpty(alignment))
            {
                return TextAnchor.MiddleCenter;
            }
            if (!Enum.TryParse(alignment, true, out TextAnchor anchor))
            {
                throw new ArgumentException("Alignment must be a UnityEngine.TextAnchor name.");
            }
            return anchor;
        }

        private static object Change(string field, object before, object after)
        {
            return new { field, before, after };
        }

        private static void RequireRange(string field, float value, float minimum, float maximum)
        {
            if (value < minimum || value > maximum)
            {
                throw new ArgumentOutOfRangeException(field, field + " must be between " + minimum + " and " + maximum + ".");
            }
        }

        private static void RequirePositive(string field, float value)
        {
            if (value <= 0f)
            {
                throw new ArgumentOutOfRangeException(field, field + " must be positive.");
            }
        }

        private static void CheckLimit(int limit)
        {
            if (limit < 1 || limit > 2000)
            {
                throw new ArgumentOutOfRangeException(nameof(limit), "Limit must be between 1 and 2000.");
            }
        }

        private static void MarkDirty(GameObject gameObject)
        {
            var scene = gameObject.scene;
            if (scene.IsValid() && !EditorSceneManager.IsPreviewScene(scene))
            {
                EditorSceneManager.MarkSceneDirty(scene);
            }
        }

        private static string CurrentRenderPipelineName()
        {
            var pipeline = GraphicsSettings.currentRenderPipeline;
            return pipeline == null ? "BuiltIn" : pipeline.GetType().Name;
        }

        private static Color? ParseOptionalColor(JObject args)
        {
            var text = GetString(args, "Color");
            return string.IsNullOrEmpty(text) ? (Color?)null : ParseColor(text);
        }

        private static Color ParseColor(string text)
        {
            var value = text.Trim();
            if (value.StartsWith("#", StringComparison.Ordinal))
            {
                value = value.Substring(1);
            }
            if (value.Length != 6 && value.Length != 8)
            {
                throw new ArgumentException("Colour must be RRGGBB or RRGGBBAA, got: " + text);
            }
            if (!ColorUtility.TryParseHtmlString("#" + value, out var color))
            {
                throw new ArgumentException("Colour could not be parsed: " + text);
            }
            return color;
        }

        private sealed class CapturePath
        {
            internal string AbsolutePath { get; set; }
            internal string RelativePath { get; set; }
            internal string AssetPath { get; set; }
        }

        private static CapturePath ResolveCapturePath(string outputPath, string cameraName)
        {
            var projectPath = Path.GetDirectoryName(Application.dataPath);
            if (string.IsNullOrEmpty(outputPath))
            {
                var directory = Path.Combine(projectPath, CaptureFolder.Replace('/', Path.DirectorySeparatorChar));
                Directory.CreateDirectory(directory);
                var fileName = SafeFileName(cameraName) + "-" + DateTime.UtcNow.ToString("yyyyMMdd_HHmmss_fff") + ".png";
                return new CapturePath
                {
                    AbsolutePath = Path.Combine(directory, fileName),
                    RelativePath = CaptureFolder + "/" + fileName,
                    AssetPath = null
                };
            }
            var normalized = outputPath.Replace('\\', '/').Trim();
            if (!normalized.EndsWith(".png", StringComparison.OrdinalIgnoreCase))
            {
                throw new ArgumentException("OutputPath must end with .png.");
            }
            var isAsset = normalized.StartsWith("Assets/", StringComparison.Ordinal);
            var isScratch = normalized.StartsWith("Temp/", StringComparison.Ordinal);
            if (!isAsset && !isScratch)
            {
                throw new ArgumentException("OutputPath must be project-relative under Assets/ or Temp/.");
            }
            if (normalized.Split('/').Any(segment => segment.Length == 0 || segment == "." || segment == ".."))
            {
                throw new ArgumentException("OutputPath must not contain empty, '.' or '..' segments.");
            }
            var absolute = Path.Combine(projectPath, normalized.Replace('/', Path.DirectorySeparatorChar));
            var directoryPath = Path.GetDirectoryName(absolute);
            if (!string.IsNullOrEmpty(directoryPath))
            {
                Directory.CreateDirectory(directoryPath);
            }
            return new CapturePath
            {
                AbsolutePath = absolute,
                RelativePath = normalized,
                AssetPath = isAsset ? normalized : null
            };
        }

        private static string NormalizeNewAssetPath(string assetPath, string extension, string field)
        {
            if (string.IsNullOrEmpty(assetPath))
            {
                return null;
            }
            var normalized = assetPath.Replace('\\', '/').Trim();
            if (!IsAssetPath(normalized))
            {
                throw new ArgumentException(field + " must be a project-relative path starting with Assets/.");
            }
            if (!normalized.EndsWith(extension, StringComparison.OrdinalIgnoreCase))
            {
                throw new ArgumentException(field + " must end with " + extension + ".");
            }
            return normalized;
        }

        private static string AssetPathToAbsolute(string assetPath)
        {
            return Path.Combine(Path.GetDirectoryName(Application.dataPath), assetPath.Replace('/', Path.DirectorySeparatorChar));
        }

        private static bool IsAssetPath(string path)
        {
            return !string.IsNullOrEmpty(path) && path.StartsWith("Assets/", StringComparison.Ordinal) &&
                !path.Contains("\\") && !path.Split('/').Any(segment => segment == "" || segment == "." || segment == "..");
        }

        private static string SafeFileName(string value)
        {
            var builder = new StringBuilder(value.Length);
            foreach (var character in value)
            {
                builder.Append(char.IsLetterOrDigit(character) || character == '-' || character == '_' ? character : '_');
            }
            return builder.Length == 0 ? "camera" : builder.ToString();
        }

        private static string Md5Hex(byte[] bytes)
        {
            using (var md5 = MD5.Create())
            {
                var hash = md5.ComputeHash(bytes);
                var builder = new StringBuilder(hash.Length * 2);
                foreach (var value in hash)
                {
                    builder.Append(value.ToString("x2"));
                }
                return builder.ToString();
            }
        }

        private static string EscapeXml(string value)
        {
            return string.IsNullOrEmpty(value)
                ? ""
                : value.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;").Replace("\"", "&quot;").Replace("'", "&apos;");
        }

        private static int? GetInt(JObject args, string name)
        {
            var token = args[name];
            return token == null || token.Type == JTokenType.Null ? (int?)null : token.Value<int>();
        }

        private static float? GetFloat(JObject args, string name)
        {
            var token = args[name];
            return token == null || token.Type == JTokenType.Null ? (float?)null : token.Value<float>();
        }

        private static bool? GetBool(JObject args, string name)
        {
            var token = args[name];
            return token == null || token.Type == JTokenType.Null ? (bool?)null : token.Value<bool>();
        }

        private static string GetString(JObject args, string name)
        {
            var token = args[name];
            return token == null || token.Type == JTokenType.Null ? null : token.Value<string>();
        }

        private static Vector2? GetVector2(JObject args, string name)
        {
            var values = GetFloatArray(args, name, 2);
            return values == null ? (Vector2?)null : new Vector2(values[0], values[1]);
        }

        private static Vector2Int? GetIntPair(JObject args, string name)
        {
            var values = GetIntArray(args, name, 2);
            return values == null ? (Vector2Int?)null : new Vector2Int(values[0], values[1]);
        }

        private static float[] GetFloatArray(JObject args, string name, int length)
        {
            var token = args[name];
            if (token == null || token.Type == JTokenType.Null)
            {
                return null;
            }
            var values = token.ToObject<float[]>();
            if (values == null || values.Length != length)
            {
                throw new ArgumentException(name + " must be an array of " + length + " numbers.");
            }
            return values;
        }

        private static int[] GetIntArray(JObject args, string name, int length)
        {
            var token = args[name];
            if (token == null || token.Type == JTokenType.Null)
            {
                return null;
            }
            var values = token.ToObject<int[]>();
            if (values == null || values.Length != length)
            {
                throw new ArgumentException(name + " must be an array of " + length + " integers.");
            }
            return values;
        }
    }
}
