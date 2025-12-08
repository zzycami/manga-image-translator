# API Key 泄漏修复说明

## ⚠️ 发现的问题

DeepSeek API Key (`sk-fa51105a356949fa91dc262b7eea2aa6`) 在以下文件中泄漏：

### 1. 脚本文件（需要立即修复）

1. **`start_translation_service_simple.sh`** (第13行)
2. **`test_image_simple.sh`** (第24行)
3. **`fc_deploy_simple.sh`** (第16行)
4. **`test_deepseek_api.py`** (第12行，作为默认值)

### 2. 文档文件（docs目录下，约20+个文件）

这些是文档文件，但也会被提交到仓库，需要清理。

## 🔧 修复方案

### 方案1：使用环境变量（推荐）

将所有硬编码的 API Key 替换为从环境变量读取。

### 方案2：使用配置文件（.gitignore）

创建 `.env` 文件存储 API Key，并确保 `.gitignore` 包含它。

## ✅ 立即行动

1. **在 DeepSeek 平台撤销当前 API Key**
2. **生成新的 API Key**
3. **修复代码文件**
4. **清理文档文件**
5. **更新 .gitignore**

## 📝 修复后的文件示例

### start_translation_service_simple.sh
```bash
# 设置 DeepSeek API Key（从环境变量读取）
if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "错误: 请设置 DEEPSEEK_API_KEY 环境变量"
    exit 1
fi
export DEEPSEEK_API_KEY
```

### test_deepseek_api.py
```python
api_key = os.getenv('DEEPSEEK_API_KEY')
if not api_key:
    print("❌ 错误: 请设置 DEEPSEEK_API_KEY 环境变量")
    sys.exit(1)
```

