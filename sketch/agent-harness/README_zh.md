# sketch-harness — AI Agent 使用说明

**一句话**：通过 JSON 设计描述文件生成可在 Sketch / Lunacy 中打开的 `.sketch` 文件。

## 安装

```bash
cd sketch-harness
npm install
```

## 核心命令

### build — 从 JSON 生成 .sketch 文件

```bash
node src/cli.js build --input <spec.json> --output <output.sketch> [--tokens <tokens.json>]
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--input, -i` | 是 | JSON 设计描述文件路径 |
| `--output, -o` | 是 | 输出 .sketch 文件路径 |
| `--tokens, -t` | 否 | 自定义 Token 文件，覆盖 spec 中的 tokens 字段 |

### list-styles — 列出可用的预定义样式

```bash
node src/cli.js list-styles [--tokens <tokens.json>]
```

## JSON Spec 格式

```json
{
  "tokens": "./tokens/default.json",
  "pages": [
    {
      "name": "页面名",
      "artboards": [
        {
          "name": "画板名",
          "width": 375,
          "height": 812,
          "backgroundColor": "#FFFFFF",
          "layout": { "type": "vertical-stack", "paddingTop": 80, "paddingHorizontal": 24, "gap": 16 },
          "layers": [
            { "type": "text", "name": "title", "value": "标题", "style": "$heading1" },
            { "type": "rectangle", "name": "btn", "width": "fill", "height": 48, "style": "$primaryButton",
              "label": { "value": "按钮", "style": "$buttonText" } },
            { "type": "group", "name": "row", "layout": { "type": "horizontal-stack", "gap": 12 },
              "children": [ ... ] },
            { "type": "spacer", "height": 24 }
          ]
        }
      ]
    }
  ]
}
```

### 图层类型

| type | 说明 | 特有字段 |
|------|------|---------|
| `text` | 文字 | `value`, `style` (fontSize, color, textAlign...) |
| `rectangle` | 矩形 | `style` (backgroundColor, cornerRadius...), `label` |
| `oval` | 椭圆/圆 | 同 rectangle |
| `group` | 分组容器 | `children`, `layout` |
| `line` | 直线 | `color`, `thickness` |
| `spacer` | 占位间距 | `height` |

### 布局模式

- **vertical-stack**: 子元素从上到下排列。支持 `gap`, `paddingTop/Bottom/Horizontal`, `alignItems` (left/center/right)
- **horizontal-stack**: 子元素从左到右排列。支持 `gap`, `justifyContent` (start/center/end/space-between), `alignItems` (top/center/bottom)
- **absolute**: 子元素手动 x/y 定位

### 尺寸

- `width: "fill"` — 填满父容器可用宽度
- 文本未指定尺寸时自动根据字号估算

## Token 引用语法

在 `style` 字段中用 `$名称` 引用 tokens 中的预定义值：

- `"style": "$heading1"` — 引用 `tokens.styles.$heading1` 整个样式对象
- `"color": "$primary"` — 引用 `tokens.colors.primary` 颜色值
- `"cornerRadius": "$lg"` — 引用 `tokens.radius.lg` 数值

## 常见用法示例

### 1. 生成移动端登录页

```bash
node src/cli.js build -i examples/login-page.json -o login.sketch
```

### 2. 生成 PC 端数据看板

```bash
node src/cli.js build -i examples/dashboard.json -o dashboard.sketch
```

### 3. 使用自定义 Token 生成

```bash
node src/cli.js build -i my-design.json -o out.sketch --tokens my-brand-tokens.json
```

### 4. 查看所有可用样式

```bash
node src/cli.js list-styles
```

### 5. AI Agent 工作流

1. 根据需求编写 JSON spec 文件
2. 运行 `node src/cli.js build -i spec.json -o design.sketch`
3. 检查输出文件是否生成（验证 ZIP 完整性）
4. 在 Sketch 或 Lunacy 中打开查看效果
