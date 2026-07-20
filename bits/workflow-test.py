"""
阿里云百炼 Application SDK 调用示例（流式输出）
"""
from http import HTTPStatus

from dashscope import Application

# 若没有配置环境变量，可替换为：api_key="sk-xxx"
# 但不建议在生产环境中硬编码 API Key
responses = Application.call(
    api_key="",
    app_id='',  # 替换为实际的应用 ID
    prompt='无',
    stream=True,  # 流式输出
    incremental_output=True,  # 增量输出
    biz_params={
        # 单文件格式（控制台参数类型: File）
        # 参数名必须与控制台定义的参数名保持一致
        # 'file_url': {
        #     "url": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3",  # 必填
        #     # "name": "welcome.mp3",  # 控制台引用了则必填
        #     # "type": "audio",        # 控制台引用了则必填，可选值：image/document/audio/video/custom
        #     # "source": "localFile",  # 控制台引用了则必填
        #     # "mimeType": "audio"     # 控制台引用了则必填，可选值：image/png 等
        # }
        # 多文件格式（控制台参数类型: Array<File>）
        # 'file_url': [
        #     {"url": "https://www.berkshirehathaway.com/letters/2024ltr.pdf", "name": "文件1.pdf"},
        #     {"url": "https://www.berkshirehathaway.com/letters/2024ltr.pdf", "name": "文件2.pdf"}
        # ]
        "company_name": "天顶星科技有限公司",
        "industry": "数字基础设施与金融科技",
        "company_size": "5000-10000人",
        "target_country": "尼日利亚",
        "business_model": "当地直营 + 跨境电商服务",
        "budget_range": "200万人民币",
        "documents": [
            {"url": "https://lexport-tmp-file.oss-cn-beijing.aliyuncs.com/14%E3%80%8A%E5%B0%BC%E6%97%A5%E5%88%A9%E4%BA%9A%E5%85%AC%E5%8F%B8%E6%89%80%E5%BE%97%E7%A8%8E%E6%B3%95%E3%80%8BCOMPANIES%20INCOME%20TAX%20ACT%20%E2%80%93%20LawCare%20Nigeria.html?Expires=1784569270&OSSAccessKeyId=REDACTED&Signature=REDACTED"},
            {"url": "https://lexport-tmp-file.oss-cn-beijing.aliyuncs.com/2%E3%80%8A%E5%B0%BC%E6%97%A5%E5%88%A9%E4%BA%9A%E5%85%AC%E5%8F%B8%E5%8F%8A%E7%9B%B8%E5%85%B3%E4%BA%8B%E5%8A%A1%E6%B3%95%E3%80%8BCompanies-and-Allied-Matters-Act-2020.pdf?Expires=1784569278&OSSAccessKeyId=REDACTED&Signature=REDACTED"}
        ],
        "relative_agency": '''机构名称：ENS (ENSafrica)，适配业务：制造业投资架构、公司注册、准入合规、跨境设立，核心优势：全非最大律所，多国执业，大型制造项目落地能力强
机构名称：Udo Udoma & Belo-Osagie (UUBO)，适配业务：公司注册、商业合规、制造业准入，核心优势：尼日利亚顶级商业律所
机构名称：Aelex，适配业务：跨境贸易、物流、关税、进出口许可，核心优势：西非贸易法律专家
机构名称：Templars，适配业务：税务筹划、税务审计应对，核心优势：尼日利亚税务领军
机构名称：Banwo & Ighodalo，适配业务：环境评估、合规审计、生产安全，核心优势：尼日利亚制造环保权威
机构名称：KPMG Africa，适配业务：审计、税务、合规，核心优势：国际四大，非洲网络完善
机构名称：EY Africa，适配业务：财务审计、税务合规，核心优势：国际四大，英语区服务稳定
机构名称：PwC Africa，适配业务：跨境税务、审计、制造业咨询，核心优势：国际四大，制造业经验成熟
机构名称：Pedabo，适配业务：本土财税申报、合规，核心优势：尼日利亚名气最大
机构名称：Jobberman，适配业务：基层工人、操作工招聘，核心优势：西非最大基层人才平台
机构名称：Andela，适配业务：自动化工程师、技术管理岗，核心优势：非洲高端技术人才库第一
机构名称：Elite Resources，适配业务：工业园劳务派遣、外包，核心优势：西非制造园区专家'''
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
