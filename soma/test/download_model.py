import os
import sys

# 设置 HuggingFace 镜像源加速下载
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

from sentence_transformers import SentenceTransformer
from pathlib import Path

# 模型配置
MODEL_CONFIGS = {
    "all-MiniLM-L6-v2": {
        "hf_name": "sentence-transformers/all-MiniLM-L6-v2",
        "description": "英文优化模型，中文效果一般"
    },
    "bge-base-zh": {
        "hf_name": "BAAI/bge-base-zh",
        "description": "中文优化模型，效果好（推荐）"
    },
    "bge-large-zh": {
        "hf_name": "BAAI/bge-large-zh",
        "description": "中文优化大模型，效果最佳"
    },
    "paraphrase-multilingual-MiniLM-L12-v2": {
        "hf_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "description": "多语言模型，支持中文"
    },
}

BASE_PATH = "D:/work/workspace/soma/workspace/.soma/models"


def download_model(model_name: str):
    """下载并保存模型到本地"""
    if model_name not in MODEL_CONFIGS:
        print(f"错误: 未知的模型 {model_name}")
        print(f"支持的模型: {', '.join(MODEL_CONFIGS.keys())}")
        return False

    config = MODEL_CONFIGS[model_name]
    hf_name = config["hf_name"]
    local_path = os.path.join(BASE_PATH, model_name)

    print(f"\n{'='*60}")
    print(f"下载模型: {model_name}")
    print(f"描述: {config['description']}")
    print(f"HuggingFace: {hf_name}")
    print(f"保存路径: {local_path}")
    print(f"{'='*60}")

    # 检查是否已存在
    if os.path.exists(local_path):
        # 检查是否有必要的文件
        config_file = os.path.join(local_path, "config.json")
        if os.path.exists(config_file):
            print(f"模型已存在: {local_path}")
            response = input("是否重新下载? (y/N): ").strip().lower()
            if response != 'y':
                print("跳过下载")
                return True

    try:
        print(f"\n正在下载模型...")
        model = SentenceTransformer(hf_name)
        print(f"正在保存到 {local_path}...")
        model.save_pretrained(local_path)
        print(f"\n✓ 模型保存成功: {local_path}")
        return True
    except Exception as e:
        print(f"\n✗ 下载失败: {e}")
        return False


def list_models():
    """列出所有可用模型"""
    print("\n可用模型:")
    print("-" * 60)
    for name, config in MODEL_CONFIGS.items():
        print(f"  {name:<40} - {config['description']}")
    print("-" * 60)


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            list_models()
            return
        model_name = sys.argv[1]
    else:
        print("Usage: python download_model.py [model_name|--list]")
        print("\n可用模型:")
        list_models()
        print("\n示例:")
        print("  python download_model.py bge-base-zh")
        print("  python download_model.py all-MiniLM-L6-v2")
        return

    download_model(model_name)


if __name__ == "__main__":
    main()