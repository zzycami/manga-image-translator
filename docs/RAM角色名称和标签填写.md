# RAM角色名称和标签填写

## 角色名称（必填）

### 推荐填写

**角色名称：** `manga-translator-role`

**或使用：**
- `manga-translator-fc-role`
- `fc-manga-translator-role`
- `manga-translator-function-role`

### 命名规则

- 只能包含字母、数字、短划线（-）和下划线（_）
- 长度：1-64个字符
- 不能以数字开头
- 建议使用有意义的名称，方便后续管理

### 示例

✅ **推荐：**
- `manga-translator-role`
- `manga-translator-fc-role`
- `fc-manga-translator-role`

❌ **不推荐：**
- `role`（太简单，不明确）
- `123role`（以数字开头）
- `manga translator role`（包含空格）

## 标签（可选）

### 是否必须填写？

**标签是可选的**，可以不填写。

### 如果填写，建议：

**标签键（Key）：**
- `Project` 或 `项目`
- `Service` 或 `服务`
- `Environment` 或 `环境`

**标签值（Value）：**
- `manga-translator` 或 `漫画翻译`
- `production` 或 `生产环境`
- `dev` 或 `开发环境`

### 示例标签

| 标签键 | 标签值 | 说明 |
|--------|--------|------|
| `Project` | `manga-translator` | 项目名称 |
| `Service` | `function-compute` | 服务类型 |
| `Environment` | `production` | 环境类型 |

### 建议

**初期测试：**
- 标签可以不填写，保持空白

**生产环境：**
- 建议填写标签，方便后续管理和查找
- 至少填写一个标签：`Project: manga-translator`

## 完整填写示例

### 方案1：最小配置（推荐初期测试）

**角色名称：** `manga-translator-role`
**标签：** 不填写（留空）

### 方案2：完整配置（推荐生产环境）

**角色名称：** `manga-translator-role`

**标签：**
- 标签键：`Project`
- 标签值：`manga-translator`

或

- 标签键：`Service`
- 标签值：`function-compute`

## 总结

### 必须填写

✅ **角色名称：** `manga-translator-role`

### 可选填写

⭕ **标签：** 可以不填写，或填写：
- 标签键：`Project`
- 标签值：`manga-translator`

## 下一步

填写完成后：
1. 继续配置权限策略（选择 `AliyunLogFullAccess`）
2. 完成角色创建
3. 回到FC函数配置页面，选择刚创建的角色

