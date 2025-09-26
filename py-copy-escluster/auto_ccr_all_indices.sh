#!/bin/bash

# Elasticsearch 自动复制所有索引脚本（修复版）
SOURCE_CLUSTER="http://10.0.2.35:9200"
TARGET_CLUSTER="http://10.10.0.8:9200"
REMOTE_CLUSTER_NAME="q1-es7"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 修复的获取索引函数
get_all_indices() {
    log_info "获取源集群所有索引列表..."
    indices=$(curl -s "$SOURCE_CLUSTER/_cat/indices?h=index" | grep -v '^\.' | grep -v '^ilm-history' | grep -v '^watcher' | sort)
    
    # 修复：检查indices是否为空
    if [ -z "$indices" ]; then
        log_warn "未找到任何非系统索引"
        return 1
    fi
    
    echo "$indices"
    local count=$(echo "$indices" | wc -l)
    log_info "找到 $count 个索引"
}

# 修复的索引存在检查
target_index_exists() {
    local index_name=$1
    response=$(curl -s -o /dev/null -w "%{http_code}" "$TARGET_CLUSTER/$index_name")
    if [ "$response" -eq 200 ]; then
        return 0
    else
        return 1
    fi
}

# 修复的创建跟随索引函数
create_follower_index() {
    local index_name=$1
    
    # 修复：验证索引名称有效性
    if [[ -z "$index_name" || "$index_name" =~ ^\[.*\]$ ]]; then
        log_warn "跳过无效索引名称: $index_name"
        return 0
    fi
    
    if target_index_exists "$index_name"; then
        log_warn "索引 $index_name 已存在于目标集群，跳过"
        return 0
    fi
    
    log_info "为索引 $index_name 创建跟随索引..."
    
    # 添加认证信息（根据需要）
    response=$(curl -s -w "%{http_code}" -X PUT "$TARGET_CLUSTER/$index_name/_ccr/follow" \
        -H "Content-Type: application/json" \
        -d '{
            "remote_cluster": "'$REMOTE_CLUSTER_NAME'",
            "leader_index": "'$index_name'",
            "read_poll_timeout": "1m"
        }')
    
    http_code=${response: -3}
    if [ "$http_code" -eq 200 ]; then
        log_info "索引 $index_name 跟随创建成功"
        return 0
    else
        log_error "索引 $index_name 跟随创建失败，HTTP状态码: $http码"
        echo "响应内容: ${response%???}"
        return 1
    fi
}

# 修复的批量处理函数
batch_create_followers() {
    local indices=$1
    local success_count=0
    local fail_count=0
    
    # 修复：正确处理行数统计
    local total_count=$(echo "$indices" | wc -l)
    local current=0
    
    log_info "开始批量创建 $total_count 个跟随索引..."
    
    while IFS= read -r index; do
        current=$((current + 1))
        
        # 修复：验证索引名称
        if [[ -n "$index" && ! "$index" =~ ^\[.*\]$ ]]; then
            log_info "处理索引 [$current/$total_count]: $index"
            
            if create_follower_index "$index"; then
                success_count=$((success_count + 1))
            else
                fail_count=$((fail_count + 1))
            fi
            
            sleep 1
        else
            log_warn "跳过无效索引行: $index"
        fi
    done <<< "$indices"
    
    log_info "批量创建完成：成功 $success_count 个，失败 $fail_count 个"
}

main() {
    log_info "开始自动复制所有索引..."
    
    # 检查连通性
    if ! curl -s -f "$SOURCE_CLUSTER" > /dev/null; then
        log_error "无法连接到源集群 $SOURCE_CLUSTER"
        exit 1
    fi
    
    if ! curl -s -f "$TARGET_CLUSTER" > /dev/null; then
        log_error "无法连接到目标集群 $TARGET_CLUSTER"
        exit 1
    fi
    
    indices=$(get_all_indices)
    if [ $? -ne 0 ]; then
        log_error "获取索引列表失败"
        exit 1
    fi
    
    batch_create_followers "$indices"
    
    log_info "所有操作完成！"
}

main "$@"