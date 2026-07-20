"""
阿里云百炼 Application SDK 调用示例（流式输出）
"""
import os
from http import HTTPStatus
from dashscope import Application

# 若没有配置环境变量，可替换为：api_key="sk-xxx"
# 但不建议在生产环境中硬编码 API Key
responses = Application.call(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    app_id='APP_ID',  # 替换为实际的应用 ID
    prompt='一句话总结文件内容',
    stream=True,           # 流式输出
    incremental_output=True,  # 增量输出
    biz_params={
        # 单文件格式（控制台参数类型: File）
        # 参数名必须与控制台定义的参数名保持一致
        'file_url': {
            "url": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3",  # 必填
            # "name": "welcome.mp3",  # 控制台引用了则必填
            # "type": "audio",        # 控制台引用了则必填，可选值：image/document/audio/video/custom
            # "source": "localFile",  # 控制台引用了则必填
            # "mimeType": "audio"     # 控制台引用了则必填，可选值：image/png 等
        }
        # 多文件格式（控制台参数类型: Array<File>）
        # 'file_url': [
        #     {"url": "https://www.berkshirehathaway.com/letters/2024ltr.pdf", "name": "文件1.pdf"},
        #     {"url": "https://www.berkshirehathaway.com/letters/2024ltr.pdf", "name": "文件2.pdf"}
        # ]
    }
)

# 处理流式响应
for response in responses:
    if response.status_code != HTTPStatus.OK:
        print(f'request_id={response.request_id}')
        print(f'code={response.status_code}')
        print(f'message={response.message}')
        print(f'请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code')
    else:
        if response.output.text:
            print(response.output.text, end='')

print()  # 换行