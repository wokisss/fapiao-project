import os
from app import create_app

# 从 app 工厂创建应用实例
# 它会自动加载 .env 文件中的配置
app = create_app()

if __name__ == '__main__':
    # 获取 .env 中定义的路径，如果不存在则使用默认值
    # (注意: create_app 已经加载了配置)
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', 5000))

    # 启动应用
    # debug=True 意味着更改代码后服务器会自动重启
    # host='0.0.0.0' 允许局域网访问 (可选)
    print(f" * 后端服务运行在 http://{host}:{port}")
    print(f" * 前端请直接打开 'frontend/index.html' 文件")
    app.run(debug=True, host=host, port=port)