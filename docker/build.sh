#!/bin/bash
# =============================================================================
# Soma Docker Build Script - 构建 Docker 镜像
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
    log_info "Docker 版本: $(docker --version)"
}

# Build backend image
build_backend() {
    log_info "构建后端镜像 (soma-backend:${VERSION})..."

    docker rmi soma-backend:${VERSION} 2>/dev/null || true

    docker build \
        --no-cache \
        -f "$SCRIPT_DIR/Dockerfile.backend" \
        -t soma-backend:${VERSION} \
        "$PROJECT_ROOT"

    log_info "后端镜像构建完成"
}

# Build frontend image
build_frontend() {
    if [ ! -d "$PROJECT_ROOT/webui/dist" ]; then
        log_error "前端 dist 目录不存在，请先在 webui 目录执行 npm run build"
        exit 1
    fi

    log_info "构建前端镜像 (soma-frontend:${VERSION})..."

    docker rmi soma-frontend:${VERSION} 2>/dev/null || true

    cp -r "$PROJECT_ROOT/webui/dist" "$SCRIPT_DIR/"

    docker build \
        --no-cache \
        -f "$SCRIPT_DIR/Dockerfile.frontend" \
        -t soma-frontend:${VERSION} \
        "$SCRIPT_DIR"

    rm -rf "$SCRIPT_DIR/dist"

    log_info "前端镜像构建完成"
}

# Show images
show_images() {
    echo ""
    echo "=== Soma Docker 镜像 ==="
    docker images | grep -E "soma-|REPOSITORY"
    echo ""
}

# Push images to registry
push_images() {
    if [ -z "$1" ]; then
        log_error "用法: $0 push <registry>"
        exit 1
    fi

    REGISTRY="$1"

    log_info "推送镜像到 $REGISTRY..."

    docker tag soma-backend:${VERSION}-minimal "$REGISTRY/soma-backend:${VERSION}"
    docker tag soma-frontend:${VERSION} "$REGISTRY/soma-frontend:${VERSION}"

    docker push "$REGISTRY/soma-backend:${VERSION}"
    docker push "$REGISTRY/soma-frontend:${VERSION}"

    log_info "推送完成"
}

# Print usage
usage() {
    echo "Soma Docker 构建脚本"
    echo ""
    echo "用法: $0 <命令>"
    echo ""
    echo "命令:"
    echo "  build            构建所有镜像"
    echo "  backend          构建后端镜像"
    echo "  frontend         构建前端镜像"
    echo "  images           显示已构建的镜像"
    echo "  push <registry>  推送镜像到私有仓库"
    echo "  help             显示帮助信息"
    echo ""
}

case "${1:-help}" in
    build)
        check_docker
        build_backend
        build_frontend
        show_images
        ;;
    backend)
        check_docker
        build_backend
        ;;
    frontend)
        check_docker
        build_frontend
        ;;
    images)
        show_images
        ;;
    push)
        check_docker
        push_images "$2"
        ;;
    help|*)
        usage
        ;;
esac