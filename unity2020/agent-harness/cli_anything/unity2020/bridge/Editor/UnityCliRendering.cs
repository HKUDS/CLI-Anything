using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
#if UNITY_2020_2_OR_NEWER
using Unity.Profiling.LowLevel.Unsafe;
#endif
using UnityEngine;
using UnityEngine.Profiling;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

namespace CliAnything.Unity
{
    /// <summary>
    /// Profiler, graphics, material, particle, animator, physics and primitive commands
    /// dispatched by <see cref="UnityCliBridge"/> for Unity 2020.3.45f1.
    /// Read-only: profiler.status, profiler.frame-debugger (status), graphics.settings,
    /// graphics.lighting, material.list, material.inspect, particle.list, particle.inspect,
    /// animator.list, animator.inspect, physics.settings, physics.layers, physics.stats,
    /// physics.raycast, physics.raycast2d, physics.overlap, physics.overlap2d.
    /// Explicit writes: profiler.start, profiler.stop, material.create, material.set,
    /// primitive.create. Optional features (Frame Debugger, Memory Profiler, ProBuilder,
    /// VFX Graph) are detected at runtime and reported instead of being compiled in, so the
    /// editor assembly keeps zero package dependencies.
    /// </summary>
    internal static class UnityCliRendering
    {
        private const string UndoCreatePrimitive = "Unity CLI Create Primitive";
        private static readonly string[] OwnedPrefixes =
        {
            "profiler.", "graphics.", "material.", "particle.", "animator.", "physics.", "primitive."
        };

        private static FrameDebuggerApi _frameDebugger;

        internal static bool TryExecute(string command, JObject args, out object result)
        {
            result = null;
            if (string.IsNullOrEmpty(command))
            {
                return false;
            }
            if (!OwnedPrefixes.Any(prefix => command.StartsWith(prefix, StringComparison.Ordinal)))
            {
                return false;
            }
            args = args ?? new JObject();
            try
            {
                switch (command)
                {
                    case "profiler.status":
                        result = Ok(ProfilerStatus());
                        return true;
                    case "profiler.start":
                        result = Ok(SetProfilerEnabled(true));
                        return true;
                    case "profiler.stop":
                        result = Ok(SetProfilerEnabled(false));
                        return true;
                    case "profiler.frame-debugger":
                        result = Ok(FrameDebugger(GetString(args, "Action") ?? "status"));
                        return true;
                    case "graphics.settings":
                        result = Ok(GraphicsSettingsInfo());
                        return true;
                    case "graphics.lighting":
                        result = Ok(LightingInfo());
                        return true;
                    case "material.list":
                        result = Ok(ListMaterials(GetString(args, "Filter") ?? "", GetInt(args, "Limit") ?? 100));
                        return true;
                    case "material.inspect":
                        result = Ok(InspectMaterial(args));
                        return true;
                    case "material.create":
                        result = Ok(CreateMaterial(args));
                        return true;
                    case "material.set":
                        result = Ok(SetMaterialProperty(args));
                        return true;
                    case "particle.list":
                        result = Ok(ListParticles(GetString(args, "Filter") ?? "", GetInt(args, "Limit") ?? 100));
                        return true;
                    case "particle.inspect":
                        result = Ok(InspectParticleSystem(args));
                        return true;
                    case "animator.list":
                        result = Ok(ListAnimators(GetString(args, "Filter") ?? "", GetInt(args, "Limit") ?? 100));
                        return true;
                    case "animator.inspect":
                        result = Ok(InspectAnimator(args));
                        return true;
                    case "physics.settings":
                        result = Ok(PhysicsSettings());
                        return true;
                    case "physics.layers":
                        result = Ok(PhysicsLayers());
                        return true;
                    case "physics.stats":
                        result = Ok(PhysicsStats());
                        return true;
                    case "physics.raycast":
                        result = Ok(PhysicsRaycast(args));
                        return true;
                    case "physics.raycast2d":
                        result = Ok(PhysicsRaycast2D(args));
                        return true;
                    case "physics.overlap":
                        result = Ok(PhysicsOverlap(args));
                        return true;
                    case "physics.overlap2d":
                        result = Ok(PhysicsOverlap2D(args));
                        return true;
                    case "primitive.create":
                        result = Ok(CreatePrimitive(args));
                        return true;
                    default:
                        result = Fail("Unsupported Unity CLI rendering command: " + command);
                        return true;
                }
            }
            catch (Exception exception)
            {
                Debug.LogError("[Unity CLI] " + exception);
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

        // -------------------------------------------------------------- profiler

        private static object ProfilerStatus()
        {
            var profiler = new Dictionary<string, object>
            {
                { "enabled", Profiler.enabled },
                { "supported", true },
                { "driverAvailable", true }
            };
            var driver = new Dictionary<string, object>();
            try
            {
                driver["enabled"] = UnityEditorInternal.ProfilerDriver.enabled;
                driver["profileEditor"] = UnityEditorInternal.ProfilerDriver.profileEditor;
                driver["firstFrameIndex"] = UnityEditorInternal.ProfilerDriver.firstFrameIndex;
                driver["lastFrameIndex"] = UnityEditorInternal.ProfilerDriver.lastFrameIndex;
                driver["frameCount"] = Math.Max(0, UnityEditorInternal.ProfilerDriver.lastFrameIndex - UnityEditorInternal.ProfilerDriver.firstFrameIndex + 1);
            }
            catch (Exception exception)
            {
                driver["error"] = exception.Message;
            }

            var frameDebugger = DescribeFrameDebugger();
            return new
            {
                unityVersion = Application.unityVersion,
                editor = new
                {
                    isPlaying = EditorApplication.isPlaying,
                    isPaused = EditorApplication.isPaused,
                    isCompiling = EditorApplication.isCompiling,
                    isUpdating = EditorApplication.isUpdating
                },
                profiler,
                editorProfiler = driver,
                frameDebugger,
                counters = DescribeProfilerCounters(),
                memorySnapshots = new
                {
                    supported = false,
                    note = "Memory snapshots stay in the Memory Profiler window. The package API is not stable across 0.7.0-preview and is not called here."
                },
                packages = FeaturePackages()
            };
        }

        private static object DescribeProfilerCounters()
        {
#if UNITY_2020_2_OR_NEWER
            var handles = new List<ProfilerRecorderHandle>();
            try
            {
                ProfilerRecorderHandle.GetAvailable(handles);
            }
            catch (Exception exception)
            {
                return new
                {
                    enumerable = false,
                    error = exception.Message,
                    note = "Unity.Profiling.LowLevel.Unsafe.ProfilerRecorderHandle.GetAvailable failed; ProfilerRecorder can still be started from a category and marker name."
                };
            }

            const int limit = 50;
            var sample = new List<object>();
            foreach (var handle in handles.Take(limit))
            {
                try
                {
                    var description = ProfilerRecorderHandle.GetDescription(handle);
                    sample.Add(new { category = description.Category.Name, name = description.Name });
                }
                catch (Exception)
                {
                    // A handle can vanish between enumeration and description; skip it.
                }
            }
            return new
            {
                enumerable = true,
                count = handles.Count,
                returned = sample.Count,
                truncated = handles.Count > sample.Count,
                sample = sample.ToArray(),
                note = "Enumerated with Unity.Profiling.LowLevel.Unsafe.ProfilerRecorderHandle.GetAvailable on Unity " +
                    Application.unityVersion + "; record values with ProfilerRecorder."
            };
#else
            return new { enumerable = false, note = "ProfilerRecorder counter enumeration requires Unity 2020.2 or newer." };
#endif
        }

        private static object SetProfilerEnabled(bool enabled)
        {
            RequireIdleEditor();
            var before = UnityEditorInternal.ProfilerDriver.enabled;
            UnityEditorInternal.ProfilerDriver.enabled = enabled;
            Profiler.enabled = enabled;
            return new
            {
                requested = enabled,
                changed = before != UnityEditorInternal.ProfilerDriver.enabled,
                editorProfiler = new
                {
                    enabled = UnityEditorInternal.ProfilerDriver.enabled,
                    profileEditor = UnityEditorInternal.ProfilerDriver.profileEditor,
                    firstFrameIndex = UnityEditorInternal.ProfilerDriver.firstFrameIndex,
                    lastFrameIndex = UnityEditorInternal.ProfilerDriver.lastFrameIndex
                },
                profilerEnabled = Profiler.enabled
            };
        }

        private static object FrameDebugger(string action)
        {
            var api = _frameDebugger ?? (_frameDebugger = DiscoverFrameDebugger());
            var normalized = (action ?? "status").Trim().ToLowerInvariant();
            if (normalized == "status")
            {
                return DescribeFrameDebugger();
            }
            if (normalized != "enable" && normalized != "disable")
            {
                throw new ArgumentException("Action must be status, enable or disable.");
            }
            var requested = normalized == "enable";
            if (!api.CanToggle)
            {
                throw new InvalidOperationException(
                    "Frame Debugger cannot be toggled through a managed API in Unity " + Application.unityVersion +
                    (string.IsNullOrEmpty(api.Partial)
                        ? ": no managed toggle was found."
                        : ": only a partial API was found (" + api.Partial + "), which cannot be verified.") +
                    " Open Window > Analysis > Frame Debugger manually instead.");
            }
            if (api.EnabledProperty != null)
            {
                api.EnabledProperty.SetValue(null, requested, null);
            }
            else
            {
                (requested ? api.EnableMethod : api.DisableMethod).Invoke(null, null);
            }
            return new { requested, frameDebugger = DescribeFrameDebugger() };
        }

        private static object DescribeFrameDebugger()
        {
            var api = _frameDebugger ?? (_frameDebugger = DiscoverFrameDebugger());
            bool? enabled = null;
            if (api.EnabledProperty != null && api.EnabledProperty.CanRead)
            {
                try
                {
                    enabled = (bool)api.EnabledProperty.GetValue(null, null);
                }
                catch (Exception)
                {
                    enabled = null;
                }
            }
            return new
            {
                available = api.CanToggle,
                partial = api.Partial,
                enabled,
                type = api.TypeName,
                discovered = api.Candidates,
                note = api.CanToggle
                    ? "Reflection found a writable managed toggle or both enable and disable methods; enable/disable use it directly."
                    : string.IsNullOrEmpty(api.Partial)
                        ? "Unity " + Application.unityVersion + " exposes the Frame Debugger only through Window > Analysis > Frame Debugger; no managed toggle was found, so enable/disable refuse instead of guessing."
                        : "Only a partial Frame Debugger API was found (" + api.Partial + "), which cannot be verified without the opposite direction or readable state; enable/disable refuse. Use Window > Analysis > Frame Debugger."
            };
        }

        private static FrameDebuggerApi DiscoverFrameDebugger()
        {
            var candidates = new List<string>();
            FrameDebuggerApi partial = null;
            FrameDebuggerApi complete = null;
            foreach (var assembly in EditorAssemblies())
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
                catch (Exception)
                {
                    continue;
                }
                foreach (var type in types)
                {
                    if (type.Name.IndexOf("FrameDebugger", StringComparison.Ordinal) < 0 || type.IsEnum)
                    {
                        continue;
                    }
                    if (candidates.Count < 12)
                    {
                        candidates.Add(type.FullName);
                    }
                    const BindingFlags flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static;
                    PropertyInfo toggle = null;
                    foreach (var property in type.GetProperties(flags))
                    {
                        if (property.PropertyType != typeof(bool) || property.GetIndexParameters().Length > 0 || !property.CanWrite)
                        {
                            continue;
                        }
                        if (property.Name == "enabled" || property.Name == "isEnabled" || property.Name == "IsEnabled")
                        {
                            toggle = property;
                            break;
                        }
                    }
                    MethodInfo enable = null;
                    MethodInfo disable = null;
                    foreach (var method in type.GetMethods(flags))
                    {
                        if (method.GetParameters().Length != 0)
                        {
                            continue;
                        }
                        if (enable == null && (method.Name == "EnableFrameDebuggerCapture" ||
                            method.Name == "EnableFrameDebugger" || method.Name == "ClickEnableFrameDebugger"))
                        {
                            enable = method;
                        }
                        else if (disable == null && (method.Name == "DisableFrameDebuggerCapture" ||
                            method.Name == "DisableFrameDebugger"))
                        {
                            disable = method;
                        }
                    }

                    var candidate = new FrameDebuggerApi
                    {
                        TypeName = type.FullName,
                        EnabledProperty = toggle,
                        EnableMethod = enable,
                        DisableMethod = disable
                    };
                    if (candidate.CanToggle)
                    {
                        complete = candidate;
                        break;
                    }
                    if (partial == null && (toggle != null || enable != null || disable != null))
                    {
                        candidate.Partial = DescribePartialFrameDebuggerApi(type, toggle, enable, disable);
                        partial = candidate;
                    }
                }
                if (complete != null)
                {
                    break;
                }
            }

            var api = complete ?? partial ?? new FrameDebuggerApi();
            api.Candidates = candidates.ToArray();
            return api;
        }

        private static string DescribePartialFrameDebuggerApi(Type type, PropertyInfo toggle, MethodInfo enable, MethodInfo disable)
        {
            var found = new List<string>();
            if (toggle != null)
            {
                found.Add(type.Name + "." + toggle.Name);
            }
            if (enable != null)
            {
                found.Add(type.Name + "." + enable.Name + "()");
            }
            if (disable != null)
            {
                found.Add(type.Name + "." + disable.Name + "()");
            }
            return string.Join(", ", found.ToArray());
        }

        // -------------------------------------------------------------- graphics

        private static object GraphicsSettingsInfo()
        {
            var pipeline = GraphicsSettings.currentRenderPipeline;
            var qualityIndex = QualitySettings.GetQualityLevel();
            var qualityNames = QualitySettings.names;
            var shaderLods = Enumerable.Range(0, qualityNames.Length)
                .Select(level => new { level, name = qualityNames[level] })
                .ToArray();
            return new
            {
                unityVersion = Application.unityVersion,
                pipeline = new
                {
                    name = pipeline == null ? "BuiltIn" : pipeline.GetType().Name,
                    type = pipeline == null ? null : pipeline.GetType().FullName,
                    assetPath = AssetPathOf(pipeline),
                    defaultAssetPath = AssetPathOf(GraphicsSettings.renderPipelineAsset),
                    scriptableBatching = GraphicsSettings.useScriptableRenderPipelineBatching,
                    transparencySortMode = GraphicsSettings.transparencySortMode.ToString(),
                    lightsUseLinearIntensity = GraphicsSettings.lightsUseLinearIntensity,
                    logWhenShaderIsCompiled = GraphicsSettings.logWhenShaderIsCompiled,
                    defaultRenderingLayerMask = GraphicsSettings.defaultRenderingLayerMask,
                    settings = PipelineAssetSettings(pipeline)
                },
                quality = new
                {
                    index = qualityIndex,
                    name = qualityIndex >= 0 && qualityIndex < qualityNames.Length ? qualityNames[qualityIndex] : null,
                    names = qualityNames,
                    levels = shaderLods,
                    settings = QualitySettingsInfo()
                },
                device = new
                {
                    graphicsDeviceName = SystemInfo.graphicsDeviceName,
                    graphicsDeviceType = SystemInfo.graphicsDeviceType.ToString(),
                    graphicsMemoryMB = SystemInfo.graphicsMemorySize,
                    graphicsShaderLevel = SystemInfo.graphicsShaderLevel,
                    maxTextureSize = SystemInfo.maxTextureSize,
                    supportsInstancing = SystemInfo.supportsInstancing,
                    processorType = SystemInfo.processorType,
                    processorCount = SystemInfo.processorCount,
                    systemMemoryMB = SystemInfo.systemMemorySize
                },
                screen = new
                {
                    width = Screen.width,
                    height = Screen.height,
                    fullScreenMode = Screen.fullScreenMode.ToString(),
                    targetFrameRate = Application.targetFrameRate,
                    colorSpace = QualitySettings.activeColorSpace.ToString()
                },
                renderSettings = RenderSettingsInfo(),
                shaderLods = new
                {
                    globalMaximumLOD = Shader.globalMaximumLOD,
                    qualityMaximumLOD = QualitySettings.maximumLODLevel,
                    lodBias = QualitySettings.lodBias
                },
                packages = FeaturePackages()
            };
        }

        private static object QualitySettingsInfo()
        {
            return new
            {
                antiAliasing = QualitySettings.antiAliasing,
                anisotropicFiltering = QualitySettings.anisotropicFiltering.ToString(),
                shadows = QualitySettings.shadows.ToString(),
                shadowResolution = QualitySettings.shadowResolution.ToString(),
                shadowProjection = QualitySettings.shadowProjection.ToString(),
                shadowCascades = QualitySettings.shadowCascades,
                shadowDistance = Number(QualitySettings.shadowDistance),
                shadowNearPlaneOffset = Number(QualitySettings.shadowNearPlaneOffset),
                shadowmaskMode = QualitySettings.shadowmaskMode.ToString(),
                pixelLightCount = QualitySettings.pixelLightCount,
                vSyncCount = QualitySettings.vSyncCount,
#if UNITY_2022_2_OR_NEWER
                masterTextureLimit = QualitySettings.globalTextureMipmapLimit,
#else
                masterTextureLimit = QualitySettings.masterTextureLimit,
#endif
                lodBias = Number(QualitySettings.lodBias),
                maximumLODLevel = QualitySettings.maximumLODLevel,
                particleRaycastBudget = QualitySettings.particleRaycastBudget,
                softParticles = QualitySettings.softParticles,
                realtimeReflectionProbes = QualitySettings.realtimeReflectionProbes,
                billboardsFaceCameraPosition = QualitySettings.billboardsFaceCameraPosition,
                skinWeights = QualitySettings.skinWeights.ToString(),
                maxQueuedFrames = QualitySettings.maxQueuedFrames,
                resolutionScalingFixedDPIFactor = Number(QualitySettings.resolutionScalingFixedDPIFactor),
                asyncUploadTimeSlice = QualitySettings.asyncUploadTimeSlice,
                asyncUploadBufferSize = QualitySettings.asyncUploadBufferSize,
                streamingMipmapsActive = QualitySettings.streamingMipmapsActive
            };
        }

        private static object RenderSettingsInfo()
        {
            var ambient = RenderSettings.ambientLight;
            var fog = RenderSettings.fogColor;
            return new
            {
                ambientMode = RenderSettings.ambientMode.ToString(),
                ambientLight = Hex(ambient),
                ambientIntensity = Number(RenderSettings.ambientIntensity),
                skybox = AssetRef(RenderSettings.skybox),
                fog = RenderSettings.fog,
                fogMode = RenderSettings.fogMode.ToString(),
                fogColor = Hex(fog),
                fogDensity = Number(RenderSettings.fogDensity),
                reflectionIntensity = Number(RenderSettings.reflectionIntensity),
                defaultReflectionMode = RenderSettings.defaultReflectionMode.ToString(),
                haloStrength = Number(RenderSettings.haloStrength),
                flareStrength = Number(RenderSettings.flareStrength)
            };
        }

        private static object PipelineAssetSettings(Object pipeline)
        {
            if (pipeline == null)
            {
                return null;
            }
            var values = new List<PipelineSetting>();
            try
            {
                foreach (var property in pipeline.GetType().GetProperties(BindingFlags.Public | BindingFlags.Instance))
                {
                    if (values.Count >= 200)
                    {
                        break;
                    }
                    if (!property.CanRead || property.GetIndexParameters().Length > 0)
                    {
                        continue;
                    }
                    var type = property.PropertyType;
                    var simple = type == typeof(bool) || type == typeof(int) || type == typeof(float) ||
                        type == typeof(double) || type == typeof(string) || type.IsEnum;
                    if (!simple)
                    {
                        continue;
                    }
                    string text;
                    try
                    {
                        var value = property.GetValue(pipeline, null);
                        text = value == null ? null : value.ToString();
                    }
                    catch (Exception)
                    {
                        continue;
                    }
                    values.Add(new PipelineSetting { Name = property.Name, Type = type.Name, Value = text });
                }
            }
            catch (Exception)
            {
                // A pipeline asset type that rejects reflection simply yields no settings.
            }
            return new
            {
                type = pipeline.GetType().FullName,
                properties = values.OrderBy(item => item.Name, StringComparer.Ordinal)
                    .Select(item => new { name = item.Name, type = item.Type, value = item.Value }).ToArray(),
                truncated = values.Count >= 200
            };
        }

        private static object LightingInfo()
        {
            var settings = Lightmapping.lightingSettings;
            var transforms = WalkScenes().ToArray();
            var lights = transforms.Select(transform => transform.GetComponent<Light>()).Where(light => light != null).ToArray();
            var probeGroups = transforms.Select(transform => transform.GetComponent<LightProbeGroup>()).Where(group => group != null).ToArray();
            var reflectionProbes = transforms.Select(transform => transform.GetComponent<ReflectionProbe>()).Where(probe => probe != null).ToArray();
            return new
            {
                baking = new
                {
                    isRunning = Lightmapping.isRunning,
                    lightingSettingsAsset = AssetRef(settings),
                    sceneUsesBakedData = settings != null && settings.bakedGI,
                    autoGenerate = settings != null && settings.autoGenerate
                },
                lightingSettings = settings == null ? null : new
                {
                    name = settings.name,
                    assetPath = AssetPathOf(settings),
                    bakedGI = settings.bakedGI,
                    realtimeGI = settings.realtimeGI,
                    lightmapper = settings.lightmapper.ToString(),
                    mixedBakeMode = settings.mixedBakeMode.ToString(),
                    lightmapResolution = settings.lightmapResolution,
                    lightmapPadding = settings.lightmapPadding,
                    lightmapMaxSize = settings.lightmapMaxSize,
                    ambientOcclusion = settings.ao,
                    ambientOcclusionMaxDistance = Number(settings.aoMaxDistance),
                    ambientOcclusionExponent = Number(settings.aoExponentIndirect),
                    directSampleCount = settings.directSampleCount,
                    indirectSampleCount = settings.indirectSampleCount,
                    environmentSampleCount = settings.environmentSampleCount,
                    maxBounces = settings.maxBounces,
                    minBounces = settings.minBounces,
                    filteringMode = settings.filteringMode.ToString(),
                    prioritizeView = settings.prioritizeView,
                    exportTrainingData = settings.exportTrainingData,
                    trainingDataDestination = settings.trainingDataDestination
                },
                lights = new
                {
                    total = lights.Length,
                    byType = lights.GroupBy(light => light.type.ToString())
                        .Select(group => new { type = group.Key, count = group.Count() }).ToArray(),
                    byBakeType = lights.GroupBy(light => light.lightmapBakeType.ToString())
                        .Select(group => new { bakeType = group.Key, count = group.Count() }).ToArray(),
                    shadowCasters = lights.Count(light => light.shadows != LightShadows.None)
                },
                probes = new
                {
                    lightProbeGroups = probeGroups.Length,
                    lightProbes = probeGroups.Sum(group => group.probePositions.Length),
                    reflectionProbes = reflectionProbes.Length,
                    reflectionProbeModes = reflectionProbes.GroupBy(probe => probe.mode.ToString())
                        .Select(group => new { mode = group.Key, count = group.Count() }).ToArray()
                },
                renderSettings = RenderSettingsInfo()
            };
        }

        // -------------------------------------------------------------- material

        private static object ListMaterials(string filter, int limit)
        {
            CheckLimit(limit);
            var renderers = WalkScenes()
                .Select(transform => transform.GetComponent<Renderer>())
                .Where(renderer => renderer != null)
                .Where(renderer => renderer.name.IndexOf(filter, StringComparison.OrdinalIgnoreCase) >= 0)
                .ToArray();
            var entries = renderers.Take(limit).Select(renderer => new
            {
                objectId = renderer.gameObject.GetInstanceID(),
                name = renderer.name,
                path = GetPath(renderer.transform),
                type = renderer.GetType().Name,
                active = renderer.gameObject.activeInHierarchy,
                enabled = renderer.enabled,
                slots = DescribeMaterialSlots(renderer.sharedMaterials)
            }).ToArray();
            var materials = renderers.SelectMany(renderer => renderer.sharedMaterials)
                .Where(material => material != null)
                .Select(AssetPathOf)
                .Where(path => !string.IsNullOrEmpty(path))
                .Distinct(StringComparer.Ordinal)
                .Count();
            return new
            {
                renderers = entries,
                total = renderers.Length,
                totalSlots = renderers.Sum(renderer => renderer.sharedMaterials.Length),
                missingSlots = renderers.Sum(renderer => renderer.sharedMaterials.Count(material => material == null)),
                uniqueMaterialAssets = materials,
                truncated = renderers.Length > limit
            };
        }

        private static object[] DescribeMaterialSlots(Material[] materials)
        {
            var slots = new object[materials.Length];
            for (var index = 0; index < materials.Length; index++)
            {
                var material = materials[index];
                slots[index] = material == null
                    ? (object)new { index, name = (string)null, assetPath = (string)null, shader = (string)null, missing = true }
                    : new { index, name = material.name, assetPath = AssetPathOf(material), shader = material.shader == null ? null : material.shader.name, missing = false };
            }
            return slots;
        }

        private static object InspectMaterial(JObject args)
        {
            var assetPath = GetString(args, "AssetPath");
            var limit = GetInt(args, "Limit") ?? 200;
            CheckLimit(limit);
            if (!string.IsNullOrEmpty(assetPath))
            {
                var material = LoadMaterialAsset(assetPath);
                return new
                {
                    source = "asset",
                    material = MaterialInfo(material, limit),
                    renderer = (object)null,
                    slot = (int?)null
                };
            }

            var transform = ResolveTarget(args, "renderer");
            var renderer = transform.GetComponent<Renderer>();
            if (renderer == null)
            {
                throw new InvalidOperationException("GameObject has no Renderer: " + GetPath(transform));
            }
            var slot = GetInt(args, "Slot") ?? 0;
            var materials = renderer.sharedMaterials;
            if (slot < 0 || slot >= materials.Length)
            {
                throw new ArgumentOutOfRangeException(nameof(slot), "Slot must be between 0 and " + (materials.Length - 1) + ".");
            }
            var target = materials[slot];
            return new
            {
                source = "renderer",
                material = target == null ? null : MaterialInfo(target, limit),
                renderer = new
                {
                    objectId = renderer.gameObject.GetInstanceID(),
                    name = renderer.name,
                    path = GetPath(renderer.transform),
                    type = renderer.GetType().Name,
                    slots = DescribeMaterialSlots(materials)
                },
                slot
            };
        }

        private static Action<UnityEngine.Object> GetIsolatedAssetSaver()
        {
            var method = typeof(AssetDatabase).GetMethod("SaveAssetIfDirty", new[] { typeof(UnityEngine.Object) });
            if (method == null)
            {
                throw new NotSupportedException("This Unity version cannot save a single asset. Material writes are unavailable.");
            }
            return (Action<UnityEngine.Object>)Delegate.CreateDelegate(typeof(Action<UnityEngine.Object>), method);
        }

        private static object CreateMaterial(JObject args)
        {
            RequireIdleEditor();
            var saveAsset = GetIsolatedAssetSaver();
            var assetPath = NormalizeAssetPath(GetString(args, "AssetPath"), ".mat", "AssetPath");
            var shaderName = GetString(args, "Shader");
            if (string.IsNullOrEmpty(shaderName))
            {
                throw new ArgumentException("Shader is required, for example Standard or Universal Render Pipeline/Lit.");
            }
            var directory = Path.GetDirectoryName(assetPath) ?? "";
            if (!AssetDatabase.IsValidFolder(directory))
            {
                throw new InvalidOperationException("Asset folder does not exist: " + directory);
            }
            var absolutePath = ProjectAbsolutePath(assetPath);
            if (File.Exists(absolutePath))
            {
                throw new InvalidOperationException(
                    "A file already exists at " + assetPath + " (it may still be importing); refusing to overwrite it.");
            }
            if (File.Exists(absolutePath + ".meta"))
            {
                throw new InvalidOperationException(
                    "A stale .meta file already exists for " + assetPath + "; let Unity import or delete it before creating the material.");
            }
            var trackedType = AssetDatabase.GetMainAssetTypeAtPath(assetPath);
            if (trackedType != null)
            {
                throw new InvalidOperationException(
                    "AssetDatabase already tracks a " + trackedType.Name + " at " + assetPath + "; refusing to overwrite it.");
            }
            var shader = Shader.Find(shaderName);
            if (shader == null)
            {
                throw new InvalidOperationException("Shader not found: " + shaderName);
            }

            var properties = args["Properties"] as JObject ?? new JObject();
            var parsed = new List<MaterialAssignment>();
            foreach (var property in properties.Properties())
            {
                var index = IndexOfShaderProperty(shader, property.Name);
                if (index < 0)
                {
                    throw new InvalidOperationException("Shader has no property named " + property.Name + ". Available: " + ShaderPropertyNames(shader) + ".");
                }
                var type = shader.GetPropertyType(index);
                parsed.Add(new MaterialAssignment
                {
                    Name = property.Name,
                    Type = type,
                    Value = ParseShaderValue(property.Name, type, property.Value)
                });
            }

            var material = new Material(shader);
            foreach (var assignment in parsed)
            {
                ApplyShaderValue(material, assignment);
            }
            material.name = Path.GetFileNameWithoutExtension(assetPath);
            AssetDatabase.CreateAsset(material, assetPath);
            EditorUtility.SetDirty(material);
            saveAsset(material);

            var created = LoadMaterialAsset(assetPath);
            return new
            {
                created = true,
                assetPath,
                shader = new { name = shader.name, assetPath = AssetPathOf(shader) },
                propertiesApplied = parsed.Select(assignment => assignment.Name).ToArray(),
                material = MaterialInfo(created, 200)
            };
        }

        private static object SetMaterialProperty(JObject args)
        {
            RequireIdleEditor();
            var saveAsset = GetIsolatedAssetSaver();
            var assetPath = GetString(args, "AssetPath");
            var material = LoadMaterialAsset(assetPath);
            var propertyName = GetString(args, "Property");
            if (string.IsNullOrEmpty(propertyName))
            {
                throw new ArgumentException("Property is required, for example _BaseColor or _Metallic.");
            }
            if (args["Value"] == null || args["Value"].Type == JTokenType.Null)
            {
                throw new ArgumentException("Value is required. Use a number for float/range, an array for color/vector or a texture asset path.");
            }
            var shader = material.shader;
            if (shader == null)
            {
                throw new InvalidOperationException("Material has no shader: " + assetPath);
            }
            var index = IndexOfShaderProperty(shader, propertyName);
            if (index < 0)
            {
                throw new InvalidOperationException("Shader " + shader.name + " has no property named " + propertyName + ". Available: " + ShaderPropertyNames(shader) + ".");
            }
            var type = shader.GetPropertyType(index);
            var parsed = ParseShaderValue(propertyName, type, args["Value"]);
            var before = ReadShaderValue(material, shader, index);

            Undo.RecordObject(material, "Unity CLI Set Material Property");
            ApplyShaderValue(material, new MaterialAssignment { Name = propertyName, Type = type, Value = parsed });
            EditorUtility.SetDirty(material);
            saveAsset(material);

            return new
            {
                assetPath = AssetPathOf(material),
                property = propertyName,
                shaderType = type.ToString(),
                before,
                after = ReadShaderValue(material, shader, index),
                applied = FormatShaderValue(parsed)
            };
        }

        private static object MaterialInfo(Material material, int limit)
        {
            var shader = material.shader;
            var properties = new List<object>();
            if (shader != null)
            {
                var count = Math.Min(shader.GetPropertyCount(), limit);
                for (var index = 0; index < count; index++)
                {
                    properties.Add(ShaderPropertyInfo(material, shader, index));
                }
            }
            return new
            {
                name = material.name,
                assetPath = AssetPathOf(material),
                shader = shader == null ? null : new
                {
                    name = shader.name,
                    assetPath = AssetPathOf(shader),
                    propertyCount = shader.GetPropertyCount()
                },
                renderQueue = material.renderQueue,
                keywords = material.shaderKeywords,
                properties,
                truncated = shader != null && shader.GetPropertyCount() > limit
            };
        }

        private static object ShaderPropertyInfo(Material material, Shader shader, int index)
        {
            var name = shader.GetPropertyName(index);
            var type = shader.GetPropertyType(index);
            return new
            {
                name,
                type = type.ToString(),
                description = shader.GetPropertyDescription(index),
                value = ReadShaderValue(material, shader, index)
            };
        }

        private static object ReadShaderValue(Material material, Shader shader, int index)
        {
            var name = shader.GetPropertyName(index);
            switch (shader.GetPropertyType(index))
            {
                case ShaderPropertyType.Color:
                    return ColorValue(material.GetColor(name));
                case ShaderPropertyType.Vector:
                    var vector = material.GetVector(name);
                    return new { vector = new[] { vector.x, vector.y, vector.z, vector.w } };
                case ShaderPropertyType.Texture:
                    return new
                    {
                        texture = material.HasProperty(name) ? AssetRef(material.GetTexture(name)) : null,
                        scale = ReadTextureScale(material, name),
                        offset = ReadTextureOffset(material, name)
                    };
                default:
                    return new { number = Number(material.GetFloat(name)) };
            }
        }

        private static object ReadTextureScale(Material material, string name)
        {
            if (!material.HasProperty(name + "_ST"))
            {
                return null;
            }
            var value = material.GetVector(name + "_ST");
            return new[] { value.x, value.y };
        }

        private static object ReadTextureOffset(Material material, string name)
        {
            if (!material.HasProperty(name + "_ST"))
            {
                return null;
            }
            var value = material.GetVector(name + "_ST");
            return new[] { value.z, value.w };
        }

        private static object ParseShaderValue(string propertyName, ShaderPropertyType type, JToken token)
        {
            switch (type)
            {
                case ShaderPropertyType.Color:
                    return ParseColorToken(propertyName, token);
                case ShaderPropertyType.Vector:
                    var vector = ParseFloatArray(propertyName, token, 3, 4);
                    return new Vector4(vector[0], vector[1], vector[2], vector.Length == 4 ? vector[3] : 0f);
                case ShaderPropertyType.Texture:
                    return ParseTextureToken(propertyName, token);
                default:
                    if (token.Type != JTokenType.Float && token.Type != JTokenType.Integer)
                    {
                        throw new ArgumentException(propertyName + " is a float property; pass a number.");
                    }
                    return token.Value<float>();
            }
        }

        private static Color ParseColorToken(string propertyName, JToken token)
        {
            if (token.Type == JTokenType.String)
            {
                var text = token.Value<string>();
                if (!ColorUtility.TryParseHtmlString(text, out var color))
                {
                    throw new ArgumentException(propertyName + " colour could not be parsed: " + text);
                }
                return color;
            }
            var values = ParseFloatArray(propertyName, token, 3, 4);
            return values.Length == 4
                ? new Color(values[0], values[1], values[2], values[3])
                : new Color(values[0], values[1], values[2], 1f);
        }

        private static Texture ParseTextureToken(string propertyName, JToken token)
        {
            if (token.Type != JTokenType.String)
            {
                throw new ArgumentException(propertyName + " is a texture property; pass an Assets/... texture path or an empty string.");
            }
            var path = token.Value<string>();
            if (string.IsNullOrEmpty(path))
            {
                return null;
            }
            if (!IsAssetPath(path))
            {
                throw new ArgumentException(propertyName + " texture must be a project-relative path starting with Assets/.");
            }
            var texture = AssetDatabase.LoadAssetAtPath<Texture>(path);
            if (texture == null)
            {
                throw new InvalidOperationException("Texture not found: " + path);
            }
            return texture;
        }

        private static void ApplyShaderValue(Material material, MaterialAssignment assignment)
        {
            switch (assignment.Type)
            {
                case ShaderPropertyType.Color:
                    material.SetColor(assignment.Name, (Color)assignment.Value);
                    break;
                case ShaderPropertyType.Vector:
                    material.SetVector(assignment.Name, (Vector4)assignment.Value);
                    break;
                case ShaderPropertyType.Texture:
                    material.SetTexture(assignment.Name, assignment.Value as Texture);
                    break;
                default:
                    material.SetFloat(assignment.Name, Convert.ToSingle(assignment.Value));
                    break;
            }
        }

        private static string FormatShaderValue(object value)
        {
            if (value == null)
            {
                return "cleared";
            }
            if (value is Color color)
            {
                return Hex(color);
            }
            if (value is Vector4 vector)
            {
                return vector.x + "," + vector.y + "," + vector.z + "," + vector.w;
            }
            if (value is Texture texture)
            {
                return AssetPathOf(texture) ?? texture.name;
            }
            return Convert.ToString(value, System.Globalization.CultureInfo.InvariantCulture);
        }

        private static float[] ParseFloatArray(string propertyName, JToken token, params int[] lengths)
        {
            if (token.Type != JTokenType.Array)
            {
                throw new ArgumentException(propertyName + " expects an array of " + string.Join(" or ", lengths) + " numbers.");
            }
            var values = token.ToObject<float[]>();
            if (values == null || !lengths.Contains(values.Length))
            {
                throw new ArgumentException(propertyName + " expects an array of " + string.Join(" or ", lengths) + " numbers.");
            }
            return values;
        }

        private static int IndexOfShaderProperty(Shader shader, string name)
        {
            var count = shader.GetPropertyCount();
            for (var index = 0; index < count; index++)
            {
                if (string.Equals(shader.GetPropertyName(index), name, StringComparison.Ordinal))
                {
                    return index;
                }
            }
            return -1;
        }

        private static string ShaderPropertyNames(Shader shader)
        {
            var count = shader.GetPropertyCount();
            var names = new List<string>();
            for (var index = 0; index < count && names.Count < 24; index++)
            {
                names.Add(shader.GetPropertyName(index));
            }
            return string.Join(", ", names) + (count > names.Count ? ", ..." : "");
        }

        private static Material LoadMaterialAsset(string assetPath)
        {
            if (!IsAssetPath(assetPath) || !assetPath.EndsWith(".mat", StringComparison.OrdinalIgnoreCase))
            {
                throw new ArgumentException("AssetPath must be a .mat asset path under Assets/.");
            }
            var material = AssetDatabase.LoadAssetAtPath<Material>(assetPath);
            if (material == null)
            {
                throw new InvalidOperationException("Material not found: " + assetPath);
            }
            return material;
        }

        // -------------------------------------------------------------- particle

        private static object ListParticles(string filter, int limit)
        {
            CheckLimit(limit);
            var transforms = WalkScenes().ToArray();
            var systems = transforms.Select(transform => transform.GetComponent<ParticleSystem>()).Where(system => system != null).ToArray();
            var lineRenderers = transforms.Select(transform => transform.GetComponent<LineRenderer>()).Where(renderer => renderer != null).ToArray();
            var trailRenderers = transforms.Select(transform => transform.GetComponent<TrailRenderer>()).Where(renderer => renderer != null).ToArray();
            var visualEffects = transforms
                .SelectMany(transform => transform.GetComponents<Component>())
                .Where(component => component != null && component.GetType().FullName == "UnityEngine.VFX.VisualEffect")
                .ToArray();
            var matching = systems
                .Where(system => system.name.IndexOf(filter, StringComparison.OrdinalIgnoreCase) >= 0)
                .Take(limit)
                .Select(system =>
                {
                    var main = system.main;
                    return new
                    {
                        objectId = system.gameObject.GetInstanceID(),
                        name = system.name,
                        path = GetPath(system.transform),
                        active = system.gameObject.activeInHierarchy,
                        isPlaying = system.isPlaying,
                        isPaused = system.isPaused,
                        isStopped = system.isStopped,
                        particleCount = system.particleCount,
                        duration = Number(main.duration),
                        looping = main.loop,
                        playOnAwake = main.playOnAwake,
                        maxParticles = main.maxParticles,
                        simulationSpace = main.simulationSpace.ToString(),
                        cullingMode = main.cullingMode.ToString(),
                        stopAction = main.stopAction.ToString()
                    };
                }).ToArray();
            return new
            {
                systems = matching,
                totalSystems = systems.Length,
                totalLineRenderers = lineRenderers.Length,
                totalTrailRenderers = trailRenderers.Length,
                totalVisualEffects = visualEffects.Length,
                vfxGraphInstalled = IsAssemblyLoaded("Unity.VisualEffectGraph.Runtime"),
                truncated = systems.Length > limit
            };
        }

        private static object InspectParticleSystem(JObject args)
        {
            var transform = ResolveTarget(args, "ParticleSystem");
            var systems = transform.GetComponents<ParticleSystem>();
            if (systems.Length == 0)
            {
                throw new InvalidOperationException("GameObject has no ParticleSystem: " + GetPath(transform));
            }
            var index = GetInt(args, "ComponentIndex") ?? 0;
            if (index < 0 || index >= systems.Length)
            {
                throw new ArgumentOutOfRangeException(nameof(index), "ComponentIndex must be between 0 and " + (systems.Length - 1) + ".");
            }
            var system = systems[index];
            var main = system.main;
            var emission = system.emission;
            var shape = system.shape;
            var velocity = system.velocityOverLifetime;
            var colorOverLifetime = system.colorOverLifetime;
            var sizeOverLifetime = system.sizeOverLifetime;
            var rotationOverLifetime = system.rotationOverLifetime;
            var noise = system.noise;
            var collision = system.collision;
            var trails = system.trails;
            var textureSheet = system.textureSheetAnimation;
            var subEmitters = system.subEmitters;
            var bursts = new List<object>();
            for (var burstIndex = 0; burstIndex < emission.burstCount && burstIndex < 16; burstIndex++)
            {
                var burst = emission.GetBurst(burstIndex);
                bursts.Add(new
                {
                    time = Curve(burst.time),
                    count = Curve(burst.count),
                    cycleCount = burst.cycleCount,
                    repeatInterval = Number(burst.repeatInterval),
                    probability = Number(burst.probability)
                });
            }

            return new
            {
                objectId = system.gameObject.GetInstanceID(),
                name = system.name,
                path = GetPath(system.transform),
                componentIndex = index,
                componentCount = systems.Length,
                active = system.gameObject.activeInHierarchy,
                runtime = new
                {
                    isPlaying = system.isPlaying,
                    isPaused = system.isPaused,
                    isStopped = system.isStopped,
                    isEmitting = system.isEmitting,
                    particleCount = system.particleCount,
                    time = Number(system.time),
                    useAutoRandomSeed = system.useAutoRandomSeed,
                    randomSeed = system.randomSeed
                },
                main = new
                {
                    duration = Number(main.duration),
                    loop = main.loop,
                    prewarm = main.prewarm,
                    startDelay = Curve(main.startDelay),
                    startLifetime = Curve(main.startLifetime),
                    startSpeed = Curve(main.startSpeed),
                    startSize = Curve(main.startSize),
                    startSize3D = main.startSize3D,
                    startColor = Gradient(main.startColor),
                    gravityModifier = Curve(main.gravityModifier),
                    simulationSpace = main.simulationSpace.ToString(),
                    simulationSpeed = Number(main.simulationSpeed),
                    scalingMode = main.scalingMode.ToString(),
                    playOnAwake = main.playOnAwake,
                    maxParticles = main.maxParticles,
                    emitterVelocityMode = main.emitterVelocityMode.ToString(),
                    stopAction = main.stopAction.ToString(),
                    cullingMode = main.cullingMode.ToString(),
                    ringBufferMode = main.ringBufferMode.ToString()
                },
                emission = new
                {
                    enabled = emission.enabled,
                    rateOverTime = Curve(emission.rateOverTime),
                    rateOverDistance = Curve(emission.rateOverDistance),
                    burstCount = emission.burstCount,
                    bursts
                },
                shape = new
                {
                    enabled = shape.enabled,
                    type = shape.shapeType.ToString(),
                    radius = Number(shape.radius),
                    angle = Number(shape.angle),
                    radiusThickness = Number(shape.radiusThickness),
                    length = Number(shape.length),
                    position = Vec(shape.position),
                    rotation = Vec(shape.rotation),
                    scale = Vec(shape.scale)
                },
                velocityOverLifetime = velocity.enabled ? new
                {
                    space = velocity.space.ToString(),
                    x = Curve(velocity.x),
                    y = Curve(velocity.y),
                    z = Curve(velocity.z)
                } : null,
                colorOverLifetime = colorOverLifetime.enabled
                    ? new { color = Gradient(colorOverLifetime.color) }
                    : null,
                sizeOverLifetime = sizeOverLifetime.enabled ? new
                {
                    separateAxes = sizeOverLifetime.separateAxes,
                    size = sizeOverLifetime.separateAxes ? null : Curve(sizeOverLifetime.size),
                    x = sizeOverLifetime.separateAxes ? Curve(sizeOverLifetime.x) : null,
                    y = sizeOverLifetime.separateAxes ? Curve(sizeOverLifetime.y) : null,
                    z = sizeOverLifetime.separateAxes ? Curve(sizeOverLifetime.z) : null
                } : null,
                rotationOverLifetime = rotationOverLifetime.enabled ? new
                {
                    separateAxes = rotationOverLifetime.separateAxes,
                    z = rotationOverLifetime.separateAxes ? null : Curve(rotationOverLifetime.z),
                    x = rotationOverLifetime.separateAxes ? Curve(rotationOverLifetime.x) : null,
                    y = rotationOverLifetime.separateAxes ? Curve(rotationOverLifetime.y) : null
                } : null,
                noise = noise.enabled ? new
                {
                    strength = Curve(noise.strength),
                    frequency = Number(noise.frequency),
                    scrollSpeed = Curve(noise.scrollSpeed),
                    octaveCount = noise.octaveCount,
                    quality = noise.quality.ToString(),
                    damping = noise.damping,
                    octaveMultiplier = Number(noise.octaveMultiplier),
                    octaveScale = Number(noise.octaveScale)
                } : null,
                collision = collision.enabled ? new
                {
                    type = collision.type.ToString(),
                    quality = collision.quality.ToString(),
                    dampen = Curve(collision.dampen),
                    bounce = Curve(collision.bounce),
                    radiusScale = Number(collision.radiusScale),
                    lifetimeLoss = Curve(collision.lifetimeLoss),
                    minKillSpeed = Number(collision.minKillSpeed)
                } : null,
                trails = trails.enabled ? new
                {
                    mode = trails.mode.ToString(),
                    ratio = Number(trails.ratio),
                    lifetime = Curve(trails.lifetime),
                    minVertexDistance = Number(trails.minVertexDistance),
                    ribbonCount = trails.ribbonCount,
                    dieWithParticles = trails.dieWithParticles,
                    sizeAffectsWidth = trails.sizeAffectsWidth,
                    inheritParticleColor = trails.inheritParticleColor,
                    generateLightingData = trails.generateLightingData
                } : null,
                textureSheetAnimation = textureSheet.enabled ? new
                {
                    numTilesX = textureSheet.numTilesX,
                    numTilesY = textureSheet.numTilesY,
                    animation = textureSheet.animation.ToString(),
                    frameOverTime = Curve(textureSheet.frameOverTime),
                    startFrame = Curve(textureSheet.startFrame),
                    cycleCount = textureSheet.cycleCount
                } : null,
                subEmitters = subEmitters.enabled
                    ? new { count = subEmitters.subEmittersCount }
                    : null,
                renderer = ParticleRendererInfo(system.GetComponent<ParticleSystemRenderer>()),
                linkedRenderers = new
                {
                    lineRenderer = DescribeLineRenderer(system.GetComponent<LineRenderer>()),
                    trailRenderer = DescribeTrailRenderer(system.GetComponent<TrailRenderer>())
                }
            };
        }

        private static object ParticleRendererInfo(ParticleSystemRenderer renderer)
        {
            if (renderer == null)
            {
                return null;
            }
            return new
            {
                renderMode = renderer.renderMode.ToString(),
                sortMode = renderer.sortMode.ToString(),
                alignment = renderer.alignment.ToString(),
                material = AssetRef(renderer.material),
                trailMaterial = AssetRef(renderer.trailMaterial),
                mesh = AssetRef(renderer.mesh),
                minParticleSize = Number(renderer.minParticleSize),
                maxParticleSize = Number(renderer.maxParticleSize),
                lengthScale = Number(renderer.lengthScale),
                velocityScale = Number(renderer.velocityScale),
                pivot = Vec(renderer.pivot),
                normalDirection = Number(renderer.normalDirection),
                enabled = renderer.enabled,
                sortingLayerName = renderer.sortingLayerName,
                sortingOrder = renderer.sortingOrder
            };
        }

        private static object DescribeLineRenderer(LineRenderer renderer)
        {
            if (renderer == null)
            {
                return null;
            }
            return new
            {
                positionCount = renderer.positionCount,
                loop = renderer.loop,
                useWorldSpace = renderer.useWorldSpace,
                widthMultiplier = Number(renderer.widthMultiplier),
                startColor = Hex(renderer.startColor),
                endColor = Hex(renderer.endColor),
                numCapVertices = renderer.numCapVertices,
                alignment = renderer.alignment.ToString(),
                textureMode = renderer.textureMode.ToString(),
                material = AssetRef(renderer.sharedMaterial),
                enabled = renderer.enabled
            };
        }

        private static object DescribeTrailRenderer(TrailRenderer renderer)
        {
            if (renderer == null)
            {
                return null;
            }
            return new
            {
                time = Number(renderer.time),
                minVertexDistance = Number(renderer.minVertexDistance),
                widthMultiplier = Number(renderer.widthMultiplier),
                startColor = Hex(renderer.startColor),
                endColor = Hex(renderer.endColor),
                numCapVertices = renderer.numCapVertices,
                alignment = renderer.alignment.ToString(),
                textureMode = renderer.textureMode.ToString(),
                positionCount = renderer.positionCount,
                autodestruct = renderer.autodestruct,
                material = AssetRef(renderer.sharedMaterial),
                enabled = renderer.enabled
            };
        }

        private static object Curve(ParticleSystem.MinMaxCurve curve)
        {
            var data = new Dictionary<string, object>
            {
                { "mode", curve.mode.ToString() },
                { "multiplier", Number(curve.curveMultiplier) }
            };
            switch (curve.mode)
            {
                case ParticleSystemCurveMode.Constant:
                    data["constant"] = Number(curve.constant);
                    break;
                case ParticleSystemCurveMode.TwoConstants:
                    data["min"] = Number(curve.constantMin);
                    data["max"] = Number(curve.constantMax);
                    break;
                case ParticleSystemCurveMode.Curve:
                    data["keyCount"] = curve.curve == null ? 0 : curve.curve.length;
                    break;
                case ParticleSystemCurveMode.TwoCurves:
                    data["minKeyCount"] = curve.curveMin == null ? 0 : curve.curveMin.length;
                    data["maxKeyCount"] = curve.curveMax == null ? 0 : curve.curveMax.length;
                    break;
            }
            return data;
        }

        private static object Gradient(ParticleSystem.MinMaxGradient gradient)
        {
            var data = new Dictionary<string, object> { { "mode", gradient.mode.ToString() } };
            switch (gradient.mode)
            {
                case ParticleSystemGradientMode.Color:
                    data["color"] = Hex(gradient.color);
                    break;
                case ParticleSystemGradientMode.TwoColors:
                    data["colorMin"] = Hex(gradient.colorMin);
                    data["colorMax"] = Hex(gradient.colorMax);
                    break;
                case ParticleSystemGradientMode.Gradient:
                    data["gradient"] = GradientKeys(gradient.gradient);
                    break;
                case ParticleSystemGradientMode.TwoGradients:
                    data["gradientMin"] = GradientKeys(gradient.gradientMin);
                    data["gradientMax"] = GradientKeys(gradient.gradientMax);
                    break;
                case ParticleSystemGradientMode.RandomColor:
                    data["gradient"] = GradientKeys(gradient.gradient);
                    break;
            }
            return data;
        }

        private static object GradientKeys(Gradient gradient)
        {
            if (gradient == null)
            {
                return null;
            }
            return new
            {
                colorKeyCount = gradient.colorKeys.Length,
                alphaKeyCount = gradient.alphaKeys.Length,
                colors = gradient.colorKeys.Take(8).Select(key => new { time = Number(key.time), color = Hex(key.color) }).ToArray()
            };
        }

        // -------------------------------------------------------------- animator

        private static object ListAnimators(string filter, int limit)
        {
            CheckLimit(limit);
            var transforms = WalkScenes().ToArray();
            var animators = transforms.Select(transform => transform.GetComponent<Animator>()).Where(animator => animator != null).ToArray();
            var legacyAnimations = transforms.Select(transform => transform.GetComponent<Animation>()).Where(animation => animation != null).ToArray();
            var entries = animators
                .Where(animator => animator.name.IndexOf(filter, StringComparison.OrdinalIgnoreCase) >= 0)
                .Take(limit)
                .Select(animator => new
                {
                    objectId = animator.gameObject.GetInstanceID(),
                    name = animator.name,
                    path = GetPath(animator.transform),
                    active = animator.gameObject.activeInHierarchy,
                    controller = AssetRef(animator.runtimeAnimatorController),
                    avatar = AssetRef(animator.avatar),
                    isHuman = animator.isHuman,
                    layerCount = animator.layerCount,
                    parameterCount = animator.parameterCount,
                    speed = Number(animator.speed),
                    applyRootMotion = animator.applyRootMotion,
                    updateMode = animator.updateMode.ToString(),
                    cullingMode = animator.cullingMode.ToString()
                }).ToArray();
            return new
            {
                animators = entries,
                totalAnimators = animators.Length,
                legacyAnimations = legacyAnimations.Take(limit).Select(animation => new
                {
                    objectId = animation.gameObject.GetInstanceID(),
                    name = animation.name,
                    path = GetPath(animation.transform),
                    clip = AssetRef(animation.clip),
                    playAutomatically = animation.playAutomatically,
                    wrapMode = animation.wrapMode.ToString(),
                    isPlaying = animation.isPlaying
                }).ToArray(),
                totalLegacyAnimations = legacyAnimations.Length,
                truncated = animators.Length > limit
            };
        }

        private static object InspectAnimator(JObject args)
        {
            var transform = ResolveTarget(args, "Animator");
            var animators = transform.GetComponents<Animator>();
            if (animators.Length == 0)
            {
                throw new InvalidOperationException("GameObject has no Animator: " + GetPath(transform));
            }
            var index = GetInt(args, "ComponentIndex") ?? 0;
            if (index < 0 || index >= animators.Length)
            {
                throw new ArgumentOutOfRangeException(nameof(index), "ComponentIndex must be between 0 and " + (animators.Length - 1) + ".");
            }
            var animator = animators[index];
            var limit = GetInt(args, "Limit") ?? 200;
            CheckLimit(limit);
            var controller = animator.runtimeAnimatorController as AnimatorController;
            var parameters = new List<object>();
            foreach (var parameter in animator.parameters)
            {
                parameters.Add(DescribeParameter(parameter, animator));
            }

            return new
            {
                objectId = animator.gameObject.GetInstanceID(),
                name = animator.name,
                path = GetPath(animator.transform),
                componentIndex = index,
                componentCount = animators.Length,
                active = animator.gameObject.activeInHierarchy,
                enabled = animator.enabled,
                runtime = new
                {
                    controller = AssetRef(animator.runtimeAnimatorController),
                    controllerType = animator.runtimeAnimatorController == null ? null : animator.runtimeAnimatorController.GetType().Name,
                    avatar = AvatarInfo(animator.avatar),
                    isHuman = animator.isHuman,
                    hasBoundPlayables = animator.hasBoundPlayables,
                    speed = Number(animator.speed),
                    applyRootMotion = animator.applyRootMotion,
                    updateMode = animator.updateMode.ToString(),
                    cullingMode = animator.cullingMode.ToString(),
                    layerCount = animator.layerCount,
                    parameterCount = animator.parameterCount,
                    parameters
                },
                controller = controller == null ? null : ControllerInfo(controller, limit),
                live = EditorApplication.isPlaying ? LiveAnimatorInfo(animator) : null
            };
        }

        private static object DescribeParameter(AnimatorControllerParameter parameter, Animator animator)
        {
            object value = null;
            if (EditorApplication.isPlaying && animator.isActiveAndEnabled)
            {
                switch (parameter.type)
                {
                    case AnimatorControllerParameterType.Float:
                        value = Number(animator.GetFloat(parameter.name));
                        break;
                    case AnimatorControllerParameterType.Int:
                        value = animator.GetInteger(parameter.name);
                        break;
                    case AnimatorControllerParameterType.Bool:
                        value = animator.GetBool(parameter.name);
                        break;
                    case AnimatorControllerParameterType.Trigger:
                        value = null;
                        break;
                }
            }
            return new
            {
                name = parameter.name,
                type = parameter.type.ToString(),
                defaultBool = parameter.defaultBool,
                defaultFloat = Number(parameter.defaultFloat),
                defaultInt = parameter.defaultInt,
                value
            };
        }

        private static object AvatarInfo(Avatar avatar)
        {
            if (avatar == null)
            {
                return null;
            }
            return new
            {
                name = avatar.name,
                assetPath = AssetPathOf(avatar),
                isValid = avatar.isValid,
                isHuman = avatar.isHuman,
                humanBoneCount = avatar.humanDescription.human == null ? 0 : avatar.humanDescription.human.Length,
                skeletonBoneCount = avatar.humanDescription.skeleton == null ? 0 : avatar.humanDescription.skeleton.Length
            };
        }

        private static object ControllerInfo(AnimatorController controller, int limit)
        {
            var layers = new List<object>();
            var states = new List<object>();
            var clips = new HashSet<string>(StringComparer.Ordinal);
            var totalStates = 0;
            foreach (var layer in controller.layers)
            {
                var layerStates = new List<object>();
                if (layer.stateMachine != null)
                {
                    CollectStates(layer.stateMachine, layerStates, clips, limit, ref totalStates);
                }
                states.AddRange(layerStates);
                layers.Add(new
                {
                    index = layers.Count,
                    name = layer.name,
                    defaultWeight = Number(layer.defaultWeight),
                    blendingMode = layer.blendingMode.ToString(),
                    iKPass = layer.iKPass,
                    avatarMask = AssetRef(layer.avatarMask),
                    syncedLayerIndex = layer.syncedLayerIndex,
                    syncedLayerAffectsTiming = layer.syncedLayerAffectsTiming,
                    stateMachine = layer.stateMachine == null ? null : new
                    {
                        name = layer.stateMachine.name,
                        defaultState = layer.stateMachine.defaultState == null ? null : layer.stateMachine.defaultState.name,
                        anyStateTransitionCount = layer.stateMachine.anyStateTransitions.Length,
                        entryTransitionCount = layer.stateMachine.entryTransitions.Length,
                        subStateMachineCount = layer.stateMachine.stateMachines.Length,
                        stateCount = layerStates.Count
                    }
                });
            }
            return new
            {
                name = controller.name,
                assetPath = AssetPathOf(controller),
                layerCount = controller.layers.Length,
                parameterCount = controller.parameters.Length,
                parameters = controller.parameters.Select(parameter => new
                {
                    name = parameter.name,
                    type = parameter.type.ToString(),
                    defaultBool = parameter.defaultBool,
                    defaultFloat = Number(parameter.defaultFloat),
                    defaultInt = parameter.defaultInt
                }).ToArray(),
                layers,
                states,
                totalStates,
                clips = clips.OrderBy(path => path, StringComparer.Ordinal).ToArray(),
                clipCount = clips.Count,
                truncated = totalStates > limit
            };
        }

        private static void CollectStates(AnimatorStateMachine stateMachine, List<object> states, HashSet<string> clips, int limit, ref int totalStates)
        {
            foreach (var child in stateMachine.states)
            {
                totalStates++;
                if (states.Count >= limit)
                {
                    continue;
                }
                var state = child.state;
                CollectClips(state.motion, clips, 200);
                var transitions = new List<object>();
                foreach (var transition in state.transitions)
                {
                    if (transitions.Count >= 8)
                    {
                        break;
                    }
                    transitions.Add(new
                    {
                        to = transition.isExit ? null : (transition.destinationState == null ? null : transition.destinationState.name),
                        isExit = transition.isExit,
                        hasExitTime = transition.hasExitTime,
                        hasFixedDuration = transition.hasFixedDuration,
                        duration = Number(transition.duration),
                        exitTime = Number(transition.exitTime),
                        mute = transition.mute,
                        conditions = transition.conditions.Take(8).Select(condition => new
                        {
                            parameter = condition.parameter,
                            mode = condition.mode.ToString(),
                            threshold = Number(condition.threshold)
                        }).ToArray()
                    });
                }
                states.Add(new
                {
                    name = state.name,
                    layer = stateMachine.name,
                    speed = Number(state.speed),
                    cycleOffset = Number(state.cycleOffset),
                    timeParameterActive = state.timeParameterActive,
                    timeParameter = state.timeParameter,
                    writeDefaultValues = state.writeDefaultValues,
                    motion = AssetRef(state.motion),
                    transitionCount = state.transitions.Length,
                    transitions
                });
            }
            foreach (var child in stateMachine.stateMachines)
            {
                CollectStates(child.stateMachine, states, clips, limit, ref totalStates);
            }
        }

        private static void CollectClips(Motion motion, HashSet<string> clips, int limit)
        {
            if (motion == null || clips.Count >= limit)
            {
                return;
            }
            if (motion is BlendTree tree)
            {
                foreach (var child in tree.children)
                {
                    CollectClips(child.motion, clips, limit);
                }
                return;
            }
            if (motion is AnimationClip clip)
            {
                clips.Add(AssetPathOf(clip) ?? clip.name);
            }
        }

        private static object LiveAnimatorInfo(Animator animator)
        {
            if (!animator.isActiveAndEnabled)
            {
                return new { active = false, layers = new object[0], parameters = new object[0] };
            }
            var layers = new List<object>();
            for (var layer = 0; layer < animator.layerCount; layer++)
            {
                AnimatorStateInfo info;
                AnimatorClipInfo[] clipInfo;
                try
                {
                    info = animator.GetCurrentAnimatorStateInfo(layer);
                    clipInfo = animator.GetCurrentAnimatorClipInfo(layer);
                }
                catch (Exception)
                {
                    continue;
                }
                layers.Add(new
                {
                    index = layer,
                    name = animator.GetLayerName(layer),
                    weight = Number(animator.GetLayerWeight(layer)),
                    inTransition = animator.IsInTransition(layer),
                    state = new
                    {
                        fullPathHash = info.fullPathHash,
                        shortNameHash = info.shortNameHash,
                        normalizedTime = Number(info.normalizedTime),
                        length = Number(info.length),
                        speed = Number(info.speed),
                        speedMultiplier = Number(info.speedMultiplier),
                        loop = info.loop
                    },
                    clips = clipInfo.Select(item => new
                    {
                        clip = item.clip == null ? null : item.clip.name,
                        assetPath = AssetRef(item.clip) == null ? null : AssetPathOf(item.clip),
                        weight = Number(item.weight)
                    }).ToArray()
                });
            }
            var parameters = new List<object>();
            foreach (var parameter in animator.parameters)
            {
                object value = null;
                switch (parameter.type)
                {
                    case AnimatorControllerParameterType.Float:
                        value = Number(animator.GetFloat(parameter.name));
                        break;
                    case AnimatorControllerParameterType.Int:
                        value = animator.GetInteger(parameter.name);
                        break;
                    case AnimatorControllerParameterType.Bool:
                        value = animator.GetBool(parameter.name);
                        break;
                }
                parameters.Add(new { name = parameter.name, type = parameter.type.ToString(), value });
            }
            return new
            {
                active = true,
                bodyPosition = Vec(animator.bodyPosition),
                deltaPosition = Vec(animator.deltaPosition),
                layers,
                parameters
            };
        }

        // -------------------------------------------------------------- physics

        private static object PhysicsSettings()
        {
            var namedLayers = new List<object>();
            for (var layer = 0; layer < 32; layer++)
            {
                var name = LayerMask.LayerToName(layer);
                if (!string.IsNullOrEmpty(name))
                {
                    namedLayers.Add(new { index = layer, name });
                }
            }
            return new
            {
                threeD = new
                {
                    gravity = Vec(Physics.gravity),
                    defaultContactOffset = Number(Physics.defaultContactOffset),
                    bounceThreshold = Number(Physics.bounceThreshold),
                    sleepThreshold = Number(Physics.sleepThreshold),
                    defaultSolverIterations = Physics.defaultSolverIterations,
                    defaultSolverVelocityIterations = Physics.defaultSolverVelocityIterations,
                    defaultMaxDepenetrationVelocity = Number(Physics.defaultMaxDepenetrationVelocity),
                    queriesHitTriggers = Physics.queriesHitTriggers,
                    queriesHitBackfaces = Physics.queriesHitBackfaces,
#if UNITY_2022_2_OR_NEWER
                    autoSimulation = Physics.simulationMode != SimulationMode.Script,
#else
                    autoSimulation = Physics.autoSimulation,
#endif
                    autoSyncTransforms = Physics.autoSyncTransforms,
                    reuseCollisionCallbacks = Physics.reuseCollisionCallbacks,
                    defaultPhysicsScene = new { valid = Physics.defaultPhysicsScene.IsValid() }
                },
                twoD = new
                {
                    gravity = Vec(Physics2D.gravity),
                    velocityIterations = Physics2D.velocityIterations,
                    positionIterations = Physics2D.positionIterations,
                    simulationMode = Physics2D.simulationMode.ToString(),
                    queriesHitTriggers = Physics2D.queriesHitTriggers,
                    queriesStartInColliders = Physics2D.queriesStartInColliders,
                    velocityThreshold = Number(Physics2D.velocityThreshold),
                    linearSleepTolerance = Number(Physics2D.linearSleepTolerance),
                    angularSleepTolerance = Number(Physics2D.angularSleepTolerance),
                    maxLinearCorrection = Number(Physics2D.maxLinearCorrection),
                    maxAngularCorrection = Number(Physics2D.maxAngularCorrection),
                    maxTranslationSpeed = Number(Physics2D.maxTranslationSpeed),
                    maxRotationSpeed = Number(Physics2D.maxRotationSpeed),
                    callbacksOnDisable = Physics2D.callbacksOnDisable,
                    defaultContactOffset = Number(Physics2D.defaultContactOffset)
                },
                layers = namedLayers,
                note = "Physics settings are project-wide and covered by ProjectSettings/DynamicsManager.asset and Physics2DSettings.asset; they are reported, not edited."
            };
        }

        private static object PhysicsLayers()
        {
            var layers = new List<object>();
            for (var layer = 0; layer < 32; layer++)
            {
                var name = LayerMask.LayerToName(layer);
                if (!string.IsNullOrEmpty(name))
                {
                    layers.Add(new { index = layer, name });
                }
            }
            var disabled3D = new List<object>();
            var disabled2D = new List<object>();
            for (var first = 0; first < 32; first++)
            {
                for (var second = first; second < 32; second++)
                {
                    if (Physics.GetIgnoreLayerCollision(first, second))
                    {
                        disabled3D.Add(new { first, second, firstName = LayerMask.LayerToName(first), secondName = LayerMask.LayerToName(second) });
                    }
                    if (Physics2D.GetIgnoreLayerCollision(first, second))
                    {
                        disabled2D.Add(new { first, second, firstName = LayerMask.LayerToName(first), secondName = LayerMask.LayerToName(second) });
                    }
                }
            }
            return new
            {
                layers,
                collisionMatrix3D = new { disabledPairs = disabled3D, disabledCount = disabled3D.Count },
                collisionMatrix2D = new { disabledPairs = disabled2D, disabledCount = disabled2D.Count }
            };
        }

        private static object PhysicsStats()
        {
            var transforms = WalkScenes().ToArray();
            var rigidbodies = transforms.Select(transform => transform.GetComponent<Rigidbody>()).Where(body => body != null).ToArray();
            var rigidbodies2D = transforms.Select(transform => transform.GetComponent<Rigidbody2D>()).Where(body => body != null).ToArray();
            var colliders = transforms.SelectMany(transform => transform.GetComponents<Collider>()).Where(collider => collider != null).ToArray();
            var colliders2D = transforms.SelectMany(transform => transform.GetComponents<Collider2D>()).Where(collider => collider != null).ToArray();
            var joints = transforms.SelectMany(transform => transform.GetComponents<Joint>()).Where(joint => joint != null).Count();
            var joints2D = transforms.SelectMany(transform => transform.GetComponents<Joint2D>()).Where(joint => joint != null).Count();
            var characterControllers = transforms.Select(transform => transform.GetComponent<CharacterController>()).Count(controller => controller != null);
            var terrains = transforms.Select(transform => transform.GetComponent<Terrain>()).Count(terrain => terrain != null);
            return new
            {
                sceneObjects = transforms.Length,
                rigidbodies = new
                {
                    total = rigidbodies.Length,
                    kinematic = rigidbodies.Count(body => body.isKinematic),
                    interpolated = rigidbodies.Count(body => body.interpolation != RigidbodyInterpolation.None),
                    useGravity = rigidbodies.Count(body => body.useGravity)
                },
                rigidbodies2D = new
                {
                    total = rigidbodies2D.Length,
                    bodyType = rigidbodies2D.GroupBy(body => body.bodyType.ToString())
                        .Select(group => new { type = group.Key, count = group.Count() }).ToArray()
                },
                colliders = new
                {
                    total = colliders.Length,
                    byType = colliders.GroupBy(collider => collider.GetType().Name)
                        .Select(group => new { type = group.Key, count = group.Count() }).ToArray(),
                    triggers = colliders.Count(collider => collider.isTrigger)
                },
                colliders2D = new
                {
                    total = colliders2D.Length,
                    byType = colliders2D.GroupBy(collider => collider.GetType().Name)
                        .Select(group => new { type = group.Key, count = group.Count() }).ToArray(),
                    triggers = colliders2D.Count(collider => collider.isTrigger)
                },
                joints,
                joints2D,
                characterControllers,
                terrains
            };
        }

        private static object PhysicsRaycast(JObject args)
        {
            var origin = RequireVector3(args, "Origin");
            var direction = RequireDirection(args, "Direction");
            var distance = GetFloat(args, "MaxDistance") ?? float.PositiveInfinity;
            if (distance <= 0f)
            {
                throw new ArgumentOutOfRangeException(nameof(distance), "MaxDistance must be positive.");
            }
            var mask = ResolveLayerMask(args);
            var triggers = ResolveTriggerInteraction(args);
            Physics.SyncTransforms();
            if (GetBool(args, "All") == true)
            {
                var hits = Physics.RaycastAll(new Ray(origin, direction), distance, mask, triggers)
                    .OrderBy(hit => hit.distance)
                    .ToArray();
                return new
                {
                    mode = "all",
                    origin = Vec(origin),
                    direction = Vec(direction),
                    maxDistance = Number(distance),
                    layerMask = mask,
                    triggerInteraction = triggers.ToString(),
                    count = hits.Length,
                    hits = hits.Select(DescribeHit).ToArray()
                };
            }
            if (!Physics.Raycast(new Ray(origin, direction), out var hit, distance, mask, triggers))
            {
                return new
                {
                    mode = "single",
                    hit = (object)null,
                    origin = Vec(origin),
                    direction = Vec(direction),
                    maxDistance = Number(distance),
                    layerMask = mask,
                    triggerInteraction = triggers.ToString()
                };
            }
            return new
            {
                mode = "single",
                hit = DescribeHit(hit),
                origin = Vec(origin),
                direction = Vec(direction),
                maxDistance = Number(distance),
                layerMask = mask,
                triggerInteraction = triggers.ToString()
            };
        }

        private static object PhysicsRaycast2D(JObject args)
        {
            var origin = RequireVector2(args, "Origin");
            var direction = RequireVector2(args, "Direction");
            if (direction.sqrMagnitude == 0f)
            {
                throw new ArgumentException("Direction must not be zero.");
            }
            var distance = GetFloat(args, "MaxDistance") ?? float.PositiveInfinity;
            if (distance <= 0f)
            {
                throw new ArgumentOutOfRangeException(nameof(distance), "MaxDistance must be positive.");
            }
            var mask = ResolveLayerMask(args);
            Physics2D.SyncTransforms();
            if (GetBool(args, "All") == true)
            {
                var hits = Physics2D.RaycastAll(origin, direction, distance, mask)
                    .OrderBy(hit => hit.distance)
                    .ToArray();
                return new
                {
                    mode = "all",
                    origin = Vec(origin),
                    direction = Vec(direction),
                    maxDistance = Number(distance),
                    layerMask = mask,
                    count = hits.Length,
                    hits = hits.Select(DescribeHit2D).ToArray()
                };
            }
            var single = Physics2D.Raycast(origin, direction, distance, mask);
            return new
            {
                mode = "single",
                hit = single.collider == null ? null : DescribeHit2D(single),
                origin = Vec(origin),
                direction = Vec(direction),
                maxDistance = Number(distance),
                layerMask = mask
            };
        }

        private static object PhysicsOverlap(JObject args)
        {
            var shape = (GetString(args, "Shape") ?? "sphere").Trim().ToLowerInvariant();
            var position = RequireVector3(args, "Position");
            var mask = ResolveLayerMask(args);
            var triggers = ResolveTriggerInteraction(args);
            var limit = GetInt(args, "Limit") ?? 100;
            CheckLimit(limit);
            Collider[] overlaps;
            Physics.SyncTransforms();
            if (shape == "sphere")
            {
                var radius = GetFloat(args, "Radius");
                if (radius == null || radius <= 0f)
                {
                    throw new ArgumentOutOfRangeException(nameof(radius), "Radius must be positive for a sphere overlap.");
                }
                overlaps = Physics.OverlapSphere(position, radius.Value, mask, triggers);
            }
            else if (shape == "box")
            {
                var size = RequireVector3(args, "Size");
                var rotation = GetVector3(args, "Rotation") ?? Vector3.zero;
                overlaps = Physics.OverlapBox(position, size * 0.5f, Quaternion.Euler(rotation), mask, triggers);
            }
            else
            {
                throw new ArgumentException("Shape must be sphere or box.");
            }
            return new
            {
                shape,
                layerMask = mask,
                triggerInteraction = triggers.ToString(),
                count = overlaps.Length,
                colliders = overlaps.Take(limit).Select(collider => new
                {
                    name = collider.name,
                    type = collider.GetType().Name,
                    path = GetPath(collider.transform),
                    isTrigger = collider.isTrigger,
                    enabled = collider.enabled,
                    bounds = new { center = Vec(collider.bounds.center), size = Vec(collider.bounds.size) },
                    attachedRigidbody = collider.attachedRigidbody == null ? null : collider.attachedRigidbody.name
                }).ToArray(),
                truncated = overlaps.Length > limit
            };
        }

        private static object PhysicsOverlap2D(JObject args)
        {
            var shape = (GetString(args, "Shape") ?? "circle").Trim().ToLowerInvariant();
            var position = RequireVector2(args, "Position");
            var mask = ResolveLayerMask(args);
            var limit = GetInt(args, "Limit") ?? 100;
            CheckLimit(limit);
            Collider2D[] overlaps;
            Physics2D.SyncTransforms();
            if (shape == "circle")
            {
                var radius = GetFloat(args, "Radius");
                if (radius == null || radius <= 0f)
                {
                    throw new ArgumentOutOfRangeException(nameof(radius), "Radius must be positive for a circle overlap.");
                }
                overlaps = Physics2D.OverlapCircleAll(position, radius.Value, mask);
            }
            else if (shape == "box")
            {
                var size = RequireVector2(args, "Size");
                var angle = GetFloat(args, "Angle") ?? 0f;
                overlaps = Physics2D.OverlapBoxAll(position, size, angle, mask);
            }
            else
            {
                throw new ArgumentException("Shape must be circle or box.");
            }
            return new
            {
                shape,
                layerMask = mask,
                count = overlaps.Length,
                colliders = overlaps.Take(limit).Select(collider => new
                {
                    name = collider.name,
                    type = collider.GetType().Name,
                    path = GetPath(collider.transform),
                    isTrigger = collider.isTrigger,
                    enabled = collider.enabled,
                    bounds = new { center = Vec(collider.bounds.center), size = Vec(collider.bounds.size) },
                    attachedRigidbody = collider.attachedRigidbody == null ? null : collider.attachedRigidbody.name
                }).ToArray(),
                truncated = overlaps.Length > limit
            };
        }

        private static object DescribeHit(RaycastHit hit)
        {
            return new
            {
                collider = hit.collider == null ? null : new
                {
                    name = hit.collider.name,
                    type = hit.collider.GetType().Name,
                    path = GetPath(hit.collider.transform),
                    objectId = hit.collider.gameObject.GetInstanceID(),
                    isTrigger = hit.collider.isTrigger
                },
                rigidbody = hit.rigidbody == null ? null : new
                {
                    name = hit.rigidbody.name,
                    path = GetPath(hit.rigidbody.transform)
                },
                distance = Number(hit.distance),
                point = Vec(hit.point),
                normal = Vec(hit.normal),
                triangleIndex = hit.triangleIndex
            };
        }

        private static object DescribeHit2D(RaycastHit2D hit)
        {
            return new
            {
                collider = hit.collider == null ? null : new
                {
                    name = hit.collider.name,
                    type = hit.collider.GetType().Name,
                    path = GetPath(hit.collider.transform),
                    objectId = hit.collider.gameObject.GetInstanceID(),
                    isTrigger = hit.collider.isTrigger
                },
                rigidbody = hit.rigidbody == null ? null : new
                {
                    name = hit.rigidbody.name,
                    path = GetPath(hit.rigidbody.transform)
                },
                distance = Number(hit.distance),
                fraction = Number(hit.fraction),
                point = Vec(hit.point),
                normal = Vec(hit.normal),
                centroid = Vec(hit.centroid)
            };
        }

        // -------------------------------------------------------------- primitive

        private static object CreatePrimitive(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("creating a primitive");
            var typeText = GetString(args, "Type");
            if (string.IsNullOrEmpty(typeText))
            {
                throw new ArgumentException("Type is required. Available: " + string.Join(", ", Enum.GetNames(typeof(PrimitiveType))) + ".");
            }
            if (!Enum.TryParse(typeText, true, out PrimitiveType primitive) || int.TryParse(typeText, out _))
            {
                throw new ArgumentException("Type must be one of " + string.Join(", ", Enum.GetNames(typeof(PrimitiveType))) + ".");
            }
            var position = GetVector3(args, "Position") ?? Vector3.zero;
            var rotation = GetVector3(args, "Rotation") ?? Vector3.zero;
            var scale = GetVector3(args, "Scale") ?? Vector3.one;
            ValidateFinite(position, "Position");
            ValidateFinite(rotation, "Rotation");
            ValidateFinite(scale, "Scale");
            if (Mathf.Approximately(scale.x, 0f) || Mathf.Approximately(scale.y, 0f) || Mathf.Approximately(scale.z, 0f))
            {
                throw new ArgumentOutOfRangeException(nameof(scale), "Scale components must be non-zero.");
            }
            var parent = ResolveOptionalParent(args);

            var created = GameObject.CreatePrimitive(primitive);
            Undo.RegisterCreatedObjectUndo(created, UndoCreatePrimitive);
            var requestedName = GetString(args, "Name");
            if (!string.IsNullOrEmpty(requestedName))
            {
                created.name = requestedName;
            }
            if (parent != null)
            {
                Undo.SetTransformParent(created.transform, parent, "Unity CLI Parent Primitive");
            }
            created.transform.position = position;
            created.transform.rotation = Quaternion.Euler(rotation);
            created.transform.localScale = scale;

            var scene = created.scene;
            if (scene.IsValid() && !EditorSceneManager.IsPreviewScene(scene))
            {
                EditorSceneManager.MarkSceneDirty(scene);
            }
            Selection.activeGameObject = created;

            return new
            {
                created = true,
                objectId = created.GetInstanceID(),
                name = created.name,
                path = GetPath(created.transform),
                primitive = primitive.ToString(),
                position = Vec(created.transform.position),
                rotation = Vec(created.transform.eulerAngles),
                scale = Vec(created.transform.localScale),
                parent = parent == null ? null : GetPath(parent),
                components = ComponentNames(created)
            };
        }

        private static void ValidateFinite(Vector3 vector, string name)
        {
            if (float.IsNaN(vector.x) || float.IsInfinity(vector.x) ||
                float.IsNaN(vector.y) || float.IsInfinity(vector.y) ||
                float.IsNaN(vector.z) || float.IsInfinity(vector.z))
            {
                throw new ArgumentException(name + " must contain finite numbers.");
            }
        }

        // -------------------------------------------------------------- shared helpers

        private static IEnumerable<Transform> WalkScenes()
        {
            for (var index = 0; index < SceneManager.sceneCount; index++)
            {
                var scene = SceneManager.GetSceneAt(index);
                if (!scene.IsValid() || !scene.isLoaded || EditorSceneManager.IsPreviewScene(scene))
                {
                    continue;
                }
                foreach (var root in scene.GetRootGameObjects())
                {
                    if (root == null)
                    {
                        continue;
                    }
                    foreach (var transform in WalkHierarchy(root.transform))
                    {
                        yield return transform;
                    }
                }
            }
        }

        private static IEnumerable<Transform> WalkHierarchy(Transform root)
        {
            yield return root;
            foreach (Transform child in root)
            {
                foreach (var transform in WalkHierarchy(child))
                {
                    yield return transform;
                }
            }
        }

        private static string GetPath(Transform transform)
        {
            if (transform == null)
            {
                return null;
            }
            var names = new List<string>();
            var current = transform;
            while (current != null)
            {
                names.Add(current.name);
                current = current.parent;
            }
            names.Reverse();
            var scene = transform.gameObject.scene;
            var prefix = string.IsNullOrEmpty(scene.name) ? "" : scene.name + "/";
            return prefix + string.Join("/", names);
        }

        private static Transform ResolveTarget(JObject args, string label)
        {
            return FindSceneObject(GetInt(args, "ObjectId"), GetString(args, "Path"), GetString(args, "ScenePath"), label);
        }

        private static Transform ResolveOptionalParent(JObject args)
        {
            var parentId = GetInt(args, "ParentId");
            var parentPath = GetString(args, "ParentPath");
            if (parentId == null && string.IsNullOrEmpty(parentPath))
            {
                return null;
            }
            return FindSceneObject(parentId, parentPath, GetString(args, "ScenePath"), "parent");
        }

        private static Transform FindSceneObject(int? objectId, string path, string scenePath, string label)
        {
            if (objectId != null)
            {
                var byId = WalkScenes().FirstOrDefault(transform => transform.gameObject.GetInstanceID() == objectId.Value);
                if (byId != null)
                {
                    return byId;
                }
                throw new InvalidOperationException("No loaded scene object with ObjectId " + objectId.Value + " for " + label + ".");
            }
            if (string.IsNullOrEmpty(path))
            {
                throw new ArgumentException("Pass ObjectId or Path to identify the " + label + ".");
            }
            var normalized = path.Replace('\\', '/').Trim('/');
            Transform nameMatch = null;
            var ambiguous = false;
            foreach (var transform in WalkScenes())
            {
                if (!string.IsNullOrEmpty(scenePath) &&
                    !string.Equals(transform.gameObject.scene.path, scenePath, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }
                var full = GetPath(transform);
                var sceneName = transform.gameObject.scene.name;
                var relative = !string.IsNullOrEmpty(sceneName) && full.StartsWith(sceneName + "/", StringComparison.Ordinal)
                    ? full.Substring(sceneName.Length + 1)
                    : full;
                if (string.Equals(full, normalized, StringComparison.OrdinalIgnoreCase) ||
                    string.Equals(relative, normalized, StringComparison.OrdinalIgnoreCase))
                {
                    return transform;
                }
                if (normalized.IndexOf('/') < 0 && string.Equals(transform.name, normalized, StringComparison.OrdinalIgnoreCase))
                {
                    if (nameMatch != null)
                    {
                        ambiguous = true;
                    }
                    else
                    {
                        nameMatch = transform;
                    }
                }
            }
            if (ambiguous)
            {
                throw new InvalidOperationException("Multiple loaded objects are named " + path + "; pass the full Path including the scene name.");
            }
            if (nameMatch != null)
            {
                return nameMatch;
            }
            throw new InvalidOperationException("No loaded scene object at Path '" + path + "' for " + label + ".");
        }

        private static string AssetPathOf(Object value)
        {
            if (value == null)
            {
                return null;
            }
            var path = AssetDatabase.GetAssetPath(value);
            return string.IsNullOrEmpty(path) ? null : path;
        }

        private static object AssetRef(Object value)
        {
            if (value == null)
            {
                return null;
            }
            return new
            {
                name = value.name,
                type = value.GetType().Name,
                assetPath = AssetPathOf(value)
            };
        }

        private static string[] ComponentNames(GameObject target)
        {
            return target.GetComponents<Component>()
                .Where(component => component != null)
                .Select(component => component.GetType().Name)
                .ToArray();
        }

        private static bool IsAssetPath(string path)
        {
            return !string.IsNullOrEmpty(path) &&
                (string.Equals(path, "Assets", StringComparison.Ordinal) || path.StartsWith("Assets/", StringComparison.Ordinal));
        }

        private static string NormalizeAssetPath(string path, string extension, string label)
        {
            if (string.IsNullOrEmpty(path))
            {
                throw new ArgumentException(label + " is required, for example Assets/Art/Materials/New.mat.");
            }
            var segments = path.Replace('\\', '/').Trim().Split('/');
            if (segments.Any(segment => segment.Length == 0 || segment == "." || segment == ".."))
            {
                throw new ArgumentException(label + " must not contain empty, . or .. segments: " + path);
            }
            var normalized = string.Join("/", segments);
            if (!IsAssetPath(normalized))
            {
                throw new ArgumentException(label + " must be a project-relative path starting with Assets/: " + path);
            }
            if (!normalized.EndsWith(extension, StringComparison.OrdinalIgnoreCase))
            {
                throw new ArgumentException(label + " must end with " + extension + ": " + path);
            }
            return normalized;
        }

        private static string ProjectAbsolutePath(string assetPath)
        {
            var projectRoot = Path.GetDirectoryName(Application.dataPath);
            return string.IsNullOrEmpty(projectRoot)
                ? assetPath
                : Path.Combine(projectRoot, assetPath.Replace('/', Path.DirectorySeparatorChar));
        }

        private static int? GetInt(JObject args, string name)
        {
            var token = args[name];
            if (token == null || token.Type == JTokenType.Null)
            {
                return null;
            }
            return token.Value<int>();
        }

        private static float? GetFloat(JObject args, string name)
        {
            var token = args[name];
            if (token == null || token.Type == JTokenType.Null)
            {
                return null;
            }
            return token.Value<float>();
        }

        private static bool? GetBool(JObject args, string name)
        {
            var token = args[name];
            if (token == null || token.Type == JTokenType.Null)
            {
                return null;
            }
            return token.Value<bool>();
        }

        private static string GetString(JObject args, string name)
        {
            var token = args[name];
            if (token == null || token.Type == JTokenType.Null)
            {
                return null;
            }
            return token.Value<string>();
        }

        private static Vector3? GetVector3(JObject args, string name)
        {
            var array = args[name] as JArray;
            if (array == null || array.Count < 3)
            {
                return null;
            }
            return new Vector3(array[0].Value<float>(), array[1].Value<float>(), array[2].Value<float>());
        }

        private static Vector2? GetVector2(JObject args, string name)
        {
            var array = args[name] as JArray;
            if (array == null || array.Count < 2)
            {
                return null;
            }
            return new Vector2(array[0].Value<float>(), array[1].Value<float>());
        }

        private static Vector3 RequireVector3(JObject args, string name)
        {
            var value = GetVector3(args, name);
            if (value == null)
            {
                throw new ArgumentException(name + " is required as an array of three numbers.");
            }
            ValidateFinite(value.Value, name);
            return value.Value;
        }

        private static Vector2 RequireVector2(JObject args, string name)
        {
            var value = GetVector2(args, name);
            if (value == null)
            {
                throw new ArgumentException(name + " is required as an array of two numbers.");
            }
            if (float.IsNaN(value.Value.x) || float.IsInfinity(value.Value.x) ||
                float.IsNaN(value.Value.y) || float.IsInfinity(value.Value.y))
            {
                throw new ArgumentException(name + " must contain finite numbers.");
            }
            return value.Value;
        }

        private static Vector3 RequireDirection(JObject args, string name)
        {
            var direction = RequireVector3(args, name);
            if (direction.sqrMagnitude == 0f)
            {
                throw new ArgumentException(name + " must not be zero.");
            }
            return direction.normalized;
        }

        private static int ResolveLayerMask(JObject args)
        {
            var mask = GetInt(args, "LayerMask");
            var layerName = GetString(args, "LayerMaskName");
            if (mask != null && !string.IsNullOrEmpty(layerName))
            {
                throw new ArgumentException("Pass LayerMask or LayerMaskName, not both.");
            }
            if (!string.IsNullOrEmpty(layerName))
            {
                var resolved = LayerMask.GetMask(layerName.Split(',').Select(part => part.Trim()).ToArray());
                if (resolved == 0)
                {
                    throw new ArgumentException("No layer matched LayerMaskName: " + layerName);
                }
                return resolved;
            }
            return mask ?? -1;
        }

        private static QueryTriggerInteraction ResolveTriggerInteraction(JObject args)
        {
            var text = GetString(args, "Triggers");
            if (string.IsNullOrEmpty(text))
            {
                return QueryTriggerInteraction.UseGlobal;
            }
            if (!Enum.TryParse(text, true, out QueryTriggerInteraction interaction))
            {
                throw new ArgumentException("Triggers must be Ignore, Collide or UseGlobal.");
            }
            return interaction;
        }

        private static void CheckLimit(int limit)
        {
            if (limit < 1 || limit > 2000)
            {
                throw new ArgumentOutOfRangeException(nameof(limit), "Limit must be between 1 and 2000.");
            }
        }

        private static object Number(float value)
        {
            return float.IsNaN(value) || float.IsInfinity(value) ? (object)null : value;
        }

        private static object Number(double value)
        {
            return double.IsNaN(value) || double.IsInfinity(value) ? (object)null : (object)(float)value;
        }

        private static object[] Vec(Vector2 value)
        {
            return new object[] { value.x, value.y };
        }

        private static object[] Vec(Vector3 value)
        {
            return new object[] { value.x, value.y, value.z };
        }

        private static object[] Vec(Vector4 value)
        {
            return new object[] { value.x, value.y, value.z, value.w };
        }

        private static string Hex(Color color)
        {
            return "#" + ColorUtility.ToHtmlStringRGBA(color);
        }

        private static object ColorValue(Color color)
        {
            return new { hex = Hex(color), rgba = new[] { color.r, color.g, color.b, color.a } };
        }

        private static IEnumerable<Assembly> EditorAssemblies()
        {
            return AppDomain.CurrentDomain.GetAssemblies()
                .Where(assembly => assembly.GetName().Name.StartsWith("UnityEditor", StringComparison.Ordinal));
        }

        private static bool IsAssemblyLoaded(string name)
        {
            return AppDomain.CurrentDomain.GetAssemblies()
                .Any(assembly => string.Equals(assembly.GetName().Name, name, StringComparison.Ordinal));
        }

        private static string AssemblyVersion(string name)
        {
            var assembly = AppDomain.CurrentDomain.GetAssemblies()
                .FirstOrDefault(candidate => string.Equals(candidate.GetName().Name, name, StringComparison.Ordinal));
            return assembly == null ? null : assembly.GetName().Version.ToString();
        }

        private static object FeaturePackages()
        {
            var api = _frameDebugger ?? (_frameDebugger = DiscoverFrameDebugger());
            return new
            {
                universalRenderPipeline = new { installed = IsAssemblyLoaded("Unity.RenderPipelines.Universal.Runtime") },
                memoryProfiler = new
                {
                    installed = IsAssemblyLoaded("Unity.MemoryProfiler.Editor"),
                    assemblyVersion = AssemblyVersion("Unity.MemoryProfiler.Editor")
                },
                proBuilder = new
                {
                    installed = IsAssemblyLoaded("Unity.ProBuilder"),
                    note = "Absent packages are reported; their editors API is never referenced at compile time."
                },
                vfxGraph = new { installed = IsAssemblyLoaded("Unity.VisualEffectGraph.Runtime") },
                frameDebugger = new
                {
                    available = api.CanToggle,
                    partial = api.Partial
                }
            };
        }

        // -------------------------------------------------------------- nested types

        private sealed class FrameDebuggerApi
        {
            public string[] Candidates;
            public string TypeName;
            public PropertyInfo EnabledProperty;
            public MethodInfo EnableMethod;
            public MethodInfo DisableMethod;
            public string Partial;

            /// <summary>
            /// A writable static bool is a complete toggle on its own; two zero-argument methods are
            /// accepted only as a pair. A single direction is not provable and is reported as partial.
            /// </summary>
            public bool CanToggle
            {
                get { return EnabledProperty != null || (EnableMethod != null && DisableMethod != null); }
            }
        }

        private sealed class PipelineSetting
        {
            public string Name;
            public string Type;
            public string Value;
        }

        private sealed class MaterialAssignment
        {
            public string Name;
            public ShaderPropertyType Type;
            public object Value;
        }
    }
}
