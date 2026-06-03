import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# --- 配置 CORS ---
# 允许跨域请求，这对于前端调试非常重要
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境可换成具体的域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法 (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # 允许所有 Header
)

@app.post("/upload")
async def upload_ium_csv(file: UploadFile = File(...)):
    """
    接收 IUM 原始 CSV 文件。
    使用 UploadFile 类型，FastAPI 会以流的方式处理，
    不需要把整个文件读入内存，非常适合大文件。
    """
    
    # 这里不做任何处理 (如需读取可用 content = await file.read())
    print(f"接收到文件: {file.filename}, 类型: {file.content_type}")
    
    return {"status": "success", "message": "File received successfully"}

if __name__ == "__main__":
    # 监听 9001 端口
    uvicorn.run(app, host="0.0.0.0", port=9001)