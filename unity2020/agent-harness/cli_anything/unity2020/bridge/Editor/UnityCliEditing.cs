using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json.Linq;
using UnityEditor;
#if !UNITY_2021_2_OR_NEWER
using UnityEditor.Experimental.SceneManagement;
#endif
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace CliAnything.Unity
{
    /// <summary>
    /// Scene, GameObject, component, prefab and asset editing dispatched by <see cref="UnityCliBridge"/>.
    /// Every write is an explicit command, guarded by Edit Mode, dirty-scene and identity checks, and
    /// recorded with Undo where Unity supports it. Commands owned here:
    /// scene.create/close/set-active,
    /// gameobject.create/rename/transform/duplicate/delete,
    /// component.add/remove/set,
    /// prefab.create/stage-open/stage-save/stage-close,
    /// asset.import/move.
    /// Deferred: prefab contents editing without a stage, asset delete/create, scene templates beyond
    /// empty/default, moving objects between scenes, object-reference properties and arrays/collections.
    /// </summary>
    internal static partial class UnityCliEditing
    {
        private const string UndoCreateGameObject = "Unity CLI Create GameObject";
        private const string UndoRenameGameObject = "Unity CLI Rename GameObject";
        private const string UndoTransformGameObject = "Unity CLI Transform GameObject";
        private const string UndoSetComponent = "Unity CLI Set Component Property";
        private const string UndoDuplicateGameObject = "Unity CLI Duplicate GameObject";

        private static readonly HashSet<string> OwnedCommands = new HashSet<string>(StringComparer.Ordinal)
        {
            "scene.create",
            "scene.close",
            "scene.set-active",
            "gameobject.create",
            "gameobject.rename",
            "gameobject.transform",
            "gameobject.duplicate",
            "gameobject.delete",
            "component.add",
            "component.remove",
            "component.set",
            "prefab.create",
            "prefab.stage-open",
            "prefab.stage-save",
            "prefab.stage-close",
            "prefab.inspect-ui",
            "prefab.edit-asset",
            "asset.import",
            "asset.import-sprite",
            "asset.move"
        };

        private static List<Type> _componentTypes;

        internal static bool TryExecute(string command, JObject args, out object result)
        {
            result = null;
            if (string.IsNullOrEmpty(command) || !OwnedCommands.Contains(command))
            {
                return false;
            }

            args = args ?? new JObject();
            try
            {
                result = Dispatch(command, args);
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
                case "scene.create":
                    return CreateScene(args);
                case "scene.close":
                    return CloseScene(args);
                case "scene.set-active":
                    return SetActiveScene(args);
                case "gameobject.create":
                    return CreateGameObject(args);
                case "gameobject.rename":
                    return RenameGameObject(args);
                case "gameobject.transform":
                    return TransformGameObject(args);
                case "gameobject.duplicate":
                    return DuplicateGameObject(args);
                case "gameobject.delete":
                    return DeleteGameObject(args);
                case "component.add":
                    return AddComponent(args);
                case "component.remove":
                    return RemoveComponent(args);
                case "component.set":
                    return SetComponentProperty(args);
                case "prefab.create":
                    return CreatePrefab(args);
                case "prefab.stage-open":
                    return OpenPrefabStage(args);
                case "prefab.stage-save":
                    return SavePrefabStage();
                case "prefab.stage-close":
                    return ClosePrefabStage(args);
                case "prefab.inspect-ui":
                    return InspectPrefabUi(args);
                case "prefab.edit-asset":
                    return EditPrefabAsset(args);
                case "asset.import":
                    return ImportAsset(args);
                case "asset.import-sprite":
                    return ImportSprite(args);
                case "asset.move":
                    return MoveAsset(args);
                default:
                    return Error("Unsupported Unity CLI editing command: " + command);
            }
        }

        // ------------------------------------------------------------------ scene

        private static object CreateScene(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("creating a scene");
            RequireMainStage("creating a scene");
            var assetPath = RequireAssetPath(args, "AssetPath", ".unity");
            if (AssetDatabase.LoadAssetAtPath<SceneAsset>(assetPath) != null ||
                File.Exists(ToAbsoluteAssetPath(assetPath)))
            {
                throw new InvalidOperationException("Scene asset already exists: " + assetPath);
            }

            var additive = GetBool(args, "Additive", false);
            var previous = Enumerable.Range(0, SceneManager.sceneCount)
                .Select(SceneManager.GetSceneAt)
                .Where(scene => scene.isLoaded && !EditorSceneManager.IsPreviewScene(scene))
                .ToArray();
            if (!additive)
            {
                var dirty = previous.Where(scene => scene.isDirty)
                    .Select(SceneName)
                    .ToArray();
                if (dirty.Length > 0)
                {
                    throw new InvalidOperationException(
                        "Save the open scenes before replacing them: " + string.Join(", ", dirty));
                }
            }

            EnsureAssetFolder(ParentFolder(assetPath));
            var template = GetString(args, "Template");
            var setup = string.Equals(template, "empty", StringComparison.OrdinalIgnoreCase)
                ? NewSceneSetup.EmptyScene
                : NewSceneSetup.DefaultGameObjects;
            var scene = EditorSceneManager.NewScene(setup, NewSceneMode.Additive);
            if (!EditorSceneManager.SaveScene(scene, assetPath))
            {
                EditorSceneManager.CloseScene(scene, true);
                throw new InvalidOperationException("Unity created the scene in memory but did not save it to " + assetPath + ".");
            }
            AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceSynchronousImport);

            var created = SceneManager.GetSceneByPath(assetPath);
            if (!created.IsValid() || !created.isLoaded)
            {
                created = scene;
            }
            SceneManager.SetActiveScene(created);
            if (!additive)
            {
                foreach (var old in previous)
                {
                    if (old.IsValid() && old != created && old.isLoaded)
                    {
                        EditorSceneManager.CloseScene(old, true);
                    }
                }
            }

            return Ok(new
            {
                path = created.path,
                name = created.name,
                active = created == SceneManager.GetActiveScene(),
                dirty = created.isDirty,
                rootCount = created.rootCount,
                remainingScenes = SceneManager.sceneCount
            });
        }

        private static object CloseScene(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("closing a scene");
            RequireMainStage("closing a scene");
            var scene = RequireLoadedScene(RequireAssetPath(args, "ScenePath", ".unity"));
            if (scene.isDirty)
            {
                throw new InvalidOperationException("Scene has unsaved changes. Save it before closing: " + SceneName(scene));
            }
            var loadedScenes = Enumerable.Range(0, SceneManager.sceneCount)
                .Select(SceneManager.GetSceneAt)
                .Where(candidate => candidate.isLoaded && !EditorSceneManager.IsPreviewScene(candidate))
                .ToArray();
            if (loadedScenes.Length <= 1)
            {
                throw new InvalidOperationException("Cannot close the only open scene.");
            }

            var path = scene.path;
            var name = scene.name;
            if (scene == SceneManager.GetActiveScene())
            {
                var replacement = loadedScenes.FirstOrDefault(candidate => candidate != scene);
                if (replacement.IsValid())
                {
                    SceneManager.SetActiveScene(replacement);
                }
            }
            var remove = GetBool(args, "RemoveScene", true);
            if (!EditorSceneManager.CloseScene(scene, remove))
            {
                throw new InvalidOperationException("Unity did not close the scene: " + path);
            }
            return Ok(new
            {
                closed = true,
                path,
                name,
                removed = remove,
                remainingScenes = SceneManager.sceneCount,
                active = SceneManager.GetActiveScene().path
            });
        }

        private static object SetActiveScene(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("changing the active scene");
            RequireMainStage("changing the active scene");
            var scene = RequireLoadedScene(RequireAssetPath(args, "ScenePath", ".unity"));
            if (!SceneManager.SetActiveScene(scene))
            {
                throw new InvalidOperationException("Unity did not activate the scene: " + scene.path);
            }
            return Ok(new { path = scene.path, name = scene.name, active = true });
        }

        // ------------------------------------------------------------- gameobject

        private static object CreateGameObject(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("creating a GameObject");
            var name = GetString(args, "Name");
            if (!string.IsNullOrEmpty(name))
            {
                RequireGameObjectName(name, "Name");
            }
            var primitiveText = GetString(args, "PrimitiveType");
            var prefabPath = GetString(args, "PrefabPath");
            if (!string.IsNullOrEmpty(primitiveText) && !string.IsNullOrEmpty(prefabPath))
            {
                throw new ArgumentException("PrimitiveType and PrefabPath are mutually exclusive.");
            }
            if (string.IsNullOrEmpty(name) && string.IsNullOrEmpty(primitiveText) && string.IsNullOrEmpty(prefabPath))
            {
                throw new ArgumentException("Provide Name, PrimitiveType or PrefabPath.");
            }

            var parent = ResolveOptionalParent(args);
            var scene = parent != null ? parent.gameObject.scene : RequireActiveScene();
            if (!scene.IsValid() || !scene.isLoaded)
            {
                throw new InvalidOperationException("Parent GameObject is not in a loaded scene.");
            }
            GameObject gameObject;
            if (!string.IsNullOrEmpty(prefabPath))
            {
                var assetPath = RequireAssetPath(args, "PrefabPath", ".prefab");
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
                if (prefab == null)
                {
                    throw new InvalidOperationException("Prefab asset not found: " + assetPath);
                }
                gameObject = PrefabUtility.InstantiatePrefab(prefab, scene) as GameObject;
                if (gameObject == null)
                {
                    throw new InvalidOperationException("Unity did not instantiate the prefab: " + assetPath);
                }
            }
            else if (!string.IsNullOrEmpty(primitiveText))
            {
                var primitive = ParsePrimitive(primitiveText);
                gameObject = GameObject.CreatePrimitive(primitive);
                var createdScene = gameObject.scene;
                if (createdScene != scene)
                {
                    SceneManager.MoveGameObjectToScene(gameObject, scene);
                }
            }
            else
            {
                gameObject = new GameObject();
                SceneManager.MoveGameObjectToScene(gameObject, scene);
            }

            Undo.RegisterCreatedObjectUndo(gameObject, UndoCreateGameObject);
            if (!string.IsNullOrEmpty(name))
            {
                gameObject.name = name;
            }
            if (parent != null)
            {
                gameObject.transform.SetParent(parent, false);
            }
            var position = GetVector3(args, "Position");
            if (position.HasValue)
            {
                gameObject.transform.position = position.Value;
            }
            var rotation = GetVector3(args, "Rotation");
            if (rotation.HasValue)
            {
                gameObject.transform.eulerAngles = rotation.Value;
            }
            var scale = GetVector3(args, "Scale");
            if (scale.HasValue)
            {
                gameObject.transform.localScale = scale.Value;
            }
            gameObject.SetActive(GetBool(args, "Active", true));

            MarkDirty(gameObject);
            return Ok(DescribeGameObject(gameObject));
        }

        private static object RenameGameObject(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("renaming a GameObject");
            var gameObject = ResolveTarget(args, "GameObject");
            var name = RequireString(args, "Name");
            RequireGameObjectName(name, "Name");
            var stage = PrefabStageUtility.GetCurrentPrefabStage();
            if (stage != null && stage.prefabContentsRoot == gameObject)
            {
                throw new InvalidOperationException(
                    "The prefab stage root mirrors the asset name. Rename the asset with asset move instead.");
            }
            if (gameObject.name == name)
            {
                return Ok(DescribeGameObject(gameObject));
            }
            Undo.RecordObject(gameObject, UndoRenameGameObject);
            var previous = gameObject.name;
            gameObject.name = name;
            MarkDirty(gameObject);
            return Ok(new
            {
                objectId = gameObject.GetInstanceID(),
                path = GetPath(gameObject.transform),
                previous,
                name = gameObject.name
            });
        }

        private static object TransformGameObject(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("changing a GameObject transform");
            var gameObject = ResolveTarget(args, "GameObject");
            var transform = gameObject.transform;
            var position = GetVector3(args, "Position");
            var rotation = GetVector3(args, "Rotation");
            var scale = GetVector3(args, "Scale");
            var active = GetOptionalBool(args, "Active");
            if (!position.HasValue && !rotation.HasValue && !scale.HasValue && !active.HasValue)
            {
                throw new ArgumentException("Provide at least one of Position, Rotation, Scale or Active.");
            }

            var changes = new List<object>();
            Undo.RecordObject(transform, UndoTransformGameObject);
            Undo.RecordObject(gameObject, UndoTransformGameObject);
            if (position.HasValue)
            {
                var before = transform.position;
                transform.position = position.Value;
                changes.Add(Change("position", Vector(before), Vector(transform.position)));
            }
            if (rotation.HasValue)
            {
                var before = transform.eulerAngles;
                transform.eulerAngles = rotation.Value;
                changes.Add(Change("rotation", Vector(before), Vector(transform.eulerAngles)));
            }
            if (scale.HasValue)
            {
                var before = transform.localScale;
                transform.localScale = scale.Value;
                changes.Add(Change("scale", Vector(before), Vector(transform.localScale)));
            }
            if (active.HasValue)
            {
                var before = gameObject.activeSelf;
                gameObject.SetActive(active.Value);
                changes.Add(Change("active", before, active.Value));
            }
            MarkDirty(gameObject);
            return Ok(new
            {
                objectId = gameObject.GetInstanceID(),
                path = GetPath(transform),
                changes = changes.ToArray()
            });
        }

        private static object DuplicateGameObject(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("duplicating a GameObject");
            var original = ResolveTarget(args, "GameObject");
            var scene = original.scene;
            if (!scene.isLoaded)
            {
                throw new InvalidOperationException("GameObject scene is not loaded: " + GetPath(original.transform));
            }

            var copy = InstantiateForDuplicate(original, scene);
            if (copy == null)
            {
                throw new InvalidOperationException("Unity did not duplicate the GameObject: " + GetPath(original.transform));
            }
            Undo.RegisterCreatedObjectUndo(copy, UndoDuplicateGameObject);
            var name = GetString(args, "NewName");
            if (!string.IsNullOrEmpty(name))
            {
                RequireGameObjectName(name, "NewName");
                copy.name = name;
            }
            else
            {
                copy.name = GameObjectUtility.GetUniqueNameForSibling(original.transform.parent, original.name);
            }
            var offset = GetVector3(args, "Offset");
            if (offset.HasValue)
            {
                copy.transform.localPosition += offset.Value;
            }
            MarkDirty(copy);
            return Ok(DescribeGameObject(copy));
        }

        private static GameObject InstantiateForDuplicate(GameObject original, Scene scene)
        {
            var source = PrefabUtility.GetCorrespondingObjectFromSource(original);
            if (source != null && AssetDatabase.Contains(source) && PrefabUtility.IsAnyPrefabInstanceRoot(original))
            {
                var instance = PrefabUtility.InstantiatePrefab(source, scene) as GameObject;
                if (instance == null)
                {
                    throw new InvalidOperationException("Unity did not instantiate the prefab source for: " + GetPath(original.transform));
                }
                instance.transform.SetParent(original.transform.parent, false);
                instance.transform.localPosition = original.transform.localPosition;
                instance.transform.localRotation = original.transform.localRotation;
                instance.transform.localScale = original.transform.localScale;
                instance.name = original.name;
                return instance;
            }
            return UnityEngine.Object.Instantiate(original, original.transform.parent, false);
        }

        private static object DeleteGameObject(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("deleting a GameObject");
            var gameObject = ResolveTarget(args, "GameObject");
            var scene = gameObject.scene;
            var stage = PrefabStageUtility.GetCurrentPrefabStage();
            if (stage != null && stage.prefabContentsRoot == gameObject)
            {
                throw new InvalidOperationException(
                    "The prefab stage root cannot be deleted. Close the stage or delete the prefab asset instead.");
            }
            var objectId = gameObject.GetInstanceID();
            var name = gameObject.name;
            var path = GetPath(gameObject.transform);
            var children = gameObject.transform.childCount;
            if (!EditorSceneManager.IsPreviewScene(scene))
            {
                MarkDirty(gameObject);
            }
            Undo.DestroyObjectImmediate(gameObject);
            return Ok(new
            {
                deleted = true,
                objectId,
                name,
                path,
                children,
                scene = scene.path
            });
        }

        // -------------------------------------------------------------- component

        private static object AddComponent(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("adding a component");
            var gameObject = ResolveTarget(args, "GameObject");
            var type = ResolveComponentType(RequireString(args, "ComponentType"));
            if (typeof(Transform).IsAssignableFrom(type))
            {
                throw new ArgumentException("Transform components are added automatically by Unity: " + type.FullName);
            }
            if (type.IsDefined(typeof(DisallowMultipleComponent), false) && gameObject.GetComponent(type) != null)
            {
                throw new InvalidOperationException("GameObject already has a " + type.FullName + " component.");
            }
            var component = Undo.AddComponent(gameObject, type);
            if (component == null)
            {
                throw new InvalidOperationException("Unity did not add " + type.FullName + " to " + GetPath(gameObject.transform) + ".");
            }
            MarkDirty(gameObject);
            return Ok(new
            {
                objectId = gameObject.GetInstanceID(),
                path = GetPath(gameObject.transform),
                added = component.GetType().FullName,
                components = ComponentNames(gameObject)
            });
        }

        private static object RemoveComponent(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("removing a component");
            var gameObject = ResolveTarget(args, "GameObject");
            var component = ResolveExistingComponent(gameObject, args);
            if (component is Transform)
            {
                throw new ArgumentException("Transform components cannot be removed.");
            }
            var type = component.GetType().FullName;
            Undo.DestroyObjectImmediate(component);
            MarkDirty(gameObject);
            return Ok(new
            {
                objectId = gameObject.GetInstanceID(),
                path = GetPath(gameObject.transform),
                removed = type,
                components = ComponentNames(gameObject)
            });
        }

        private static object SetComponentProperty(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("changing a component property");
            var gameObject = ResolveTarget(args, "GameObject");
            var component = ResolveExistingComponent(gameObject, args);
            var propertyName = RequireString(args, "Property");
            var token = args["Value"];
            if (token == null || token.Type == JTokenType.Null)
            {
                throw new ArgumentException("Provide Value for Property " + propertyName + ".");
            }

            var member = FindWritableMember(component.GetType(), propertyName);
            var memberType = member is PropertyInfo property ? property.PropertyType : ((FieldInfo)member).FieldType;
            var converted = ConvertPropertyValue(token, memberType, propertyName);
            var before = GetMemberValue(member, component);
            Undo.RecordObject(component, UndoSetComponent);
            try
            {
                SetMemberValue(member, component, converted);
            }
            catch (TargetInvocationException exception)
            {
                throw new InvalidOperationException(
                    "Setter for " + member.Name + " failed: " + (exception.InnerException ?? exception).Message);
            }
            EditorUtility.SetDirty(component);
            MarkDirty(gameObject);
            var after = GetMemberValue(member, component);
            return Ok(new
            {
                objectId = gameObject.GetInstanceID(),
                path = GetPath(gameObject.transform),
                component = component.GetType().FullName,
                property = member.Name,
                before = DescribeValue(before),
                after = DescribeValue(after)
            });
        }

        // ----------------------------------------------------------------- prefab

        private static object CreatePrefab(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("creating a prefab");
            var gameObject = ResolveTarget(args, "GameObject");
            if (EditorSceneManager.IsPreviewScene(gameObject.scene))
            {
                throw new InvalidOperationException(
                    "Cannot save a prefab from a prefab stage. Use prefab stage-save, or save an object from a scene.");
            }
            var assetPath = RequireAssetPath(args, "AssetPath", ".prefab");
            var exists = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath) != null ||
                File.Exists(ToAbsoluteAssetPath(assetPath));
            if (exists && !GetBool(args, "Overwrite", false))
            {
                throw new InvalidOperationException(
                    "Prefab asset already exists: " + assetPath + ". Pass Overwrite=true to replace it.");
            }
            EnsureAssetFolder(ParentFolder(assetPath));
            var saved = PrefabUtility.SaveAsPrefabAssetAndConnect(gameObject, assetPath, InteractionMode.AutomatedAction);
            if (saved == null)
            {
                throw new InvalidOperationException("Unity did not save the prefab to " + assetPath + ".");
            }
            AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceSynchronousImport);
            return Ok(new
            {
                assetPath = AssetDatabase.GUIDToAssetPath(AssetDatabase.AssetPathToGUID(assetPath)),
                guid = AssetDatabase.AssetPathToGUID(assetPath),
                name = saved.name,
                objectId = gameObject.GetInstanceID(),
                connected = PrefabUtility.IsPartOfPrefabInstance(gameObject)
            });
        }

        private static object OpenPrefabStage(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("opening a prefab stage");
            var assetPath = RequireAssetPath(args, "AssetPath", ".prefab");
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
            if (prefab == null)
            {
                throw new InvalidOperationException("Prefab asset not found: " + assetPath);
            }
            var current = PrefabStageUtility.GetCurrentPrefabStage();
            if (current != null)
            {
                if (PrefabStagePath(current) == assetPath && current.prefabContentsRoot != null)
                {
                    return Ok(DescribePrefabStage(current));
                }
                if (current.scene.isDirty)
                {
                    throw new InvalidOperationException(
                        "The open prefab stage has unsaved changes: " + PrefabStagePath(current) +
                        ". Run prefab stage-save or stage-close --discard first.");
                }
            }
            // Unity 2020.3 exposes PrefabStageUtility.OpenPrefab only internally; opening the prefab
            // asset is the supported public route and enters Prefab Mode on the same stage API.
            if (!AssetDatabase.OpenAsset(prefab))
            {
                throw new InvalidOperationException("Unity did not open a prefab stage for " + assetPath + ".");
            }
            var stage = PrefabStageUtility.GetCurrentPrefabStage();
            if (stage == null || stage.prefabContentsRoot == null || PrefabStagePath(stage) != assetPath)
            {
                throw new InvalidOperationException("Unity did not enter Prefab Mode for " + assetPath + ".");
            }
            return Ok(DescribePrefabStage(stage));
        }

        private static object SavePrefabStage()
        {
            RequireIdleEditor();
            RequireEditMode("saving a prefab stage");
            var stage = RequirePrefabStage();
            var root = stage.prefabContentsRoot;
            var saved = PrefabUtility.SaveAsPrefabAsset(root, PrefabStagePath(stage));
            if (saved == null)
            {
                throw new InvalidOperationException("Unity did not save the prefab stage to " + PrefabStagePath(stage) + ".");
            }
            stage.ClearDirtiness();
            AssetDatabase.ImportAsset(PrefabStagePath(stage), ImportAssetOptions.ForceSynchronousImport);
            return Ok(new
            {
                assetPath = PrefabStagePath(stage),
                guid = AssetDatabase.AssetPathToGUID(PrefabStagePath(stage)),
                name = saved.name,
                dirty = false
            });
        }

        private static object ClosePrefabStage(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("closing a prefab stage");
            var stage = RequirePrefabStage();
            var dirty = stage.scene.isDirty;
            if (dirty && !GetBool(args, "Discard", false))
            {
                throw new InvalidOperationException(
                    "Prefab stage has unsaved changes: " + PrefabStagePath(stage) +
                    ". Run prefab stage-save or pass Discard=true.");
            }
            var assetPath = PrefabStagePath(stage);
            if (dirty)
            {
                stage.ClearDirtiness();
            }
            StageUtility.GoToMainStage();
            return Ok(new { closed = true, assetPath, hadUnsavedChanges = dirty });
        }

        private static string PrefabStagePath(PrefabStage stage)
        {
#if UNITY_2020_2_OR_NEWER
            return stage.assetPath;
#else
            return stage.prefabAssetPath;
#endif
        }

        private static object DescribePrefabStage(PrefabStage stage)
        {
            return new
            {
                assetPath = PrefabStagePath(stage),
                rootId = stage.prefabContentsRoot.GetInstanceID(),
                name = stage.prefabContentsRoot.name,
                dirty = stage.scene.isDirty
            };
        }

        private static PrefabStage RequirePrefabStage()
        {
            var stage = PrefabStageUtility.GetCurrentPrefabStage();
            if (stage == null || stage.prefabContentsRoot == null)
            {
                throw new InvalidOperationException("No prefab stage is open. Run prefab stage-open first.");
            }
            return stage;
        }

        // ------------------------------------------------------------------ asset

        private static object ImportAsset(JObject args)
        {
            RequireIdleEditor();
            var assetPath = RequireAssetPath(args, "AssetPath");
            var absolute = ToAbsoluteAssetPath(assetPath);
            var isFolder = Directory.Exists(absolute);
            if (!isFolder && !File.Exists(absolute))
            {
                throw new InvalidOperationException("Asset does not exist on disk: " + assetPath);
            }
            var options = ImportAssetOptions.ForceSynchronousImport;
            if (isFolder && GetBool(args, "Recursive", false))
            {
                options |= ImportAssetOptions.ImportRecursive;
            }
            AssetDatabase.ImportAsset(assetPath, options);
            var type = AssetDatabase.GetMainAssetTypeAtPath(assetPath);
            var folder = AssetDatabase.IsValidFolder(assetPath);
            if (type == null && !folder)
            {
                throw new InvalidOperationException("Unity did not import the asset: " + assetPath);
            }
            return Ok(new
            {
                path = assetPath,
                guid = AssetDatabase.AssetPathToGUID(assetPath),
                type = type == null ? "Folder" : type.FullName,
                folder,
                recursive = isFolder && GetBool(args, "Recursive", false)
            });
        }

        private static object MoveAsset(JObject args)
        {
            RequireIdleEditor();
            var source = RequireAssetPath(args, "SourcePath");
            var destination = RequireAssetPath(args, "DestinationPath");
            if (source == destination)
            {
                throw new ArgumentException("SourcePath and DestinationPath are identical.");
            }
            if (AssetDatabase.LoadMainAssetAtPath(source) == null && !AssetDatabase.IsValidFolder(source))
            {
                throw new InvalidOperationException("Asset not found: " + source);
            }
            if (AssetDatabase.LoadMainAssetAtPath(destination) != null || AssetDatabase.IsValidFolder(destination))
            {
                throw new InvalidOperationException("Destination already exists: " + destination);
            }
            var parent = ParentFolder(destination);
            if (!AssetDatabase.IsValidFolder(parent))
            {
                throw new InvalidOperationException("Destination folder does not exist: " + parent);
            }
            var loadedScene = Enumerable.Range(0, SceneManager.sceneCount)
                .Select(SceneManager.GetSceneAt)
                .FirstOrDefault(scene => scene.path == source ||
                    scene.path.StartsWith(source + "/", StringComparison.Ordinal));
            if (loadedScene.IsValid())
            {
                throw new InvalidOperationException("Close the scene before moving it: " + loadedScene.path);
            }
            var prefabStage = PrefabStageUtility.GetCurrentPrefabStage();
            if (prefabStage != null &&
                (PrefabStagePath(prefabStage) == source || PrefabStagePath(prefabStage).StartsWith(source + "/", StringComparison.Ordinal)))
            {
                throw new InvalidOperationException("Close the prefab stage before moving its prefab: " + PrefabStagePath(prefabStage));
            }
            var invalid = AssetDatabase.ValidateMoveAsset(source, destination);
            if (!string.IsNullOrEmpty(invalid))
            {
                throw new InvalidOperationException(invalid);
            }
            var guid = AssetDatabase.AssetPathToGUID(source);
            var moved = AssetDatabase.MoveAsset(source, destination);
            if (!string.IsNullOrEmpty(moved))
            {
                throw new InvalidOperationException(moved);
            }
            return Ok(new
            {
                source,
                destination,
                guid,
                moved = true
            });
        }

        // ---------------------------------------------------------------- helpers

        private static object Ok(object data)
        {
            return new { ok = true, data };
        }

        private static object Error(string error)
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

        private static void RequireMainStage(string action)
        {
            var stage = PrefabStageUtility.GetCurrentPrefabStage();
            if (stage != null)
            {
                throw new InvalidOperationException(
                    "Prefab Mode is open on " + PrefabStagePath(stage) + ". Run prefab stage-close before " + action + ".");
            }
        }

        private static Scene RequireActiveScene()
        {
            var scene = SceneManager.GetActiveScene();
            if (!scene.IsValid() || !scene.isLoaded)
            {
                throw new InvalidOperationException("No active loaded scene. Open or create a scene first.");
            }
            return scene;
        }

        private static Scene RequireLoadedScene(string scenePath)
        {
            var scene = SceneManager.GetSceneByPath(scenePath);
            if (!scene.IsValid() || !scene.isLoaded)
            {
                throw new InvalidOperationException("Scene is not open in the Editor: " + scenePath);
            }
            if (EditorSceneManager.IsPreviewScene(scene))
            {
                throw new InvalidOperationException("Prefab stage scenes are managed by prefab stage commands: " + scenePath);
            }
            return scene;
        }

        private static GameObject ResolveTarget(JObject args, string label)
        {
            var objectId = GetInt(args, "ObjectId");
            var path = GetString(args, "Path");
            var scenePath = GetString(args, "ScenePath");
            if (objectId.HasValue)
            {
                var gameObject = EditorUtility.InstanceIDToObject(objectId.Value) as GameObject;
                if (gameObject == null || !gameObject.scene.IsValid() || !gameObject.scene.isLoaded)
                {
                    throw new InvalidOperationException(
                        label + " instance ID does not identify a loaded scene object: " + objectId.Value);
                }
                if (EditorUtility.IsPersistent(gameObject))
                {
                    throw new InvalidOperationException(
                        label + " instance ID identifies a project asset, not a loaded scene object: " + objectId.Value);
                }
                if (!string.IsNullOrEmpty(scenePath) && gameObject.scene.path != scenePath)
                {
                    throw new InvalidOperationException(
                        label + " is in scene " + gameObject.scene.path + ", not " + scenePath + ".");
                }
                return gameObject;
            }
            if (string.IsNullOrEmpty(path))
            {
                throw new InvalidOperationException("Provide ObjectId or Path for the " + label + ".");
            }
            var normalized = path.Trim('/');
            var matches = WalkScenes()
                .Where(transform => string.Equals(GetPath(transform), normalized, StringComparison.Ordinal))
                .Where(transform => string.IsNullOrEmpty(scenePath) || transform.gameObject.scene.path == scenePath)
                .Select(transform => transform.gameObject)
                .ToArray();
            if (matches.Length == 0)
            {
                throw new InvalidOperationException("No loaded scene object matches path: " + path);
            }
            if (matches.Length > 1)
            {
                throw new InvalidOperationException(
                    "Path matches " + matches.Length + " objects. Pass ObjectId or ScenePath.");
            }
            return matches[0];
        }

        private static Transform ResolveOptionalParent(JObject args)
        {
            var parentId = GetInt(args, "ParentId");
            var parentPath = GetString(args, "ParentPath");
            if (!parentId.HasValue && string.IsNullOrEmpty(parentPath))
            {
                return null;
            }
            var parentArgs = new JObject();
            if (parentId.HasValue)
            {
                parentArgs["ObjectId"] = parentId.Value;
            }
            if (!string.IsNullOrEmpty(parentPath))
            {
                parentArgs["Path"] = parentPath;
            }
            return ResolveTarget(parentArgs, "parent").transform;
        }

        private static Component ResolveExistingComponent(GameObject gameObject, JObject args)
        {
            var type = ResolveComponentType(RequireString(args, "ComponentType"));
            var components = gameObject.GetComponents(type);
            if (components.Length == 0)
            {
                throw new InvalidOperationException(
                    "GameObject has no " + type.FullName + " component: " + GetPath(gameObject.transform));
            }
            var index = GetInt(args, "Index");
            if (index.HasValue)
            {
                if (index.Value < 0 || index.Value >= components.Length)
                {
                    throw new ArgumentOutOfRangeException(
                        "Index", "Index must be between 0 and " + (components.Length - 1) + ".");
                }
                return components[index.Value];
            }
            if (components.Length > 1)
            {
                throw new InvalidOperationException(
                    "GameObject has " + components.Length + " " + type.FullName +
                    " components. Pass Index to select one.");
            }
            return components[0];
        }

        private static Type ResolveComponentType(string name)
        {
            if (string.IsNullOrWhiteSpace(name))
            {
                throw new ArgumentException("ComponentType must name a UnityEngine.Component type.");
            }
            var exact = new List<Type>();
            var shortNames = new List<Type>();
            foreach (var type in ComponentTypes())
            {
                if (string.Equals(type.FullName, name, StringComparison.Ordinal))
                {
                    exact.Add(type);
                }
                else if (string.Equals(type.Name, name, StringComparison.OrdinalIgnoreCase))
                {
                    shortNames.Add(type);
                }
            }
            if (exact.Count == 1)
            {
                return exact[0];
            }
            if (exact.Count > 1)
            {
                throw new ArgumentException("Ambiguous component type " + name + ": " + Candidates(exact) + ".");
            }
            if (shortNames.Count == 1)
            {
                return shortNames[0];
            }
            if (shortNames.Count == 0)
            {
                throw new ArgumentException("Unknown component type: " + name + ".");
            }
            throw new ArgumentException(
                "Component type " + name + " matches " + shortNames.Count + " types. Use a full name: " +
                Candidates(shortNames) + ".");
        }

        private static List<Type> ComponentTypes()
        {
            if (_componentTypes != null)
            {
                return _componentTypes;
            }
            var types = new List<Type>();
            var fullNames = new HashSet<string>(StringComparer.Ordinal);
            foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                if (assembly.IsDynamic)
                {
                    continue;
                }
                Type[] assemblyTypes;
                try
                {
                    assemblyTypes = assembly.GetTypes();
                }
                catch (ReflectionTypeLoadException exception)
                {
                    assemblyTypes = exception.Types.Where(type => type != null).ToArray();
                }
                catch (Exception)
                {
                    continue;
                }
                foreach (var type in assemblyTypes)
                {
                    if (type == null || !typeof(Component).IsAssignableFrom(type) ||
                        type.IsAbstract || type.IsGenericTypeDefinition || type.FullName == null)
                    {
                        continue;
                    }
                    if (fullNames.Add(type.FullName))
                    {
                        types.Add(type);
                    }
                }
            }
            _componentTypes = types;
            return types;
        }

        private static string Candidates(IEnumerable<Type> types)
        {
            return string.Join(", ", types.Select(type => type.FullName).OrderBy(name => name).Take(10));
        }

        private static MemberInfo FindWritableMember(Type type, string name)
        {
            var properties = type.GetProperties(BindingFlags.Public | BindingFlags.Instance);
            var property = properties.FirstOrDefault(candidate =>
                    candidate.Name == name && candidate.CanRead && candidate.CanWrite &&
                    candidate.GetIndexParameters().Length == 0)
                ?? properties.FirstOrDefault(candidate =>
                    string.Equals(candidate.Name, name, StringComparison.OrdinalIgnoreCase) &&
                    candidate.CanRead && candidate.CanWrite && candidate.GetIndexParameters().Length == 0);
            if (property != null)
            {
                return property;
            }
            var fields = type.GetFields(BindingFlags.Public | BindingFlags.Instance);
            var field = fields.FirstOrDefault(candidate => candidate.Name == name && !candidate.IsInitOnly && !candidate.IsLiteral)
                ?? fields.FirstOrDefault(candidate => string.Equals(candidate.Name, name, StringComparison.OrdinalIgnoreCase) &&
                    !candidate.IsInitOnly && !candidate.IsLiteral);
            if (field != null)
            {
                return field;
            }
            throw new ArgumentException(
                "No writable public property or field named " + name + " on " + type.FullName + ".");
        }

        private static object GetMemberValue(MemberInfo member, object target)
        {
            if (member is PropertyInfo property)
            {
                return property.GetValue(target, null);
            }
            return ((FieldInfo)member).GetValue(target);
        }

        private static void SetMemberValue(MemberInfo member, object target, object value)
        {
            if (member is PropertyInfo property)
            {
                property.SetValue(target, value, null);
                return;
            }
            ((FieldInfo)member).SetValue(target, value);
        }

        private static object ConvertPropertyValue(JToken token, Type target, string label)
        {
            if (target == typeof(string))
            {
                if (token.Type != JTokenType.String)
                {
                    throw new ArgumentException(label + " requires a JSON string value.");
                }
                return token.Value<string>();
            }
            if (target == typeof(bool))
            {
                if (token.Type == JTokenType.Boolean)
                {
                    return token.Value<bool>();
                }
                if (token.Type == JTokenType.String && bool.TryParse(token.Value<string>(), out var parsed))
                {
                    return parsed;
                }
                throw new ArgumentException(label + " requires true or false.");
            }
            if (target.IsEnum)
            {
                if (token.Type == JTokenType.Integer)
                {
                    return Enum.ToObject(target, token.Value<int>());
                }
                if (token.Type != JTokenType.String)
                {
                    throw new ArgumentException(label + " requires an enum name or integer value.");
                }
                try
                {
                    return Enum.Parse(target, token.Value<string>(), true);
                }
                catch (ArgumentException)
                {
                    throw new ArgumentException(
                        label + " is not a value of " + target.Name + ". Expected one of: " +
                        string.Join(", ", Enum.GetNames(target)) + ".");
                }
            }
            if (target == typeof(Vector2))
            {
                var values = Numbers(token, label, 2);
                return new Vector2((float)values[0], (float)values[1]);
            }
            if (target == typeof(Vector3))
            {
                return Vector3From(Numbers(token, label, 3));
            }
            if (target == typeof(Vector4))
            {
                var values = Numbers(token, label, 4);
                return new Vector4((float)values[0], (float)values[1], (float)values[2], (float)values[3]);
            }
            if (target == typeof(Quaternion))
            {
                var values = Numbers(token, label, 3, 4);
                return values.Length == 3
                    ? Quaternion.Euler((float)values[0], (float)values[1], (float)values[2])
                    : new Quaternion((float)values[0], (float)values[1], (float)values[2], (float)values[3]);
            }
            if (target == typeof(Color))
            {
                var values = Numbers(token, label, 3, 4);
                return new Color(
                    (float)values[0], (float)values[1], (float)values[2],
                    values.Length == 4 ? (float)values[3] : 1f);
            }
            if (target == typeof(Color32))
            {
                var values = Numbers(token, label, 3, 4);
                return new Color32(
                    Byte(values[0], label), Byte(values[1], label), Byte(values[2], label),
                    values.Length == 4 ? Byte(values[3], label) : (byte)255);
            }
            if (target == typeof(Vector2Int))
            {
                var values = Numbers(token, label, 2);
                return new Vector2Int(Int(values[0], label), Int(values[1], label));
            }
            if (target == typeof(Vector3Int))
            {
                var values = Numbers(token, label, 3);
                return new Vector3Int(Int(values[0], label), Int(values[1], label), Int(values[2], label));
            }
            if (target == typeof(Rect))
            {
                var values = Numbers(token, label, 4);
                return new Rect(
                    (float)values[0], (float)values[1], (float)values[2], (float)values[3]);
            }
            if (target == typeof(Bounds))
            {
                var values = Numbers(token, label, 6);
                return new Bounds(
                    new Vector3((float)values[0], (float)values[1], (float)values[2]),
                    new Vector3((float)values[3], (float)values[4], (float)values[5]));
            }
            if (IsNumeric(target))
            {
                return ConvertNumber(token, target, label);
            }
            if (typeof(UnityEngine.Object).IsAssignableFrom(target))
            {
                throw new ArgumentException(
                    label + " is an object reference (" + target.FullName + "). Object references are not supported.");
            }
            throw new ArgumentException(
                label + " has unsupported type " + target.FullName +
                ". Supported types: primitives, string, enums, Vector2/3/4, Quaternion, Color, Color32, Vector2Int, Vector3Int, Rect and Bounds.");
        }

        private static bool IsNumeric(Type type)
        {
            return type == typeof(byte) || type == typeof(sbyte) || type == typeof(short) ||
                type == typeof(ushort) || type == typeof(int) || type == typeof(uint) ||
                type == typeof(long) || type == typeof(ulong) || type == typeof(float) ||
                type == typeof(double) || type == typeof(decimal);
        }

        private static bool IsIntegral(Type type)
        {
            return type == typeof(byte) || type == typeof(sbyte) || type == typeof(short) ||
                type == typeof(ushort) || type == typeof(int) || type == typeof(uint) ||
                type == typeof(long) || type == typeof(ulong);
        }

        private static object ConvertNumber(JToken token, Type target, string label)
        {
            double value;
            if (token.Type == JTokenType.Integer || token.Type == JTokenType.Float)
            {
                value = token.Value<double>();
            }
            else if (token.Type == JTokenType.String &&
                double.TryParse(token.Value<string>(), NumberStyles.Float, CultureInfo.InvariantCulture, out var parsed))
            {
                value = parsed;
            }
            else
            {
                throw new ArgumentException(label + " requires a number for " + target.Name + ".");
            }
            if (IsIntegral(target) && value != Math.Truncate(value))
            {
                throw new ArgumentException(label + " requires an integer value for " + target.Name + ".");
            }
            try
            {
                return Convert.ChangeType(value, target, CultureInfo.InvariantCulture);
            }
            catch (OverflowException)
            {
                throw new ArgumentException(label + " is out of range for " + target.Name + ".");
            }
        }

        private static double[] Numbers(JToken token, string label, params int[] allowedCounts)
        {
            double[] values;
            if (!TryReadNumbers(token, out values))
            {
                throw new ArgumentException(label + " requires numeric values.");
            }
            if (!allowedCounts.Contains(values.Length))
            {
                throw new ArgumentException(
                    label + " requires " + string.Join(" or ", allowedCounts) + " numbers, got " + values.Length + ".");
            }
            return values;
        }

        private static bool TryReadNumbers(JToken token, out double[] values)
        {
            values = null;
            if (token == null || token.Type == JTokenType.Null)
            {
                return false;
            }
            if (token.Type == JTokenType.Array)
            {
                var list = new List<double>();
                foreach (var item in token.Children())
                {
                    if (item.Type != JTokenType.Integer && item.Type != JTokenType.Float &&
                        item.Type != JTokenType.String)
                    {
                        return false;
                    }
                    if (!double.TryParse(item.ToString(), NumberStyles.Float, CultureInfo.InvariantCulture, out var number))
                    {
                        return false;
                    }
                    list.Add(number);
                }
                values = list.ToArray();
                return true;
            }
            if (token.Type == JTokenType.Integer || token.Type == JTokenType.Float)
            {
                values = new[] { token.Value<double>() };
                return true;
            }
            if (token.Type == JTokenType.String)
            {
                var parts = token.Value<string>().Split(new[] { ',', ' ' }, StringSplitOptions.RemoveEmptyEntries);
                var list = new List<double>();
                foreach (var part in parts)
                {
                    if (!double.TryParse(part, NumberStyles.Float, CultureInfo.InvariantCulture, out var number))
                    {
                        return false;
                    }
                    list.Add(number);
                }
                values = list.ToArray();
                return true;
            }
            return false;
        }

        private static byte Byte(double value, string label)
        {
            var number = Int(value, label);
            if (number < 0 || number > 255)
            {
                throw new ArgumentException(label + " colour channels must be between 0 and 255.");
            }
            return (byte)number;
        }

        private static int Int(double value, string label)
        {
            if (value != Math.Floor(value))
            {
                throw new ArgumentException(label + " requires integer values.");
            }
            if (value < int.MinValue || value > int.MaxValue)
            {
                throw new ArgumentException(label + " is out of range for a 32-bit integer.");
            }
            return (int)value;
        }

        private static Vector3 Vector3From(double[] values)
        {
            return new Vector3((float)values[0], (float)values[1], (float)values[2]);
        }

        private static float[] Vector(Vector3 value)
        {
            return new[] { value.x, value.y, value.z };
        }

        private static object DescribeValue(object value)
        {
            if (value == null)
            {
                return null;
            }
            if (value is Vector2 vector2)
            {
                return new[] { vector2.x, vector2.y };
            }
            if (value is Vector3 vector3)
            {
                return Vector(vector3);
            }
            if (value is Vector4 vector4)
            {
                return new[] { vector4.x, vector4.y, vector4.z, vector4.w };
            }
            if (value is Quaternion quaternion)
            {
                return new[] { quaternion.x, quaternion.y, quaternion.z, quaternion.w };
            }
            if (value is Color color)
            {
                return new[] { color.r, color.g, color.b, color.a };
            }
            if (value is Color32 color32)
            {
                return new[] { (int)color32.r, (int)color32.g, (int)color32.b, (int)color32.a };
            }
            if (value is Rect rect)
            {
                return new[] { rect.x, rect.y, rect.width, rect.height };
            }
            if (value is Bounds bounds)
            {
                return new[]
                {
                    bounds.center.x, bounds.center.y, bounds.center.z,
                    bounds.size.x, bounds.size.y, bounds.size.z
                };
            }
            if (value is Vector2Int vector2Int)
            {
                return new[] { vector2Int.x, vector2Int.y };
            }
            if (value is Vector3Int vector3Int)
            {
                return new[] { vector3Int.x, vector3Int.y, vector3Int.z };
            }
            if (value is Enum)
            {
                return value.ToString();
            }
            return value;
        }

        private static bool? GetOptionalBool(JObject args, string name)
        {
            var token = args?[name];
            if (token == null || token.Type == JTokenType.Null)
            {
                return null;
            }
            if (token.Type == JTokenType.Boolean)
            {
                return token.Value<bool>();
            }
            if (bool.TryParse(token.Value<string>(), out var parsed))
            {
                return parsed;
            }
            throw new ArgumentException(name + " must be true or false.");
        }

        private static bool GetBool(JObject args, string name, bool fallback)
        {
            var value = GetOptionalBool(args, name);
            return value ?? fallback;
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

        private static string GetString(JObject args, string name)
        {
            var token = args?[name];
            if (token == null || token.Type == JTokenType.Null)
            {
                return null;
            }
            return token.Value<string>();
        }

        private static int? GetInt(JObject args, string name)
        {
            var token = args?[name];
            if (token == null || token.Type == JTokenType.Null)
            {
                return null;
            }
            if (token.Type == JTokenType.Integer)
            {
                return token.Value<int>();
            }
            if (int.TryParse(token.Value<string>(), NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed))
            {
                return parsed;
            }
            throw new ArgumentException(name + " must be an integer.");
        }

        private static Vector3? GetVector3(JObject args, string name)
        {
            var token = args?[name];
            if (token == null || token.Type == JTokenType.Null)
            {
                return null;
            }
            return Vector3From(Numbers(token, name, 3));
        }

        private static PrimitiveType ParsePrimitive(string text)
        {
            PrimitiveType primitive;
            if (!Enum.TryParse(text, true, out primitive) ||
                !new[]
                {
                    PrimitiveType.Cube, PrimitiveType.Sphere,
                    PrimitiveType.Capsule, PrimitiveType.Cylinder,
                    PrimitiveType.Plane, PrimitiveType.Quad
                }.Contains(primitive))
            {
                throw new ArgumentException(
                    "PrimitiveType must be one of Cube, Sphere, Capsule, Cylinder, Plane or Quad, got: " + text);
            }
            return primitive;
        }

        private static void RequireGameObjectName(string name, string field)
        {
            if (string.IsNullOrWhiteSpace(name))
            {
                throw new ArgumentException(field + " must not be empty.");
            }
            if (name.IndexOf('/') >= 0 || name.IndexOf('\\') >= 0)
            {
                throw new ArgumentException(field + " must not contain '/' or '\\'.");
            }
        }

        private static string RequireAssetPath(JObject args, string name, string extension = null)
        {
            var value = RequireString(args, name);
            if (!value.StartsWith("Assets/", StringComparison.Ordinal))
            {
                throw new ArgumentException(name + " must be a project-relative path under Assets/, for example Assets/Folder/Name.");
            }
            if (value.Contains("\\") || value.Split('/').Any(segment => segment.Length == 0 || segment == "." || segment == ".."))
            {
                throw new ArgumentException(name + " must not contain '\\', empty, '.' or '..' segments.");
            }
            if (!string.IsNullOrEmpty(extension) && !value.EndsWith(extension, StringComparison.OrdinalIgnoreCase))
            {
                throw new ArgumentException(name + " must end with " + extension + ".");
            }
            return value;
        }

        private static string ParentFolder(string assetPath)
        {
            var index = assetPath.LastIndexOf('/');
            return index <= 0 ? "Assets" : assetPath.Substring(0, index);
        }

        private static void EnsureAssetFolder(string folder)
        {
            if (string.IsNullOrEmpty(folder) || folder == "Assets" || AssetDatabase.IsValidFolder(folder))
            {
                return;
            }
            var index = folder.LastIndexOf('/');
            var parent = index <= 0 ? "Assets" : folder.Substring(0, index);
            EnsureAssetFolder(parent);
            var created = AssetDatabase.CreateFolder(parent, folder.Substring(index + 1));
            if (string.IsNullOrEmpty(created))
            {
                throw new InvalidOperationException("Could not create asset folder: " + folder);
            }
        }

        private static string ToAbsoluteAssetPath(string assetPath)
        {
            var projectPath = Path.GetDirectoryName(Application.dataPath);
            return Path.GetFullPath(Path.Combine(projectPath, assetPath.Replace('/', Path.DirectorySeparatorChar)));
        }

        private static string SceneName(Scene scene)
        {
            return string.IsNullOrEmpty(scene.path) ? scene.name : scene.path;
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

        private static object DescribeGameObject(GameObject gameObject)
        {
            var transform = gameObject.transform;
            return new
            {
                objectId = gameObject.GetInstanceID(),
                name = gameObject.name,
                path = GetPath(transform),
                scene = gameObject.scene.path,
                active = gameObject.activeSelf,
                prefabInstance = PrefabUtility.IsPartOfPrefabInstance(gameObject),
                position = Vector(transform.position),
                rotation = Vector(transform.eulerAngles),
                scale = Vector(transform.localScale),
                parentId = transform.parent == null ? (int?)null : transform.parent.gameObject.GetInstanceID(),
                components = ComponentNames(gameObject)
            };
        }

        private static object Change(string field, object before, object after)
        {
            return new { field, before, after };
        }

        private static void MarkDirty(GameObject gameObject)
        {
            var scene = gameObject.scene;
            if (scene.IsValid() && scene.isLoaded && !EditorSceneManager.IsPreviewScene(scene))
            {
                EditorSceneManager.MarkSceneDirty(scene);
            }
        }

        private static IEnumerable<Transform> WalkScenes()
        {
            var seen = new HashSet<int>();
            for (var i = 0; i < SceneManager.sceneCount; i++)
            {
                var scene = SceneManager.GetSceneAt(i);
                if (!scene.isLoaded)
                {
                    continue;
                }
                foreach (var root in scene.GetRootGameObjects())
                {
                    if (!seen.Add(root.GetInstanceID()))
                    {
                        continue;
                    }
                    foreach (var transform in Walk(root.transform))
                    {
                        yield return transform;
                    }
                }
            }
            var stage = PrefabStageUtility.GetCurrentPrefabStage();
            if (stage != null && stage.prefabContentsRoot != null &&
                seen.Add(stage.prefabContentsRoot.GetInstanceID()))
            {
                foreach (var transform in Walk(stage.prefabContentsRoot.transform))
                {
                    yield return transform;
                }
            }
        }

        private static IEnumerable<Transform> Walk(Transform root)
        {
            var pending = new Stack<Transform>();
            pending.Push(root);
            while (pending.Count > 0)
            {
                var transform = pending.Pop();
                yield return transform;
                for (var i = transform.childCount - 1; i >= 0; i--)
                {
                    pending.Push(transform.GetChild(i));
                }
            }
        }
    }
}
