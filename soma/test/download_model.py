import os
# 同样建议设置镜像源加速下载
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

from sentence_transformers import SentenceTransformer

# 指定模型名称和要保存的本地路径
model_name = "sentence-transformers/all-MiniLM-L6-v2"
local_path = "D:/work/workspace/soma/workspace/.soma/models/all-MiniLM-L6-v2"

# 下载并保存模型
print(f"正在下载模型 {model_name} ...")
model = SentenceTransformer(model_name)
model.save_pretrained(local_path)
print(f"模型已成功保存到: {local_path}")