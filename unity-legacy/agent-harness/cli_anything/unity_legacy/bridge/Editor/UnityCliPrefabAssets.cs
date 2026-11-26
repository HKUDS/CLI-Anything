using System;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
#if !UNITY_2021_2_OR_NEWER
using UnityEditor.Experimental.SceneManagement;
#endif
using UnityEngine;
using UnityEngine.UI;

namespace CliAnything.Unity
{
    internal static partial class UnityCliEditing
    {
        private static GameObject LoadPrefabAsset(JObject args)
        {
            var path = RequireAssetPath(args, "AssetPath", ".prefab");
            return AssetDatabase.LoadAssetAtPath<GameObject>(path)
                ?? throw new InvalidOperationException("Prefab asset not found: " + path);
        }

        private static object InspectPrefabUi(JObject args)
        {
            var prefab = LoadPrefabAsset(args);
            var nodes = prefab.GetComponentsInChildren<RectTransform>(true).Select(node =>
            {
                var image = node.GetComponent<Image>();
                var text = node.GetComponent<Text>();
                var sprite = image == null ? null : image.sprite;
                return new
                {
                    path = AnimationUtility.CalculateTransformPath(node, prefab.transform),
                    active = node.gameObject.activeSelf,
                    position = new[] { node.anchoredPosition.x, node.anchoredPosition.y },
                    size = new[] { node.sizeDelta.x, node.sizeDelta.y },
                    anchorMin = new[] { node.anchorMin.x, node.anchorMin.y },
                    anchorMax = new[] { node.anchorMax.x, node.anchorMax.y },
                    pivot = new[] { node.pivot.x, node.pivot.y },
                    text = text == null ? null : text.text,
                    sprite = sprite == null ? null : new
                    {
                        path = AssetDatabase.GetAssetPath(sprite),
                        name = sprite.name,
                        rect = new[] { sprite.rect.x, sprite.rect.y, sprite.rect.width, sprite.rect.height }
                    },
                    components = node.GetComponents<Component>()
                        .Where(component => component != null && !(component is RectTransform) && !(component is CanvasRenderer))
                        .Select(component => new
                        {
                            type = component.GetType().FullName,
                            enabled = !(component is Behaviour behaviour) || behaviour.enabled,
                            data = EditorJsonUtility.ToJson(component)
                        }).ToArray()
                };
            }).ToArray();
            if (nodes.Length == 0)
                throw new ArgumentException("Prefab does not contain any RectTransform.");
            return Ok(new { nodes });
        }

        private static object EditPrefabAsset(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("editing a Prefab asset");
            var source = LoadPrefabAsset(args);
            var rootComponent = args.Value<string>("RequiredRootComponent");
            if (rootComponent != null && source.GetComponent(ResolveComponentType(rootComponent)) == null)
                throw new ArgumentException("Source Prefab root requires " + rootComponent + ".");
            var sourcePath = AssetDatabase.GetAssetPath(source);
            var path = RequireAssetPath(args, "OutputPath", ".prefab");
            var file = CheckedLocalFile(ToAbsoluteAssetPath(path), Application.dataPath);
            var expectedHash = args.Value<string>("ExpectedSha256");
            var patch = !string.IsNullOrEmpty(expectedHash);
            var stage = PrefabStageUtility.GetCurrentPrefabStage();
            if (stage != null && PrefabStagePath(stage).Equals(path, StringComparison.OrdinalIgnoreCase))
                throw new IOException("Close the destination Prefab stage before editing it.");
            if (string.Equals(sourcePath, path, StringComparison.OrdinalIgnoreCase))
                throw new ArgumentException("OutputPath must differ from the source Prefab.");
            if (!patch && (File.Exists(file) || File.Exists(file + ".meta") || Directory.Exists(file) ||
                AssetDatabase.LoadMainAssetAtPath(path) != null))
                throw new IOException("Asset or .meta already exists: " + path);

            var before = patch ? File.ReadAllBytes(file) : null;
            if (patch && !string.Equals(HashContent(before), expectedHash, StringComparison.OrdinalIgnoreCase))
                throw new IOException("Destination SHA-256 differs from ExpectedSha256.");
            var copied = false;
            var saved = false;
            try
            {
                if (!patch)
                {
                    EnsureAssetFolder(ParentFolder(path));
                    if (!AssetDatabase.CopyAsset(sourcePath, path))
                        throw new IOException("Unity could not copy the Prefab to " + path);
                    copied = true;
                }
                var root = PrefabUtility.LoadPrefabContents(path);
                try
                {
                    ApplyPrefabEdits(root.transform, args["Edits"]);
                    if (patch && HashContent(File.ReadAllBytes(file)) != HashContent(before))
                        throw new IOException("The Prefab changed while preparing the edits.");
                    saved = true;
                    if (PrefabUtility.SaveAsPrefabAsset(root, path) == null)
                        throw new IOException("Unity could not save the Prefab: " + path);
                }
                finally { PrefabUtility.UnloadPrefabContents(root); }
                var asset = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                if (asset == null)
                    throw new IOException("Cannot read back saved Prefab: " + path);
                VerifyPrefabEdits(asset.transform, args["Edits"]);
                var missingScripts = asset.GetComponentsInChildren<Transform>(true)
                    .Where(node => GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(node.gameObject) != 0)
                    .Select(node => AnimationUtility.CalculateTransformPath(node, asset.transform)).ToArray();
                return Ok(new { assetPath = path, sha256 = HashContent(File.ReadAllBytes(file)), missingScripts });
            }
            catch
            {
                if (copied && !AssetDatabase.DeleteAsset(path))
                {
                    File.Delete(file);
                    File.Delete(file + ".meta");
                }
                else if (patch && saved)
                {
                    File.WriteAllBytes(file, before);
                    AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
                }
                throw;
            }
        }

        private static object ImportSprite(JObject args)
        {
            RequireIdleEditor();
            RequireEditMode("importing a Sprite");
            var path = RequireAssetPath(args, "AssetPath", ".png");
            var file = CheckedLocalFile(ToAbsoluteAssetPath(path), Application.dataPath);
            if (!File.Exists(file))
                throw new FileNotFoundException("Sprite PNG not found", file);
            var pixels = args.Value<float?>("PixelsPerUnit") ?? 100f;
            var border = args["Border"] == null ? Vector4.zero :
                (Vector4)ConvertPropertyValue(args["Border"], typeof(Vector4), "Border");
            if (pixels <= 0 || float.IsNaN(pixels) || float.IsInfinity(pixels) ||
                border.x < 0 || border.y < 0 || border.z < 0 || border.w < 0)
                throw new ArgumentException("Sprite PixelsPerUnit must be positive and Border must be nonnegative.");
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
            var importer = AssetImporter.GetAtPath(path) as TextureImporter
                ?? throw new IOException("Texture importer unavailable for " + path);
            importer.textureType = TextureImporterType.Sprite;
            importer.spriteImportMode = SpriteImportMode.Single;
            importer.spritePixelsPerUnit = pixels;
            importer.spriteBorder = border;
            importer.alphaIsTransparency = true;
            importer.mipmapEnabled = false;
            importer.npotScale = TextureImporterNPOTScale.None;
            importer.textureCompression = TextureImporterCompression.Uncompressed;
            var settings = new TextureImporterSettings();
            importer.ReadTextureSettings(settings);
            settings.spriteMeshType = SpriteMeshType.FullRect;
            importer.SetTextureSettings(settings);
            importer.SaveAndReimport();
            var sprite = AssetDatabase.LoadAssetAtPath<Sprite>(path)
                ?? throw new IOException("Unity did not import a Sprite from " + path);
            return Ok(new { assetPath = path, sprite.name });
        }

        private static void ApplyPrefabEdits(Transform root, JToken edits)
        {
            if (edits == null) return;
            if (!(edits is JArray items)) throw new ArgumentException("Edits must be an array.");
            foreach (var item in items.Cast<JObject>())
            {
                var path = item.Value<string>("Node") ?? throw new ArgumentException("Provide Node, empty for the root.");
                var node = GetEditablePrefabNode(root, path, item["Create"] as JObject);
                if (item["SiblingIndex"] != null)
                {
                    if (node == root || PrefabUtility.IsPartOfPrefabInstance(node))
                        throw new ArgumentException("Cannot reorder the root or a nested Prefab node: " + path);
                    node.SetSiblingIndex(item.Value<int>("SiblingIndex"));
                }
                if (item["Active"] != null)
                {
                    node.gameObject.SetActive(item.Value<bool>("Active"));
                    PrefabUtility.RecordPrefabInstancePropertyModifications(node.gameObject);
                }
                foreach (var value in (item["Properties"] as JArray ?? new JArray()).Cast<JObject>())
                    ProcessPrefabProperty(node, value, false);
            }
        }

        private static void VerifyPrefabEdits(Transform root, JToken edits)
        {
            if (!(edits is JArray items)) return;
            foreach (var group in items.Cast<JObject>().GroupBy(item => item.Value<string>("Node")))
            {
                var node = FindPrefabNode(root, group.Key);
                var activity = group.LastOrDefault(item => item["Active"] != null);
                if (activity != null && node.gameObject.activeSelf != activity.Value<bool>("Active"))
                    throw new IOException("Saved activation differs: " + group.Key);
                foreach (var properties in group.SelectMany(item => item["Properties"] as JArray ?? new JArray())
                    .Cast<JObject>().GroupBy(item => (item.Value<string>("Component"), item.Value<string>("Member"), item.Value<bool>("Serialized"))))
                    ProcessPrefabProperty(node, properties.Last(), true);
            }
        }

        private static Transform GetEditablePrefabNode(Transform root, string path, JObject create)
        {
            if (create == null) return FindPrefabNode(root, path);
            var split = path.LastIndexOf('/');
            var name = path.Substring(split + 1);
            RequireGameObjectName(name, "Node");
            var parent = FindPrefabNode(root, split < 0 ? "" : path.Substring(0, split));
            if (parent.Cast<Transform>().Any(child => child.name == name))
                throw new ArgumentException("Prefab child already exists: " + path);

            GameObject childObject;
            if (create["SourceAsset"] != null)
            {
                var sourcePath = RequireAssetPath(create, "SourceAsset", ".prefab");
                var source = AssetDatabase.LoadAssetAtPath<GameObject>(sourcePath)
                    ?? throw new ArgumentException("Clone source Prefab not found: " + sourcePath);
                childObject = UnityEngine.Object.Instantiate(
                    FindPrefabNode(source.transform, create.Value<string>("SourceNode") ?? "").gameObject, parent, false);
                childObject.name = name;
            }
            else
            {
                var types = (create["Components"] as JArray ?? new JArray()).Values<string>()
                    .Select(ResolveComponentType).ToArray();
                childObject = new GameObject(name, types) { layer = parent.gameObject.layer };
                childObject.transform.SetParent(parent, false);
            }
            return childObject.transform;
        }

        private static Transform FindPrefabNode(Transform root, string path)
        {
            var node = root;
            if (path == "") return node;
            foreach (var segment in path.Split('/'))
            {
                var matches = node.Cast<Transform>().Where(child => child.name == segment).ToArray();
                if (matches.Length != 1)
                    throw new ArgumentException("Prefab path must identify exactly one child: " + path);
                node = matches[0];
            }
            return node;
        }

        private static void ProcessPrefabProperty(Transform node, JObject edit, bool verify)
        {
            var typeName = RequireString(edit, "Component");
            var memberName = RequireString(edit, "Member");
            var value = edit["Value"] ?? throw new ArgumentException("Provide Value for " + memberName);
            var matches = node.GetComponents<Component>().Where(component => component != null &&
                (component.GetType().Name == typeName || component.GetType().FullName == typeName)).ToArray();
            if (matches.Length != 1)
                throw new ArgumentException("Prefab component must be unique: " + node.name + "/" + typeName);
            var component = matches[0];
            if (GetBool(edit, "Serialized", false))
            {
                SetPrefabSerializedProperty(component, memberName, value, verify);
            }
            else
            {
                var member = FindWritableMember(component.GetType(), memberName);
                var memberType = member is PropertyInfo property ? property.PropertyType : ((FieldInfo)member).FieldType;
                var expected = typeof(UnityEngine.Object).IsAssignableFrom(memberType)
                    ? ResolvePrefabAssetReference(value, memberType) : ConvertPropertyValue(value, memberType, memberName);
                if (verify)
                {
                    var actual = GetMemberValue(member, component);
                    if (!Equals(actual, expected))
                        throw new IOException("Saved property differs: " + node.name + "/" + memberName);
                }
                else SetMemberValue(member, component, expected);
            }
            if (!verify) PrefabUtility.RecordPrefabInstancePropertyModifications(component);
        }

        private static UnityEngine.Object ResolvePrefabAssetReference(JToken value, Type type)
        {
            if (value.Type == JTokenType.Null) return null;
            if (!(value is JObject reference))
                throw new ArgumentException("Asset references need an AssetPath and optional Name.");
            var path = RequireAssetPath(reference, "AssetPath");
            var name = reference.Value<string>("Name");
            var matches = AssetDatabase.LoadAllAssetsAtPath(path)
                .Where(asset => asset != null && type.IsInstanceOfType(asset) && (name == null || asset.name == name)).ToArray();
            if (matches.Length != 1)
                throw new ArgumentException("Asset reference must match exactly one " + type.Name + ": " + path);
            return matches[0];
        }

        private static void SetPrefabSerializedProperty(Component component, string name, JToken value, bool verify)
        {
            var serialized = new SerializedObject(component);
            var property = serialized.FindProperty(name);
            if (property == null || !property.editable || name == "m_Script")
                throw new ArgumentException("Serialized property is not writable: " + name);
            var text = value.Type == JTokenType.String ? value.Value<string>() : value.ToString(Newtonsoft.Json.Formatting.None);
            switch (property.propertyType)
            {
                case SerializedPropertyType.Boolean:
                    var boolean = bool.Parse(text);
                    if (verify && property.boolValue != boolean) throw new IOException("Saved property differs: " + name);
                    if (!verify) property.boolValue = boolean;
                    break;
                case SerializedPropertyType.Integer:
                case SerializedPropertyType.Enum:
                    var integer = int.Parse(text, CultureInfo.InvariantCulture);
                    if (verify && property.intValue != integer) throw new IOException("Saved property differs: " + name);
                    if (!verify) property.intValue = integer;
                    break;
                case SerializedPropertyType.Float:
                    var number = float.Parse(text, CultureInfo.InvariantCulture);
                    if (float.IsNaN(number) || float.IsInfinity(number)) throw new ArgumentException("Expected finite value: " + name);
                    if (verify && !Mathf.Approximately(property.floatValue, number)) throw new IOException("Saved property differs: " + name);
                    if (!verify) property.floatValue = number;
                    break;
                case SerializedPropertyType.String:
                    if (verify && property.stringValue != text) throw new IOException("Saved property differs: " + name);
                    if (!verify) property.stringValue = text;
                    break;
                case SerializedPropertyType.ObjectReference when value.Type == JTokenType.Null:
                    if (verify && property.objectReferenceValue != null) throw new IOException("Saved reference differs: " + name);
                    if (!verify) property.objectReferenceValue = null;
                    break;
                default:
                    throw new ArgumentException("Unsupported serialized property type: " + name);
            }
            if (!verify) serialized.ApplyModifiedPropertiesWithoutUndo();
        }

        private static string CheckedLocalFile(string path, string root)
        {
            root = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar);
            if (!path.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                throw new ArgumentException("Path is outside " + root + ": " + path);
            for (var current = path; !string.Equals(current, root, StringComparison.OrdinalIgnoreCase);
                current = Path.GetDirectoryName(current))
                if ((File.Exists(current) || Directory.Exists(current)) &&
                    (File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                    throw new IOException("Path contains a symbolic link or junction: " + current);
            return path;
        }

        private static string HashContent(byte[] content)
        {
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(content)).Replace("-", "").ToLowerInvariant();
        }
    }
}
