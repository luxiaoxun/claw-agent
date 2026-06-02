#!/bin/bash
# =============================================================================
# Soma Docker Manage Script - 管理容器生命周期
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Version
VERSION="1.0.0"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi

    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE="docker compose"
    elif command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE="docker-compose"
    else
        log_error "Docker Compose 未安装"
        exit 1
    fi
}

check_images() {
    if ! docker images | grep -q "soma-backend"; then
        log_error "镜像 soma-backend:${VERSION} 不存在，请先运行 build.sh"
        exit 1
    fi
    if ! docker images | grep -q "soma-frontend"; then
        log_error "镜像 soma-frontend:${VERSION} 不存在，请先运行 build.sh"
        exit 1
    fi
}

setup_env() {
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        log_info "创建环境配置文件..."
        cp "$SCRIPT_DIR/.env.docker" "$PROJECT_ROOT/.env"
        log_warn ".env 文件已创建，请编辑并填入实际配置值"
    fi
}

create_dirs() {
    mkdir -p "$PROJECT_ROOT/workspace/uploads"
    mkdir -p "$PROJECT_ROOT/workspace/outputs"
    mkdir -p "$PROJECT_ROOT/logs"
}

# Sync workspace content to docker volume directory
sync_workspace() {
    local docker_workspace_dir="/home/work/soma/docker/workspace"
    local docker_logs_dir="/home/work/soma/docker/logs"

    # Create docker workspace directory if not exists
    mkdir -p "$docker_workspace_dir"

    # Copy all workspace content to docker workspace directory
    if [ -d "$PROJECT_ROOT/workspace" ] && [ "$(ls -A $PROJECT_ROOT/workspace 2>/dev/null)" ]; then
        log_info "同步 workspace 内容到 $docker_workspace_dir ..."
        cp -r "$PROJECT_ROOT/workspace/"* "$docker_workspace_dir/"
    fi

    # Create logs directory
    mkdir -p "$docker_logs_dir"
}

# Start services
start() {
    log_info "启动 Soma 服务..."
    sync_workspace
    cd "$SCRIPT_DIR"
    $DOCKER_COMPOSE --env-file "$PROJECT_ROOT/.env" up -d
    log_info "服务已启动"
}

# Stop services
stop() {
    log_info "停止 Soma 服务..."
    cd "$SCRIPT_DIR"
    $DOCKER_COMPOSE --env-file "$PROJECT_ROOT/.env" down
    log_info "服务已停止"
}

# Restart services
restart() {
    log_info "重启 Soma 服务..."
    cd "$SCRIPT_DIR"
    $DOCKER_COMPOSE restart
    log_info "服务已重启"
}

# Show status
status() {
    cd "$SCRIPT_DIR"
    echo ""
    echo "=== 容器状态 ==="
    $DOCKER_COMPOSE ps
    echo ""
    echo "=== 镜像状态 ==="
    docker images | grep -E "soma-|REPOSITORY"
    echo ""
}

# Show logs
logs() {
    cd "$SCRIPT_DIR"
    if [ -z "$1" ]; then
        $DOCKER_COMPOSE logs -f
    else
        $DOCKER_COMPOSE logs -f "$1"
    fi
}

# Print usage
usage() {
    echo "Soma Docker 管理脚本"
    echo ""
    echo "用法: $0 <命令>"
    echo ""
    echo "命令:"
    echo "  start     启动服务"
    echo "  stop      停止服务"
    echo "  restart   重启服务"
    echo "  status    查看状态"
    echo "  logs      查看日志"
    echo "  help      显示帮助信息"
    echo ""
}

# Main
case "${1:-help}" in
    start)
        check_docker
        check_images
        setup_env
        create_dirs
        start
        ;;
    stop)
        check_docker
        stop
        ;;
    restart)
        check_docker
        check_images
        restart
        ;;
    status)
        check_docker
        status
        ;;
    logs)
        check_docker
        logs "$2"
        ;;
    help|*)
        usage
        ;;
esac