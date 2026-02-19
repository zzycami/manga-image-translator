# Result 文件夹清理指南

## 问题背景

由于翻译服务会在 `result` 文件夹下保存缓存文件（verbose 模式下会保存更多中间文件），长时间运行会导致磁盘空间不足。建议定期清理这些缓存文件。

## 清理方式

### 方式1：通过 API 接口清理（推荐）

**优点：**
- 安全可靠，通过服务内部清理，不会导致容器路径问题
- 有日志记录
- 可以远程调用

**使用方法：**

```bash
# 直接调用 API
curl -X DELETE http://localhost:8000/results/clear

# 或使用提供的脚本
./cleanup_result_via_api.sh
```

**API 返回示例：**
```json
{
  "message": "Deleted 150 result directories",
  "deleted_count": 150
}
```

### 方式2：使用清理脚本

**快速清理（删除所有文件夹）：**
```bash
./cleanup_result.sh
```

**定时清理（推荐用于 cron）：**
```bash
./cleanup_result_cron.sh
```

### 方式3：设置定时任务（推荐）

使用 cron 每天晚上自动清理：

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每天凌晨 2 点执行，通过 API 清理）
0 2 * * * /path/to/manga-image-translator/cleanup_result_via_api.sh >> /path/to/manga-image-translator/cleanup_result.log 2>&1

# 或者每天凌晨 3 点执行，清理超过 1 天的文件
0 3 * * * /path/to/manga-image-translator/cleanup_result_cron.sh >> /path/to/manga-image-translator/cleanup_result.log 2>&1
```

**如果服务运行在 Docker 容器中：**

```bash
# 方法1：在宿主机上通过 API 清理（推荐）
0 2 * * * curl -X DELETE http://localhost:8000/results/clear >> /path/to/cleanup_result.log 2>&1

# 方法2：在容器内执行（需要在容器内安装 cron）
0 2 * * * docker exec manga_image_translator_gpu python -c "import requests; requests.delete('http://localhost:8000/results/clear')"
```

## 改进说明

### API 接口改进

`/results/clear` 接口已经改进：
- ✅ **删除所有文件夹**（不再只删除包含 `final.png` 的）
- ✅ 包括 verbose 模式下的所有文件夹
- ✅ 更安全的错误处理
- ✅ 详细的日志记录

### 注意事项

1. **手动删除风险**：直接在宿主机删除 `result` 文件夹内容可能导致容器内路径不一致，建议使用 API 接口
2. **清理时机**：建议在低峰期清理（如凌晨）
3. **保留策略**：如果需要保留最近的文件，可以修改 `cleanup_result_cron.sh` 中的 `KEEP_DAYS` 变量

## 监控磁盘空间

定期检查磁盘使用情况：

```bash
# 查看 result 文件夹大小
du -sh /path/to/manga-image-translator/result

# 查看每个子文件夹大小
du -sh /path/to/manga-image-translator/result/* | sort -h

# 查看磁盘总体使用情况
df -h
```

## 清理日志

所有脚本都会生成日志文件 `cleanup_result.log`，记录清理操作的详细信息。


